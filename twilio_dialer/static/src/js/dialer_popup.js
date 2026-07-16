/** @odoo-module **/

import { Component, useState, onWillStart, onWillUnmount, onWillUpdateProps } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { COUNTRY_CODES } from "./country_codes";
import { deviceManager } from "./device_manager";

export class DialerPopup extends Component {
    static template = "twilio_dialer.DialerPopup";

    static props = {
        onClose: { type: Function, optional: false },
        phone: { type: String, optional: true },
        requestId: { type: Number, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        const defaultCountry = COUNTRY_CODES.find((country) => country.code === "+91") || COUNTRY_CODES[0];

        this.state = useState({
            activeTab: "dialpad",
            phoneNumber: "",
            lastDialedNumber: "",
            connectionStatus: "initializing",
            selectedCountry: defaultCountry,
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

        onWillStart(async () => {
            await this._loadConfiguredPhoneNumber();
            await this._loadContacts();
            await deviceManager.initialize(
                this._onDeviceStatusChange.bind(this)
            );
        });

        onWillUpdateProps((nextProps) => {
            if (nextProps.requestId !== this.props.requestId) {
                this._applyIncomingPhone(nextProps.phone);
                this.state.activeTab = "dialpad";
            }
        });

        onWillUnmount(() => {
            deviceManager.destroy();
        });
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
    }

    async _loadConfiguredPhoneNumber() {
        const result = await rpc("/twilio_dialer/phone_number");
        if (result.phone_number) {
            const caller = {
                number: result.phone_number,
                friendlyName: "Twilio Number",
            };
            this.state.callerNumbers = [caller];
            this.state.selectedCaller = caller;
        }
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
        if (tab === "auto_dialer") {
            this.openAutoCallingSetup();
        } else if (tab === "contacts") {
            this.openContacts();
        }
    }

    openAutoCallingSetup() {
        this.action.doAction("twilio_dialer.action_twilio_auto_dialer");
        if (this.props.onClose) {
            this.props.onClose();
        }
    }

    openContacts() {
        this.action.doAction("twilio_dialer.action_twilio_contacts");
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
        return !!this.state.lastDialedNumber;
    }

    get isCallActive() {
        return this.state.connectionStatus === "connecting" || this.state.connectionStatus === "connected";
    }

    get canCall() {
        return this.state.phoneNumber.length === 10 && !this.isCallActive && this.state.connectionStatus === "ready";
    }

    get statusClass() {
        const map = {
            initializing: "connecting",
            fetching_token: "connecting",
            registering: "connecting",
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
            connecting: "Connecting...",
            connected: "Connected",
            ready: "Ready",
            disconnected: "Disconnected",
            error: "Error",
        };
        return labels[this.state.connectionStatus] || "Ready";
    }

    appendDigit(digit) {
        if (digit === "*" || digit === "#") {
            return;
        }
        if (this.state.phoneNumber.length >= 10) {
            return;
        }
        this.state.phoneNumber += digit;
    }

    onInput(ev) {
        this.state.phoneNumber = ev.target.value.replace(/\D/g, "").slice(0, 10);
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
        deviceManager.makeCall(fullNumber, {
            From: this.state.selectedCaller?.number,
            from_number: this.state.selectedCaller?.number,
        });
    }

    onHangUp() {
        deviceManager.disconnect();
    }

    onRedial() {
        if (!this.state.lastDialedNumber) {
            return;
        }
        this.state.phoneNumber = this.state.lastDialedNumber;
    }
}
