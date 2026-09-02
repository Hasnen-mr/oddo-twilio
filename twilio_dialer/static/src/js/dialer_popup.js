/** @odoo-module **/

import { BillingDashboard } from "@twilio_dialer/js/billing";
import { NumberAllocationPanel } from "@twilio_dialer/js/number_allocation";

import { Component, onMounted, onWillStart, onWillUnmount, onWillUpdateProps, useExternalListener } from "@odoo/owl";
import * as owl from "@odoo/owl";
const useState = owl.useState || owl.proxy || ((obj) => obj);
import { AutoDialerRunner } from "@twilio_dialer/js/auto_dialer_runner";
import { COUNTRY_CODES } from "@twilio_dialer/js/country_codes";
import { deviceManager } from "@twilio_dialer/js/device_manager";
import { splitPhoneNumber } from "@twilio_dialer/js/phone_utils";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

const LAST_DIAL_STORAGE_KEY = "twilio_dialer.last_dial";
const CONTACT_PAGE_SIZE = 30;

export class DialerPopup extends Component {
    static template = "twilio_dialer.DialerPopup";
    static components = { AutoDialerRunner, NumberAllocationPanel, BillingDashboard };

    static props = {
        onClose: { type: Function, optional: false },
        phone: { type: String, optional: true },
        fromNumber: { type: String, optional: true },
        partnerId: { type: Number, optional: true },
        partnerName: { type: String, optional: true },
        autoDialerId: { type: Number, optional: true },
        requestId: { type: Number, optional: true },
    };

    setup() {
                this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        const defaultCountry = COUNTRY_CODES.find((country) => country.code === "+91") || COUNTRY_CODES[0];
        const lastDial = this._loadLastDial();
        const savedCountry =
            this._findCountry(lastDial?.countryCode, lastDial?.countryLabel) || defaultCountry;

        const hasAutoDialer = !!(this.props.autoDialerId);
        const initialTab = hasAutoDialer ? "auto_dialer" : "dialpad";

        this.state = useState({
            activeTab: initialTab,
            phoneNumber: "",
            lastDialedNumber: lastDial?.phoneNumber || "",
            lastDialedCountryCode: lastDial?.countryCode || savedCountry.code,
            lastDialedFromNumber: lastDial?.fromNumber || "",
            connectionStatus: "initializing",
            isMuted: false,
            dtmfBuffer: "",
            selectedCountry: savedCountry,
            countrySearchQuery: "",
            showCountryDropdown: false,
            showCallerDropdown: false,
            callerNumbers: [],
            selectedCaller: null,
            systemPhoneNumber: "",
            showIncomingKeypad: false,
            callDuration: 0,
            autoDialerList: "",
            contactSearchQuery: "",
            contacts: [],
            contactsOffset: 0,
            contactsHasMore: true,
            contactsLoading: false,
            dndEnabled: deviceManager.isDoNotDisturb,
            refreshingToken: false,
            showQuickDebugBanner: false,
            showQuickDebugModal: false,
            lastCallDuration: 0,
            debugChecking: false,
            settingsSubView: null,
            subViewLoading: false,
            aiSettings: {
                ai_provider: "openai",
                openai_api_key: "",
                openai_speech_model: "whisper-1",
                anthropic_api_key: "",
                gemini_api_key: "",
                deepgram_api_key: "",
            },
            callSettings: {
                enable_incoming: true,
                record_incoming: true,
                record_outgoing: true,
                enable_transcription: false,
                enable_smart_copy: false,
            },
            accountSettings: {
                account_sid: "",
                auth_token: "",
                phone_number: "",
            },
            showSecretKey: false,
        });

        this._callTimer = null;
        this._callStartTime = null;
        this._contactSearchTimer = null;
        this._debugBannerTimer = null;
        this._isOutboundCallInProgress = false;

        this._applyIncomingPhone(this.props.phone);
        useExternalListener(window, "keydown", this._onKeydown.bind(this));

        onWillStart(async () => {
            await this._loadConfiguredPhoneNumber();
            this._applyFromNumber(this.props.fromNumber || this.state.lastDialedFromNumber);
            
            // Connect UI status change listener to global deviceManager
            deviceManager.setStatusCallback((status) => this._onDeviceStatusChange(status));
            
            // Sync status if deviceManager is already ready or in another state
            if (deviceManager.status) {
                this._onDeviceStatusChange(deviceManager.status);
            }
        });

        onWillUpdateProps((nextProps) => {
            if (nextProps.requestId !== this.props.requestId) {
                this._applyIncomingPhone(nextProps.phone);
                this._applyFromNumber(nextProps.fromNumber);
                if (this.state.connectionStatus === "incoming") {
                    this.state.activeTab = "dialpad";
                } else if (nextProps.autoDialerId) {
                    this.state.activeTab = "auto_dialer";
                } else if (nextProps.phone && !nextProps.autoDialerId) {
                    this.state.activeTab = "dialpad";
                }
            }
            if (this.dialerState.openTroubleshooter) {
                this.dialerState.openTroubleshooter = false;
                setTimeout(() => this.openQuickDebugModal(), 100);
            }
        });

        onMounted(() => {
            if (this.dialerState.openTroubleshooter) {
                this.dialerState.openTroubleshooter = false;
                setTimeout(() => this.openQuickDebugModal(), 100);
            }
        });

        onWillUnmount(() => {
            clearTimeout(this._contactSearchTimer);
            // Unregister status callback when UI unmounts; DO NOT destroy global deviceManager
            deviceManager.setStatusCallback(null);
        });
    }

    get dialerState() {
        return this.env.services.twilio_dialer?.state || {};
    }

    async onNavigateQueue(actionName) {
        const dialerId = this.dialerState.autoDialerId;
        if (!dialerId) {
            return;
        }
        try {
            const result = await rpc("/twilio_dialer/auto_dialer/navigate", {
                dialer_id: dialerId,
                action_name: actionName,
            });
            if (result && result.success && result.queue_line_id) {
                this.dialerState.queueLineId = result.queue_line_id;
                this.dialerState.partnerName = result.partner_name;
                this.dialerState.queuePosition = result.queue_position;
                this.dialerState.queueAttempts = result.queue_attempts;
                this.dialerState.queueNotes = result.queue_notes;
                this.dialerState.queueStatus = result.queue_status;
                if (result.phone) {
                    this._applyIncomingPhone(result.phone);
                }
            }
        } catch (err) {
            console.error("Queue navigation failed:", err);
        }
    }

    onSkipQueueContact() {
        this.onNavigateQueue("skip");
    }

    onNextQueueContact() {
        this.onNavigateQueue("next");
    }

    onPrevQueueContact() {
        this.onNavigateQueue("prev");
    }

    get isIncoming() {
        return this.state.connectionStatus === "incoming";
    }

    onAcceptCall() {
        deviceManager.acceptCall();
    }

    onRejectCall() {
        deviceManager.rejectCall();
    }

    _onDeviceStatusChange(status) {
        this.state.connectionStatus = status;
        if (status === "incoming") {
            this.state.activeTab = "dialpad";
        }
    }

    _loadLastDial() {
        try {
            const raw = window.localStorage.getItem(LAST_DIAL_STORAGE_KEY);
            if (!raw) {
                return null;
            }
            const parsed = JSON.parse(raw);
            if (!parsed || typeof parsed !== "object") {
                return null;
            }
            return parsed;
        } catch (error) {
            console.warn("Failed to load last dial settings:", error);
            return null;
        }
    }

    _onKeydown(event) {
        if (event.key === "Escape") {
            event.preventDefault();
            this.closePopup();
            return;
        }

        const target = event.target;
        const isPhoneInput = target && target.classList && target.classList.contains("o_dialer_phone_input");
        const isOtherInput = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) && !isPhoneInput;

        if (isOtherInput) {
            return;
        }

        if (event.key === "Enter" || event.code === "NumpadEnter") {
            if (this.state.connectionStatus === "incoming" || this.isIncoming) {
                event.preventDefault();
                this.onAcceptCall();
                return;
            }
            if (this.state.activeTab === "dialpad" && this.canCall) {
                event.preventDefault();
                this.onCall();
                return;
            }
        }

        // Support laptop numpad direct dialing when dialpad tab is active
        if (this.state.activeTab === "dialpad" && !isPhoneInput) {
            const validDigits = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "#", "+"];
            if (validDigits.includes(event.key)) {
                event.preventDefault();
                this.appendDigit(event.key);
            } else if (event.key === "Backspace") {
                event.preventDefault();
                this.backspace();
            }
        }
    }

    onPhoneInputKeydown(event) {
        if (event.key === "Enter" || event.code === "NumpadEnter") {
            event.preventDefault();
            if (this.canCall) {
                this.onCall();
            }
        }
    }

    _saveLastDial({ country, phoneNumber, fromNumber }) {
        try {
            window.localStorage.setItem(
                LAST_DIAL_STORAGE_KEY,
                JSON.stringify({
                    countryCode: country?.code || "",
                    countryLabel: country?.label || "",
                    phoneNumber: phoneNumber || "",
                    fromNumber: fromNumber || "",
                    updatedAt: Date.now(),
                })
            );
        } catch (error) {
            console.warn("Failed to save last dial settings:", error);
        }
    }

    _findCountry(countryCode, countryLabel) {
        return (
            COUNTRY_CODES.find((country) => country.code === countryCode) ||
            COUNTRY_CODES.find((country) => country.label === countryLabel) ||
            false
        );
    }

    _applyIncomingPhone(phone) {
        if (!phone) {
            return;
        }
        const { country, nationalNumber } = splitPhoneNumber(phone);
        this.state.selectedCountry = country;
        this.state.phoneNumber = nationalNumber;
    }

        _onDeviceStatusChange(status) {
        this.state.connectionStatus = status;

        if (status === "connecting" || status === "connected") {
            if (!this._wasDialing) {
                this._wasDialing = true;
                this._callStartedAt = Date.now();
            }
        }

        if (status === "disconnected" || status === "error" || status === "ready") {
            if (this._wasDialing) {
                const elapsed = Math.floor((Date.now() - (this._callStartedAt || Date.now())) / 1000);
                const duration = Math.max(1, elapsed);
                if (duration <= 10) {
                    this.triggerQuickDebugBanner(duration);
                } else {
                    this._wasDialing = false;
                }
            }
        }

        if (status === "incoming") {
            this.state.activeTab = "dialpad";
            this.state.showIncomingKeypad = false;
            if (deviceManager.activeIncomingNumber) {
                this._applyIncomingPhone(deviceManager.activeIncomingNumber);
            }
        }
        if (status === "connected" || status === "connecting" || status === "incoming") {
            this._startTimer();
        } else {
            this._stopTimer();
            this.state.isMuted = false;
            this.state.dtmfBuffer = "";
            this.state.showIncomingKeypad = false;
        }
    }

    _startTimer() {
        if (!this._callTimer) {
            this._callStartTime = Date.now();
            this.state.callDuration = 0;
            this._callTimer = setInterval(() => {
                if (this._callStartTime) {
                    this.state.callDuration = Math.floor((Date.now() - this._callStartTime) / 1000);
                }
            }, 1000);
        }
    }

    _stopTimer() {
        if (this._callTimer) {
            clearInterval(this._callTimer);
            this._callTimer = null;
        }
        this._callStartTime = null;
        this.state.callDuration = 0;
    }

    get formattedCallDuration() {
        const dur = this.state.callDuration || 0;
        const mins = String(Math.floor(dur / 60)).padStart(2, "0");
        const secs = String(dur % 60).padStart(2, "0");
        return `${mins}:${secs}`;
    }

    get fullIncomingDisplayNumber() {
        if (this.props.phone) {
            return this.props.phone;
        }
        if (deviceManager.activeIncomingNumber) {
            return deviceManager.activeIncomingNumber;
        }
        if (this.state.phoneNumber) {
            return (this.state.selectedCountry?.code || "") + " " + this.state.phoneNumber;
        }
        return "Incoming Call";
    }

    get incomingToDisplayNumber() {
        const raw = this.props.fromNumber || this.dialerState.fromNumber || deviceManager.activeIncomingTo || "";
        if (raw && !raw.startsWith("client:") && !raw.startsWith("id_odoo_")) {
            return raw;
        }
        return this.state.selectedCaller?.number || this.state.systemPhoneNumber || "";
    }

    toggleIncomingKeypad() {
        this.state.showIncomingKeypad = !this.state.showIncomingKeypad;
    }

    backToIncomingView() {
        this.state.showIncomingKeypad = false;
    }

    async _loadConfiguredPhoneNumber() {
        const result = await rpc("/twilio_dialer/phone_number");
        this.state.systemPhoneNumber = result.phone_number || "";
        const preferredNumber =
            this.props.fromNumber ||
            this.state.selectedCaller?.number ||
            result.phone_number;
        const numbers = result.phone_numbers || [];
        deviceManager.setAllowedNumbers(numbers);
        const callers = [];
        const seen = new Set();

        for (const item of numbers) {
            const number = item.phone_number;
            if (!number || seen.has(number)) {
                continue;
            }
            seen.add(number);
            const isOutgoingCallerId = item.type === "outgoing_caller_id";
            callers.push({
                number,
                type: isOutgoingCallerId ? "outgoing_caller_id" : "incoming",
                friendlyName:
                    item.friendly_name ||
                    (isOutgoingCallerId ? "Outgoing Caller ID" : "Twilio Number"),
            });
        }

        if (result.phone_number && !seen.has(result.phone_number)) {
            callers.unshift({
                number: result.phone_number,
                type: "incoming",
                friendlyName: "Twilio Number",
            });
        }

        this.state.callerNumbers = callers;
        this.state.selectedCaller =
            callers.find((caller) => caller.number === preferredNumber) ||
            callers[0] ||
            null;
        if (this.props.fromNumber) {
            this._applyFromNumber(this.props.fromNumber);
        }
    }

    _applyFromNumber(fromNumber) {
        if (!fromNumber) {
            return;
        }
        const existing = this.state.callerNumbers.find(
            (caller) => caller.number === fromNumber
        );
        if (existing) {
            this.state.selectedCaller = existing;
            return;
        }
        const caller = {
            number: fromNumber,
            friendlyName: "Campaign Number",
        };
        this.state.callerNumbers = [...this.state.callerNumbers, caller];
        this.state.selectedCaller = caller;
    }

    _contactDomain() {
        const hasPhone = [["phone", "!=", false]];
        const query = (this.state.contactSearchQuery || "").trim();
        if (!query) {
            return hasPhone;
        }
        return [
            "&",
            ...hasPhone,
            "|",
            "|",
            "|",
            ["name", "ilike", query],
            ["phone", "ilike", query],
            ["parent_name", "ilike", query],
            ["email", "ilike", query],
        ];
    }

    _mapPartnerToContact(partner) {
        const phone = partner.phone || "";
        const name = partner.name || "Unknown";
        const company =
            partner.commercial_company_name ||
            partner.parent_name ||
            "";
        const companyLabel = company && company !== name ? company : "";
        const parts = name.trim().split(/\s+/);
        const initials = ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || "?";
        return {
            id: partner.id,
            name,
            company: companyLabel,
            phone,
            initials,
        };
    }

    async _loadContacts({ reset = false } = {}) {
        if (this.state.contactsLoading) {
            return;
        }
        if (!reset && !this.state.contactsHasMore) {
            return;
        }

        this.state.contactsLoading = true;
        try {
            const offset = reset ? 0 : this.state.contactsOffset;
            const partners = await this.orm.searchRead(
                "res.partner",
                this._contactDomain(),
                ["name", "phone", "parent_name", "commercial_company_name", "email"],
                { limit: CONTACT_PAGE_SIZE, offset, order: "name asc" }
            );
            const mapped = (partners || [])
                .map((partner) => this._mapPartnerToContact(partner))
                .filter((contact) => contact.phone);

            this.state.contacts = reset ? mapped : [...this.state.contacts, ...mapped];
            this.state.contactsOffset = offset + (partners || []).length;
            this.state.contactsHasMore = (partners || []).length >= CONTACT_PAGE_SIZE;
        } catch (error) {
            console.error("Failed to load contacts:", error);
            if (reset) {
                this.state.contacts = [];
                this.state.contactsOffset = 0;
                this.state.contactsHasMore = false;
            }
        } finally {
            this.state.contactsLoading = false;
        }
    }

        async setActiveTab(tab) {
        this.state.activeTab = tab;
        this.closeAllDropdowns();
        if (tab === "contacts") {
            this._loadContacts({ reset: true });
        } else if (tab === "settings") {
            this.state.settingsSubView = null;
            this.state.subViewLoading = true;
            try {
                const res = await rpc("/twilio_dialer/settings/get");
                if (res && res.success && res.call) {
                    Object.assign(this.state.callSettings, res.call);
                }
            } catch (err) {
                console.error("[Dialer] Failed to load call settings:", err);
            } finally {
                this.state.subViewLoading = false;
            }
        }
    }

    openAutoCallingSetup() {
        this.action.doAction("twilio_dialer.action_twilio_auto_dialer_menu");
        if (this.props.onClose) {
            this.props.onClose();
        }
    }

        openFullPageConfiguration(sectionId = "call") {
        const section = typeof sectionId === "string" ? sectionId : "call";
        // Close dialer popup when opening full page view
        if (this.props.onClose) {
            this.props.onClose();
        }
        const dialer = this.env.services.twilio_dialer;
        if (dialer) {
            dialer.close();
        }
        this.action.doAction("twilio_dialer.action_twilio_configuration_menu", {
            additionalContext: {
                default_active_section: section,
                active_section: section,
            },
        });
    }

    openConfiguration(sectionId = "call") {
        this.openFullPageConfiguration(sectionId);
    }

    get filteredContacts() {
        return this.state.contacts;
    }

    _applyContactPhone(contact) {
        if (!contact?.phone) {
            return false;
        }
        const { country, nationalNumber } = splitPhoneNumber(contact.phone);
        this.state.selectedCountry = country;
        this.state.phoneNumber = nationalNumber || contact.phone.replace(/\D/g, "").slice(-15);
        return !!this.state.phoneNumber;
    }

    dialContact(contact) {
        if (!this._applyContactPhone(contact) || this.state.dndEnabled || this.isCallActive) {
            return;
        }
        this.state.activeTab = "dialpad";
        this.closeAllDropdowns();
    }

    callContact(contact) {
        if (!this._applyContactPhone(contact) || this.state.dndEnabled || this.isCallActive) {
            return;
        }
        this.state.activeTab = "dialpad";
        this.closeAllDropdowns();
        // Place the call once the dial pad is active and caller ID is ready.
        Promise.resolve().then(() => {
            if (this.canCall) {
                this.onCall();
            }
        });
    }

    get countryCodes() {
        return COUNTRY_CODES;
    }

    get twilioCallerNumbers() {
        return (this.state.callerNumbers || []).filter(
            (caller) => caller.type !== "outgoing_caller_id"
        );
    }

    get outgoingCallerIds() {
        return (this.state.callerNumbers || []).filter(
            (caller) => caller.type === "outgoing_caller_id"
        );
    }

    get filteredCountries() {
        const query = this.state.countrySearchQuery.toLowerCase().trim();
        if (!query) {
            return COUNTRY_CODES;
        }
        return COUNTRY_CODES.filter(
            (c) =>
                c.name.toLowerCase().includes(query) ||
                c.code.includes(query) ||
                c.label.toLowerCase().includes(query)
        );
    }

    get dialPadKeys() {
        return [
            { digit: "1", letters: "" },
            { digit: "2", letters: "ABC" },
            { digit: "3", letters: "DEF" },
            { digit: "4", letters: "GHI" },
            { digit: "5", letters: "JKL" },
            { digit: "6", letters: "MNO" },
            { digit: "7", letters: "PQRS" },
            { digit: "8", letters: "TUV" },
            { digit: "9", letters: "WXYZ" },
            { digit: "*", letters: "" },
            { digit: "0", letters: "+" },
            { digit: "#", letters: "" },
        ];
    }

    get displayPhoneNumber() {
        const num = this.state.phoneNumber;
        if (!num) {
            return "";
        }
        if (num.length <= 3) {
            return num;
        }
        if (num.length <= 6) {
            return `${num.slice(0, 3)} ${num.slice(3)}`;
        }
        return `${num.slice(0, 3)} ${num.slice(3, 6)} ${num.slice(6)}`;
    }

    get formattedCallerDisplay() {
        const caller = this.state.selectedCaller;
        if (!caller) {
            return "Select number";
        }
        if (caller.friendlyName) {
            return `${caller.friendlyName} (${caller.number})`;
        }
        return caller.number;
    }

    get canRedial() {
        return (
            !!this.state.lastDialedNumber &&
            this.state.lastDialedNumber.length >= 5 &&
            !this.isCallActive &&
            this.state.connectionStatus === "ready" &&
            !this.state.dndEnabled
        );
    }

    get isCallActive() {
        return this.state.connectionStatus === "connecting" || this.state.connectionStatus === "connected";
    }

    get canCall() {
        return (
            this.state.phoneNumber.length >= 5 &&
            this.state.phoneNumber.length <= 15 &&
            !!this.state.selectedCaller &&
            !this.isCallActive &&
            this.state.connectionStatus === "ready" &&
            !this.state.dndEnabled
        );
    }

    get isTokenBusy() {
        return (
            this.state.refreshingToken ||
            ["initializing", "fetching_token", "registering"].includes(this.state.connectionStatus)
        );
    }

    get showTokenOverlay() {
        if (this.isCallActive || this.isIncoming || this.state.dndEnabled) {
            return false;
        }
        return (
            this.isTokenBusy ||
            this.state.connectionStatus === "error" ||
            this.state.connectionStatus === "disconnected"
        );
    }

    get statusClass() {
        const map = {
            initializing: "connecting",
            fetching_token: "connecting",
            registering: "connecting",
            incoming: "connecting",
            connecting: "connecting",
            connected: "ready",
            ready: "ready",
            disconnected: this.state.dndEnabled ? "ready" : "disconnected",
            error: "disconnected",
        };
        return map[this.state.connectionStatus] || "offline";
    }

    get statusLabel() {
        if (this.state.dndEnabled) {
            return "Do Not Disturb";
        }
        const labels = {
            initializing: "Initializing...",
            fetching_token: "Fetching Token...",
            registering: "Registering...",
            incoming: "Incoming Call...",
            connecting: "Connecting...",
            connected: "Connected",
            ready: "Connected",
            disconnected: "Disconnected",
            error: "Failed",
        };
        return labels[this.state.connectionStatus] || "Connected";
    }

    appendDigit(digit) {
        if (this.state.dndEnabled && !this.isCallActive && !this.isIncoming) {
            return;
        }
        if (this.isCallActive) {
            const sent = deviceManager.sendDigits(digit);
            if (sent) {
                this.state.dtmfBuffer = `${this.state.dtmfBuffer || ""}${digit}`.slice(-24);
            }
            return;
        }
        if (digit === "*" || digit === "#") {
            return;
        }
        if (this.state.phoneNumber.length >= 15) {
            return;
        }
        this.state.phoneNumber += digit;
    }

    onToggleMute() {
        if (!this.isCallActive) {
            return;
        }
        this.state.isMuted = deviceManager.toggleMute();
    }

    onHangUp() {
        deviceManager.disconnect();
        this.state.isMuted = false;
        this.state.dtmfBuffer = "";
    }

    onInput(ev) {
        if (this.isCallActive || this.isIncoming || this.state.dndEnabled) {
            ev.target.value = this.state.phoneNumber;
            return;
        }
        this.state.phoneNumber = ev.target.value.replace(/\D/g, "").slice(0, 15);
        ev.target.value = this.state.phoneNumber;
    }

    backspace() {
        if (this.isCallActive || this.isIncoming || this.state.dndEnabled) {
            return;
        }
        this.state.phoneNumber = this.state.phoneNumber.slice(0, -1);
    }

    clearNumber() {
        if (this.isCallActive || this.isIncoming || this.state.dndEnabled) {
            return;
        }
        this.state.phoneNumber = "";
    }

    selectCountry(country) {
        if (this.isCallActive || this.isIncoming || this.state.dndEnabled) {
            return;
        }
        this.state.selectedCountry = country;
        this.state.showCountryDropdown = false;
        this.state.countrySearchQuery = "";
        this._saveLastDial({
            country,
            phoneNumber: this.state.lastDialedNumber || this.state.phoneNumber,
            fromNumber: this.state.selectedCaller?.number || this.state.lastDialedFromNumber,
        });
    }

    toggleCountryDropdown() {
        if (this.isCallActive || this.isIncoming || this.state.dndEnabled) {
            return;
        }
        this.state.showCountryDropdown = !this.state.showCountryDropdown;
        this.state.showCallerDropdown = false;
        if (this.state.showCountryDropdown) {
            this.state.countrySearchQuery = "";
        }
    }

    onCountrySearch(ev) {
        this.state.countrySearchQuery = ev.target.value;
    }

    selectCaller(caller) {
        this.state.selectedCaller = caller;
        this.state.showCallerDropdown = false;
    }

    toggleCallerDropdown() {
        if (this.state.dndEnabled) {
            return;
        }
        this.state.showCallerDropdown = !this.state.showCallerDropdown;
        if (this.state.showCallerDropdown) {
            this._loadConfiguredPhoneNumber();
        }
        this.state.showCountryDropdown = false;
    }

    closeAllDropdowns() {
        this.state.showCountryDropdown = false;
        this.state.showCallerDropdown = false;
        this.state.countrySearchQuery = "";
    }

    closeCountryDropdown() {
        this.state.showCountryDropdown = false;
        this.state.countrySearchQuery = "";
    }

    closeCallerDropdown() {
        this.state.showCallerDropdown = false;
    }

    closePopup() {
        this.props.onClose();
    }

        async onCall() {
        if (!this.canCall) {
            return;
        }
        const fullNumber = this.state.selectedCountry.code + this.state.phoneNumber;
        this.state.lastDialedNumber = this.state.phoneNumber;
        this.state.lastDialedCountryCode = this.state.selectedCountry.code;
        this.state.lastDialedFromNumber = this.state.selectedCaller?.number || "";
        this._saveLastDial({
            country: this.state.selectedCountry,
            phoneNumber: this.state.phoneNumber,
            fromNumber: this.state.selectedCaller?.number || "",
        });

        this._callStartedAt = Date.now();
        this._wasDialing = true;

        try {
            const res = await deviceManager.makeCall(fullNumber, {
                From: this.state.selectedCaller?.number,
                from_number: this.state.selectedCaller?.number,
            }, {
                partnerId: this.props.partnerId || this.dialerState.partnerId,
                resModel: this.dialerState.resModel || null,
                resId: this.dialerState.resId || null,
                queueLineId: this.dialerState.queueLineId || null,
            });
            if (res === false) {
                this.triggerQuickDebugBanner(1);
            }
        } catch (err) {
            console.error("makeCall threw error:", err);
            this.triggerQuickDebugBanner(1);
        }
    }

    onRedial() {
        if (!this.canRedial) {
            return;
        }
        const lastDial = this._loadLastDial() || {};
        const country =
            this._findCountry(
                this.state.lastDialedCountryCode || lastDial.countryCode,
                lastDial.countryLabel
            ) || this.state.selectedCountry;
        const phoneNumber = this.state.lastDialedNumber || lastDial.phoneNumber || "";
        const fromNumber =
            this.state.lastDialedFromNumber ||
            lastDial.fromNumber ||
            this.state.selectedCaller?.number ||
            "";

        this.state.selectedCountry = country;
        this.state.phoneNumber = phoneNumber;
        this.state.activeTab = "dialpad";
        if (fromNumber) {
            this._applyFromNumber(fromNumber);
        }

        if (!this.canCall) {
            return;
        }
        this.onCall();
    }

    async onToggleDnd() {
        if (this.isCallActive || this.isIncoming || this.state.refreshingToken) {
            return;
        }
        const next = !this.state.dndEnabled;
        this.state.dndEnabled = next;
        if (next) {
            this.closeAllDropdowns();
        }
        try {
            await deviceManager.setDoNotDisturb(next);
            this.state.dndEnabled = deviceManager.isDoNotDisturb;
            this.state.connectionStatus = deviceManager.status;
        } catch (err) {
            console.error("[DialerPopup] DND toggle failed:", err);
            this.state.dndEnabled = deviceManager.isDoNotDisturb;
        }
    }

    async onRefreshToken() {
        if (this.state.refreshingToken || this.isCallActive || this.isIncoming) {
            return;
        }
        this.state.refreshingToken = true;
        this.state.dndEnabled = false;
        try {
            const ready = await deviceManager.ensureRegistered({
                regenerate: true,
                timeoutMs: 45000,
            });
            this.state.connectionStatus = deviceManager.status;
            if (!ready) {
                this.state.connectionStatus = "error";
            }
        } catch (err) {
            console.error("[DialerPopup] Token refresh failed:", err);
            this.state.connectionStatus = "error";
        } finally {
            this.state.refreshingToken = false;
        }
    }

        openQuickDebugModal() {
        this.state.showQuickDebugBanner = false;
        this.state.showQuickDebugModal = true;
        this.state.debugStep = 0;

        clearTimeout(this._debugStepTimer);
        const advance = (s) => {
            if (!this.state.showQuickDebugModal) return;
            this.state.debugStep = s;
            if (s < 5) {
                this._debugStepTimer = setTimeout(() => advance(s + 1), 350);
            }
        };
        advance(1);
    }

    closeQuickDebugModal() {
        this.state.showQuickDebugModal = false;
        clearTimeout(this._debugStepTimer);
    }

    get isUSCanadaCall() {
        const num = this.state.phoneNumber || this.state.lastDialedNumber || "";
        const code = this.state.selectedCountry?.code || "";
        return code === "+1" || num.startsWith("+1") || num.startsWith("1");
    }

    openHelpSupport() {
        this.closeQuickDebugModal();
        try {
            this.action.doAction("twilio_dialer.action_twilio_help");
        } catch (e) {
            this.action.doAction("twilio_dialer.action_twilio_contact_us", {
                additionalContext: { twilio_about_section: "help" },
            });
        }
    }

            triggerQuickDebugBanner(duration = 1) {
        this._wasDialing = false;
        this.state.lastCallDuration = duration;
        this.state.showQuickDebugBanner = true;
        clearTimeout(this._debugBannerTimer);
        this._debugBannerTimer = setTimeout(() => {
            this.state.showQuickDebugBanner = false;
        }, 10000);

        setTimeout(() => {
            const bodyEl = document.querySelector(".o_dialer_body") || document.querySelector(".o_dialer_popup") || document.querySelector(".o_dialer_tab_panel");
            if (bodyEl) {
                bodyEl.scrollTop = bodyEl.scrollHeight;
            }
        }, 50);
    }
    async openSettingsSubView(viewName) {
        this.state.settingsSubView = viewName;
        this.state.showSecretKey = false;
        if (viewName === "ai" || viewName === "call" || viewName === "account") {
            this.state.subViewLoading = true;
            try {
                const res = await rpc("/twilio_dialer/settings/get");
                if (res && res.success) {
                    if (res.ai) Object.assign(this.state.aiSettings, res.ai);
                    if (res.call) Object.assign(this.state.callSettings, res.call);
                    if (res.account) Object.assign(this.state.accountSettings, res.account);
                }
            } catch (err) {
                console.error("[Dialer] Failed to load settings:", err);
            } finally {
                this.state.subViewLoading = false;
            }
        }
    }

    closeSettingsSubView() {
        this.state.settingsSubView = null;
    }

    

    async saveSubViewSettings(section) {
        this.state.subViewLoading = true;
        try {
            let payload = {};
            if (section === "ai") payload = this.state.aiSettings;
            else if (section === "call") payload = this.state.callSettings;
            else if (section === "account") payload = this.state.accountSettings;

            const res = await rpc("/twilio_dialer/settings/save", {
                section: section,
                values: payload,
            });
            if (res && res.success) {
                this.notification.add(_t("Settings saved successfully!"), { type: "success" });
            } else {
                this.notification.add(res?.message || _t("Failed to save settings"), { type: "danger" });
            }
        } catch (err) {
            console.error("[Dialer] Save settings error:", err);
            this.notification.add(_t("Error saving settings"), { type: "danger" });
        } finally {
            this.state.subViewLoading = false;
        }
    }

    openFullPageBilling() {
        if (this.props.onClose) {
            this.props.onClose();
        }
        const dialer = this.env.services.twilio_dialer;
        if (dialer) {
            dialer.close();
        }
        try {
            this.action.doAction("twilio_dialer.action_twilio_billing");
        } catch (e) {
            this.action.doAction("twilio_dialer.action_twilio_billing");
        }
    }

    toggleSecretKeyVisibility() {
        this.state.showSecretKey = !this.state.showSecretKey;
    }

}
