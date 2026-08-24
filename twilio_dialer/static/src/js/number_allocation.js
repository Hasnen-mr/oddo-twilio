/** @odoo-module **/

import { Component, onWillStart, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class NumberAllocationPanel extends Component {
    static template = "twilio_dialer.NumberAllocationPanel";
    static props = {
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            savingId: null,
            searchQuery: "",
            filterTab: "all", // "all", "custom", "default"
            numbers: [],
            allocations: [],
            activeDropdownId: null,
            draftSelection: {},
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call("twilio.number.allocation", "get_allocation_data", []);
            if (data && data.success) {
                this.state.numbers = data.numbers || [];
                this.state.allocations = data.allocations || [];
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

        for (const a of this.state.allocations) {
            const hasAll = !a.number_ids || a.number_ids.length === 0 || (allOptId && a.number_ids.includes(allOptId));
            if (hasAll) {
                allAccessCount++;
            } else {
                customCount++;
            }
        }

        return {
            totalUsers: total,
            allAccessCount: allAccessCount,
            customCount: customCount,
            totalNumbers: this.realNumbers.length,
        };
    }

    get filteredAllocations() {
        const q = this.state.searchQuery.trim().toLowerCase();
        const allOptId = this.allOptionNumber ? this.allOptionNumber.id : null;

        return this.state.allocations.filter((a) => {
            const hasAll = !a.number_ids || a.number_ids.length === 0 || (allOptId && a.number_ids.includes(allOptId));

            if (this.state.filterTab === "default" && !hasAll) {
                return false;
            }
            if (this.state.filterTab === "custom" && hasAll) {
                return false;
            }

            if (q) {
                const nameMatch = (a.user_name || "").toLowerCase().includes(q);
                const loginMatch = (a.user_login || "").toLowerCase().includes(q);
                const statusMatch = (a.status || "").toLowerCase().includes(q);
                if (!nameMatch && !loginMatch && !statusMatch) {
                    return false;
                }
            }

            return true;
        });
    }

    isAllAssigned(alloc) {
        const allOptId = this.allOptionNumber ? this.allOptionNumber.id : null;
        return !alloc.number_ids || alloc.number_ids.length === 0 || (allOptId && alloc.number_ids.includes(allOptId));
    }

    getAssignedNumberObjs(alloc) {
        if (this.isAllAssigned(alloc)) {
            return [];
        }
        const set = new Set(alloc.number_ids);
        return this.realNumbers.filter((n) => set.has(n.id));
    }

    getUserInitials(name) {
        if (!name) return "U";
        const parts = name.trim().split(" ");
        if (parts.length === 1) {
            return parts[0].substring(0, 2).toUpperCase();
        }
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }

    getUserColor(name) {
        const colors = ["#4F46E5", "#059669", "#7C3AED", "#DB2777", "#D97706", "#2563EB", "#0D9488"];
        let hash = 0;
        for (let i = 0; i < (name || "").length; i++) {
            hash = name.charCodeAt(i) + ((hash << 5) - hash);
        }
        return colors[Math.abs(hash) % colors.length];
    }

    openPicker(alloc) {
        if (this.state.activeDropdownId === alloc.id) {
            this.state.activeDropdownId = null;
            return;
        }
        this.state.activeDropdownId = alloc.id;
        const allOptId = this.allOptionNumber ? this.allOptionNumber.id : null;
        const isAll = this.isAllAssigned(alloc);

        this.state.draftSelection[alloc.id] = isAll ? (allOptId ? [allOptId] : []) : [...alloc.number_ids];
    }

    closePicker() {
        this.state.activeDropdownId = null;
    }

    isDraftSelected(allocId, numId) {
        const draft = this.state.draftSelection[allocId] || [];
        return draft.includes(numId);
    }

    toggleDraftNumber(allocId, num) {
        const allOptId = this.allOptionNumber ? this.allOptionNumber.id : null;
        let draft = [...(this.state.draftSelection[allocId] || [])];

        if (num.is_all || num.phone_number === "ALL") {
            // Selected "All numbers" -> replace draft with only ALL option
            draft = [num.id];
        } else {
            // Remove ALL option if present
            if (allOptId) {
                draft = draft.filter((id) => id !== allOptId);
            }
            if (draft.includes(num.id)) {
                draft = draft.filter((id) => id !== num.id);
            } else {
                draft.push(num.id);
            }
            // If empty, revert to ALL option
            if (draft.length === 0 && allOptId) {
                draft = [allOptId];
            }
        }

        this.state.draftSelection[allocId] = draft;
    }

    async saveDraft(alloc) {
        const draft = this.state.draftSelection[alloc.id] || [];
        this.state.savingId = alloc.id;
        try {
            const res = await this.orm.call("twilio.number.allocation", "update_allocation", [alloc.id, draft]);
            if (res && res.success) {
                alloc.number_ids = res.number_ids;
                alloc.status = res.status;
                this.state.activeDropdownId = null;
                this.notification.add(_t("Number allocation updated for %s", alloc.user_name), {
                    type: "success",
                });
            }
        } catch (error) {
            console.error("Failed to save allocation:", error);
            this.notification.add(_t("Failed to update allocation"), { type: "danger" });
        } finally {
            this.state.savingId = null;
        }
    }

    async quickSetAll(alloc) {
        const allOptId = this.allOptionNumber ? this.allOptionNumber.id : null;
        if (!allOptId) return;

        this.state.savingId = alloc.id;
        try {
            const res = await this.orm.call("twilio.number.allocation", "update_allocation", [alloc.id, [allOptId]]);
            if (res && res.success) {
                alloc.number_ids = res.number_ids;
                alloc.status = res.status;
                this.notification.add(_t("%s set to All Numbers", alloc.user_name), {
                    type: "success",
                });
            }
        } catch (error) {
            console.error("Failed to set all numbers:", error);
            this.notification.add(_t("Failed to update allocation"), { type: "danger" });
        } finally {
            this.state.savingId = null;
        }
    }

    async quickRemoveNumber(alloc, numId) {
        const current = alloc.number_ids.filter((id) => id !== numId);
        const allOptId = this.allOptionNumber ? this.allOptionNumber.id : null;
        const target = current.length > 0 ? current : (allOptId ? [allOptId] : []);

        this.state.savingId = alloc.id;
        try {
            const res = await this.orm.call("twilio.number.allocation", "update_allocation", [alloc.id, target]);
            if (res && res.success) {
                alloc.number_ids = res.number_ids;
                alloc.status = res.status;
                this.notification.add(_t("Updated allocation for %s", alloc.user_name), {
                    type: "info",
                });
            }
        } catch (error) {
            console.error("Failed to remove number:", error);
            this.notification.add(_t("Failed to update allocation"), { type: "danger" });
        } finally {
            this.state.savingId = null;
        }
    }

    async resetAllToDefault() {
        if (!confirm(_t("Reset all team members to have access to 'All numbers'?"))) {
            return;
        }
        this.state.loading = true;
        try {
            const data = await this.orm.call("twilio.number.allocation", "reset_all_to_default", []);
            if (data && data.success) {
                this.state.numbers = data.numbers || [];
                this.state.allocations = data.allocations || [];
                this.notification.add(_t("All users have been reset to All Numbers"), {
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
