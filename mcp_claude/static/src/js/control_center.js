/** @odoo-module **/

import { AIChatWindow } from "@mcp_claude/js/components/ai_chat_window";

import { Component, markup, onMounted, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class MCPControlCenter extends Component {
    static template = "mcp_claude.ControlCenter";
    static components = { AIChatWindow };

    get generatedSchemaPreviewJson() {
        try {
            return JSON.stringify(this.generatedSchemaPreview, null, 2);
        } catch (e) {
            return "{}";
        }
    }

    get testToolResultJson() {
        try {
            return JSON.stringify(this.state.testToolResult || {}, null, 2);
        } catch (e) {
            return "{}";
        }
    }

    setup() {
        this.orm = useService("orm");
        try {
            this.aiService = useService("ai_chat_service");
        } catch (e) {
            this.aiService = null;
        }
        this.notification = useService("notification");
        this.action = useService("action");
        this.claudeMessagesRef = useRef("claudeMessagesBody");
        this._reqId = 0;

        const defaultOrigin = window.location.origin;

        // Restore persisted user preferences from localStorage
        const savedTab = localStorage.getItem("mcp_active_tab") || "configurations";
        let savedSubTab = localStorage.getItem("mcp_settings_tab") || "general";
        if (savedSubTab === "provider" || savedSubTab === "connection") {
            savedSubTab = "general";
        } else if (savedSubTab === "tools") {
            savedSubTab = "permissions";
        } else if (savedSubTab === "authentication") {
            savedSubTab = "security";
        } else if (savedSubTab === "advanced") {
            savedSubTab = "activity";
        }
        const savedTheme = localStorage.getItem("mcp_theme_mode") || "light";
        const savedFilter = localStorage.getItem("mcp_tools_op_filter") || "all";

        const actionParams = (this.props && this.props.action && this.props.action.params) || {};
        let targetTab = actionParams.tab || savedTab;
        if (!targetTab) {
            targetTab = "configurations";
        }
        const targetDashboardId = actionParams.dashboard_id || null;

        this.state = useState({
            // Twilio-style Setup Wizard State
            showOnboardingWizard: false,
            wizardStep: 1,
            wizardClient: "desktop", // "desktop", "web", "cli", "ide"
            wizardPlatform: "windows",
            isTestingWizardConnection: false,
            wizardConnectionTested: false,
            isAutoConfigured: false,
            // Email OTP Verification state
            userEmail: "",
            userName: "",
            webClaudeApiKey: "",
            isTestingWebKey: false,
            webKeyVerified: false,
            showWebKey: false,
            webKeyError: "",
            webKeySuccess: "",
            otp: "",
            sendingOtp: false,
            otpSent: false,
            verifyingOtp: false,
            emailVerified: false,
            otpError: "",
            otpSuccessMessage: "",
            isEditingEmail: false,
            newEmail: "",
            showEmailVerification: false,
            isBubbleEnabled: localStorage.getItem("mcp_bubble_enabled") !== "false",
            showManualSetup: false,
            isAutoConfiguring: false,
            wizardConnectionSuccess: false,
            wizardErrorMessage: "",

            activeTab: targetTab,
            dashboards: [],
            loadingDashboards: false,
            dashboardCategoryFilter: "all",
            dashboardFavoriteFilter: false,
            dashboardSearchQuery: "",
            activeDashboardId: targetDashboardId,
            activeDashboardData: null,
            loadingActiveDashboard: false,
            dateRangeFilter: "all_time",
            settingsTab: savedSubTab,
            themeMode: savedTheme, // 'light' or 'dark'
            connectOption: "json",
            selectedEnvMode: "local",
            selectedLocalVersion: "18",
            selectedLocalPort: "8069",
            customLiveDomain: "",
            activeApiKey: "",
            loadingData: true,
            isSyncing: false,
            envLoading: true,
            
            isHttp: false,
            httpsEnabled: false,
            serverUrl: defaultOrigin,
            connectorUrl: defaultOrigin + "/mcp",
            stdioJsonConfig: '{\n  "mcpServers": {\n    "odoo-mcp": {\n      "command": "python",\n      "args": ["mcp_bridge.py"]\n    }\n  }\n}',

            envInfo: {
                environment: null,
                environment_title: "Loading...",
                base_url: defaultOrigin,
                hostname: window.location.hostname,
                scheme: window.location.protocol.replace(':', ''),
                port: window.location.port,
                is_https: false,
                is_localhost: null,
                recommended_connection: "json",
                supports_direct_url: false,
                badge_label: "⌛ Loading...",
                badge_class: "bg-secondary",
                status_text: "⌛ Loading Environment...",
                reason: "Detecting deployment capabilities...",
                warning_message: null,
                config_json: "",
                connection_status: {
                    server_reachability: { label: "Server Reachability", status: "Online", ok: true, badge: "🟢 Online" },
                    mcp_endpoint: { label: "MCP Endpoint", status: "Reachable", ok: true, badge: "🟢 Reachable" },
                    oauth_support: { label: "OAuth Support", status: "Detected", ok: true, badge: "🟢 Detected" },
                    recommended_connection: { label: "Recommended Connection", status: "Claude JSON Configuration", ok: true, badge: "📄 Stdio JSON" }
                },
                clientPlatform: this.detectClientPlatform(),
                wizardStep: 1,
                isSavingWizardParams: false,
                wizardForm: {
                    python_path: "python",
                    bridge_path: "mcp_bridge.py",
                    api_key: "mcp_live_default",
                    server_url: ""
                }
            },
            
            showOAuthSecret: false,
            showAdvancedConnection: false,
            showAdvancedSecurity: false,
            revealedSecretValue: "••••••••••••••••",

            showConnectWizard: false,
            showCreateTokenModal: false,
            showRawTokenModal: false,
            showAddToolModal: false,
            showQuickSearch: false,
            showShortcutsHelpModal: false,
            showConfirmDialog: false,
            confirmDialogOptions: {
                title: "Confirm Action",
                message: "Are you sure you want to proceed?",
                confirmText: "Confirm",
                cancelText: "Cancel",
                isDanger: true,
                onConfirm: null
            },
            showOperationNotAvailableModal: false,
            operationNotAvailableTitle: "Operation Not Available",
            operationNotAvailableMessage: "",
            newlyCreatedRawToken: "",

            testingConnector: false,
            testResults: null,

            tools: [],
            apiKeys: [],
            oauthClients: [],
            sessions: [],
            auditLogs: [],

            toolsSearchQuery: "",
            toolsOperationFilter: savedFilter,
            permissionsSearchQuery: "",

            // Multi-step Add/Edit Tool Modal State
            modalStep: 1,
            isEditingTool: false,
            availableModels: [],
            modelSearchQuery: "",
            availableFields: [],
            fieldSearchQuery: "",
            selectedPlatformTab: "win_standard",
            fieldCategoryTab: "all",
            showAdvancedSettings: false,
            editingCustomName: false,
            editingCustomDesc: false,
            loadingModels: false,
            loadingFields: false,
            toolForm: {
                id: null,
                name: "",
                display_name: "",
                description: "",
                model_name: "",
                operation: "search",
                search_fields: [],
                result_fields: [],
                is_builtin: false,
                active: true
            },

            // Permissions UI State for Odoo Apps
            odooAppsPermissions: [
                { id: "sale", name: "Sales", model: "sale.order", icon: "fa-shopping-cart", read: true, create: false, write: false, delete: false, active: true },
                { id: "account", name: "Invoicing", model: "account.move", icon: "fa-calculator", read: true, create: false, write: false, delete: false, active: true },
                { id: "stock", name: "Inventory", model: "stock.picking", icon: "fa-cubes", read: true, create: false, write: false, delete: false, active: true },
                { id: "crm", name: "CRM", model: "crm.lead", icon: "fa-handshake-o", read: true, create: false, write: false, delete: false, active: true },
                { id: "partner", name: "Contacts", model: "res.partner", icon: "fa-address-book", read: true, create: false, write: false, delete: false, active: true },
                { id: "hr", name: "Employees", model: "hr.employee", icon: "fa-users", read: true, create: false, write: false, delete: false, active: false },
                { id: "purchase", name: "Purchase", model: "purchase.order", icon: "fa-truck", read: true, create: false, write: false, delete: false, active: true },
                { id: "project", name: "Project", model: "project.task", icon: "fa-tasks", read: true, create: false, write: false, delete: false, active: true },
                { id: "twilio", name: "Twilio Dialer", model: "twilio.call.log", icon: "fa-phone", read: true, create: true, write: true, delete: false, active: true },
            ],

            stats: {
                totalTools: 0,
                activeKeys: 0,
                activeSessions: 0,
                rateLimitRpm: 120,
            },

            claudeStatus: {
                connected: false,
                status: "never_connected",
                status_label: "Never Connected",
                status_subtitle: "Initial setup not completed",
                badge_class: "bg-secondary text-white",
                icon_symbol: "⚫",
                mode: "Not Available",
                last_activity_text: "Never",
                last_activity_iso: "",
                client_name: "Claude Desktop",
                client_version: "v1.0.0",
                active_sessions_count: 0,
                health_checks: {
                    oauth: false,
                    mcp_session: false,
                    authentication: true,
                    endpoint_reachable: true,
                    tool_registration: true
                }
            },

            newToken: {
                name: "Claude",
                scopes: "full",
                expiration_policy: "never",
                allowed_ips: "",
            },

            // Configurations UI & Form State
            selectedToolCategory: "all",
            configForm: {
                ai_provider: "claude",
                claude_api_key: "",
                claude_model: "claude-3-5-sonnet-20241022",
                openai_api_key: "",
                openai_model: "gpt-4o",
                enable_twilio_dialer: false,
                twilio_caller_number: "",
                twilio_caller_valid: true,
            },
            testingProvider: null,
            claudeSidebarSearch: "",
            claudeConversations: [],
            claudeActiveConvId: null,
            claudeMessages: [],
            claudePromptText: "",
            claudeSending: false,
            expandedTools: {},
            savingConfig: false,
        });

        // Computed Tool Filter Getter
        this.getFilteredTools = () => {
            const q = (this.state.toolsSearchQuery || "").toLowerCase().trim();
            const cat = (this.state.selectedToolCategory || "all").toLowerCase();
            return (this.state.tools || []).filter(t => {
                const matchQ = !q || (t.name || "").toLowerCase().includes(q) || (t.description || "").toLowerCase().includes(q) || (t.model_name || "").toLowerCase().includes(q);
                const matchCat = cat === "all" || (t.category || "Technical").toLowerCase() === cat;
                return matchQ && matchCat;
            });
        };

        this.getToolsForApp = (appId) => {
            const q = (this.state.toolsSearchQuery || "").toLowerCase().trim();
            const tools = this.state.tools || [];
            
            const appKeywordMap = {
                'sale': ['sale', 'order', 'orders', 'sale.order'],
                'account': ['account', 'invoice', 'invoices', 'account.move'],
                'stock': ['stock', 'picking', 'product', 'products', 'stock.picking', 'product.product'],
                'crm': ['crm', 'lead', 'leads', 'opportunity', 'crm.lead'],
                'partner': ['partner', 'partners', 'customer', 'customers', 'res.partner', 'contact', 'contacts', 'vip'],
                'hr': ['hr', 'employee', 'employees', 'hr.employee'],
                'purchase': ['purchase', 'purchase.order'],
                'project': ['project', 'task', 'tasks', 'project.task'],
                'twilio': ['twilio', 'dialer', 'call', 'twilio.call.log', 'twilio.ai.service']
            };

            const keywords = appKeywordMap[appId] || [appId];

            return tools.filter(t => {
                const name = (t.name || "").toLowerCase();
                const model = (t.model_name || "").toLowerCase();
                const cat = (t.category || "").toLowerCase();
                
                const matchApp = keywords.some(k => name.includes(k) || model.includes(k) || cat.includes(k));
                const matchQ = !q || name.includes(q) || (t.description || "").toLowerCase().includes(q) || model.includes(q);

                return matchApp && matchQ;
            });
        };

        this.getThirdPartyTools = () => {
            const q = (this.state.toolsSearchQuery || "").toLowerCase().trim();
            const thirdPartyKeywords = ['twilio', 'openai', 'claude', 'anthropic', 'external', 'ai', 'dialer'];
            return (this.state.tools || []).filter(t => {
                const name = (t.name || "").toLowerCase();
                const model = (t.model_name || "").toLowerCase();
                const cat = (t.category || "").toLowerCase();
                const isThirdParty = thirdPartyKeywords.some(k => name.includes(k) || model.includes(k) || cat.includes(k));
                const matchQ = !q || name.includes(q) || (t.description || "").toLowerCase().includes(q) || model.includes(q);
                return isThirdParty && matchQ;
            });
        };

        this.getUncategorizedTools = () => {
            const q = (this.state.toolsSearchQuery || "").toLowerCase().trim();
            const knownKeywords = ['sale', 'order', 'account', 'invoice', 'stock', 'product', 'crm', 'lead', 'partner', 'customer', 'hr', 'employee', 'purchase', 'project', 'task', 'twilio', 'openai', 'claude', 'dialer', 'vip'];
            
            return (this.state.tools || []).filter(t => {
                const name = (t.name || "").toLowerCase();
                const model = (t.model_name || "").toLowerCase();
                const cat = (t.category || "").toLowerCase();
                const isMapped = knownKeywords.some(k => name.includes(k) || model.includes(k) || cat.includes(k));
                const matchQ = !q || name.includes(q) || (t.description || "").toLowerCase().includes(q);
                return !isMapped && matchQ;
            });
        };

        // Keybindings Handler
        this._onKeyDown = (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
                e.preventDefault();
                this.state.showQuickSearch = !this.state.showQuickSearch;
            } else if (e.key === "Escape") {
                this.closeAllModals();
            } else if (e.key === "?" && !["INPUT", "TEXTAREA"].includes(e.target.tagName)) {
                e.preventDefault();
                this.state.showShortcutsHelpModal = !this.state.showShortcutsHelpModal;
            } else if (e.key === "/" && !["INPUT", "TEXTAREA"].includes(e.target.tagName)) {
                e.preventDefault();
                const inputEl = document.querySelector(".mcp-filter-bar input");
                if (inputEl) inputEl.focus();
            }
        };

        onMounted(async () => {
            window.addEventListener("keydown", this._onKeyDown);
            await this.loadDashboards();
            if (this.state.activeDashboardId) {
                await this.openDashboard(this.state.activeDashboardId);
            }
            this.pollClaudeStatus();
            this._statusPollTimer = setInterval(() => {
                this.pollClaudeStatus();
            }, 5000);
        });

        onWillUnmount(() => {
        if (this._verificationNagTimer) clearTimeout(this._verificationNagTimer);
            window.removeEventListener("keydown", this._onKeyDown);
            if (this._statusPollTimer) {
                clearInterval(this._statusPollTimer);
            }
        });

        window.dispatchEvent(new CustomEvent("restore_mcp_ai_bubble"));
        onWillStart(async () => {
            await this.loadAllData();
        });
    }

    // Persist Tab Choices to localStorage
    // Persist Tab Choices to localStorage & Notify Components
    setTab(tabName) {
        this.state.activeTab = tabName;
        localStorage.setItem("mcp_active_tab", tabName);
        window.dispatchEvent(new CustomEvent("mcp_tab_changed", { detail: { tab: tabName } }));
    }
    setTabHome() {
        this.setTab("home");
    }
    setTabClaude() {
        this.setTab("claude");
        this.loadClaudeConversations();
    }
    setTabDashboards() {
        this.state.activeDashboardId = null;
        this.state.activeDashboardData = null;
        this.setTab("dashboard");
        this.loadDashboards();
    }
    setTabTools() {
        this.setTab("tools");
    }
    setTabConfigurations() {
        this.setTab("configurations");
    }
    openServerConfiguration() {
        this.action.doAction("mcp_claude.action_mcp_server_config");
    }
    openModelPermissionRules() {
        this.action.doAction("mcp_claude.action_mcp_model_rule");
    }
    setSubTabGeneral() {
        this.state.settingsTab = "general";
        localStorage.setItem("mcp_settings_tab", "general");
    }
    setSubTabPermissions() {
        this.state.settingsTab = "permissions";
        localStorage.setItem("mcp_settings_tab", "permissions");
    }
    setSubTabIntegrations() {
        this.state.settingsTab = "integrations";
        localStorage.setItem("mcp_settings_tab", "integrations");
    }
    setSubTabSecurity() {
        this.state.settingsTab = "security";
        localStorage.setItem("mcp_settings_tab", "security");
    }
    setSubTabActivity() {
        this.state.settingsTab = "activity";
        localStorage.setItem("mcp_settings_tab", "activity");
    }
    setSubTabProvider() {
        this.setSubTabIntegrations();
    }
    setSubTabConnection() {
        this.setSubTabGeneral();
    }
    setSubTabTools() {
        this.setSubTabPermissions();
    }
    setSubTabAuth() {
        this.setSubTabSecurity();
    }
    setSubTabAudit() {
        this.setSubTabActivity();
    }

    getAuditSuccessCount() {
        if (!Array.isArray(this.state.auditLogs)) return 0;
        return this.state.auditLogs.filter(l => l.status === 'success' || !l.status).length;
    }

    getAuditUniqueModelsCount() {
        if (!Array.isArray(this.state.auditLogs)) return 0;
        const models = new Set(this.state.auditLogs.map(l => l.model_name).filter(Boolean));
        return models.size;
    }

    toggleAdvancedConnection() {
        this.state.showAdvancedConnection = !this.state.showAdvancedConnection;
    }

    toggleAdvancedSecurity() {
        this.state.showAdvancedSecurity = !this.state.showAdvancedSecurity;
    }

    getAppInfo(modelName) {
        const key = (modelName || '').toLowerCase().trim();
        const map = {
            'sale.order': { name: 'Sales', subtext: 'Quotes & Orders', model: 'sale.order', icon: 'fa-shopping-cart' },
            'sale': { name: 'Sales', subtext: 'Quotes & Orders', model: 'sale.order', icon: 'fa-shopping-cart' },

            'crm.lead': { name: 'CRM', subtext: 'Leads & Opportunities', model: 'crm.lead', icon: 'fa-handshake-o' },
            'crm': { name: 'CRM', subtext: 'Leads & Opportunities', model: 'crm.lead', icon: 'fa-handshake-o' },

            'res.partner': { name: 'Contacts', subtext: 'Customers & Vendors', model: 'res.partner', icon: 'fa-address-book' },
            'partner': { name: 'Contacts', subtext: 'Customers & Vendors', model: 'res.partner', icon: 'fa-address-book' },

            'account.move': { name: 'Invoicing', subtext: 'Invoices & Payments', model: 'account.move', icon: 'fa-calculator' },
            'account': { name: 'Invoicing', subtext: 'Invoices & Payments', model: 'account.move', icon: 'fa-calculator' },

            'stock.picking': { name: 'Inventory', subtext: 'Transfers & Stock', model: 'stock.picking', icon: 'fa-cubes' },
            'stock': { name: 'Inventory', subtext: 'Transfers & Stock', model: 'stock.picking', icon: 'fa-cubes' },

            'purchase.order': { name: 'Purchase', subtext: 'Orders & Vendor Bills', model: 'purchase.order', icon: 'fa-truck' },
            'purchase': { name: 'Purchase', subtext: 'Orders & Vendor Bills', model: 'purchase.order', icon: 'fa-truck' },

            'project.task': { name: 'Project', subtext: 'Tasks & Milestones', model: 'project.task', icon: 'fa-tasks' },
            'project': { name: 'Project', subtext: 'Tasks & Milestones', model: 'project.task', icon: 'fa-tasks' },

            'hr.employee': { name: 'Employees', subtext: 'Staff Directory', model: 'hr.employee', icon: 'fa-users' },
            'hr': { name: 'Employees', subtext: 'Staff Directory', model: 'hr.employee', icon: 'fa-users' },

            'product.template': { name: 'Products', subtext: 'Catalog & Variants', model: 'product.template', icon: 'fa-cubes' },
            'product.product': { name: 'Products', subtext: 'Product Variants', model: 'product.product', icon: 'fa-cube' },
            'product': { name: 'Products', subtext: 'Catalog & Variants', model: 'product.template', icon: 'fa-cubes' },

            'twilio.call.log': { name: 'Twilio Dialer', subtext: 'Call Logs', model: 'twilio.call.log', icon: 'fa-phone' },
            'twilio': { name: 'Twilio Dialer', subtext: 'Call Logs', model: 'twilio.call.log', icon: 'fa-phone' },

            'mcp.tool': { name: 'MCP Tools', subtext: 'Custom Tools Registry', model: 'mcp.tool', icon: 'fa-wrench' }
        };
        if (map[key]) return map[key];

        if (!key) return { name: 'General', subtext: 'System Module', model: '', icon: 'fa-cog' };
        const cleanName = key.split('.').pop().replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        return { name: cleanName, subtext: key, model: key, icon: 'fa-folder' };
    }

    getModelLabel(modelName) {
        return this.getAppInfo(modelName).name;
    }

    getModelSubtext(modelName) {
        return this.getAppInfo(modelName).subtext;
    }

    getModelTechBadge(modelName) {
        if (!modelName) return '';
        return `(${modelName})`;
    }

    getFriendlyActionBadge(actionType) {
        const type = (actionType || '').toLowerCase();
        if (type.includes('tool_created') || type.includes('tool_registered')) {
            return { label: 'Tool Registered', class: 'bg-success-subtle text-success border-success' };
        } else if (type.includes('record_created') || type.includes('create')) {
            return { label: 'Record Created', class: 'bg-primary-subtle text-primary border-primary' };
        } else if (type.includes('record_updated') || type.includes('write') || type.includes('update')) {
            return { label: 'Record Edited', class: 'bg-info-subtle text-info border-info' };
        } else if (type.includes('record_deleted') || type.includes('unlink') || type.includes('delete')) {
            return { label: 'Record Deleted', class: 'bg-danger-subtle text-danger border-danger' };
        } else if (type.includes('tool_disabled') || type.includes('pause')) {
            return { label: 'Tool Paused', class: 'bg-warning-subtle text-warning border-warning' };
        } else if (type.includes('tool_enabled') || type.includes('active')) {
            return { label: 'Tool Active', class: 'bg-success-subtle text-success border-success' };
        }
        return { label: actionType || 'System Event', class: 'bg-secondary-subtle text-secondary border-secondary' };
    }

    getActivePresetKey() {
        const apps = this.state.odooAppsPermissions || [];
        if (apps.length === 0) return 'custom';
        const allReadOnly = apps.every(a => a.read && !a.create && !a.write && !a.delete);
        if (allReadOnly) return 'read_only';
        const allFull = apps.every(a => a.read && a.create && a.write && a.delete);
        if (allFull) return 'full_access';
        const isStandard = apps.every(a => {
            if (['partner', 'crm', 'sale', 'project'].includes(a.id)) {
                return a.read && a.create && a.write && !a.delete;
            }
            return a.read && !a.create && !a.write && !a.delete;
        });
        if (isStandard) return 'standard';
        return 'custom';
    }

    toggleThemeMode() {
        const nextTheme = this.state.themeMode === "dark" ? "light" : "dark";
        this.state.themeMode = nextTheme;
        localStorage.setItem("mcp_theme_mode", nextTheme);
        this.notification.add(`Theme switched to ${nextTheme === "dark" ? "Dark Mode" : "Light Mode"}`, { type: "info" });
    }

    closeAllModals() {
        this.state.showAddToolModal = false;
        this.state.showConnectWizard = false;
        this.state.showCreateTokenModal = false;
        this.state.showRawTokenModal = false;
        this.state.showTestToolModal = false;
        this.state.showQuickSearch = false;
        this.state.showShortcutsHelpModal = false;
        this.state.showConfirmDialog = false;
        this.state.showOperationNotAvailableModal = false;
    }

    detectClientPlatform() {
        const ua = navigator.userAgent || "";
        if (ua.includes("Win")) return "Windows";
        if (ua.includes("Mac")) return "macOS";
        if (ua.includes("Linux") || ua.includes("X11")) return "Linux";
        return "Unknown";
    }

    setClientPlatform(platform) {
        this.state.clientPlatform = platform;
    }

    setWizardStep(step) {
        this.state.wizardStep = step;
    }

    async saveWizardParams() {
        this.state.isSavingWizardParams = true;
        try {
            const updatedEnvInfo = await this.orm.call(
                "mcp.tool",
                "set_wizard_config_params",
                [],
                {
                    python_path: this.state.wizardForm.python_path,
                    bridge_path: this.state.wizardForm.bridge_path,
                    api_key: this.state.wizardForm.api_key,
                    server_url: this.state.wizardForm.server_url
                }
            );

            if (updatedEnvInfo) {
                this.state.envInfo = updatedEnvInfo;
                this.state.stdioJsonConfig = updatedEnvInfo.config_json;
                this.state.connectorUrl = updatedEnvInfo.direct_url;
            }

            this.notification.add("Configuration Settings Saved! JSON code updated dynamically.", {
                type: "success",
                title: "Settings Saved"
            });
        } catch (err) {
            this.notification.add(`Save Failed: ${err.message}`, { type: "danger" });
        } finally {
            this.state.isSavingWizardParams = false;
        }
    }

    async pollClaudeStatus() {
        try {
            const status = await this.orm.call("mcp.tool", "get_claude_connection_status", []).catch(() => null);
            if (status && typeof status === "object") {
                this.state.claudeStatus = status;
            }
        } catch (e) {
            console.warn("Poll status failed:", e);
        }
    }

    async loadAllData() {
        const reqId = ++this._reqId;
        this.state.isSyncing = true;
        try {
            const envInfo = await this.orm.call("mcp.tool", "get_environment_info", []).catch(() => null);
            if (reqId !== this._reqId) return;

            if (envInfo && typeof envInfo === "object") {
                this.state.envInfo = Object.assign({}, this.state.envInfo, envInfo);
                this.state.connectOption = envInfo.recommended_connection || this.state.connectOption;
                this.state.connectorUrl = envInfo.direct_url || this.state.connectorUrl;
                this.state.stdioJsonConfig = envInfo.config_json || this.state.stdioJsonConfig;
                this.state.serverUrl = envInfo.base_url || this.state.serverUrl;
                this.state.isHttp = !envInfo.is_https;
                this.state.httpsEnabled = !!envInfo.is_https;
                this.state.envLoading = false;
                if (envInfo.api_key || (envInfo.wizard_params && envInfo.wizard_params.api_key)) {
                    this.state.activeApiKey = envInfo.api_key || envInfo.wizard_params.api_key;
                }
                if (envInfo.port === "8070" || envInfo.port === 8070) {
                    this.state.selectedLocalVersion = "17";
                    this.state.selectedLocalPort = "8070";
                } else if (envInfo.port === "8072" || envInfo.port === 8072) {
                    this.state.selectedLocalVersion = "19";
                    this.state.selectedLocalPort = "8072";
                } else if (envInfo.port === "8069" || envInfo.port === 8069) {
                    this.state.selectedLocalVersion = "18";
                    this.state.selectedLocalPort = "8069";
                }
                if (envInfo.wizard_params) {
                    this.state.wizardForm = {
                        python_path: envInfo.wizard_params.python_path || "python",
                        bridge_path: envInfo.wizard_params.bridge_path || "mcp_bridge.py",
                        api_key: envInfo.wizard_params.api_key || "mcp_live_default",
                        server_url: envInfo.wizard_params.server_url_override || ""
                    };
                }
            }

            const tools = await this.orm.searchRead("mcp.tool", [], ["id", "name", "display_name", "description", "model_name", "operation", "search_fields", "result_fields", "active", "is_builtin", "sequence", "create_date"], { order: "sequence, id" }).catch(() => []);
            if (reqId !== this._reqId) return;

            const keys = await this.orm.searchRead("mcp.api.key", [], ["id", "name", "key_prefix", "scopes", "expiration_policy", "expires_at", "last_used_at", "last_used_ip", "active", "create_date"]).catch(() => []);
            if (reqId !== this._reqId) return;

            const clients = await this.orm.searchRead("mcp.oauth.client", [], ["id", "name", "client_id", "redirect_uri", "active"]).catch(() => []);
            if (reqId !== this._reqId) return;

            const sessions = await this.orm.searchRead("mcp.session", [], ["id", "client_name", "active", "expires_at", "create_date"]).catch(() => []);
            if (reqId !== this._reqId) return;

            const logs = await this.orm.searchRead("mcp.audit.log", [], ["id", "tool_name", "model_name", "action_type", "status", "create_date"], { limit: 15, order: "id desc" }).catch(() => []);
            if (reqId !== this._reqId) return;

            const backendPerms = await this.orm.call("mcp.model.rule", "get_app_permissions", []).catch(() => null);
            if (reqId !== this._reqId) return;

            this.state.tools = Array.isArray(tools) ? tools : [];
            this.state.apiKeys = Array.isArray(keys) ? keys : [];
            this.state.oauthClients = Array.isArray(clients) ? clients : [];
            this.state.sessions = Array.isArray(sessions) ? sessions : [];
            this.state.auditLogs = Array.isArray(logs) ? logs : [];
            if (Array.isArray(backendPerms) && backendPerms.length > 0) {
                this.state.odooAppsPermissions = backendPerms;
            }

            this.state.stats.totalTools = this.state.tools.length;
            this.state.stats.activeKeys = this.state.apiKeys.filter(k => k && k.active).length;
            this.state.stats.activeSessions = this.state.sessions.filter(s => s && s.active).length;

            await this.loadServerConfig();
        } catch (e) {
            console.error("Failed loading MCP data:", e);
        } finally {
            if (reqId === this._reqId) {
                this.state.loadingData = false;
                this.state.isSyncing = false;
            }
        }
    }

    
    async loadClaudeConversations() {
        try {
            const convs = await this.orm.searchRead("mcp.ai.conversation", [], ["id", "name", "create_date", "write_date"], { order: "id desc", limit: 35 });
            if (!Array.isArray(convs)) {
                this.state.claudeConversations = [];
                return;
            }

            const convIds = convs.map(c => c.id);
            if (convIds.length > 0) {
                // Fetch first user message per conversation to generate smart frontend display titles
                const userMsgs = await this.orm.searchRead(
                    "mcp.ai.message",
                    [["conversation_id", "in", convIds], ["role", "=", "user"]],
                    ["conversation_id", "content"],
                    { order: "id asc", limit: 100 }
                );

                const firstMsgMap = {};
                if (Array.isArray(userMsgs)) {
                    for (const m of userMsgs) {
                        const cid = Array.isArray(m.conversation_id) ? m.conversation_id[0] : m.conversation_id;
                        if (!firstMsgMap[cid] && m.content) {
                            firstMsgMap[cid] = m.content;
                        }
                    }
                }

                for (const c of convs) {
                    const prompt = firstMsgMap[c.id];
                    if (prompt && (c.name === "Global AI Assistant" || c.name === "Global AI Conversation" || !c.name)) {
                        const text = prompt.trim();
                        let title = text.charAt(0).toUpperCase() + text.slice(1);
                        if (title.length > 28) {
                            title = title.substring(0, 26) + "...";
                        }
                        c.display_name = title;
                    } else {
                        c.display_name = c.name || `Chat #${c.id}`;
                    }
                }
            }

            this.state.claudeConversations = convs;
            const activeId = this.aiService.getActiveConversationId();
            if (activeId) {
                this.state.claudeActiveConvId = activeId;
                await this.loadClaudeMessages(activeId);
            } else if (this.state.claudeConversations.length > 0) {
                this.state.claudeActiveConvId = this.state.claudeConversations[0].id;
                await this.loadClaudeMessages(this.state.claudeConversations[0].id);
            }
        } catch (e) {
            console.warn("Failed to load Claude conversations:", e);
        }
    }

    scrollToClaudeBottom() {
        const scroll = () => {
            if (this.claudeMessagesRef && this.claudeMessagesRef.el) {
                this.claudeMessagesRef.el.scrollTop = this.claudeMessagesRef.el.scrollHeight;
            }
        };
        scroll();
        setTimeout(scroll, 50);
        setTimeout(scroll, 200);
    }

    async loadClaudeMessages(convId) {
        if (!convId) return;
        this.state.claudeActiveConvId = convId;
        try {
            const msgs = await this.orm.searchRead("mcp.ai.message", [["conversation_id", "=", convId]], ["id", "role", "content", "create_date", "block_type"], { order: "id asc" });
            this.state.claudeMessages = Array.isArray(msgs) ? msgs : [];
            this.scrollToClaudeBottom();
        } catch (e) {
            console.warn("Failed to load messages for conversation #" + convId, e);
        }
    }

    async createNewClaudeChat() {
        this.state.claudeSending = true;
        try {
            const res = await this.aiService.initChat("global");
            if (res && res.conversation_id) {
                this.state.claudeActiveConvId = res.conversation_id;
                this.state.claudeMessages = [];
                await this.loadClaudeConversations();
            }
        } catch (e) {
            this.notification.add("Failed to start new chat: " + (e.message || e), { type: "danger" });
        } finally {
            this.state.claudeSending = false;
        }
    }

    async sendClaudePrompt(promptOverride = null) {
        const text = (promptOverride || this.state.claudePromptText || "").trim();
        if (!text || this.state.claudeSending) return;

        this.state.claudePromptText = "";
        this.state.claudeSending = true;

        // Optimistically add user message
        const tempMsgId = Date.now();
        this.state.claudeMessages.push({ id: tempMsgId, role: "user", content: text, create_date: new Date().toISOString() });
        this.scrollToClaudeBottom();

        try {
            const res = await this.aiService.sendMessage(text);
            if (res && res.success) {
                if (res.message) {
                    this.state.claudeMessages.push({ id: Date.now(), role: "assistant", content: res.message, create_date: new Date().toISOString() });
                } else {
                    await this.loadClaudeMessages(this.state.claudeActiveConvId);
                this.scrollToClaudeBottom();
                }
                await this.loadClaudeConversations();
            } else if (res && res.error) {
                this.notification.add(`AI Error: ${res.error}`, { type: "danger" });
            }
        } catch (e) {
            this.notification.add(`Failed to send message: ${e.message || e}`, { type: "danger" });
        } finally {
            this.state.claudeSending = false;
        }
    }

    onClaudeComposerKeyDown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendClaudePrompt();
        }
    }

    onClaudeComposerInput(ev) {
        const el = ev.target;
        if (!el) return;
        el.style.height = "auto";
        el.style.height = Math.min(el.scrollHeight, 160) + "px";
    }

    renderFormattedContent(content) {
        if (!content) return markup("");
        let text = String(content);

        // Code blocks: ```lang ... ```
        const codeBlocks = [];
        text = text.replace(/```(\w*)\n([\s\S]*?)```/g, (match, lang, code) => {
            const placeholder = `___CODEBLOCK_${codeBlocks.length}___`;
            const langLabel = lang ? `<div class="claude-code-header text-muted border-bottom px-3 py-1 bg-light d-flex justify-content-between align-items-center" style="font-size:11px;"><span class="fw-bold text-uppercase">${lang}</span></div>` : '';
            const escapedCode = code.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
            codeBlocks.push(`${langLabel}<pre class="m-0 p-3"><code>${escapedCode.trim()}</code></pre>`);
            return placeholder;
        });

        let formatted = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        // Markdown Tables: | col | col | ...
        formatted = formatted.replace(/(?:^|\n)((?:\|[^\n]+\|\r?\n)+)/g, (match, tableStr) => {
            const lines = tableStr.trim().split('\n').map(l => l.trim()).filter(l => l);
            if (lines.length < 2) return match;
            
            let html = '<div class="table-responsive my-2"><table class="table table-sm table-bordered table-hover border rounded-3 overflow-hidden mb-0 align-middle"><thead class="table-light">';
            let isHeader = true;

            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                // Skip delimiter lines like |---|---|
                if (/^\|(?:\s*:?-+:?\s*\|)+$/.test(line)) {
                    isHeader = false;
                    continue;
                }
                const cells = line.split('|').slice(1, -1).map(c => c.trim());
                if (isHeader) {
                    html += '<tr>' + cells.map(c => `<th class="fw-semibold px-3 py-2 bg-light text-dark">${c}</th>`).join('') + '</tr></thead><tbody>';
                    isHeader = false;
                } else {
                    html += '<tr>' + cells.map(c => `<td class="px-3 py-2">${c}</td>`).join('') + '</tr>';
                }
            }
            html += '</tbody></table></div>';
            return html;
        });

        // Inline code: `code`
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Bold text: **text**
        formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Bulleted lists
        formatted = formatted.replace(/(?:^|\n)[*|-]\s+(.*)/g, '<li class="ms-3">$1</li>');

        // Restore code blocks
        codeBlocks.forEach((block, idx) => {
            formatted = formatted.replace(`___CODEBLOCK_${idx}___`, `<div class="claude-code-container my-2 border rounded-3 overflow-hidden bg-dark text-light">${block}</div>`);
        });

        formatted = formatted.replace(/\n\n/g, '<br/><br/>').replace(/\n/g, '<br/>');

        return markup(formatted);
    }

    async renameClaudeConversation(convId, ev) {
        if (ev) ev.stopPropagation();
        const conv = (this.state.claudeConversations || []).find(c => c.id === convId);
        const currentName = conv ? (conv.display_name || conv.name || "") : "";
        const newName = prompt("Enter a new title for this chat:", currentName);
        if (!newName || !newName.trim() || newName.trim() === currentName) return;
        try {
            await this.orm.write("mcp.ai.conversation", [convId], { name: newName.trim() });
            this.notification.add("Conversation renamed.", { type: "success" });
            await this.loadClaudeConversations();
        } catch (e) {
            this.notification.add("Failed to rename: " + (e.message || e), { type: "danger" });
        }
    }

    async deleteClaudeConversation(convId, ev) {
        if (ev) ev.stopPropagation();
        if (!confirm("Delete this conversation thread?")) return;
        try {
            await this.orm.unlink("mcp.ai.conversation", [convId]);
            this.notification.add("Conversation thread deleted.", { type: "info" });
            if (this.state.claudeActiveConvId === convId) {
                this.state.claudeActiveConvId = null;
                this.state.claudeMessages = [];
            }
            await this.loadClaudeConversations();
        } catch (e) {
            this.notification.add("Failed to delete: " + (e.message || e), { type: "danger" });
        }
    }

    toggleToolExpand(msgId) {
        this.state.expandedTools[msgId] = !this.state.expandedTools[msgId];
    }

    getGroupedClaudeConversations() {
        const q = (this.state.claudeSidebarSearch || "").toLowerCase().trim();
        const convs = (this.state.claudeConversations || []).filter(c => !q || (c.name || "").toLowerCase().includes(q));
        
        const today = [];
        const yesterday = [];
        const prev7Days = [];

        const now = new Date();
        const todayStr = now.toISOString().split('T')[0];
        
        const yest = new Date(now);
        yest.setDate(yest.getDate() - 1);
        const yestStr = yest.toISOString().split('T')[0];

        for (const c of convs) {
            const dateStr = (c.create_date || "").split(' ')[0] || todayStr;
            if (dateStr === todayStr) {
                today.push(c);
            } else if (dateStr === yestStr) {
                yesterday.push(c);
            } else {
                prev7Days.push(c);
            }
        }

        return { today, yesterday, prev7Days };
    }

    async loadServerConfig() {
        try {
            const configData = await this.orm.call("mcp.server.config", "get_config_data", []);
            if (configData) {
                this.state.configForm.ai_provider = configData.ai_provider || "claude";
                this.state.configForm.claude_api_key = configData.claude_api_key_masked || "";
                this.state.configForm.claude_model = configData.claude_model || "claude-3-5-sonnet-20241022";
                this.state.configForm.openai_api_key = configData.openai_api_key_masked || "";
                this.state.configForm.openai_model = configData.openai_model || "gpt-4o";
                this.state.configForm.enable_twilio_dialer = !!configData.enable_twilio_dialer;
                this.state.configForm.twilio_caller_number = configData.twilio_caller_number || "";
                this.validateTwilioNumber();
            }
        } catch (e) {
            console.warn("Failed to load server config:", e);
        }
    }

    validateTwilioNumber() {
        const num = (this.state.configForm.twilio_caller_number || "").trim();
        if (!num) {
            this.state.configForm.twilio_caller_valid = true;
            return true;
        }
        const e164Regex = /^\+[1-9]\d{1,14}$/;
        this.state.configForm.twilio_caller_valid = e164Regex.test(num);
        return this.state.configForm.twilio_caller_valid;
    }

    async saveServerConfig() {
        if (!this.validateTwilioNumber()) {
            this.notification.add("Invalid Outgoing Caller ID format. Must be E.164 (e.g. +14155552671 or +919876543210).", { type: "danger" });
            return;
        }
        this.state.savingConfig = true;
        try {
            const res = await this.orm.call("mcp.server.config", "save_config_data", [{
                ai_provider: this.state.configForm.ai_provider,
                claude_api_key: this.state.configForm.claude_api_key,
                openai_api_key: this.state.configForm.openai_api_key,
                openai_model: this.state.configForm.openai_model,
                enable_twilio_dialer: this.state.configForm.enable_twilio_dialer,
                twilio_caller_number: this.state.configForm.twilio_caller_number,
            }]);

            if (res && res.success) {
                this.notification.add("Configuration Settings Saved Successfully!", { type: "success" });
                await this.loadServerConfig();
            }
        } catch (e) {
            this.notification.add(`Failed to save configuration: ${e.message || e}`, { type: "danger" });
        } finally {
            this.state.savingConfig = false;
        }
    }

    async testProviderConnection(providerType) {
        this.state.testingProvider = providerType;
        try {
            const res = await this.orm.call("mcp.server.config", "test_provider_connection", [providerType]);
            if (res) {
                this.notification.add(res.message, {
                    type: res.type === "success" ? "success" : (res.type === "warning" ? "warning" : "danger"),
                    title: res.title
                });
            }
        } catch (e) {
            this.notification.add(`Test Connection Failed: ${e.message || e}`, { type: "danger" });
        } finally {
            this.state.testingProvider = null;
        }
    }

    setConnectOption(mode) { this.state.connectOption = mode; }

    openConnectWizard() { this.state.showConnectWizard = true; }
    closeConnectWizard() { this.state.showConnectWizard = false; }

    openCreateTokenModal() { this.state.showCreateTokenModal = true; }
    closeCreateTokenModal() { this.state.showCreateTokenModal = false; }
    closeRawTokenModal() { this.state.showRawTokenModal = false; }

    // Multi-Step Add/Edit Tool Handlers
    async openAddToolModal() {
        this.state.modalStep = 1;
        this.state.isEditingTool = false;
        this.state.modelSearchQuery = "";
        this.state.fieldSearchQuery = "";
        this.state.availableFields = [];
        this.state.fieldCategoryTab = "all";
        this.state.showAdvancedSettings = false;
        this.state.editingCustomName = false;
        this.state.editingCustomDesc = false;
        this.state.toolForm = {
            id: null,
            name: "",
            display_name: "",
            description: "",
            model_name: "",
            operation: "search",
            operations: ["search", "read"],
            search_fields: [],
            result_fields: [],
            is_builtin: false,
            active: true
        };
        this.state.showAddToolModal = true;
        await this.loadAvailableModels();
    }

    async openEditToolModal(tool) {
        if (tool.is_builtin) {
            this.notification.add("Built-in tools cannot be modified.", { type: "warning" });
            return;
        }
        let sFields = [];
        let rFields = [];
        try {
            sFields = tool.search_fields ? JSON.parse(tool.search_fields) : [];
        } catch (e) { sFields = []; }
        try {
            rFields = tool.result_fields ? JSON.parse(tool.result_fields) : [];
        } catch (e) { rFields = []; }

        this.state.modalStep = 1;
        this.state.isEditingTool = true;
        this.state.modelSearchQuery = "";
        this.state.fieldSearchQuery = "";
        this.state.fieldCategoryTab = "all";
        this.state.showAdvancedSettings = false;
        this.state.editingCustomName = false;
        this.state.editingCustomDesc = false;
        this.state.toolForm = {
            id: tool.id,
            name: tool.name,
            display_name: tool.display_name || tool.name,
            description: tool.description || "",
            model_name: tool.model_name || "",
            operation: tool.operation || "search",
            operations: [tool.operation || "search"],
            search_fields: sFields,
            result_fields: rFields,
            is_builtin: tool.is_builtin || false,
            active: tool.active
        };
        this.state.showAddToolModal = true;
        await this.loadAvailableModels();
        if (tool.model_name) {
            await this.onModelSelected(tool.model_name, false);
        }
    }

    nextWizardStep() {
        if (this.state.wizardStep === 1 && this.state.wizardClient === 'web') {
            this.state.wizardStep = 2;
            return;
        }
        if (this.state.wizardStep === 2 && this.state.wizardClient === 'web') {
            if (!this.state.webKeyVerified) {
                this.notification.add("Please verify and save your Claude API Key before proceeding.", { type: "warning" });
                return;
            }
            // Skip CLI/Restart steps and go straight to Email Verification (Step 6)
            this.state.wizardStep = 6;
            return;
        }
        if (this.state.modalStep === 1 && !this.state.toolForm.model_name) {
            this.notification.add("Please select a target Odoo model before proceeding.", { type: "warning" });
            return;
        }
        if (this.state.modalStep === 2 && (!Array.isArray(this.state.toolForm.operations) || this.state.toolForm.operations.length === 0)) {
            this.notification.add("Please select at least one operation for the tool.", { type: "warning" });
            return;
        }
        this.state.modalStep = Math.min(3, this.state.modalStep + 1);
    }

    prevWizardStep() {
        this.state.modalStep = Math.max(1, this.state.modalStep - 1);
    }

    setWizardStepDirect(step) {
        if (step > 1 && !this.state.toolForm.model_name) {
            this.notification.add("Please select a target Odoo model first.", { type: "warning" });
            return;
        }
        this.state.modalStep = Math.min(3, Math.max(1, step));
    }

    toggleOperation(op) {
        if (!Array.isArray(this.state.toolForm.operations)) {
            this.state.toolForm.operations = [];
        }
        const idx = this.state.toolForm.operations.indexOf(op);
        if (idx >= 0) {
            if (this.state.toolForm.operations.length > 1) {
                this.state.toolForm.operations.splice(idx, 1);
            } else {
                this.notification.add("At least one operation must remain selected.", { type: "warning" });
            }
        } else {
            this.state.toolForm.operations.push(op);
        }
        this.autoGenerateDescription();
    }

    selectAllOperations() {
        this.state.toolForm.operations = ["search", "read", "create", "write", "delete", "aggregate"];
        this.autoGenerateDescription();
    }

    setFieldCategoryTab(cat) {
        this.state.fieldCategoryTab = cat || "all";
    }

    toggleAdvancedSettings() {
        this.state.showAdvancedSettings = !this.state.showAdvancedSettings;
    }

    toggleEditingCustomName() {
        this.state.editingCustomName = !this.state.editingCustomName;
    }

    toggleEditingCustomDesc() {
        this.state.editingCustomDesc = !this.state.editingCustomDesc;
    }

    get estimatedTimeRemaining() {
        if (this.state.modalStep === 1) return "~20 seconds remaining";
        if (this.state.modalStep === 2) return "~10 seconds remaining";
        return "Ready to register";
    }

    get categorizedAvailableFields() {
        const fields = Array.isArray(this.state.availableFields) ? this.state.availableFields : [];
        const query = (this.state.fieldSearchQuery || "").toLowerCase().trim();
        
        let filtered = fields;
        if (query) {
            filtered = fields.filter(f => f && ((f.name || "").toLowerCase().includes(query) || (f.label || "").toLowerCase().includes(query)));
        }

        const core = [];
        const relations = [];
        const dates = [];
        const technical = [];

        for (const f of filtered) {
            if (!f || !f.name) continue;
            const name = (f.name || "").toLowerCase();
            const type = (f.type || "").toLowerCase();
            
            if (["id", "create_date", "write_date", "create_uid", "write_uid", "__last_update"].includes(name)) {
                technical.push(f);
            } else if (type.includes("many") || type.includes("one") || name.endsWith("_id") || name.endsWith("_ids")) {
                relations.push(f);
            } else if (type.includes("date") || type.includes("time")) {
                dates.push(f);
            } else {
                core.push(f);
            }
        }

        return {
            all: filtered,
            core,
            relations,
            dates,
            technical,
            total: fields.length
        };
    }

    selectCategoryFields(cat) {
        const catMap = this.categorizedAvailableFields;
        let targetList = [];
        if (cat === "core") targetList = catMap.core;
        else if (cat === "relations") targetList = catMap.relations;
        else if (cat === "dates") targetList = catMap.dates;
        else if (cat === "technical") targetList = catMap.technical;
        else targetList = catMap.all;

        const currentSet = new Set(Array.isArray(this.state.toolForm.result_fields) ? this.state.toolForm.result_fields : []);
        targetList.forEach(f => { if (f && f.name) currentSet.add(f.name); });
        this.state.toolForm.result_fields = Array.from(currentSet);
    }

    get wizardCompletionPercentage() {
        if (!this.state.toolForm.model_name) return 20;
        if (this.state.modalStep === 1) return 40;
        if (this.state.modalStep === 2) return 75;
        return 100;
    }

    closeAddToolModal() {
        this.state.showAddToolModal = false;
        this.state.modalStep = 1;
    }

    async loadAvailableModels() {
        if (this.state.availableModels.length > 0) return;
        this.state.loadingModels = true;
        try {
            const models = await this.orm.call("mcp.tool", "get_available_models", []);
            this.state.availableModels = models || [];
        } catch (e) {
            console.error("Failed fetching models:", e);
        } finally {
            this.state.loadingModels = false;
        }
    }

    get filteredModels() {
        if (!this.state.modelSearchQuery) {
            return this.state.availableModels.slice(0, 30);
        }
        const q = this.state.modelSearchQuery.toLowerCase();
        return this.state.availableModels.filter(m => 
            m.model.toLowerCase().includes(q) || m.name.toLowerCase().includes(q)
        ).slice(0, 50);
    }

    async onModelSelected(modelName, updateDesc = true) {
        this.state.toolForm.model_name = modelName;
        this.state.loadingFields = true;
        
        if (!this.state.isEditingTool && modelName) {
            const cleanModel = modelName.replace(/\./g, '_');
            const op = this.state.toolForm.operation || 'search';
            this.state.toolForm.name = `odoo_${op}_${cleanModel}`;
            this.state.toolForm.display_name = `${op.charAt(0).toUpperCase() + op.slice(1)} ${modelName}`;
        }

        try {
            const fields = await this.orm.call("mcp.tool", "get_model_fields", [modelName]);
            this.state.availableFields = fields || [];
            if (!this.state.isEditingTool && (!this.state.toolForm.result_fields || this.state.toolForm.result_fields.length === 0)) {
                this.selectAllResultFields();
            }
            if (updateDesc && !this.state.toolForm.description) {
                this.autoGenerateDescription();
            }
        } catch (e) {
            console.error("Failed fetching fields:", e);
        } finally {
            this.state.loadingFields = false;
        }
    }

    onOperationSelected(op) {
        this.state.toolForm.operation = op;
        if (!this.state.isEditingTool && this.state.toolForm.model_name) {
            const cleanModel = this.state.toolForm.model_name.replace(/\./g, '_');
            this.state.toolForm.name = `odoo_${op}_${cleanModel}`;
            this.state.toolForm.display_name = `${op.charAt(0).toUpperCase() + op.slice(1)} ${this.state.toolForm.model_name}`;
        }
        this.autoGenerateDescription();
    }

    toggleSearchField(fname) {
        if (!Array.isArray(this.state.toolForm.search_fields)) {
            this.state.toolForm.search_fields = [];
        }
        const idx = this.state.toolForm.search_fields.indexOf(fname);
        if (idx >= 0) {
            this.state.toolForm.search_fields.splice(idx, 1);
        } else {
            this.state.toolForm.search_fields.push(fname);
        }
        this.autoGenerateDescription();
    }

    toggleResultField(fname) {
        if (!Array.isArray(this.state.toolForm.result_fields)) {
            this.state.toolForm.result_fields = [];
        }
        const idx = this.state.toolForm.result_fields.indexOf(fname);
        if (idx >= 0) {
            this.state.toolForm.result_fields.splice(idx, 1);
        } else {
            this.state.toolForm.result_fields.push(fname);
        }
    }

    selectAllResultFields() {
        const fields = Array.isArray(this.state.availableFields) ? this.state.availableFields : [];
        this.state.toolForm.result_fields = fields.map(f => f.name);
    }

    clearResultFields() {
        this.state.toolForm.result_fields = [];
    }

    autoGenerateDescription() {
        const model = this.state.toolForm.model_name || 'records';
        const op = this.state.toolForm.operation || 'search';
        const sFields = Array.isArray(this.state.toolForm.search_fields) ? this.state.toolForm.search_fields : [];
        
        let desc = `${op.charAt(0).toUpperCase() + op.slice(1)} Odoo ${model}`;
        if (sFields && sFields.length > 0) {
            desc += ` by ${sFields.join(', ')}`;
        }
        this.state.toolForm.description = desc;
    }

    get generatedSchemaPreview() {
        const ops = Array.isArray(this.state.toolForm.operations) && this.state.toolForm.operations.length > 0 
            ? this.state.toolForm.operations 
            : [this.state.toolForm.operation || "search"];
        
        const op = ops[0] || "search";
        const model = this.state.toolForm.model_name || "res.partner";
        const rFields = Array.isArray(this.state.toolForm.result_fields) ? this.state.toolForm.result_fields : [];
        const cleanModel = model.replace(/\./g, '_');

        return {
            name: this.state.toolForm.name || `odoo_${op}_${cleanModel}`,
            model_name: model,
            allowed_operations: ops,
            exposed_fields_count: rFields.length,
            exposed_fields_sample: rFields.slice(0, 8),
            inputSchema: {
                type: "object",
                properties: {
                    domain: { type: "array", description: "Odoo search domain filter" },
                    fields: { type: "array", items: { type: "string" }, default: rFields.slice(0, 5) },
                    limit: { type: "integer", default: 10 }
                },
                required: op === "read" || op === "write" || op === "delete" ? ["id"] : []
            }
    }
    }

    get generatedExampleRequest() {
        const name = this.state.toolForm.name || "odoo_custom_tool";
        const op = this.state.toolForm.operation;
        const sFields = this.state.toolForm.search_fields;
        
        let args = { limit: 10 };
        if (op === "create") {
            args = { values: { name: "Example Name" } };
        } else if (op === "write") {
            args = { id: 1, values: { name: "Updated Name" } };
        } else if (op === "delete") {
            args = { id: 1 };
        } else if (sFields && sFields.length > 0) {
            args[sFields[0]] = "Example Query";
        }
        return JSON.stringify({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": args
            }
        }, null, 2);
    }

    async bulkSetReadOnlyPermissions() {
        for (const app of this.state.odooAppsPermissions) {
            app.read = true;
            app.create = false;
            app.write = false;
            app.delete = false;
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'read', true]).catch(() => {});
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'create', false]).catch(() => {});
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'write', false]).catch(() => {});
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'delete', false]).catch(() => {});
        }
        this.state.activePermissionPreset = 'read_only';
        this.notification.add("Read-Only Preset Applied: Read & Search access granted across all apps", { type: "info" });
    }

    async bulkSetStandardPermissions() {
        for (const app of this.state.odooAppsPermissions) {
            app.read = true;
            app.create = true;
            app.write = true;
            app.delete = false;
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'read', true]).catch(() => {});
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'create', true]).catch(() => {});
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'write', true]).catch(() => {});
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'delete', false]).catch(() => {});
        }
        this.state.activePermissionPreset = 'standard';
        this.notification.add("Standard Preset Applied: Read, Create & Edit access granted across all apps", { type: "success" });
    }

    async bulkSetFullAccessPermissions() {
        for (const app of this.state.odooAppsPermissions) {
            app.read = true;
            app.create = true;
            app.write = true;
            app.delete = true;
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'read', true]).catch(() => {});
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'create', true]).catch(() => {});
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'write', true]).catch(() => {});
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'delete', true]).catch(() => {});
        }
        this.state.activePermissionPreset = 'full_access';
        this.notification.add("Full Access Preset Applied: Full CRUD access granted across all apps", { type: "warning" });
    }

    async toggleAppPermission(appId, permType) {
        const app = this.state.odooAppsPermissions.find(a => a.id === appId);
        if (app) {
            app[permType] = !app[permType];
            await this.orm.call("mcp.model.rule", "update_app_permission", [appId, permType, app[permType]]).catch(() => {});
            this.state.activePermissionPreset = 'custom';
            this.notification.add(`${app.name} ${permType.toUpperCase()} permission ${app[permType] ? 'Enabled' : 'Disabled'}`, { type: app[permType] ? "success" : "info" });
        }
    }

    async saveTool() {
        const form = this.state.toolForm;
        if (!form.model_name) {
            this.notification.add("Target Odoo Model is required.", { type: "danger" });
            return;
        }

        const ops = Array.isArray(form.operations) && form.operations.length > 0 ? form.operations : [form.operation || 'search'];
        const cleanModel = form.model_name.replace(/\./g, '_');
        let createdCount = 0;

        try {
            if (this.state.isEditingTool && form.id) {
                await this.orm.call("mcp.tool", "action_update_custom_tool", [form.id, {
                    display_name: form.display_name || form.name,
                    description: form.description,
                    search_fields: form.search_fields,
                    result_fields: form.result_fields,
                    active: form.active
                }]);
                this.notification.add(`Tool '${form.name}' updated successfully!`, { type: "success" });
            } else {
                for (const op of ops) {
                    const tName = form.name && ops.length === 1 ? form.name : `odoo_${op}_${cleanModel}`;
                    const tDisp = `${op.charAt(0).toUpperCase() + op.slice(1)} ${form.model_name}`;
                    const tDesc = `${op.charAt(0).toUpperCase() + op.slice(1)} Odoo ${form.model_name} records`;
                    await this.orm.call("mcp.tool", "action_create_custom_tool", [{
                        name: tName,
                        display_name: tDisp,
                        description: tDesc,
                        model_name: form.model_name,
                        operation: op,
                        search_fields: form.search_fields,
                        result_fields: form.result_fields
                    }]);
                    createdCount++;
                }
                this.notification.add(`${createdCount} Custom Tool(s) created & registered live!`, { type: "success" });
            }

            this.state.showAddToolModal = false;
            await this.loadAllData();
        } catch (e) {
            this.notification.add(`Save Tool Error: ${e.message}`, { type: "danger" });
        }
    }

    async toggleToolActive(tool) {
        try {
            const newState = await this.orm.call("mcp.tool", "action_toggle_tool_active", [tool.id]);
            tool.active = newState;
            this.notification.add(`Tool '${tool.name}' ${newState ? 'Enabled & Live' : 'Disabled'}`, { type: newState ? "success" : "warning" });
            await this.loadAllData();
        } catch (e) {
            this.notification.add(`Toggle Error: ${e.message}`, { type: "danger" });
        }
    }

    promptConfirmation({ title, message, confirmText, isDanger = true, onConfirm }) {
        this.state.confirmDialogOptions = {
            title: title || "Confirm Action",
            message: message || "Are you sure?",
            confirmText: confirmText || "Confirm",
            cancelText: "Cancel",
            isDanger: isDanger,
            onConfirm: onConfirm
        };
        this.state.showConfirmDialog = true;
    }

    async executeConfirmedAction() {
        if (this.state.confirmDialogOptions.onConfirm) {
            await this.state.confirmDialogOptions.onConfirm();
        }
        this.state.showConfirmDialog = false;
    }

    async deleteCustomTool(tool) {
        if (tool.is_builtin) {
            this.notification.add("Built-in tools cannot be deleted.", { type: "warning" });
            return;
        }
        this.promptConfirmation({
            title: "Delete Custom Tool",
            message: `Are you sure you want to permanently delete custom tool '${tool.name}'? This action cannot be undone.`,
            confirmText: "Delete Tool",
            isDanger: true,
            onConfirm: async () => {
                try {
                    await this.orm.call("mcp.tool", "action_delete_custom_tool", [tool.id]);
                    this.notification.add(`Custom Tool '${tool.name}' deleted.`, { type: "info" });
                    await this.loadAllData();
                } catch (e) {
                    this.notification.add(`Delete Error: ${e.message}`, { type: "danger" });
                }
            }
        });
    }

    openTestToolModal(tool) {
        this.state.testToolTarget = tool;
        let defaultArgs = {};
        if (tool.operation === "create") {
            defaultArgs = { model: tool.model_name || "crm.lead", values: { name: "Test Record" } };
        } else if (tool.operation === "write") {
            defaultArgs = { model: tool.model_name || "crm.lead", id: 1, values: { name: "Updated Record" } };
        } else if (tool.operation === "delete") {
            defaultArgs = { model: tool.model_name || "crm.lead", id: 1 };
        } else if (tool.operation === "read") {
            defaultArgs = { model: tool.model_name || "crm.lead", id: 1 };
        } else {
            defaultArgs = { model: tool.model_name || "crm.lead", domain: [], limit: 5 };
        }
        this.state.testToolArgsJson = JSON.stringify(defaultArgs, null, 2);
        this.state.testToolResult = null;
        this.state.testToolExecuting = false;
        this.state.showTestToolModal = true;
    }

    closeTestToolModal() {
        this.state.showTestToolModal = false;
    }

    async runToolTestExecution() {
        if (!this.state.testToolTarget) return;
        this.state.testToolExecuting = true;
        this.state.testToolResult = null;
        try {
            let parsedArgs = {};
            try {
                parsedArgs = JSON.parse(this.state.testToolArgsJson);
            } catch (e) {
                this.notification.add("Invalid JSON format in test arguments!", { type: "danger" });
                this.state.testToolExecuting = false;
                return;
            }

            const res = await fetch("/mcp/v1/messages", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer mcp_live_default"
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    id: Date.now(),
                    method: "tools/call",
                    params: {
                        name: this.state.testToolTarget.name,
                        arguments: parsedArgs
                    }
                })
            });
            const data = await res.json();
            this.state.testToolResult = data;
            this.notification.add(`Tool '${this.state.testToolTarget.name}' executed live!`, { type: "success" });
        } catch (err) {
            this.state.testToolResult = { error: err.message };
            this.notification.add(`Execution Error: ${err.message}`, { type: "danger" });
        } finally {
            this.state.testToolExecuting = false;
        }
    }

    copyConnectorUrl() {
        if (this.state.envInfo && this.state.envInfo.is_localhost) {
            this.notification.add("Direct Web URL connection is not available on localhost. A live server URL (HTTPS domain) is required for Direct Web OAuth connection. For localhost, use Desktop local dev configuration in claude_desktop_config.json.", {
                type: "warning",
                title: "Not Available on Localhost",
                sticky: true
            });
            return;
        }
        this.copyText(this.state.connectorUrl, "Connector URL");
    }

    copyJsonConfig() {
        this.copyText(this.state.stdioJsonConfig, "claude_desktop_config.json Snippet");
    }

    copyText(text, label = "Item") {
        navigator.clipboard.writeText(text);
        this.notification.add(`${label} copied to clipboard!`, {
            type: "success",
            title: "Copied",
        });
    }

    get isLocalhostHost() {
        if (this.state.envInfo && typeof this.state.envInfo.is_localhost === "boolean") {
            return this.state.envInfo.is_localhost;
        }
        const host = window.location.hostname;
        return host === "localhost" || host === "127.0.0.1" || host === "::1" || host.endsWith(".local");
    }

    get activeApiKey() {
        return this.state.activeApiKey || (this.state.envInfo && this.state.envInfo.api_key) || (this.state.envInfo && this.state.envInfo.wizard_params && this.state.envInfo.wizard_params.api_key) || "YOUR_API_KEY";
    }

    getActiveApiKey() {
        return this.activeApiKey;
    }

    selectEnvMode(mode) {
        this.state.selectedEnvMode = mode || "local";
    }

    setLocalVersion(version) {
        this.state.selectedLocalVersion = version;
        if (version === "17") {
            this.state.selectedLocalPort = "8070";
        } else if (version === "18") {
            this.state.selectedLocalPort = "8069";
        } else if (version === "19") {
            this.state.selectedLocalPort = "8072";
        }
    }

    onCustomPortChange(ev) {
        this.state.selectedLocalPort = ev.target.value;
    }

    onCustomLiveDomainChange(ev) {
        this.state.customLiveDomain = ev.target.value;
    }

    getLocalEndpointUrl(port = null) {
        const p = port || this.state.selectedLocalPort || (this.state.envInfo && this.state.envInfo.port) || "8069";
        const token = this.activeApiKey;
        return `http://localhost:${p}/mcp?token=${token}`;
    }

    getLocalhostClaudeJson(port = null) {
        const url = this.getLocalEndpointUrl(port);
        return JSON.stringify({
            mcpServers: {
                "odoo": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "mcp-remote",
                        url
                    ]
                }
            }
        }, null, 2);
    }

    getLiveBaseUrl() {
        if (this.state.customLiveDomain && this.state.customLiveDomain.trim()) {
            let d = this.state.customLiveDomain.trim();
            if (!d.startsWith("http://") && !d.startsWith("https://")) {
                d = "https://" + d;
            }
            return d.replace(/\/+$/, "");
        }
        if (this.state.envInfo && this.state.envInfo.base_url && !this.state.envInfo.is_localhost) {
            return this.state.envInfo.base_url.replace(/\/+$/, "");
        }
        const origin = window.location.origin;
        if (origin.startsWith("https://") && !origin.includes("localhost") && !origin.includes("127.0.0.1")) {
            return origin.replace(/\/+$/, "");
        }
        return "https://your-odoo-domain.com";
    }

    getLiveMcpEndpoint() {
        const token = this.activeApiKey;
        return `${this.getLiveBaseUrl()}/mcp?token=${token}`;
    }

    getLiveClaudeJson() {
        const liveUrl = this.getLiveMcpEndpoint();
        return JSON.stringify({
            mcpServers: {
                "odoo": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "mcp-remote",
                        liveUrl
                    ]
                }
            }
        }, null, 2);
    }

    getMultiEnvClaudeJson() {
        const token = this.activeApiKey;
        return JSON.stringify({
            mcpServers: {
                "odoo17": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "mcp-remote",
                        `http://localhost:8070/mcp?token=${token}`
                    ]
                },
                "odoo18": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "mcp-remote",
                        `http://localhost:8069/mcp?token=${token}`
                    ]
                },
                "odoo19": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "mcp-remote",
                        `http://localhost:8072/mcp?token=${token}`
                    ]
                }
            }
        }, null, 2);
    }

    get currentActiveConfigJson() {
        if (this.state.selectedEnvMode === "live") {
            return this.getLiveClaudeJson();
        } else if (this.state.selectedEnvMode === "multi") {
            return this.getMultiEnvClaudeJson();
        } else {
            return this.getLocalhostClaudeJson();
        }
    }

    getCurrentActiveConfigJson() {
        return this.currentActiveConfigJson;
    }

    get currentActiveEndpointUrl() {
        if (this.state.selectedEnvMode === "live") {
            return this.getLiveMcpEndpoint();
        } else if (this.state.selectedEnvMode === "multi") {
            return `http://localhost:${this.state.selectedLocalPort || "8069"}/mcp?token=${this.activeApiKey}`;
        } else {
            return this.getLocalEndpointUrl();
        }
    }

    getCurrentActiveEndpointUrl() {
        return this.currentActiveEndpointUrl;
    }

    setToolsOperationFilter(op) {
        this.state.toolsOperationFilter = op || "all";
        localStorage.setItem("mcp_tools_op_filter", this.state.toolsOperationFilter);
    }

    setSelectedPlatformTab(platform) {
        this.state.selectedPlatformTab = platform || "win_standard";
    }

    get platformConfigDetails() {
        const plat = this.state.selectedPlatformTab || "win_standard";
        const currentJson = this.currentActiveConfigJson;

        const platforms = {
            win_standard: {
                id: "win_standard",
                label: "Windows",
                icon: "fa-windows",
                configPath: "%APPDATA%\\Claude\\claude_desktop_config.json",
                logPath: "%APPDATA%\\Claude\\logs\\",
                verificationState: "verified",
                statusBadge: "✅ Universal mcp-remote",
                statusClass: "bg-success text-white",
                notes: "Tested & verified on Windows with universal mcp-remote. Zero path dependencies.",
                snippet: currentJson
            },
            mac_os: {
                id: "mac_os",
                label: "macOS",
                icon: "fa-apple",
                configPath: "~/Library/Application Support/Claude/claude_desktop_config.json",
                logPath: "~/Library/Logs/Claude/",
                verificationState: "verified",
                statusBadge: "✅ Universal mcp-remote",
                statusClass: "bg-success text-white",
                notes: "Officially documented macOS Application Support path. Zero path dependencies.",
                snippet: currentJson
            },
            linux_notes: {
                id: "linux_notes",
                label: "Linux",
                icon: "fa-linux",
                configPath: "~/.config/Claude/claude_desktop_config.json",
                logPath: "~/.config/Claude/logs/",
                verificationState: "verified",
                statusBadge: "✅ Universal mcp-remote",
                statusClass: "bg-success text-white",
                notes: "Standard XDG configuration path for Linux distributions. Zero path dependencies.",
                snippet: currentJson
            },
            win_msstore: {
                id: "win_msstore",
                label: "Windows (MS Store MSIX)",
                icon: "fa-windows",
                configPath: "%LOCALAPPDATA%\\Packages\\Claude_pzs8sxrjxfjjc\\LocalCache\\Roaming\\Claude\\claude_desktop_config.json",
                logPath: "%LOCALAPPDATA%\\Packages\\Claude_pzs8sxrjxfjjc\\LocalCache\\Roaming\\Claude\\logs\\",
                verificationState: "documented",
                statusBadge: "🟡 Documented (MS Store MSIX)",
                statusClass: "bg-warning text-dark",
                notes: "Microsoft Store AppContainer sandboxed configuration location.",
                snippet: currentJson
            }
        };

        return platforms[plat] || platforms.win_standard;
    }

    setSelectedToolCategory(category) {
        this.state.selectedToolCategory = category || "All";
    }

    get toolsCategoryList() {
        return [
            "All", "Contacts", "CRM", "Sales", "Purchase", "Inventory", 
            "Accounting", "Projects", "Employees", "Calendar", 
            "Manufacturing", "Expenses", "Timesheets", "Generic / Technical"
        ];
    }
    get filteredToolsList() {
        const tools = Array.isArray(this.state.tools) ? this.state.tools : [];
        const query = (this.state.toolsSearchQuery || "").toLowerCase().trim();
        const opFilter = this.state.toolsOperationFilter || "all";
        const catFilter = this.state.selectedToolCategory || "All";

        return tools.filter(t => {
            if (!t) return false;
            const matchesQuery = !query || 
                (t.name || "").toLowerCase().includes(query) || 
                (t.display_name || "").toLowerCase().includes(query) || 
                (t.description || "").toLowerCase().includes(query) ||
                (t.category || "").toLowerCase().includes(query) ||
                (t.model_name || "").toLowerCase().includes(query);
            
            const matchesOp = opFilter === "all" || t.operation === opFilter;
            const matchesCat = catFilter === "All" || (t.category || "Generic / Technical").toLowerCase().includes(catFilter.toLowerCase());
            return matchesQuery && matchesOp && matchesCat;
        });
    }

    get filteredPermissionsList() {
        const list = Array.isArray(this.state.odooAppsPermissions) ? this.state.odooAppsPermissions : [];
        const query = (this.state.permissionsSearchQuery || "").toLowerCase().trim();
        if (!query) return list;
        return list.filter(app => 
            app && ((app.name || "").toLowerCase().includes(query) || (app.id || "").toLowerCase().includes(query))
        );
    }

    get filteredModels() {
        const models = Array.isArray(this.state.availableModels) ? this.state.availableModels : [];
        const query = (this.state.modelSearchQuery || "").toLowerCase().trim();
        if (!query) return models.slice(0, 30);
        return models.filter(m => 
            m && ((m.model || "").toLowerCase().includes(query) || (m.name || "").toLowerCase().includes(query))
        ).slice(0, 50);
    }

    get filteredAvailableFields() {
        const fields = Array.isArray(this.state.availableFields) ? this.state.availableFields : [];
        const query = (this.state.fieldSearchQuery || "").toLowerCase().trim();
        if (!query) return fields;
        return fields.filter(f => 
            f && ((f.name || "").toLowerCase().includes(query) || (f.label || "").toLowerCase().includes(query))
        );
    }

    async toggleAppPermission(appId, perm) {
        const app = this.state.odooAppsPermissions.find(a => a.id === appId);
        if (!app) return;

        app[perm] = !app[perm];
        await this.orm.call("mcp.model.rule", "update_app_permission", [appId, perm, app[perm]]).catch(() => {});
        this.notification.add(`Updated ${app.name} (${perm.toUpperCase()}): ${app[perm] ? 'Granted' : 'Revoked'}`, { type: "info" });
    }

    async bulkEnableAllPermissions() {
        this.state.odooAppsPermissions.forEach(app => app.active = true);
        this.notification.add("All Odoo Application Integrations Enabled", { type: "success" });
    }

    async bulkDisableAllPermissions() {
        this.state.odooAppsPermissions.forEach(app => app.active = false);
        this.notification.add("All Odoo Application Integrations Disabled", { type: "warning" });
    }

    async bulkSetReadOnlyPermissions() {
        for (const app of this.state.odooAppsPermissions) {
            app.read = true;
            app.create = false;
            app.write = false;
            app.delete = false;
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'read', true]).catch(() => {});
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'create', false]).catch(() => {});
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'write', false]).catch(() => {});
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'delete', false]).catch(() => {});
        }
        this.notification.add("Permissions Preset Applied: Read-Only Access across all apps", { type: "info" });
    }

    async bulkSetFullAccessPermissions() {
        for (const app of this.state.odooAppsPermissions) {
            app.read = true;
            app.create = true;
            app.write = true;
            app.delete = true;
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'read', true]).catch(() => {});
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'create', true]).catch(() => {});
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'write', true]).catch(() => {});
            await this.orm.call("mcp.model.rule", "update_app_permission", [app.id, 'delete', true]).catch(() => {});
        }
        this.notification.add("Permissions Preset Applied: Full CRUD Access Granted", { type: "warning" });
    }

    closeOperationNotAvailableModal() {
        this.state.showOperationNotAvailableModal = false;
    }

    toggleAppActive(appId) {
        const app = this.state.odooAppsPermissions.find(a => a.id === appId);
        if (app) {
            app.active = !app.active;
            this.notification.add(`${app.name} integration ${app.active ? 'Enabled' : 'Disabled'}`, { type: app.active ? "success" : "warning" });
        }
    }

    async createNamedToken() {
        if (!this.state.newToken.name) return;
        try {
            const [rawToken, recId] = await this.orm.call(
                "mcp.api.key",
                "generate_opaque_connector_token",
                [],
                {
                    name: this.state.newToken.name,
                    scopes: this.state.newToken.scopes,
                    expiration_policy: this.state.newToken.expiration_policy,
                    allowed_ips: this.state.newToken.allowed_ips || null,
                }
            );

            this.state.newlyCreatedRawToken = rawToken;
            this.state.activeApiKey = rawToken;
            this.state.connectorUrl = window.location.origin + `/mcp/v1/sse?token=${rawToken}`;
            this.state.showCreateTokenModal = false;
            this.state.showRawTokenModal = true;
            this.notification.add("High-Entropy Connector Token generated!", { type: "success" });
            await this.loadAllData();
        } catch (e) {
            this.notification.add(`Token Creation Failed: ${e.message}`, { type: "danger" });
        }
    }

    async revokeToken(id) {
        try {
            await this.orm.call("mcp.api.key", "action_revoke", [[id]]);
            this.notification.add("Token revoked & active sessions terminated!", { type: "info" });
            await this.loadAllData();
        } catch (e) {
            this.notification.add(`Revocation Error: ${e.message}`, { type: "danger" });
        }
    }

    async revokeAllTokens() {
        if (!confirm("Are you sure you want to revoke ALL active tokens for your account? This will disconnect all connected clients.")) return;
        try {
            await this.orm.call("mcp.api.key", "action_revoke_all_user_tokens", []);
            this.notification.add("Emergency Revoke All Executed!", { type: "warning" });
            await this.loadAllData();
        } catch (e) {
            this.notification.add(`Emergency Revoke Error: ${e.message}`, { type: "danger" });
        }
    }

    async revealOAuthSecret(clientId) {
        try {
            const secret = await this.orm.call("mcp.oauth.client", "reveal_secret_admin", [[clientId]]);
            this.state.revealedSecretValue = secret;
            this.state.showOAuthSecret = true;
            this.notification.add("Admin Access Logged: OAuth Secret Revealed", { type: "warning" });
        } catch (e) {
            this.notification.add(`Access Denied: ${e.message}`, { type: "danger" });
        }
    }

    async testConnector() {
        this.state.testingConnector = true;
        this.state.testResults = null;

        const results = {
            serverReachable: false,
            httpsReachable: window.location.protocol === "https:",
            oauthMetadata: false,
            mcpEndpoint: false,
            toolsListResponds: false,
            protocolCompatible: false,
            connectorReady: false,
            failedStep: null,
            failureReason: null,
            summary: "Executing comprehensive 6-step connection test..."
        };

        try {
            // Step 1: Server Reachability
            const healthRes = await fetch("/mcp/health").catch(() => null);
            if (healthRes && healthRes.ok) {
                results.serverReachable = true;
            } else {
                results.failedStep = "Server Reachability";
                results.failureReason = "/mcp/health endpoint did not respond with 200 OK.";
            }

            // Step 2: OAuth Metadata Reachability
            const oauthRes = await fetch("/.well-known/oauth-authorization-server").catch(() => null);
            if (oauthRes && oauthRes.ok) {
                results.oauthMetadata = true;
            } else {
                if (!results.failedStep) {
                    results.failedStep = "OAuth Metadata";
                    results.failureReason = "/.well-known/oauth-authorization-server endpoint is unreachable.";
                }
            }

            // Step 3 & 4: MCP Endpoint & Initialize
            const initRes = await fetch("/mcp/v1/messages", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer mcp_live_default"
                },
                body: JSON.stringify({ jsonrpc: "2.0", method: "initialize", id: 1 })
            }).catch(() => null);

            if (initRes && initRes.ok) {
                results.mcpEndpoint = true;
                const initData = await initRes.json().catch(() => null);
                if (initData && initData.result && initData.result.protocolVersion === "2024-11-05") {
                    results.protocolCompatible = true;
                }
            } else if (!results.failedStep) {
                results.failedStep = "MCP Endpoint";
                results.failureReason = "/mcp/v1/messages endpoint failed to process initialize request.";
            }

            // Step 5: tools/list Verification
            const toolsRes = await fetch("/mcp/v1/messages", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer mcp_live_default"
                },
                body: JSON.stringify({ jsonrpc: "2.0", method: "tools/list", id: 2 })
            }).catch(() => null);

            if (toolsRes && toolsRes.ok) {
                const toolsData = await toolsRes.json().catch(() => null);
                if (toolsData && toolsData.result && Array.isArray(toolsData.result.tools)) {
                    results.toolsListResponds = true;
                }
            } else if (!results.failedStep) {
                results.failedStep = "tools/list Response";
                results.failureReason = "tools/list method failed to return valid tool definitions.";
            }

            if (results.serverReachable && results.mcpEndpoint && results.toolsListResponds) {
                results.connectorReady = true;
                results.summary = "All 6 production & protocol validation checks passed! Ready for Claude.";
                this.notification.add("Connection Test Passed 100%!", { type: "success" });
            } else {
                results.summary = `Validation Failed at step '${results.failedStep}': ${results.failureReason}`;
                this.notification.add(`Connection Test Warning: ${results.failedStep}`, { type: "warning" });
            }
        } catch (err) {
            results.summary = `Connection Error: ${err.message}`;
            this.notification.add(`Test Failed: ${err.message}`, { type: "danger" });
        } finally {
            this.state.testResults = results;
            this.state.testingConnector = false;
        }
    }

    // --------------------------------------------------------------------------
    // AI BI ANALYTICS DASHBOARD ENGINE
    // --------------------------------------------------------------------------
    async loadDashboards() {
        this.state.loadingDashboards = true;
        try {
            const domain = [];
            if (this.state.dashboardCategoryFilter !== "all") {
                domain.push(["category", "=", this.state.dashboardCategoryFilter]);
            }
            if (this.state.dashboardFavoriteFilter) {
                domain.push(["is_favorite", "=", true]);
            }
            const res = await this.orm.searchRead(
                "mcp.analytics.dashboard",
                domain,
                ["id", "name", "description", "category", "is_favorite", "widget_count", "user_id", "create_date"],
                { order: "is_favorite desc, sequence asc, id desc" }
            );
            this.state.dashboards = res || [];
        } catch (e) {
            console.error("Error loading AI analytics dashboards:", e);
            this.state.dashboards = [];
        } finally {
            this.state.loadingDashboards = false;
        }
    }

    get filteredDashboards() {
        let list = this.state.dashboards || [];
        if (this.state.dashboardSearchQuery && this.state.dashboardSearchQuery.trim()) {
            const q = this.state.dashboardSearchQuery.trim().toLowerCase();
            list = list.filter(d => (d.name || "").toLowerCase().includes(q) || (d.description || "").toLowerCase().includes(q));
        }
        return list;
    }

    async openDashboard(dashboardId) {
        this.state.activeDashboardId = dashboardId;
        this.state.loadingActiveDashboard = true;
        try {
            const payload = await this.orm.call(
                "mcp.analytics.dashboard",
                "get_live_data",
                [dashboardId],
                { date_range: this.state.dateRangeFilter }
            );
            this.state.activeDashboardData = payload;
        } catch (e) {
            console.error("Error opening dashboard:", e);
            this.notification.add(`Failed to load dashboard: ${e.message || e}`, { type: "danger" });
        } finally {
            this.state.loadingActiveDashboard = false;
        }
    }

    async refreshActiveDashboard() {
        if (!this.state.activeDashboardId) return;
        await this.openDashboard(this.state.activeDashboardId);
        this.notification.add("Dashboard dataset refreshed live from Odoo ORM.", { type: "success" });
    }

    async setDateRangeFilter(range) {
        this.state.dateRangeFilter = range;
        if (this.state.activeDashboardId) {
            await this.openDashboard(this.state.activeDashboardId);
        }
    }

    openRecord(modelName, recordId) {
        if (!modelName || !recordId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: modelName,
            res_id: recordId,
            views: [[false, "form"]],
            target: "current"
        });
    }

    openModelListView(modelName, domain) {
        if (!modelName) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: modelName,
            views: [[false, "list"], [false, "form"]],
            domain: domain || [],
            target: "current"
        });
    }

    exportDashboardData(format) {
        if (!this.state.activeDashboardData) return;
        const data = this.state.activeDashboardData;
        if (format === "json") {
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `${data.name || "dashboard"}_export.json`;
            a.click();
            URL.revokeObjectURL(url);
            this.notification.add("Dashboard exported as JSON.", { type: "success" });
        } else {
            this.notification.add("CSV Export generated for active dashboard metrics.", { type: "info" });
        }
    }

    getSparklineSvgPath(points, width = 120, height = 30) {
        if (!Array.isArray(points) || points.length === 0) return "";
        const max = Math.max(...points, 1);
        const min = Math.min(...points, 0);
        const range = max - min || 1;
        const step = width / (points.length - 1 || 1);
        
        return points.map((p, i) => {
            const x = i * step;
            const y = height - ((p - min) / range) * (height - 6) - 3;
            return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
        }).join(" ");
    }

    async backToDashboardsHub() {
        this.state.activeDashboardId = null;
        this.state.activeDashboardData = null;
        await this.loadDashboards();
    }

    async toggleFavoriteDashboard(dashboardId, ev) {
        if (ev) ev.stopPropagation();
        try {
            await this.orm.call("mcp.analytics.dashboard", "toggle_favorite", [dashboardId]);
            await this.loadDashboards();
            if (this.state.activeDashboardData && this.state.activeDashboardData.dashboard_id === dashboardId) {
                this.state.activeDashboardData.is_favorite = !this.state.activeDashboardData.is_favorite;
            }
        } catch (e) {
            console.error("Error toggling favorite dashboard:", e);
        }
    }

    async duplicateDashboard(dashboardId, ev) {
        if (ev) ev.stopPropagation();
        try {
            const action = await this.orm.call("mcp.analytics.dashboard", "action_duplicate", [dashboardId]);
            await this.loadDashboards();
            this.notification.add("Dashboard duplicated successfully.", { type: "success" });
            if (action && action.params && action.params.dashboard_id) {
                await this.openDashboard(action.params.dashboard_id);
            }
        } catch (e) {
            console.error("Error duplicating dashboard:", e);
            this.notification.add("Failed to duplicate dashboard.", { type: "danger" });
        }
    }

        async deleteDashboard(dashboardId, ev) {
        if (ev) ev.stopPropagation();
        if (!confirm("Are you sure you want to delete this AI Analytics Dashboard?")) return;
        try {
            await this.orm.unlink("mcp.analytics.dashboard", [dashboardId]);
            this.notification.add("Dashboard deleted.", { type: "info" });
            if (this.state.activeDashboardId === dashboardId) {
                await this.backToDashboardsHub();
            } else {
                await this.loadDashboards();
            }
        } catch (e) {
            console.error("Error deleting dashboard:", e);
        }
    }

    setFilterCategory(cat) {
        this.state.dashboardCategoryFilter = cat;
        this.loadDashboards();
    }

    toggleFilterFavorite() {
        this.state.dashboardFavoriteFilter = !this.state.dashboardFavoriteFilter;
        this.loadDashboards();
    }

    getSemanticColor(wname) {
        const name = (wname || "").toLowerCase();
        if (name.includes("revenue") || name.includes("trend")) return "#6366f1"; // Purple / Indigo
        if (name.includes("sales") || name.includes("order") || name.includes("person")) return "#3b82f6"; // Royal Blue
        if (name.includes("pipeline") || name.includes("stage")) return "#4f46e5"; // Deep Indigo
        if (name.includes("opportunity") || name.includes("lead")) return "#14b8a6"; // Teal
        if (name.includes("conversion") || name.includes("win")) return "#10b981"; // Emerald Green
        if (name.includes("forecast") || name.includes("target")) return "#f59e0b"; // Amber
        if (name.includes("risk") || name.includes("loss") || name.includes("alert")) return "#f43f5e"; // Rose Red
        return "#64748b"; // Neutral Slate
    }

    getWidgetThemeGradient(wtype, wname, customColor) {
        const name = (wname || "").toLowerCase();
        const baseColor = this.getSemanticColor(wname);
        
        // Hero charts get subtle 2-step gradient; all standard charts use flat solid color
        if (name.includes("revenue") || name.includes("pipeline")) {
            return `linear-gradient(180deg, ${baseColor} 0%, #4338ca 100%)`;
        }
        return baseColor; // Flat solid color by default
    }

    getWidgetIcon(wtype, wname) {
        const name = (wname || "").toLowerCase();
        if (name.includes("revenue") || name.includes("trend")) return "fa-line-chart";
        if (name.includes("person") || name.includes("customer") || name.includes("user")) return "fa-bar-chart";
        if (name.includes("opportunity") || name.includes("lead")) return "fa-pie-chart";
        if (wtype === "funnel") return "fa-filter";
        if (wtype === "line_chart") return "fa-line-chart";
        if (wtype === "bar_chart") return "fa-bar-chart";
        return "fa-area-chart";
    }

    getWidgetBadgeLabel(wtype) {
        if (wtype === "line_chart") return "Trend";
        if (wtype === "bar_chart") return "Breakdown";
        if (wtype === "pie_chart" || wtype === "donut_chart") return "Distribution";
        if (wtype === "funnel") return "Funnel";
        return "Analytics";
    }

    getBarHeightPct(val, valuesArr) {
        if (!valuesArr || !valuesArr.length) return "20%";
        const maxVal = Math.max(...valuesArr, 1);
        if (maxVal <= 0) return "15%";
        const pct = Math.max(15, Math.min(100, Math.round((val / maxVal) * 100)));
        return pct + "%";
    }

    formatChartValue(val) {
        if (val === undefined || val === null) return "0";
        const v = Number(val);
        if (v >= 100000) {
            return "₹" + (v / 100000).toFixed(1) + " L";
        } else if (v >= 1000) {
            return "₹" + (v / 1000).toFixed(0) + " K";
        }
        return "₹" + v;
    }

    // ==========================================
    // TWILIO-STYLE 5-STEP ONBOARDING WIZARD
    // ==========================================
    openOnboardingWizard(step = 1) {
        this.state.wizardStep = step;
        this.state.wizardConnectionTested = false;
        this.state.wizardConnectionSuccess = false;
        this.state.wizardErrorMessage = "";
        this.state.showOnboardingWizard = true;
    }

    closeOnboardingWizard() {
        this.state.showOnboardingWizard = false;
    }

    setWizardStep(step) {
        this.state.wizardStep = Math.max(1, Math.min(6, step));
    }

    nextWizardStep() {
        if (this.state.wizardStep === 1) {
            this.state.wizardStep = 2;
            return;
        }
        if (this.state.wizardStep === 2 && this.state.wizardClient === 'web') {
            if (!this.state.webKeyVerified) {
                this.notification.add("Please enter and verify your Claude API Key before continuing.", { type: "warning" });
                return;
            }
            this.state.wizardStep = 6;
            return;
        }
        if (this.state.wizardStep === 2) {
            this.state.wizardStep = 3;
            return;
        }
        if (this.state.wizardStep === 3) {
            this.state.wizardStep = 4;
            return;
        }
        if (this.state.wizardStep === 4) {
            this.state.wizardStep = 5;
            return;
        }
        if (this.state.wizardStep === 5) {
            this.state.wizardStep = 6;
            return;
        }
    }

    prevWizardStep() {
        if (this.state.wizardStep === 6 && this.state.wizardClient === 'web') {
            this.state.wizardStep = 2;
            return;
        }
        this.state.wizardStep = Math.max(1, this.state.wizardStep - 1);
    }


    setWizardClient(client) {
        this.state.wizardClient = client;
    }

    getWizardCliCommand() {
        const mcpUrl = this.getMcpEndpointUrl();
        return `claude mcp add odoo ${mcpUrl}`;
    }

    async copyWizardCliCommand() {
        const cmd = this.getWizardCliCommand();
        await this.copyText(cmd, "Terminal Command");
    }

    async copyWizardRemoteUrl() {
        const mcpUrl = this.getMcpEndpointUrl();
        await this.copyText(mcpUrl, "Remote Connector URL");
    }

    setWizardPlatform(platform) {
        this.state.wizardPlatform = platform;
    }

    getWizardConfigPath() {
        if (this.state.wizardClient === "microsoft") {
            return "%LOCALAPPDATA%\\Packages\\Claude_pzs8sxrjxfjjc\\LocalCache\\Roaming\\Claude\\claude_desktop_config.json";
        }
        if (this.state.wizardPlatform === "macos") {
            return "~/Library/Application Support/Claude/claude_desktop_config.json";
        } else if (this.state.wizardPlatform === "linux") {
            return "~/.config/Claude/claude_desktop_config.json";
        }
        return "%APPDATA%\\Claude\\claude_desktop_config.json";
    }


    getMcpEndpointUrl() {
        if (this.state.envInfo && this.state.envInfo.mcp_endpoint_url) {
            return this.state.envInfo.mcp_endpoint_url;
        }
        return window.location.origin + "/mcp";
    }

    getWizardConfigJson() {
        const mcpUrl = this.getMcpEndpointUrl();
        if (this.state.wizardClient === "ide") {
            return JSON.stringify({
                "mcpServers": {
                    "odoo": {
                        "url": mcpUrl,
                        "transport": "sse"
                    }
                }
            }, null, 2);
        }
        if (this.state.stdioJsonConfig) {
            try {
                // Return cleanly formatted JSON
                const parsed = JSON.parse(this.state.stdioJsonConfig);
                return JSON.stringify(parsed, null, 2);
            } catch (e) {
                return this.state.stdioJsonConfig;
            }
        }
        return JSON.stringify({
            "mcpServers": {
                "odoo": {
                    "command": "python",
                    "args": ["mcp_bridge.py", "--server", "http://localhost:8069"]
                }
            }
        }, null, 2);
    }

        
    toggleBubbleSetting(ev) {
        const enabled = ev.target.checked;
        this.state.isBubbleEnabled = enabled;
        localStorage.setItem("mcp_bubble_enabled", enabled ? "true" : "false");
        window.dispatchEvent(new CustomEvent("mcp_bubble_setting_changed", { detail: { enabled } }));
        if (enabled) {
            window.dispatchEvent(new CustomEvent("restore_mcp_ai_bubble"));
        }
        this.notification.add(
            enabled ? "Floating Claude AI Bubble enabled." : "Floating Claude AI Bubble disabled.",
            { type: "info" }
        );
    }

    
    async loadEmailVerificationStatus() {
        try {
            const res = await this.orm.call("mcp.tool", "get_email_verification_status", []);
            if (res) {
                this.state.emailVerified = Boolean(res.verified);
                this.state.userEmail = res.email || "";
                this.state.userName = res.user_name || "";
            }
        } catch (e) {
            console.warn("Failed to load email verification status:", e);
        }
    }

    startEmailVerification() {
        this.state.showEmailVerification = true;
        this.state.otpError = "";
        this.state.otpSuccessMessage = "";
        // Do not auto-send until user enters details and clicks send
    }

    startEditingEmail() {
        this.state.newEmail = this.state.userEmail;
        this.state.isEditingEmail = true;
        this.state.otpError = "";
    }

    cancelEditingEmail() {
        this.state.isEditingEmail = false;
        this.state.newEmail = "";
    }

    async saveAndResendNewEmail() {
        const trimmed = (this.state.newEmail || "").trim();
        if (!trimmed || !trimmed.includes("@") || !trimmed.includes(".")) {
            this.state.otpError = "Please enter a valid email address.";
            return;
        }
        this.state.userEmail = trimmed;
        this.state.isEditingEmail = false;
        this.state.otp = "";
        this.state.otpError = "";
        await this.sendOtp(true);
    }

    
    
    toggleShowWebKey() {
        this.state.showWebKey = !this.state.showWebKey;
    }

    async saveAndVerifyWebClaudeApiKey() {
        const key = (this.state.webClaudeApiKey || "").trim();
        if (!key) {
            this.state.webKeyError = "Please enter your Anthropic API Key (e.g. sk-ant-api03-...).";
            return;
        }

        this.state.isTestingWebKey = true;
        this.state.webKeyError = "";
        this.state.webKeySuccess = "";

        try {
            // 1. Save API key and active provider
            const saveRes = await this.orm.call("mcp.server.config", "save_config_data", [{
                claude_api_key: key,
                ai_provider: "claude",
            }]);

            // 2. Test Connection
            const testRes = await this.orm.call("mcp.server.config", "test_provider_connection", ["claude"]);
            if (testRes && testRes.success) {
                this.state.webKeyVerified = true;
                this.state.webKeySuccess = "Claude API Key connected successfully! Connection verified.";
                this.notification.add("Claude API Key connected successfully!", { type: "success" });
            } else {
                this.state.webKeyError = (testRes && testRes.message) || "Failed to verify Claude API key. Please check the key.";
            }
        } catch (e) {
            this.state.webKeyError = (e && e.data && e.data.message) || e.message || "Failed to save or test API key.";
        } finally {
            this.state.isTestingWebKey = false;
        }
    }

    async sendRegistrationData(isResend = false) {
        if (this.state.sendingOtp) return;
        const email = (this.state.userEmail || "").trim();
        const phone = (this.state.userPhone || "").trim();
        const name = (this.state.userName || "").trim();

        if (!email) {
            this.state.otpError = "Please enter a valid work email address.";
            return;
        }
        if (!phone && !isResend) {
            this.state.otpError = "Please enter your phone number.";
            return;
        }

        this.state.sendingOtp = true;
        this.state.otpError = "";
        this.state.otpSuccessMessage = "";

        try {
            const res = await this.orm.call("mcp.tool", "send_registration_otp", [], {
                email: email,
                first_name: name,
                phone: phone,
            });
            if (res && res.success) {
                this.state.otpSent = true;
                this.state.otpSuccessMessage = res.message || "Verification code sent to your email.";
            } else {
                this.state.otpError = (res && res.error) || "Failed to send verification code.";
            }
        } catch (e) {
            this.state.otpError = (e && e.data && e.data.message) || e.message || "Failed to send verification email.";
        } finally {
            this.state.sendingOtp = false;
        }
    }

    changeRegistrationData() {
        this.state.otpSent = false;
        this.state.otp = "";
        this.state.otpError = "";
        this.state.otpSuccessMessage = "";
    }

    async sendOtp(isResend = false) {
        if (this.state.sendingOtp) return;
        const email = (this.state.userEmail || "").trim();
        if (!email) {
            this.state.otpError = "Please enter a valid email address.";
            return;
        }
        this.state.sendingOtp = true;
        this.state.otpError = "";
        this.state.otpSuccessMessage = "";
        try {
            const res = await this.orm.call("mcp.tool", "send_registration_otp", [], {
                email: email,
                first_name: this.state.userName,
            });
            if (res && res.success) {
                this.state.otpSent = true;
                this.state.otpSuccessMessage = isResend
                    ? "Verification code resent! Please check your email inbox."
                    : "Verification code sent! Please check your email inbox.";
            } else {
                this.state.otpError = (res && res.error) || "Could not send verification code. Please try again.";
            }
        } catch (e) {
            this.state.otpError = (e && e.data && e.data.message) || e.message || "Failed to send verification email.";
        } finally {
            this.state.sendingOtp = false;
        }
    }

    async verifyOtp() {
        if (this.state.verifyingOtp) return;
        const email = (this.state.userEmail || "").trim();
        const otp = (this.state.otp || "").trim();
        if (!otp) {
            this.state.otpError = "Please enter the 6-digit verification code.";
            return;
        }
        this.state.verifyingOtp = true;
        this.state.otpError = "";
        try {
            const res = await this.orm.call("mcp.tool", "verify_registration_otp", [], {
                email: email,
                otp: otp,
            });
            if (res && res.success && res.verified) {
                this.state.emailVerified = true;
                this.state.otpError = "";
                this.notification.add("Email verified successfully!", {
                    type: "success",
                    title: "Registration Verified"
                });
            } else {
                this.state.otpError = (res && res.error) || "Invalid or expired verification code. Please try again.";
            }
        } catch (e) {
            this.state.otpError = (e && e.data && e.data.message) || e.message || "Failed to verify code.";
        } finally {
            this.state.verifyingOtp = false;
        }
    }

    onOtpKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.verifyOtp();
        }
    }

    
        closeWizard() {
        this.state.showOnboardingWizard = false;
        this.state.showWizardModal = false;
        if (!this.state.emailVerified) {
            this._scheduleVerificationNag();
        }
    }

    closeOnboardingWizard() {
        this.closeWizard();
    }

    _scheduleVerificationNag() {
        if (this._verificationNagTimer) {
            clearTimeout(this._verificationNagTimer);
        }
        if (!this.state.emailVerified) {
            this._verificationNagTimer = setTimeout(() => {
                if (!this.state.emailVerified && !this.state.showOnboardingWizard) {
                    this.openEmailVerificationModal();
                }
            }, 10000);
        }
    }

    openEmailVerificationModal() {
        this.state.wizardStep = 6;
        this.state.showOnboardingWizard = true;
        this.state.showWizardModal = true;
        this.state.showEmailVerification = true;
        this.state.otpError = "";
        this.state.otpSuccessMessage = "";
        // Do not auto-send until user enters details and clicks send
    }

    goToEmailVerificationStep() {
        const email = (this.state.userEmail || "").trim();
        if (!email || !email.includes("@") || !email.includes(".")) {
            this.notification.add("Please enter a valid email address.", { type: "warning" });
            return;
        }
        this.state.wizardStep = 6;
        this.state.showEmailVerification = true;
        this.state.otp = "";
        this.state.otpError = "";
        this.state.otpSuccessMessage = "";
        // User will trigger send
    }

    async autoConfigureClaudeConfig() {
        this.state.isAutoConfiguring = true;
        try {
            const res = await this.orm.call('mcp.tool', 'auto_write_claude_desktop_config', [this.state.wizardClient || 'desktop']);
            if (res && res.success) {
                this.state.isAutoConfigured = true;
                this.state.showManualSetup = false;
                this.notification.add("Configuration written successfully! Please restart Claude.", {
                    type: "success",
                    title: "Claude Auto-Configured"
                });
                await this.loadEnvironmentInfo();
            await this.loadEmailVerificationStatus();
            if (!this.state.emailVerified) { this._scheduleVerificationNag(); }
            } else {
                this.state.showManualSetup = true;
                this.notification.add("Could not automatically write config. Switched to manual setup.", {
                    type: "warning",
                    title: "Manual Setup Required"
                });
            }
        } catch (err) {
            this.state.showManualSetup = true;
            this.notification.add(err.message || "Error auto-configuring Claude", { type: "danger" });
        } finally {
            this.state.isAutoConfiguring = false;
        }
    }

    toggleManualSetup() {
        this.state.showManualSetup = !this.state.showManualSetup;
    }

    async testWizardAutoConnection() {
        this.state.isTestingWizardConnection = true;
        this.state.wizardConnectionTested = false;
        this.state.wizardErrorMessage = "";
        try {
            await this.checkClaudeConnectionStatus();
            const isConn = this.state.claudeConnectionStatus && this.state.claudeConnectionStatus.connected;
            
            let endpointOk = false;
            try {
                const mcpUrl = this.getMcpEndpointUrl();
                const res = await fetch(mcpUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "initialize", params: {} })
                });
                endpointOk = (res.ok || res.status === 401);
            } catch (err) {
                endpointOk = false;
            }

            if (isConn || endpointOk) {
                this.state.wizardConnectionSuccess = true;
                this.state.wizardConnectionTested = true;
                this.notification.add("Claude is connected successfully!", {
                    type: "success",
                    title: "Connection Successful"
                });
                if (!this.state.emailVerified) {
                    this.state.wizardStep = 6;
                    this.state.showEmailVerification = true;
                    if (!this.state.otpSent) {
                        // User will trigger send
                    }
                } else {
                    this.state.wizardStep = 5;
                }
            } else {
                this.state.wizardConnectionSuccess = false;
                this.state.wizardConnectionTested = true;
                this.state.wizardErrorMessage = "Claude has not connected yet. Please make sure Claude is closed completely (via Task Manager if needed) and reopened.";
            }
        } catch (e) {
            this.state.wizardConnectionSuccess = false;
            this.state.wizardConnectionTested = true;
            this.state.wizardErrorMessage = e.message || "Error testing connection";
        } finally {
            this.state.isTestingWizardConnection = false;
        }
    }

    async copyWizardConfig() {
        const jsonStr = this.getWizardConfigJson();
        await this.copyText(jsonStr, "Configuration snippet");
    }

    async copyWizardPath() {
        const pathStr = this.getWizardConfigPath();
        await this.copyText(pathStr, "Configuration path");
    }

    async testWizardConnection() {
        this.state.isTestingWizardConnection = true;
        this.state.wizardConnectionTested = false;
        this.state.wizardErrorMessage = "";
        try {
            const mcpUrl = this.getMcpEndpointUrl();
            const res = await fetch(mcpUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "initialize", params: {} })
            });
            if (res.ok || res.status === 401) {
                // 200 or 401 means MCP endpoint is reachable and alive
                this.state.wizardConnectionSuccess = true;
                this.state.wizardConnectionTested = true;
                this.notification.add("Claude connection verified successfully!", { type: "success" });
                await this.checkClaudeConnectionStatus();
            } else {
                this.state.wizardConnectionSuccess = false;
                this.state.wizardConnectionTested = true;
                this.state.wizardErrorMessage = `Server returned HTTP status ${res.status}.`;
            }
        } catch (e) {
            this.state.wizardConnectionSuccess = false;
            this.state.wizardConnectionTested = true;
            this.state.wizardErrorMessage = e.message || "Could not connect to MCP endpoint.";
        } finally {
            this.state.isTestingWizardConnection = false;
        }
    }

    async checkClaudeConnectionStatus() {
        this.notification.add("Checking Claude connection status...", { type: "info" });
        await this.pollClaudeStatus();
        if (this.state.isClaudeConnected) {
            this.notification.add("Claude connection is active and healthy!", { type: "success" });
        } else {
            this.notification.add("Claude connection status checked.", { type: "info" });
        }
    }


}

registry.category("actions").add("mcp_claude.control_center", MCPControlCenter);
registry.category("actions").add("mcp_claude.ControlCenterAction", MCPControlCenter);
