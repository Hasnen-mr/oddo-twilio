/** @odoo-module **/

import { Component, useState, onWillStart, onWillUnmount, useEffect } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

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

            // Restore an in-progress queue from dialerSvc state (across tab switches)
            const svc = this.dialerSvc.state;
            if (svc.autoDialerId) {
                await this._restoreQueue(svc.autoDialerId);
            }
        });
    }

    // ── Queue Loading ────────────────────────────────────────

    async _loadQueues() {
        this.state.loadingQueues = true;
        try {
            const queues = await this.orm.searchRead(
                "twilio.auto.dialer",
                [["state", "in", ["draft", "running", "paused"]]],
                ["id", "name", "state", "total_contacts", "pending_contacts",
                 "completed_contacts", "failed_contacts", "calling_contacts",
                 "busy_contacts", "no_answer_contacts", "skipped_contacts",
                 "progress", "current_line_id", "from_number"],
                { order: "create_date desc", limit: 50 }
            );
            this.state.queues = queues;

            // Auto-restore if dialerSvc already has an active queue
            const svc = this.dialerSvc.state;
            if (svc.autoDialerId && !this.state.activeQueue) {
                const found = queues.find((q) => q.id === svc.autoDialerId);
                if (found) {
                    this._applyQueueState(found, null);
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
                 "progress", "current_line_id", "from_number"]
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
             "progress", "current_line_id", "from_number"]
        );
        this._applyQueueState(detail[0], null);

        // If this queue already has an active line (running/paused), restore it
        if (detail[0].current_line_id && (detail[0].state === "running" || detail[0].state === "paused")) {
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
            // If "current" action not supported, fall back gracefully
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
        // Sync into dialerService so the dialpad reflects this contact
        this.dialerSvc.open({
            phone: result.phone,
            fromNumber: this.state.activeQueue?.from_number || "",
            partnerId: result.partner_id || null,
            partnerName: result.partner_name || result.phone,
            autoDialerId: this.state.activeQueue?.id || null,
            queueLineId: result.queue_line_id,
            queueName: result.queue_name || "",
            queuePosition: result.queue_position || "",
            queueAttempts: result.queue_attempts || 0,
            queueNotes: result.queue_notes || "",
            queueStatus: result.queue_status || "",
        });
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
        this.state.actionPending = true;
        try {
            // Call action_start which returns the dialer action params
            const result = await rpc("/web/dataset/call_kw", {
                model: "twilio.auto.dialer",
                method: "action_start",
                args: [[this.state.activeQueue.id]],
                kwargs: {},
            });

            await this._refreshQueue();

            // Load the current line into the dialpad
            const svc = this.dialerSvc.state;
            const dialer = this.state.activeQueue;
            if (dialer && this.state.currentLine) {
                this.dialerSvc.open({
                    phone: this.state.currentLine.phone,
                    fromNumber: dialer.from_number || "",
                    partnerId: null,
                    partnerName: this.state.currentLine.partner_name || this.state.currentLine.phone,
                    autoDialerId: dialer.id,
                    queueLineId: this.state.currentLine.id,
                    queueName: dialer.name,
                    queuePosition: this.state.currentLine.queue_position || "",
                    queueAttempts: this.state.currentLine.attempt_count || 0,
                    queueNotes: this.state.currentLine.notes || "",
                    queueStatus: this.state.currentLine.status || "pending",
                });
            }
        } catch (err) {
            console.error("[AutoDialerRunner] Start failed:", err);
        } finally {
            this.state.actionPending = false;
        }
    }

    async onPause() {
        await this._callQueueAction("action_pause");
    }

    async onResume() {
        if (!this.state.activeQueue || this.state.actionPending) return;
        this.state.actionPending = true;
        try {
            await this.orm.call("twilio.auto.dialer", "action_resume", [this.state.activeQueue.id]);
            await this._refreshQueue();
            // Re-populate dialpad with current contact
            if (this.state.currentLine) {
                this._loadCurrentLineIntoDialpad();
            }
        } catch (err) {
            console.error("[AutoDialerRunner] Resume failed:", err);
        } finally {
            this.state.actionPending = false;
        }
    }

    async onStop() {
        await this._callQueueAction("action_stop");
        this.state.currentLine = null;
        // Clear queue state from dialerService
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
                 "progress", "current_line_id", "from_number"]
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

            // If the queue now has a current_line_id and we don't have a current line, fetch it
            if (queue.current_line_id && !this.state.currentLine) {
                await this._fetchCurrentLineData(queue.current_line_id[0]);
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
        this.dialerSvc.open({
            phone: line.phone,
            fromNumber: queue.from_number || "",
            partnerId: null,
            partnerName: line.partner_name || line.phone,
            autoDialerId: queue.id,
            queueLineId: line.id,
            queueName: queue.name,
            queuePosition: line.queue_position || "",
            queueAttempts: line.attempt_count || 0,
            queueNotes: line.notes || "",
            queueStatus: line.status || "pending",
        });
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
}
