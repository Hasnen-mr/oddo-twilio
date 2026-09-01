/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useEffect } from "@odoo/owl";
import * as owl from "@odoo/owl";
const useState = owl.useState || owl.proxy || ((obj) => obj);
import { deviceManager } from "@twilio_dialer/js/device_manager";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

/**
 * AutoDialerRunner — Phase 2A Queue Runner
 *
 * Orchestrates the existing DialerPopup / DeviceManager.
 * Does NOT create a new Twilio Device or duplicate any call logic.
 * Reads queues from Odoo, populates existing dialer via dialerService.open(),
 * and syncs call status back via /auto_dialer/sync_line.
 */
export class AutoDialerRunner extends Component {
    static template = "twilio_dialer.AutoDialerRunner";

    setup() {
                this.orm = useService("orm");
        this.action = useService("action");
        this.dialerSvc = useService("twilio_dialer");

        this.state = useState({
            // Queue list
            queues: [],
            loadingQueues: false,

            // Active queue runtime
            activeQueue: null,    // full queue object from Odoo
            queueState: null,     // "draft"|"running"|"paused"|"completed"|"cancelled"
            actionPending: false,

            // Current contact card
            currentLine: null,    // { id, phone, partner_name, queue_position, attempt_count, notes, status }

            // Stats snapshot
            stats: {
                total: 0,
                pending: 0,
                calling: 0,
                completed: 0,
                busy: 0,
                no_answer: 0,
                failed: 0,
                skipped: 0,
                progress: 0,
            },
        });

        onWillStart(async () => {
            await this._loadQueues();

            // Guard: unsubscribe any prior listener before registering a new one.
            // Owl calls onWillStart exactly once per mount, but this is a safety net
            // against edge cases (e.g. asset hot-reload re-mounting the component).
            if (this._unsubStatus) {
                this._unsubStatus();
                this._unsubStatus = null;
            }

            // Listen to device status changes (ready/disconnected/error) to drive auto-dialing
            this._unsubStatus = deviceManager.onStatusChange((status) => {
                this._onDeviceStatusChanged(status);
            });

            // Restore an in-progress queue from dialerSvc state (across tab switches)
            const svc = this.dialerSvc.state;
            if (svc.autoDialerId) {
                await this._restoreQueue(svc.autoDialerId);
            }
        });

        onWillUnmount(() => {
            this._clearAutoTimers();
            if (this._unsubStatus) {
                this._unsubStatus();
            }
        });
    }

    _clearAutoTimers() {
        if (this._delayTimer) {
            clearTimeout(this._delayTimer);
            this._delayTimer = null;
        }
        if (this._ringTimer) {
            clearTimeout(this._ringTimer);
            this._ringTimer = null;
        }
    }

    // ── Device Status Callback & Automatic Progression ────────

    async _onDeviceStatusChanged(status) {
        if (!this.isRunning || this.state.queueState !== "running" || this._isStopped || !this.state.activeQueue) {
            this._lastDeviceStatus = status;
            this._clearAutoTimers();
            return;
        }

        const wasCallActive = this._lastDeviceStatus === "connecting" || this._lastDeviceStatus === "connected";
        console.log(`[AutoDialerRunner] Device status changed: ${this._lastDeviceStatus} -> ${status}`);
        this._lastDeviceStatus = status;

        if (status === "connecting" || status === "connected") {
            // Call is active; clear max_ring_time timeout when call connects
            if (status === "connected") {
                if (this._ringTimer) {
                    clearTimeout(this._ringTimer);
                    this._ringTimer = null;
                }
            }
            return;
        }

        // Progression MUST only occur if a call was previously active (connecting/connected)
        // or if an explicit call failure/disconnect occurred while campaign is running.
        if (wasCallActive && (status === "ready" || status === "disconnected" || status === "error")) {
            this._clearAutoTimers();

            // Refresh queue statistics from backend
            await this._refreshQueue();

            if (!this.isRunning || this.state.queueState !== "running" || this._isStopped) {
                console.log("[AutoDialerRunner] Queue is no longer running (paused or stopped).");
                this._clearAutoTimers();
                return;
            }

            // Check if queue completed
            if (this.state.stats.pending <= 0) {
                console.log("[AutoDialerRunner] Campaign finished! Marking completed.");
                await this._callQueueAction("action_stop");
                this.state.queueState = "completed";
                this.state.currentLine = null;
                return;
            }

            // Schedule next call after call_delay
            const delaySec = this.state.activeQueue.call_delay || 5;
            console.log(`[AutoDialerRunner] Scheduling next call in ${delaySec}s...`);

            this._delayTimer = setTimeout(async () => {
                this._delayTimer = null;
                if (this.isRunning && this.state.queueState === "running" && !this._isStopped) {
                    await this._dialNextPendingContact();
                } else {
                    console.log("[AutoDialerRunner] Delay timer fired but campaign is not running. Ignoring.");
                }
            }, delaySec * 1000);
        }
    }

    async _dialNextPendingContact() {
        if (!this.isRunning || this.state.queueState !== "running" || this._isStopped || !this.state.activeQueue) {
            this._clearAutoTimers();
            return;
        }

        // Advance to next pending contact
        await this._navigate("next");

        if (!this.isRunning || this.state.queueState !== "running" || this._isStopped) {
            this._clearAutoTimers();
            return;
        }

        const line = this.state.currentLine;
        if (!line || line.status !== "pending") {
            // No more pending contacts
            await this._refreshQueue();
            if (this.state.stats.pending <= 0) {
                this.state.queueState = "completed";
                this.state.currentLine = null;
            }
            return;
        }

        // Initiate call using existing DeviceManager
        await this._triggerCallForCurrentLine();
    }

    async _syncLineWithRetry(lineId, status, durationSec = 0, retries = 3) {
        for (let attempt = 1; attempt <= retries; attempt++) {
            try {
                const res = await rpc("/twilio_dialer/auto_dialer/sync_line", {
                    line_id: lineId,
                    status: status,
                    duration_sec: durationSec,
                });
                if (res && res.success !== false) {
                    return res;
                }
            } catch (err) {
                console.warn(`[AutoDialerRunner] Sync line ${lineId} attempt ${attempt}/${retries} failed:`, err);
                if (attempt === retries) {
                    console.error(`[AutoDialerRunner] Network sync exhausted after ${retries} attempts. Safely pausing campaign.`);
                    this._isStopped = true;
                    this.state.queueState = "paused";
                    this._clearAutoTimers();
                    throw err; // Re-throw error so application layer is notified
                } else {
                    await new Promise((r) => setTimeout(r, 500 * attempt));
                }
            }
        }
        return null;
    }

    async _triggerCallForCurrentLine() {
        const line = this.state.currentLine;
        const queue = this.state.activeQueue;
        if (!line || !queue || !this.isRunning || this.state.queueState !== "running" || this._isStopped || this._isDialing) {
            return;
        }

        this._isDialing = true;
        this._clearAutoTimers();
        this._callStartTimeMs = Date.now();

        const fullNumber = line.phone;
        const fromNum = queue.from_number || "";

        console.log(`[AutoDialerRunner] Auto-dialing ${fullNumber} (Line ID: ${line.id})...`);

        // Set max_ring_time timeout (e.g. 30s)
        const ringTimeSec = queue.max_ring_time || 30;
        this._ringTimer = setTimeout(async () => {
            // Guard: Only drop call if call is still connecting/ringing (NOT connected!)
            if (deviceManager.status === "connecting" || deviceManager.status === "registering") {
                console.warn(`[AutoDialerRunner] Ringing exceeded max_ring_time (${ringTimeSec}s). Hanging up...`);
                this._ringTimer = null;
                deviceManager.disconnect();
                const dur = Math.floor((Date.now() - (this._callStartTimeMs || Date.now())) / 1000);
                await this._syncLineWithRetry(line.id, "no_answer", dur);
            } else {
                console.log(`[AutoDialerRunner] Ring timer expired but call status is "${deviceManager.status}". Ignoring timeout.`);
                this._ringTimer = null;
            }
        }, ringTimeSec * 1000);

        try {
            console.log("[AutoDialerRunner] Placing call via deviceManager:", {
                fullNumber: fullNumber,
                fromNum: fromNum,
                lineId: line.id
            });
            // Execute call via DeviceManager
            const success = await deviceManager.makeCall(fullNumber, {
                From: fromNum,
                from_number: fromNum,
            }, {
                partnerId: null,
                queueLineId: line.id,
            });

            if (!success) {
                console.error(`[AutoDialerRunner] makeCall failed for ${fullNumber}. Marking failed.`);
                this._clearAutoTimers();
                const dur = Math.floor((Date.now() - (this._callStartTimeMs || Date.now())) / 1000);
                await this._syncLineWithRetry(line.id, "failed", dur);
                // Move to next contact after short delay
                this._delayTimer = setTimeout(() => {
                    this._delayTimer = null;
                    if (this.isRunning && this.state.queueState === "running" && !this._isStopped) {
                        this._dialNextPendingContact();
                    }
                }, (queue.call_delay || 5) * 1000);
            }
        } finally {
            this._isDialing = false;
        }
    }

    // ── Queue Loading ────────────────────────────────────────

    async _loadQueues() {
        this.state.loadingQueues = true;
        try {
            const queues = await this.orm.searchRead(
                "twilio.auto.dialer",
                ["|", ["state", "in", ["draft", "running", "paused"]], ["pending_contacts", ">", 0]],
                ["id", "name", "state", "total_contacts", "pending_contacts",
                 "completed_contacts", "failed_contacts", "calling_contacts",
                 "busy_contacts", "no_answer_contacts", "skipped_contacts",
                 "progress", "current_line_id", "from_number", "call_delay", "max_ring_time"],
                { order: "create_date desc", limit: 50 }
            );
            this.state.queues = queues;

            // Restore only an in-progress queue already tied to this dialer session.
            // Do not auto-select draft/paused queues on every page load — that raced the
            // dashboard form mount and hammered /auto_dialer/navigate.
            const svc = this.dialerSvc.state;
            if (svc.autoDialerId) {
                const found = queues.find((q) => q.id === svc.autoDialerId);
                if (found) {
                    await this.onSelectQueue(found.id);
                    return;
                }
            }

            // If a campaign is actively running, keep the runner pointed at it.
            if (!this.state.activeQueue && queues.length > 0) {
                const runningQ = queues.find((q) => q.state === "running");
                if (runningQ) {
                    await this.onSelectQueue(runningQ.id);
                }
            }
        } catch (err) {
            console.error("[AutoDialerRunner] Failed to load queues:", err);
        } finally {
            this.state.loadingQueues = false;
        }
    }

    async _restoreQueue(dialerId) {
        try {
            const queues = await this.orm.read(
                "twilio.auto.dialer",
                [dialerId],
                ["id", "name", "state", "total_contacts", "pending_contacts",
                 "completed_contacts", "failed_contacts", "calling_contacts",
                 "busy_contacts", "no_answer_contacts", "skipped_contacts",
                 "progress", "current_line_id", "from_number", "call_delay", "max_ring_time"]
            );
            if (!queues.length) return;
            const queue = queues[0];
            const svc = this.dialerSvc.state;
            const currentLine = queue.current_line_id ? {
                id: svc.queueLineId,
                phone: svc.phone,
                partner_name: svc.partnerName,
                queue_position: svc.queuePosition,
                attempt_count: svc.queueAttempts,
                notes: svc.queueNotes,
                status: svc.queueStatus,
            } : null;
            this._applyQueueState(queue, currentLine);
        } catch (err) {
            console.error("[AutoDialerRunner] Failed to restore queue:", err);
        }
    }

    _applyQueueState(queue, currentLine) {
        this.state.activeQueue = queue;
        this.state.queueState = queue.state;
        this.state.currentLine = currentLine;
        this.state.stats = {
            total: queue.total_contacts || 0,
            pending: queue.pending_contacts || 0,
            calling: queue.calling_contacts || 0,
            completed: queue.completed_contacts || 0,
            busy: queue.busy_contacts || 0,
            no_answer: queue.no_answer_contacts || 0,
            failed: queue.failed_contacts || 0,
            skipped: queue.skipped_contacts || 0,
            progress: Math.round(queue.progress || 0),
        };
    }

    // ── Queue Selection ──────────────────────────────────────

    async onSelectQueue(queueId) {
        const queue = this.state.queues.find((q) => q.id === Number(queueId));
        if (!queue) return;

        // Fetch full detail
        const detail = await this.orm.read(
            "twilio.auto.dialer",
            [queue.id],
            ["id", "name", "state", "total_contacts", "pending_contacts",
             "completed_contacts", "failed_contacts", "calling_contacts",
             "busy_contacts", "no_answer_contacts", "skipped_contacts",
             "progress", "current_line_id", "from_number", "call_delay", "max_ring_time"]
        );
        this._applyQueueState(detail[0], null);

        // Fetch and apply current line contact info for the selected queue
        if (detail[0].current_line_id) {
            await this._fetchAndApplyCurrentLine(queue.id);
        } else if (detail[0].pending_contacts > 0) {
            // Navigate to first pending contact if no pointer set
            await this._fetchAndApplyCurrentLine(queue.id);
        }
    }

    async _fetchAndApplyCurrentLine(dialerId) {
        try {
            const result = await rpc("/twilio_dialer/auto_dialer/navigate", {
                dialer_id: dialerId,
                action_name: "current",
            });
            if (result && result.success && result.queue_line_id) {
                this._applyCurrentLine(result);
            }
        } catch (err) {
            // Fallback
        }
    }

    _applyCurrentLine(result) {
        this.state.currentLine = {
            id: result.queue_line_id,
            phone: result.phone,
            partner_name: result.partner_name,
            queue_position: result.queue_position,
            attempt_count: result.queue_attempts,
            notes: result.queue_notes,
            status: result.queue_status,
        };
        // Update dialerSvc state properties without incrementing requestId (avoids infinite OWL re-render loops)
        const svcState = this.dialerSvc.state;
        svcState.phone = result.phone || "";
        svcState.partnerName = result.partner_name || result.phone || "";
        svcState.autoDialerId = this.state.activeQueue?.id || null;
        svcState.queueLineId = result.queue_line_id;
        svcState.queueName = result.queue_name || "";
        svcState.queuePosition = result.queue_position || "";
        svcState.queueAttempts = result.queue_attempts || 0;
        svcState.queueNotes = result.queue_notes || "";
        svcState.queueStatus = result.queue_status || "";
    }

    // ── Queue Controls ───────────────────────────────────────

    async _callQueueAction(actionName) {
        if (!this.state.activeQueue) return;
        this.state.actionPending = true;
        try {
            await this.orm.call("twilio.auto.dialer", actionName, [this.state.activeQueue.id]);
            await this._refreshQueue();
        } catch (err) {
            console.error(`[AutoDialerRunner] ${actionName} failed:`, err);
        } finally {
            this.state.actionPending = false;
        }
    }

    async onStart() {
        if (!this.state.activeQueue || this.state.actionPending) return;
        this._isStopped = false;
        this.state.actionPending = true;
        try {
            await rpc("/web/dataset/call_kw", {
                model: "twilio.auto.dialer",
                method: "action_start",
                args: [[this.state.activeQueue.id]],
                kwargs: {},
            });

            await this._refreshQueue();

            if (this.state.currentLine && this.isRunning && !this._isStopped) {
                this._loadCurrentLineIntoDialpad();
                // Start auto-dialing first contact
                await this._triggerCallForCurrentLine();
            }
        } catch (err) {
            console.error("[AutoDialerRunner] Start failed:", err);
        } finally {
            this.state.actionPending = false;
        }
    }

    async onPause() {
        console.log("[AutoDialerRunner] Pause requested. Halting campaign immediately.");
        this._isStopped = true;
        this.state.queueState = "paused";
        this._clearAutoTimers();

        if (deviceManager.status === "connecting" || deviceManager.status === "connected") {
            deviceManager.disconnect();
        }
        this._clearAutoTimers();

        await this._callQueueAction("action_pause");
        this.state.queueState = "paused";
        this._clearAutoTimers();
    }

    async onResume() {
        if (!this.state.activeQueue || this.state.actionPending) return;
        this._isStopped = false;
        this.state.actionPending = true;
        try {
            await this.orm.call("twilio.auto.dialer", "action_resume", [this.state.activeQueue.id]);
            await this._refreshQueue();
            if (this.state.currentLine && this.isRunning && !this._isStopped) {
                this._loadCurrentLineIntoDialpad();
                await this._triggerCallForCurrentLine();
            }
        } catch (err) {
            console.warn("[AutoDialerRunner] Resume caught expected error or server offline:", err.message || err);
            await this._refreshQueue();
        } finally {
            this.state.actionPending = false;
        }
    }

    async onStop() {
        console.log("[AutoDialerRunner] Stop requested. Halting campaign immediately.");
        this._isStopped = true;
        this.state.queueState = "paused";
        this._clearAutoTimers();

        // If call is active or connecting, hang up WebRTC connection immediately
        if (deviceManager.status === "connecting" || deviceManager.status === "connected" || deviceManager.status === "registering") {
            try {
                deviceManager.disconnect();
            } catch (e) {
                console.warn("[AutoDialerRunner] Disconnect on stop caught:", e);
            }
        }
        this._clearAutoTimers();

        await this._callQueueAction("action_stop");
        this._isStopped = true;
        this.state.queueState = "paused";
        this._clearAutoTimers();
        this.state.currentLine = null;
        this.dialerSvc.state.autoDialerId = null;
        this.dialerSvc.state.queueLineId = null;
    }

    // ── Navigation ───────────────────────────────────────────

    async _navigate(actionName) {
        if (!this.state.activeQueue || this.state.actionPending) return;
        this.state.actionPending = true;
        try {
            const result = await rpc("/twilio_dialer/auto_dialer/navigate", {
                dialer_id: this.state.activeQueue.id,
                action_name: actionName,
            });
            if (result && result.success) {
                if (result.queue_line_id) {
                    this._applyCurrentLine(result);
                } else if (result.queue_state === "completed") {
                    this.state.currentLine = null;
                    this.state.queueState = "completed";
                }
                await this._refreshQueue();
            }
        } catch (err) {
            console.error(`[AutoDialerRunner] Navigate "${actionName}" failed:`, err);
        } finally {
            this.state.actionPending = false;
        }
    }

    onNext() { this._navigate("next"); }
    onPrev() { this._navigate("prev"); }
    onSkip() { this._navigate("skip"); }

    // ── Refresh ──────────────────────────────────────────────

    async _refreshQueue() {
        if (!this.state.activeQueue) return;
        try {
            const detail = await this.orm.read(
                "twilio.auto.dialer",
                [this.state.activeQueue.id],
                ["id", "name", "state", "total_contacts", "pending_contacts",
                 "completed_contacts", "failed_contacts", "calling_contacts",
                 "busy_contacts", "no_answer_contacts", "skipped_contacts",
                 "progress", "current_line_id", "from_number", "call_delay", "max_ring_time"]
            );
            if (!detail.length) return;
            const queue = detail[0];
            this.state.activeQueue = queue;
            this.state.queueState = queue.state;
            this.state.stats = {
                total: queue.total_contacts || 0,
                pending: queue.pending_contacts || 0,
                calling: queue.calling_contacts || 0,
                completed: queue.completed_contacts || 0,
                busy: queue.busy_contacts || 0,
                no_answer: queue.no_answer_contacts || 0,
                failed: queue.failed_contacts || 0,
                skipped: queue.skipped_contacts || 0,
                progress: Math.round(queue.progress || 0),
            };

            if (queue.current_line_id) {
                await this._fetchCurrentLineData(queue.current_line_id[0]);
            } else {
                this.state.currentLine = null;
            }
        } catch (err) {
            console.error("[AutoDialerRunner] Refresh failed:", err);
        }
    }

    async _fetchCurrentLineData(lineId) {
        try {
            const lines = await this.orm.read(
                "twilio.auto.dialer.line",
                [lineId],
                ["id", "phone", "partner_id", "sequence", "status", "attempt_count", "notes"]
            );
            if (!lines.length) return;
            const line = lines[0];
            const allLines = this.state.activeQueue.total_contacts;
            this.state.currentLine = {
                id: line.id,
                phone: line.phone,
                partner_name: line.partner_id ? line.partner_id[1] : line.phone,
                queue_position: `Line ${line.sequence} of ${allLines}`,
                attempt_count: line.attempt_count,
                notes: line.notes || "",
                status: line.status,
            };
            this._loadCurrentLineIntoDialpad();
        } catch (err) {
            console.error("[AutoDialerRunner] Failed to fetch current line data:", err);
        }
    }

    _loadCurrentLineIntoDialpad() {
        const line = this.state.currentLine;
        const queue = this.state.activeQueue;
        if (!line || !queue) return;
        const svcState = this.dialerSvc.state;
        svcState.phone = line.phone || "";
        svcState.fromNumber = queue.from_number || "";
        svcState.partnerName = line.partner_name || line.phone || "";
        svcState.autoDialerId = queue.id;
        svcState.queueLineId = line.id;
        svcState.queueName = queue.name || "";
        svcState.queuePosition = line.queue_position || "";
        svcState.queueAttempts = line.attempt_count || 0;
        svcState.queueNotes = line.notes || "";
        svcState.queueStatus = line.status || "pending";
    }

    async onRefresh() {
        await this._loadQueues();
        if (this.state.activeQueue) {
            await this._refreshQueue();
        }
    }

    // ── Template Helpers ─────────────────────────────────────

    get isRunning() { return this.state.queueState === "running"; }
    get isPaused()  { return this.state.queueState === "paused"; }
    get isDraft()   { return !this.state.queueState || this.state.queueState === "draft"; }
    get isCompleted() { return this.state.queueState === "completed" || this.state.queueState === "cancelled"; }

    get statusBadgeClass() {
        const map = {
            draft: "o_dialer_qrunner_badge--draft",
            running: "o_dialer_qrunner_badge--running",
            paused: "o_dialer_qrunner_badge--paused",
            completed: "o_dialer_qrunner_badge--completed",
            cancelled: "o_dialer_qrunner_badge--cancelled",
        };
        return map[this.state.queueState] || "o_dialer_qrunner_badge--draft";
    }

    get statusLabel() {
        const map = {
            draft: "Draft",
            running: "Running",
            paused: "Paused",
            completed: "Completed",
            cancelled: "Stopped",
        };
        return map[this.state.queueState] || "Draft";
    }

    get lineStatusBadgeClass() {
        const s = this.state.currentLine?.status;
        const map = {
            pending:    "o_dialer_qrunner_line_badge--pending",
            calling:    "o_dialer_qrunner_line_badge--calling",
            completed:  "o_dialer_qrunner_line_badge--completed",
            busy:       "o_dialer_qrunner_line_badge--busy",
            no_answer:  "o_dialer_qrunner_line_badge--busy",
            failed:     "o_dialer_qrunner_line_badge--failed",
            skipped:    "o_dialer_qrunner_line_badge--skipped",
            cancelled:  "o_dialer_qrunner_line_badge--failed",
        };
        return map[s] || "o_dialer_qrunner_line_badge--pending";
    }

    get lineStatusLabel() {
        const s = this.state.currentLine?.status;
        const map = {
            pending: "Pending",
            calling: "Calling…",
            completed: "Completed",
            busy: "Busy",
            no_answer: "No Answer",
            failed: "Failed",
            skipped: "Skipped",
            cancelled: "Cancelled",
        };
        return map[s] || "Pending";
    }

    openQueueInOdoo() {
        if (!this.state.activeQueue) return;
        this.action.doAction({
            name: this.state.activeQueue.name,
            type: "ir.actions.act_window",
            res_model: "twilio.auto.dialer",
            res_id: this.state.activeQueue.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openSettings() {
        // Open Auto Dialer campaigns list; keep dialer panel open.
        if (this.dialerSvc?.state) {
            this.dialerSvc.state.isOpen = true;
        }
        this.action.doAction("twilio_dialer.action_twilio_auto_dialer");
    }

    get successRate() {
        const done = this.state.stats.completed || 0;
        const failed = this.state.stats.failed || 0;
        const processed = done + failed;
        if (processed <= 0) return 0;
        return Math.round((done / processed) * 100);
    }

    get pacingDelay() {
        return (this.state.activeQueue?.call_delay || 5) + "s delay";
    }

    get maxRingTime() {
        return (this.state.activeQueue?.max_ring_time || 30) + "s ring limit";
    }
}