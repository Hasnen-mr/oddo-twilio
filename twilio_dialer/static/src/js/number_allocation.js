/** @odoo-module **/

import { Component, useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class NumberAllocationPanel extends Component {
    static template = "twilio_dialer.NumberAllocationPanel";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.busService = this.env.services.bus_service || null;
        this.trackedChannels = new Set();
        this._onImStatusUpdated = this._onImStatusUpdated.bind(this);
        this.state = useState({
            loading: true,
            savingId: null,
            searchQuery: "",
            filterTab: "all", // "all", "all_lines", "custom", "none"
            numbers: [],
            allocations: [],
            activeDropdownId: null,
            activeMenuId: null,
            draftNumberIds: [],
            currentUserIsAdmin: false,
            adminUserId: null,
        });

        onWillStart(async () => {
            await this.loadData();
            this.subscribePresenceChannels();
        });

        onWillUnmount(() => {
            this.unsubscribePresenceChannels();
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call("twilio.number.allocation", "get_allocation_data", []);
            if (data && data.success) {
                this.state.numbers = data.numbers || [];
                this.state.allocations = data.allocations || [];
                this.state.currentUserIsAdmin = Boolean(data.current_user_is_admin);
                this.state.adminUserId = data.admin_user_id;
            }
        } catch (error) {
            console.error("Failed to load number allocation data:", error);
            this.notification.add(_t("Failed to load number allocations"), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    get allOptionNumber() {
        return this.state.numbers.find((n) => n.is_all || n.phone_number === "ALL");
    }

    get realNumbers() {
        return this.state.numbers.filter((n) => !n.is_all && n.phone_number !== "ALL");
    }

    get stats() {
        const total = this.state.allocations.length;
        const allOption = this.allOptionNumber;
        const allOptId = allOption ? allOption.id : null;

        let allAccessCount = 0;
        let customCount = 0;
        let noneCount = 0;
        let onlineCount = 0;

        for (const alloc of this.state.allocations) {
            if ((alloc.im_status || "").toLowerCase().trim() === "online") {
                onlineCount++;
            }
            const nIds = alloc.number_ids || [];
            if (allOptId && nIds.includes(allOptId)) {
                allAccessCount++;
            } else if (nIds.length > 0) {
                customCount++;
            } else {
                allAccessCount++; // Default fallback in Odoo is all lines
            }
        }

        return {
            totalUsers: total,
            onlineCount,
            allAccessCount,
            customCount,
            noneCount,
            totalNumbers: this.realNumbers.length,
        };
    }

    get filteredAllocations() {
        let list = this.state.allocations;
        const q = (this.state.searchQuery || "").trim().toLowerCase();
        if (q) {
            list = list.filter(
                (a) =>
                    (a.user_name && a.user_name.toLowerCase().includes(q)) ||
                    (a.user_login && a.user_login.toLowerCase().includes(q)) ||
                    (a.user_email && a.user_email.toLowerCase().includes(q))
            );
        }

        const allOption = this.allOptionNumber;
        const allOptId = allOption ? allOption.id : null;

        if (this.state.filterTab === "all_lines") {
            list = list.filter((a) => {
                const nIds = a.number_ids || [];
                return nIds.length === 0 || (allOptId && nIds.includes(allOptId));
            });
        } else if (this.state.filterTab === "custom") {
            list = list.filter((a) => {
                const nIds = a.number_ids || [];
                return nIds.length > 0 && (!allOptId || !nIds.includes(allOptId));
            });
        }

        return list;
    }

    isAllAssigned(alloc) {
        const allOption = this.allOptionNumber;
        const allOptId = allOption ? allOption.id : null;
        const nIds = alloc.number_ids || [];
        return nIds.length === 0 || (allOptId && nIds.includes(allOptId));
    }

    getAssignedNumberObjs(alloc) {
        const nIds = alloc.number_ids || [];
        return this.state.numbers.filter((n) => nIds.includes(n.id) && !n.is_all && n.phone_number !== "ALL");
    }

    getVisibleAssignedNumbers(alloc, limit = 2) {
        const all = this.getAssignedNumberObjs(alloc);
        return all.slice(0, limit);
    }

    getRemainingCount(alloc, limit = 2) {
        const all = this.getAssignedNumberObjs(alloc);
        return Math.max(0, all.length - limit);
    }

    getUserInitials(name) {
        if (!name) return "?";
        const parts = name.trim().split(" ");
        if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }

    getUserColor(name) {
        if (!name) return "#6c757d";
        const colors = [
            "#4e73df", "#1cc88a", "#36b9cc", "#f6c23e",
            "#e74a3b", "#6f42c1", "#fd7e14", "#20c997"
        ];
        let hash = 0;
        for (let i = 0; i < name.length; i++) {
            hash = name.charCodeAt(i) + ((hash << 5) - hash);
        }
        return colors[Math.abs(hash) % colors.length];
    }

    
    getLiveStatusDotStyle(alloc) {
        const s = (alloc && alloc.im_status ? alloc.im_status : "offline").toLowerCase().trim();
        if (s === "online") return "background-color: #10b981 !important;";
        if (s === "away" || s === "idle") return "background-color: #f59e0b !important;";
        if (s === "busy" || s === "dnd") return "background-color: #ef4444 !important;";
        return "background-color: #9ca3af !important;";
    }

    getLiveStatusBadgeStyle(alloc) {
        const s = (alloc && alloc.im_status ? alloc.im_status : "offline").toLowerCase().trim();
        if (s === "online") return "background-color: #ecfdf5 !important; color: #065f46 !important; border: 1px solid #a7f3d0 !important;";
        if (s === "away" || s === "idle") return "background-color: #fffbeb !important; color: #92400e !important; border: 1px solid #fde68a !important;";
        if (s === "busy" || s === "dnd") return "background-color: #fef2f2 !important; color: #991b1b !important; border: 1px solid #fecaca !important;";
        return "background-color: #f3f4f6 !important; color: #6b7280 !important; border: 1px solid #e5e7eb !important;";
    }

    getLiveStatusLabel(alloc) {
        const s = alloc.im_status;
        if (s === "online") return _t("Online");
        if (s === "away") return _t("Away");
        if (s === "busy") return _t("Busy");
        return _t("Offline");
    }

    getLiveStatusDotClass(alloc) {
        const s = alloc.im_status;
        if (s === "online") return "bg-success";
        if (s === "away") return "bg-warning";
        if (s === "busy") return "bg-danger";
        return "bg-secondary";
    }

    getLiveStatusBadgeClass(alloc) {
        const s = alloc.im_status;
        if (s === "online") return "bg-success-subtle text-success border border-success-subtle";
        if (s === "away") return "bg-warning-subtle text-warning border border-warning-subtle";
        if (s === "busy") return "bg-danger-subtle text-danger border border-danger-subtle";
        return "bg-light text-muted border";
    }

    
    handlePickerKeyDown(ev, alloc) {
        if (ev.key === "Escape") {
            ev.preventDefault();
            this.closePicker();
        } else if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.saveDraft(alloc);
        }
    }

    openPicker(alloc) {
        if (!this.state.currentUserIsAdmin) {
            this.notification.add(_t("Only the Twilio Admin can modify phone number allocations."), { type: "warning" });
            return;
        }
        this.state.activeMenuId = null;
        this.state.activeDropdownId = alloc.id;
        const nIds = alloc.number_ids || [];
        const allOption = this.allOptionNumber;
        if (nIds.length === 0 && allOption) {
            this.state.draftNumberIds = [allOption.id];
        } else {
            this.state.draftNumberIds = [...nIds];
        }
    }

    closePicker() {
        this.state.activeDropdownId = null;
        this.state.draftNumberIds = [];
    }

    toggleActionMenu(allocId) {
        if (this.state.activeMenuId === allocId) {
            this.state.activeMenuId = null;
        } else {
            this.state.activeMenuId = allocId;
            this.state.activeDropdownId = null;
        }
    }

    closeActionMenu() {
        this.state.activeMenuId = null;
    }

    isDraftSelected(allocId, numId) {
        if (this.state.activeDropdownId !== allocId) return false;
        return this.state.draftNumberIds.includes(numId);
    }

    toggleDraftNumber(allocId, num) {
        const allOption = this.allOptionNumber;
        const allOptId = allOption ? allOption.id : null;

        if (num.is_all || num.phone_number === "ALL") {
            this.state.draftNumberIds = [num.id];
            return;
        }

        let current = this.state.draftNumberIds.filter((id) => id !== allOptId);
        if (current.includes(num.id)) {
            current = current.filter((id) => id !== num.id);
        } else {
            current.push(num.id);
        }

        if (current.length === 0 && allOptId) {
            current = [allOptId];
        }

        this.state.draftNumberIds = current;
    }

    async saveDraft(alloc) {
        if (!this.state.currentUserIsAdmin) {
            this.notification.add(_t("Only the Twilio Admin can modify phone number allocations."), { type: "warning" });
            return;
        }
        this.state.savingId = alloc.id;
        try {
            const data = await this.orm.call("twilio.number.allocation", "update_allocation", [
                alloc.id,
                this.state.draftNumberIds,
            ]);
            if (data && data.success) {
                this.state.numbers = data.numbers || [];
                this.state.allocations = data.allocations || [];
                this.closePicker();
                this.notification.add(_t(`Allocations updated for ${alloc.user_name}`), {
                    type: "success",
                });
            }
        } catch (error) {
            console.error("Failed to save allocation:", error);
            this.notification.add(_t("Failed to save allocation"), { type: "danger" });
        } finally {
            this.state.savingId = null;
        }
    }

    async quickSetAll(alloc) {
        if (!this.state.currentUserIsAdmin) {
            this.notification.add(_t("Only the Twilio Admin can modify phone number allocations."), { type: "warning" });
            return;
        }
        this.state.activeMenuId = null;
        const allOption = this.allOptionNumber;
        const allOptId = allOption ? allOption.id : null;
        this.state.draftNumberIds = allOptId ? [allOptId] : [];
        await this.saveDraft(alloc);
    }

    async quickRemoveNumber(alloc, numId) {
        if (!this.state.currentUserIsAdmin) {
            this.notification.add(_t("Only the Twilio Admin can modify phone number allocations."), { type: "warning" });
            return;
        }
        const current = (alloc.number_ids || []).filter((id) => id !== numId);
        const allOption = this.allOptionNumber;
        const allOptId = allOption ? allOption.id : null;
        this.state.draftNumberIds = current.length > 0 ? current : (allOptId ? [allOptId] : []);
        await this.saveDraft(alloc);
    }

    async resetAllToDefault() {
        if (!this.state.currentUserIsAdmin) {
            this.notification.add(_t("Only the Twilio Admin can reset all number allocations."), { type: "warning" });
            return;
        }
        if (confirm(_t("Are you sure you want to reset all users to 'All numbers'?"))) {
            this.state.loading = true;
            try {
                const data = await this.orm.call("twilio.number.allocation", "reset_all_to_default", []);
                if (data && data.success) {
                    this.state.numbers = data.numbers || [];
                    this.state.allocations = data.allocations || [];
                    this.notification.add(_t("All users reset to 'All numbers' successfully."), {
                        type: "success",
                    });
                }
            } catch (error) {
                console.error("Failed to reset allocations:", error);
                this.notification.add(_t("Failed to reset allocations"), { type: "danger" });
            } finally {
                this.state.loading = false;
            }
        }
    }

    async transferAdmin(alloc) {
        if (!this.state.currentUserIsAdmin) {
            this.notification.add(_t("Only the current Twilio Admin can transfer admin privileges."), { type: "warning" });
            return;
        }
        this.state.activeMenuId = null;
        if (confirm(_t(`Are you sure you want to transfer Twilio Admin privileges to ${alloc.user_name}? You will become a standard user.`))) {
            this.state.loading = true;
            try {
                const data = await this.orm.call("twilio.number.allocation", "action_transfer_admin", [alloc.user_id]);
                if (data && data.success) {
                    this.state.numbers = data.numbers || [];
                    this.state.allocations = data.allocations || [];
                    this.state.currentUserIsAdmin = Boolean(data.current_user_is_admin);
                    this.state.adminUserId = data.admin_user_id;
                    this.notification.add(_t(`Twilio Admin privileges successfully transferred to ${alloc.user_name}`), {
                        type: "success",
                    });
                }
            } catch (error) {
                console.error("Failed to transfer admin:", error);
                this.notification.add(_t("Failed to transfer admin privileges"), { type: "danger" });
            } finally {
                this.state.loading = false;
            }
        }
    }

    openAgentCallLogs(alloc) {
        this.state.activeMenuId = null;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t(`Call Logs: ${alloc.user_name}`),
            res_model: "twilio.call.log",
            views: [[false, "list"], [false, "form"]],
            domain: [["user_id", "=", alloc.user_id]],
            context: { default_user_id: alloc.user_id },
        });
    }

    subscribePresenceChannels() {
        if (!this.busService) return;
        if (this.busService.subscribe) {
            this.busService.subscribe("bus.bus/im_status_updated", this._onImStatusUpdated);
        }
        if (this.busService.addChannel && this.state.allocations) {
            for (const alloc of this.state.allocations) {
                const pid = alloc.partner_id || alloc.partnerId;
                if (pid) {
                    const channel = `odoo-presence-res.partner_${pid}`;
                    if (!this.trackedChannels.has(channel)) {
                        this.busService.addChannel(channel);
                        this.trackedChannels.add(channel);
                    }
                }
            }
        }
    }

    unsubscribePresenceChannels() {
        if (!this.busService) return;
        if (this.busService.unsubscribe) {
            this.busService.unsubscribe("bus.bus/im_status_updated", this._onImStatusUpdated);
        }
        if (this.busService.deleteChannel && this.trackedChannels) {
            for (const channel of this.trackedChannels) {
                this.busService.deleteChannel(channel);
            }
            this.trackedChannels.clear();
        }
    }

    _onImStatusUpdated(payload) {
        if (!payload || typeof payload !== "object") return;
        const partnerId = payload.partner_id || payload.partnerId;
        if (!partnerId) return;
        const newStatus = (payload.im_status || payload.presence_status || "offline").toLowerCase();
        
        for (const alloc of this.state.allocations) {
            const pid = alloc.partner_id || alloc.partnerId;
            if (pid === partnerId || alloc.user_id === partnerId) {
                if (alloc.im_status !== newStatus) {
                    alloc.im_status = newStatus;
                }
            }
        }
    }

    getLiveStatusDotStyle(alloc) {
        const s = (alloc && alloc.im_status ? alloc.im_status : "offline").toLowerCase().trim();
        if (s === "online") return "background-color: #10b981 !important;";
        if (s === "away" || s === "idle") return "background-color: #f59e0b !important;";
        if (s === "busy" || s === "dnd") return "background-color: #ef4444 !important;";
        return "background-color: #9ca3af !important;";
    }

    getLiveStatusBadgeStyle(alloc) {
        const s = (alloc && alloc.im_status ? alloc.im_status : "offline").toLowerCase().trim();
        if (s === "online") return "background-color: #ecfdf5 !important; color: #065f46 !important; border: 1px solid #a7f3d0 !important;";
        if (s === "away" || s === "idle") return "background-color: #fffbeb !important; color: #92400e !important; border: 1px solid #fde68a !important;";
        if (s === "busy" || s === "dnd") return "background-color: #fef2f2 !important; color: #991b1b !important; border: 1px solid #fecaca !important;";
        return "background-color: #f3f4f6 !important; color: #6b7280 !important; border: 1px solid #e5e7eb !important;";
    }

    getLiveStatusLabel(alloc) {
        const s = (alloc && alloc.im_status ? alloc.im_status : "offline").toLowerCase();
        if (s === "online") return _t("Online");
        if (s === "away" || s === "idle") return _t("Away");
        if (s === "busy" || s === "dnd") return _t("Busy");
        return _t("Offline");
    }

    getLiveStatusDotClass(alloc) {
        const s = (alloc && alloc.im_status ? alloc.im_status : "offline").toLowerCase();
        if (s === "online") return "bg-success";
        if (s === "away" || s === "idle") return "bg-warning";
        if (s === "busy" || s === "dnd") return "bg-danger";
        return "bg-secondary";
    }

    getLiveStatusBadgeClass(alloc) {
        const s = (alloc && alloc.im_status ? alloc.im_status : "offline").toLowerCase();
        if (s === "online") return "bg-success-subtle text-success border border-success-subtle";
        if (s === "away" || s === "idle") return "bg-warning-subtle text-warning border border-warning-subtle";
        if (s === "busy" || s === "dnd") return "bg-danger-subtle text-danger border border-danger-subtle";
        return "bg-light text-muted border";
    }

    getUserInitials(name) {
        if (!name) return "U";
        const parts = name.trim().split(/\s+/);
        if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }

    getUserColor(name) {
        if (!name) return "#714b67";
        const colors = [
            "#714b67", "#5c3c54", "#2563eb", "#0d9488", "#d97706",
            "#dc2626", "#7c3aed", "#0891b2", "#4f46e5", "#059669"
        ];
        let hash = 0;
        for (let i = 0; i < name.length; i++) {
            hash = name.charCodeAt(i) + ((hash << 5) - hash);
        }
        return colors[Math.abs(hash) % colors.length];
    }
}

registry.category("fields").add("twilio_number_allocation_widget", {
    component: NumberAllocationPanel,
    displayName: _t("Twilio Number Allocation Widget"),
    supportedTypes: ["char", "text", "boolean", "integer"],
}, { force: true });
