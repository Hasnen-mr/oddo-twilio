/** @odoo-module **/

import { Component, useEffect, useExternalListener, useState } from "@odoo/owl";
import { COUNTRY_CODES } from "@twilio_dialer/js/country_codes";
import { buildE164, splitPhoneNumber } from "@twilio_dialer/js/phone_utils";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class TwilioPhoneCountryField extends Component {
    static template = "twilio_dialer.TwilioPhoneCountryField";
    static props = { ...standardFieldProps };

    setup() {
        this.rpc = useService("rpc");
        const parsed = splitPhoneNumber(this.props.record.data[this.props.name]);
        this.state = useState({
            selectedCountry: parsed.country,
            nationalNumber: parsed.nationalNumber,
            countrySearchQuery: "",
            showCountryDropdown: false,
        });
        useExternalListener(window, "click", this._onWindowClick.bind(this));

        useEffect(
            () => {
                const value = this.props.record.data[this.props.name] || "";
                const built = buildE164(this.state.selectedCountry, this.state.nationalNumber);
                if (value === built) {
                    return;
                }
                const next = splitPhoneNumber(value);
                this.state.selectedCountry = next.country;
                this.state.nationalNumber = next.nationalNumber;
            },
            () => [this.props.record.data[this.props.name]]
        );
    }

    get filteredCountries() {
        const query = this.state.countrySearchQuery.toLowerCase().trim();
        if (!query) {
            return COUNTRY_CODES;
        }
        return COUNTRY_CODES.filter(
            (country) =>
                country.name.toLowerCase().includes(query) ||
                country.code.includes(query) ||
                country.label.toLowerCase().includes(query)
        );
    }

    get isReadonly() {
        return this.props.readonly;
    }

    _onWindowClick() {
        this.state.showCountryDropdown = false;
        this.state.countrySearchQuery = "";
    }

    toggleCountryDropdown(ev) {
        ev.stopPropagation();
        if (this.isReadonly) {
            return;
        }
        this.state.showCountryDropdown = !this.state.showCountryDropdown;
        if (!this.state.showCountryDropdown) {
            this.state.countrySearchQuery = "";
        }
    }

    onCountrySearch(ev) {
        this.state.countrySearchQuery = ev.target.value;
    }

    async selectCountry(country) {
        this.state.selectedCountry = country;
        this.state.showCountryDropdown = false;
        this.state.countrySearchQuery = "";
        await this._commitValue();
    }

    async onNationalInput(ev) {
        const digits = String(ev.target.value || "").replace(/\D/g, "");
        this.state.nationalNumber = digits;
        await this._commitValue();
    }

    async clearNumber(ev) {
        ev.stopPropagation();
        this.state.nationalNumber = "";
        await this._commitValue();
    }

    async _commitValue() {
        if (this.isReadonly) {
            return;
        }
        const value = buildE164(this.state.selectedCountry, this.state.nationalNumber);
        const current = this.props.record.data[this.props.name] || "";
        if (value === current) {
            return;
        }
        await this.props.record.update({ [this.props.name]: value });
    }
}

export const twilioPhoneCountryField = {
    component: TwilioPhoneCountryField,
    supportedTypes: ["char"],
};

registry.category("fields").add("twilio_phone_country", twilioPhoneCountryField, { force: true });