/** @odoo-module **/

import { COUNTRY_CODES } from "./country_codes";

const LAST_DIAL_STORAGE_KEY = "twilio_dialer.last_dial";
const FALLBACK_COUNTRY_CODE = "+91";

export function getDefaultCountryCode() {
    try {
        const lastDial = JSON.parse(window.localStorage.getItem(LAST_DIAL_STORAGE_KEY));
        const code = lastDial?.countryCode;
        if (COUNTRY_CODES.some((country) => country.code === code)) {
            return code;
        }
    } catch {
        // A missing or invalid history must not prevent opening the dialer.
    }
    return FALLBACK_COUNTRY_CODE;
}

export function normalizePhoneNumber(number) {
    const value = String(number || "").trim();
    if (!value || value.startsWith("+")) {
        return value;
    }
    const nationalNumber = value.replace(/\D/g, "").replace(/^0+/, "");
    return nationalNumber ? `${getDefaultCountryCode()}${nationalNumber}` : "";
}
