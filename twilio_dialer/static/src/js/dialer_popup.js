/** @odoo-module **/

import { Component, useExternalListener, useState, onWillStart, onWillUnmount, onWillUpdateProps } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { COUNTRY_CODES } from "./country_codes";
import { deviceManager } from "./device_manager";
import { AutoDialerRunner } from "./auto_dialer_runner";

const LAST_DIAL_STORAGE_KEY = "twilio_dialer.last_dial";

export class DialerPopup extends Component {
    static template = "twilio_dialer.DialerPopup";
    static components = { AutoDialerRunner };

    static props = {
        onClose: { type: Function, optional: false },
        phone: { type: String, optional: true },
        fromNumber: { type: String, optional: true },
        partnerId: { type: Number, optional: true },
        partnerName: { type: String, optional: true },
        requestId: { type: Number, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        const defaultCountry = COUNTRY_CODES.find((country) => country.code === "+91") || COUNTRY_CODES[0];
        const lastDial = this._loadLastDial();
        const savedCountry =
            this._findCountry(lastDial?.countryCode, lastDial?.countryLabel) || defaultCountry;

        this.state = useState({
            activeTab: "dialpad",
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
            autoDialerList: "",
            contactSearchQuery: "",
            contacts: [],
        });

        this._applyIncomingPhone(this.props.phone);
        useExternalListener(window, "keydown", this._onKeydown.bind(this));

        onWillStart(async () => {
            await this._loadConfiguredPhoneNumber();
            this._applyFromNumber(this.props.fromNumber || this.state.lastDialedFromNumber);
            await this._loadContacts();
            deviceManager.onIncomingCall((call, fromNumber, callSid) => {
                console.log("[Twilio JS DialerPopup] Incoming call received from:", fromNumber);
                this.state.activeTab = "dialpad";
                this.state.phoneNumber = fromNumber ? String(fromNumber).replace(/\D/g, "").slice(-10) : "";
            });
            try {
                await deviceManager.initialize(
                    this._onDeviceStatusChange.bind(this)
                );
            } catch (err) {
                console.error("[DialerPopup] Device initialization failed:", err);
                this.state.connectionStatus = "error";
            }
        });

        onWillUpdateProps((nextProps) => {
            if (nextProps.requestId !== this.props.requestId) {
                this._applyIncomingPhone(nextProps.phone);
                this._applyFromNumber(nextProps.fromNumber);
                this.state.activeTab = "dialpad";
            }
        });

        onWillUnmount(() => {
            deviceManager.destroy();
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
        console.log("[Twilio JS DialerPopup] User clicked Accept Call button");
        deviceManager.acceptCall();
    }

    onRejectCall() {
        console.log("[Twilio JS DialerPopup] User clicked Decline/Reject Call button");
        deviceManager.rejectCall();
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
        const digits = String(phone).replace(/\D/g, "");
        if (!digits) {
            return;
        }
        const matchedCountry = [...COUNTRY_CODES]
            .sort((a, b) => b.code.length - a.code.length)
            .find((country) => digits.startsWith(country.code.replace("+", "")));
        if (matchedCountry) {
            this.state.selectedCountry = matchedCountry;
            this.state.phoneNumber = digits
                .slice(matchedCountry.code.replace("+", "").length)
                .slice(0, 15);
        } else {
            this.state.phoneNumber = digits.slice(-10);
        }
    }

    _onDeviceStatusChange(status) {
        this.state.connectionStatus = status;
        if (status !== "connecting" && status !== "connected") {
            this.state.isMuted = false;
            this.state.dtmfBuffer = "";
        }
    }

    async _loadConfiguredPhoneNumber() {
        const result = await rpc("/twilio_dialer/phone_number");
        const preferredNumber =
            this.props.fromNumber ||
            this.state.selectedCaller?.number ||
            result.phone_number;
        const numbers = result.phone_numbers || [];
        const callers = [];
        const seen = new Set();

        for (const item of numbers) {
            const number = item.phone_number;
            if (!number || seen.has(number)) {
                continue;
            }
            seen.add(number);
            callers.push({
                number,
                friendlyName: item.friendly_name || "Twilio Number",
            });
        }

        if (result.phone_number && !seen.has(result.phone_number)) {
            callers.unshift({
                number: result.phone_number,
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

    async _loadContacts() {
        try {
            const partners = await this.orm.searchRead(
                "res.partner",
                ["|", ["phone", "!=", false], ["mobile", "!=", false]],
                ["name", "phone", "mobile"],
                { limit: 50, order: "name asc" }
            );
            this.state.contacts = (partners || []).map((partner) => {
                const phone = partner.mobile || partner.phone || "";
                const name = partner.name || "Unknown";
                const parts = name.trim().split(/\s+/);
                const initials = ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || "?";
                return {
                    id: partner.id,
                    name,
                    phone,
                    initials,
                };
            }).filter((contact) => contact.phone);
        } catch (error) {
            console.error("Failed to load contacts:", error);
            this.state.contacts = [];
        }
    }

    setActiveTab(tab) {
        this.state.activeTab = tab;
        this.closeAllDropdowns();
        if (tab === "contacts") {
            this.openContacts();
        }
    }

    openAutoCallingSetup() {
        this.action.doAction("twilio_dialer.action_twilio_auto_dialer_menu");
        if (this.props.onClose) {
            this.props.onClose();
        }
    }

    openContacts() {
        this.action.doAction("contacts.action_contacts");
        if (this.props.onClose) {
            this.props.onClose();
        }
    }

    onAutoDialerListInput(ev) {
        this.state.autoDialerList = ev.target.value;
    }

    onContactSearch(ev) {
        this.state.contactSearchQuery = ev.target.value;
    }

    get filteredContacts() {
        const query = this.state.contactSearchQuery.toLowerCase().trim();
        if (!query) {
            return this.state.contacts;
        }
        return this.state.contacts.filter(
            (contact) =>
                contact.name.toLowerCase().includes(query) ||
                contact.phone.toLowerCase().includes(query)
        );
    }

    dialContact(contact) {
        if (!contact?.phone) {
            return;
        }
        const digits = contact.phone.replace(/\D/g, "");
        const matchedCountry = COUNTRY_CODES.find((country) =>
            digits.startsWith(country.code.replace("+", ""))
        );
        if (matchedCountry) {
            this.state.selectedCountry = matchedCountry;
            this.state.phoneNumber = digits
                .slice(matchedCountry.code.replace("+", "").length)
                .slice(0, 10);
        } else {
            this.state.phoneNumber = digits.slice(-10);
        }
        this.setActiveTab("dialpad");
    }

    get countryCodes() {
        return COUNTRY_CODES;
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
            this.state.connectionStatus === "ready"
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
            this.state.connectionStatus === "ready"
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
            disconnected: "disconnected",
            error: "disconnected",
        };
        return map[this.state.connectionStatus] || "offline";
    }

    get statusLabel() {
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
        this.state.phoneNumber = ev.target.value.replace(/\D/g, "").slice(0, 15);
        ev.target.value = this.state.phoneNumber;
    }

    backspace() {
        this.state.phoneNumber = this.state.phoneNumber.slice(0, -1);
    }

    clearNumber() {
        this.state.phoneNumber = "";
    }

    selectCountry(country) {
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
        this.state.showCallerDropdown = !this.state.showCallerDropdown;
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

    onCall() {
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
        deviceManager.makeCall(fullNumber, {
            From: this.state.selectedCaller?.number,
            from_number: this.state.selectedCaller?.number,
        }, {
            partnerId: this.props.partnerId || this.dialerState.partnerId,
            queueLineId: this.dialerState.queueLineId || null,
        });
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
}
