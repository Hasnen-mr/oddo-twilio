/** @odoo-module **/

export const CACHE_KEY = "twilio_api_cache";
export const CACHE_DURATION_MS = 10 * 60 * 1000; // 10 minutes (600,000 ms)

/**
 * Sanitize API response data to ensure only non-sensitive call configuration
 * data is stored in client localStorage. Secrets/tokens are strictly excluded.
 */
export function sanitizeCallSettingsData(payload) {
    if (!payload || typeof payload !== "object") {
        return null;
    }
    const incoming = payload.incoming || payload.incomingCallSetting || {};
    const outgoing = payload.outgoing || payload.outgoingCallSetting || {};

    return {
        success: Boolean(payload.success),
        accountSid: payload.accountSid || "",
        device: payload.device || "",
        incoming: {
            allow: Boolean(incoming.allow),
            record: Boolean(incoming.record),
            voicemail: Boolean(incoming.voicemail),
            voicemailText: incoming.voicemailText || "",
            welcomeGreeting: Boolean(incoming.welcomeGreeting),
            welcomeGreetingText: incoming.welcomeGreetingText || "",
            forward: Boolean(incoming.forward),
            forwardTo: incoming.forwardTo || "",
        },
        outgoing: {
            record: Boolean(outgoing.record),
            smartCopy: incoming.smartCopy !== undefined ? Boolean(incoming.smartCopy) : Boolean(outgoing.smartCopy),
        },
        incomingCallSetting: {
            allow: Boolean(incoming.allow),
            record: Boolean(incoming.record),
            voicemail: Boolean(incoming.voicemail),
            voicemailText: incoming.voicemailText || "",
            welcomeGreeting: Boolean(incoming.welcomeGreeting),
            welcomeGreetingText: incoming.welcomeGreetingText || "",
            forward: Boolean(incoming.forward),
            forwardTo: incoming.forwardTo || "",
        },
        outgoingCallSetting: {
            record: Boolean(outgoing.record),
            smartCopy: incoming.smartCopy !== undefined ? Boolean(incoming.smartCopy) : Boolean(outgoing.smartCopy),
        },
    };
}

/**
 * Read valid cached call settings from localStorage.
 * Returns the cached data object if it exists and is less than 10 minutes old,
 * otherwise returns null.
 */
export function getCachedCallSettings() {
    try {
        const raw = localStorage.getItem(CACHE_KEY);
        if (!raw) {
            return null;
        }
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object" || !parsed.timestamp || !parsed.data) {
            return null;
        }
        const age = Date.now() - parsed.timestamp;
        if (age >= 0 && age < CACHE_DURATION_MS) {
            return parsed.data;
        }
    } catch (err) {
        console.warn("[TwilioDialer] Error reading call settings cache:", err);
    }
    return null;
}

/**
 * Retrieve raw cache entry including data and timestamp.
 */
export function getRawCacheEntry() {
    try {
        const raw = localStorage.getItem(CACHE_KEY);
        if (!raw) {
            return null;
        }
        return JSON.parse(raw);
    } catch {
        return null;
    }
}

/**
 * Store sanitized call settings in localStorage with current timestamp.
 */
export function setCachedCallSettings(data) {
    try {
        const sanitized = sanitizeCallSettingsData(data);
        if (!sanitized) {
            return;
        }
        const entry = {
            data: sanitized,
            timestamp: Date.now(),
        };
        localStorage.setItem(CACHE_KEY, JSON.stringify(entry));
    } catch (err) {
        console.warn("[TwilioDialer] Error writing call settings cache:", err);
    }
}

/**
 * Clear the call settings cache from localStorage.
 */
export function clearCachedCallSettings() {
    try {
        localStorage.removeItem(CACHE_KEY);
    } catch {
        // ignore
    }
}

/**
 * Unified fetch helper with 10-minute client-side caching:
 * - Checks localStorage first.
 * - If valid cached data exists (<10 min old), returns it without calling API.
 * - If missing or older than 10 min, calls orm to fetch from API.
 * - On success, updates cache and timestamp.
 * - On failure with valid cache, falls back to existing cache without overwriting.
 */
export async function fetchCallSettingsWithCache(orm, accountSid = "") {
    // 1. Check existing valid cache (< 10 minutes old)
    const validCache = getCachedCallSettings();
    if (validCache) {
        return { success: true, data: validCache, fromCache: true };
    }

    // 2. Fetch from API via backend RPC
    try {
        const res = await orm.call(
            "res.config.settings",
            "twilio_get_call_settings_api",
            [],
            { account_sid: accountSid }
        );
        if (res && res.success && res.data) {
            setCachedCallSettings(res.data);
            return { success: true, data: getCachedCallSettings() || res.data, fromCache: false };
        }
        // If API returned error but we have raw cached data (even if slightly aged), fallback
        const rawEntry = getRawCacheEntry();
        if (rawEntry && rawEntry.data) {
            return { success: true, data: rawEntry.data, fromCache: true, fallback: true };
        }
        return { success: false, error: (res && res.error) || "Could not fetch call settings." };
    } catch (err) {
        // Network error fallback to cached data if exists
        const rawEntry = getRawCacheEntry();
        if (rawEntry && rawEntry.data) {
            return { success: true, data: rawEntry.data, fromCache: true, fallback: true };
        }
        return {
            success: false,
            error: (err && err.data && err.data.message) || (err && err.message) || "Network error fetching call settings.",
        };
    }
}
