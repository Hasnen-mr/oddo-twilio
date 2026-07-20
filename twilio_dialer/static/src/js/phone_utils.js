/** @odoo-module **/

import { COUNTRY_CODES } from "./country_codes";

const LAST_DIAL_STORAGE_KEY = "twilio_dialer.last_dial";
const FALLBACK_COUNTRY_CODE = "+91";

export function getDefaultCountry() {
    try {
        const lastDial = JSON.parse(window.localStorage.getItem(LAST_DIAL_STORAGE_KEY));
        const code = lastDial?.countryCode;
        const label = lastDial?.countryLabel;
        const match =
            COUNTRY_CODES.find((country) => country.code === code && country.label === label) ||
            COUNTRY_CODES.find((country) => country.code === code);
        if (match) {
            return match;
        }
    } catch {
        // Ignore invalid history.
    }
    return COUNTRY_CODES.find((country) => country.code === FALLBACK_COUNTRY_CODE) || COUNTRY_CODES[0];
}

export function getDefaultCountryCode() {
    return getDefaultCountry().code;
}

export function normalizePhoneNumber(number) {
    const value = String(number || "").trim();
    if (!value || value.startsWith("+")) {
        return value;
    }
    const nationalNumber = value.replace(/\D/g, "").replace(/^0+/, "");
    return nationalNumber ? `${getDefaultCountryCode()}${nationalNumber}` : "";
}

/** Split an E.164 / digit string into { country, nationalNumber }. */
export function splitPhoneNumber(number) {
    const raw = String(number || "").trim();
    const digits = raw.replace(/\D/g, "");
    const defaultCountry = getDefaultCountry();
    if (!digits) {
        return { country: defaultCountry, nationalNumber: "" };
    }

    const withPlus = raw.startsWith("+") ? `+${digits}` : digits;
    const matchedCountry = [...COUNTRY_CODES]
        .sort((a, b) => b.code.length - a.code.length)
        .find((country) => {
            const codeDigits = country.code.replace("+", "");
            if (withPlus.startsWith("+")) {
                return withPlus.startsWith(country.code);
            }
            return digits.startsWith(codeDigits);
        });

    if (!matchedCountry) {
        return { country: defaultCountry, nationalNumber: digits.replace(/^0+/, "") };
    }
    const codeDigits = matchedCountry.code.replace("+", "");
    const national = digits.startsWith(codeDigits)
        ? digits.slice(codeDigits.length)
        : digits;
    return {
        country: matchedCountry,
        nationalNumber: national.replace(/^0+/, ""),
    };
}

export function buildE164(country, nationalNumber) {
    const national = String(nationalNumber || "").replace(/\D/g, "").replace(/^0+/, "");
    if (!national) {
        return "";
    }
    const code = (country?.code || getDefaultCountryCode()).replace(/\s/g, "");
    return `${code}${national}`;
}
