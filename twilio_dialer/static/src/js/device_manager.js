/** @odoo-module **/

// Safe browser autoplay rejection handler
if (typeof window !== "undefined" && window.HTMLAudioElement && !window._odooAudioPlayPatched) {
    window._odooAudioPlayPatched = true;
    const origPlay = HTMLAudioElement.prototype.play;
    HTMLAudioElement.prototype.play = function() {
        try {
            const res = origPlay.apply(this, arguments);
            if (res && typeof res.catch === "function") {
                return res.catch((err) => {
                    if (err && (err.name === "NotAllowedError" || String(err).includes("interact with the document"))) {
                        return;
                    }
                    console.warn("[Twilio Audio] Autoplay suppressed:", err);
                });
            }
            return res;
        } catch (e) {
            if (e && (e.name === "NotAllowedError" || String(e).includes("interact with the document"))) {
                return Promise.resolve();
            }
            return Promise.reject(e);
        }
    };
}



import { loadJS } from "@web/core/assets";
import { rpc } from "@web/core/network/rpc";

const TWILIO_SDK_PATH = "/twilio_dialer/static/lib/twilio/twilio.min.js";

const STATUS = Object.freeze({
    INITIALIZING: "initializing",
    FETCHING_TOKEN: "fetching_token",
    REGISTERING: "registering",
    READY: "ready",
    INCOMING: "incoming",
    CONNECTING: "connecting",
    CONNECTED: "connected",
    DISCONNECTED: "disconnected",
    ERROR: "error",
});

class DeviceManager {
    constructor() {
        this.device = null;
        this.token = null;
        this.status = STATUS.DISCONNECTED;
        this._onStatusChange = null;
        this._statusListeners = new Set();
        this._onIncomingCall = null;
        this._destroyed = false;
        this._activeConnection = null;
        this._activePartnerId = null;
        this.activeIncomingNumber = null;
        this.activeIncomingTo = null;
        this.allowedPhoneNumbers = [];
        this.isAllAllowed = false;
        this._activeQueueLineId = null;
        this._tokenRegenAttempted = false;
        this._registering = false;
        this._dndEnabled = false;
    }

    _setStatus(status) {
        this.status = status;
        if (!this._destroyed) {
            if (typeof this._onStatusChange === "function") {
                this._onStatusChange(status);
            }
            for (const listener of this._statusListeners) {
                try {
                    listener(status);
                } catch (e) {
                    console.error("[DeviceManager] Error in status listener:", e);
                }
            }
        }
    }

    setStatusCallback(callback) {
        this._onStatusChange = callback;
    }

    onStatusChange(callback) {
        if (typeof callback === "function") {
            this._statusListeners.add(callback);
            return () => this._statusListeners.delete(callback);
        }
        return () => {};
    }

    _isAccessTokenInvalid(error) {
        if (!error) {
            return false;
        }
        const code = error.code || error.twilioError?.code;
        const name = String(error.name || error.twilioError?.name || "");
        const message = String(error.message || "");
        return (
            code === 20101 ||
            name.includes("AccessTokenInvalid") ||
            message.includes("AccessTokenInvalid") ||
            message.includes("unable to validate your Access Token")
        );
    }

    async initialize(onStatusChange) {
        if (onStatusChange) {
            this._onStatusChange = onStatusChange;
        }
        if (this._dndEnabled) {
            this._setStatus(STATUS.DISCONNECTED);
            return;
        }
        if (this.device && (this.status === STATUS.READY || this.status === STATUS.REGISTERING || this.status === STATUS.INCOMING || this.status === STATUS.CONNECTED)) {
            console.log("[DeviceManager] Already initialized, status:", this.status);
            this._setStatus(this.status);
            return;
        }
        this._destroyed = false;
        this._tokenRegenAttempted = false;

        try {
            this._setStatus(STATUS.INITIALIZING);
            this._setStatus(STATUS.FETCHING_TOKEN);

            const token = await this._fetchToken(false);
            if (this._destroyed) return;

            this._setStatus(STATUS.REGISTERING);
            await this._createDevice(token);
        } catch (error) {
            console.error("[DeviceManager] initialize() failed:", error);
            if (!this._destroyed && this._isAccessTokenInvalid(error)) {
                await this._recoverInvalidAccessToken(error);
                return;
            }
            this._setStatus(STATUS.ERROR);
        }
    }

    /**
     * Tear down the Device, fetch a fresh token (optionally regenerating
     * Twilio credentials), register, and resolve when READY or ERROR.
     * @returns {Promise<boolean>} true when registered successfully
     */
    async ensureRegistered({ regenerate = false, timeoutMs = 45000 } = {}) {
        this._destroyed = false;
        this._dndEnabled = false;
        this._tokenRegenAttempted = false;
        this._teardownDevice({ keepListeners: true });

        let settled = false;
        let resolveFn = () => {};
        const result = new Promise((resolve) => {
            resolveFn = resolve;
        });
        const finish = (ok) => {
            if (settled) {
                return;
            }
            settled = true;
            clearTimeout(timer);
            unsub();
            resolveFn(ok);
        };
        const timer = setTimeout(() => finish(false), timeoutMs);
        const unsub = this.onStatusChange((status) => {
            if (status === STATUS.READY) {
                finish(true);
            } else if (status === STATUS.ERROR) {
                finish(false);
            }
        });

        try {
            this._setStatus(STATUS.INITIALIZING);
            this._setStatus(STATUS.FETCHING_TOKEN);
            const token = await this._fetchToken(regenerate);
            if (this._destroyed) {
                finish(false);
                return result;
            }
            this._setStatus(STATUS.REGISTERING);
            await this._createDevice(token);
            if (this.status === STATUS.READY) {
                finish(true);
            }
        } catch (error) {
            console.error("[DeviceManager] ensureRegistered() failed:", error);
            if (!this._destroyed && this._isAccessTokenInvalid(error)) {
                try {
                    await this._recoverInvalidAccessToken(error);
                    if (this.status === STATUS.READY) {
                        finish(true);
                        return result;
                    }
                } catch (recoverError) {
                    console.error("[DeviceManager] recover during ensureRegistered failed:", recoverError);
                }
            }
            this._setStatus(STATUS.ERROR);
            finish(false);
        }

        return result;
    }

    get isDoNotDisturb() {
        return this._dndEnabled;
    }

    async setDoNotDisturb(enabled) {
        this._dndEnabled = !!enabled;
        if (this._dndEnabled) {
            if (this.device && typeof this.device.unregister === "function") {
                try {
                    const result = this.device.unregister();
                    if (result && typeof result.then === "function") {
                        await result;
                    }
                } catch (err) {
                    console.warn("[DeviceManager] DND unregister failed:", err);
                }
            }
            this._setStatus(STATUS.DISCONNECTED);
            return true;
        }
        return this.ensureRegistered({ regenerate: false });
    }

    _teardownDevice({ keepListeners = false } = {}) {
        if (this.device) {
            try {
                if (typeof this.device.destroy === "function") {
                    this.device.destroy();
                }
            } catch (err) {
                console.warn("[DeviceManager] device.destroy() error:", err);
            }
            this.device = null;
        }
        this.token = null;
        this._activeConnection = null;
        this._activePartnerId = null;
        this.activeIncomingNumber = null;
        this.activeIncomingTo = null;
        this.allowedPhoneNumbers = null;
        this.activeIncomingNumber = null;
        this.activeIncomingTo = null;
        this.allowedPhoneNumbers = null;
        this._activeQueueLineId = null;
        this._registering = false;
        if (!keepListeners) {
            this._onStatusChange = null;
            this._statusListeners.clear();
        }
    }

    async _fetchToken(regenerate = false) {
        const url = regenerate
            ? "/twilio_dialer/token?refresh=1"
            : "/twilio_dialer/token";
        const response = await fetch(url, {
            method: "GET",
            credentials: "same-origin",
        });

        if (!response.ok) {
            let errorMsg = `Unable to fetch token (HTTP ${response.status})`;
            try {
                const errData = await response.json();
                if (errData && errData.message) {
                    errorMsg = errData.message;
                }
            } catch (e) {
                // Ignore JSON parse error if response is HTML error page
            }
            throw new Error(errorMsg);
        }

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.message || "Token request failed");
        }
        this.token = data.token;
        if (data.allowed_numbers) {
            this.setAllowedNumbers(data.allowed_numbers);
        }

        console.log(regenerate ? "JWT regenerated" : "JWT received");
        return data.token;
    }

    async _ensureTwilioSdk() {
        if (window.Twilio && window.Twilio.Device) {
            return window.Twilio;
        }
        await loadJS(TWILIO_SDK_PATH);
        if (!window.Twilio || !window.Twilio.Device) {
            throw new Error("Twilio Voice SDK not loaded");
        }
        return window.Twilio;
    }

    _teardownDevice() {
        if (!this.device) {
            return;
        }
        try {
            if (typeof this.device.removeAllListeners === "function") {
                this.device.removeAllListeners();
            }
        } catch (e) {
            // ignore
        }
        try {
            if (typeof this.device.destroy === "function") {
                this.device.destroy();
            } else if (typeof this.device.unregister === "function") {
                const result = this.device.unregister();
                if (result && typeof result.catch === "function") {
                    result.catch(() => {});
                }
            }
        } catch (e) {
            console.warn("[DeviceManager] device teardown warning:", e);
        }
        this.device = null;
        this._activeConnection = null;
    }

    _isAccessTokenInvalid(error) {
        if (!error) return false;
        const msg = (error.message || "" || String(error)).toLowerCase();
        const name = (error.name || "").toLowerCase();
        const code = error.code;
        return (
            code === 20101 ||
            code === 20104 ||
            code === 20105 ||
            code === 20107 ||
            code === 31204 ||
            code === 31205 ||
            name.includes("accesstokeninvalid") ||
            name.includes("accesstokenexpired") ||
            msg.includes("accesstokeninvalid") ||
            msg.includes("unable to validate your access token") ||
            msg.includes("access token expired") ||
            msg.includes("jwt")
        );
    }

    async _recoverInvalidAccessToken(error) {
        if (this._destroyed || this._tokenRegenAttempted) {
            console.error("[DeviceManager] Access token still invalid after regenerate:", error);
            this._setStatus(STATUS.ERROR);
            return;
        }
        this._tokenRegenAttempted = true;
        console.warn(
            "[DeviceManager] AccessTokenInvalid — regenerating Twilio credentials and token..."
        );
        try {
            this._teardownDevice();
            this._setStatus(STATUS.FETCHING_TOKEN);
            const token = await this._fetchToken(true);
            if (this._destroyed) {
                return;
            }
            this._setStatus(STATUS.REGISTERING);
            await this._createDevice(token);
        } catch (regenError) {
            console.error("[DeviceManager] Token regenerate failed:", regenError);
            this._setStatus(STATUS.ERROR);
        }
    }

    async _createDevice(token) {
        if (this._destroyed) return;

        const Twilio = await this._ensureTwilioSdk();
        if (this._destroyed) return;

        this._teardownDevice();

        console.log("[Twilio JS] Creating Twilio Device with token identity");

        this.device = new Twilio.Device(token, {
            codecPreferences: ["opus", "pcmu"],
            fakeLocalDTMF: true,
            enableRingingState: true,
            disableAudioContextSounds: true,
            sounds: {
                incoming: false,
                outgoing: false,
                disconnect: false,
                dtmf: false,
            },
        });

        this.device.on("error", (error) => {
            if (this._destroyed) {
                return;
            }
            console.error("[Twilio JS] Device error:", error.message || error);
            if (this._isAccessTokenInvalid(error)) {
                // Fire-and-forget; catch so UncaughtPromiseError is avoided.
                this._recoverInvalidAccessToken(error).catch((err) => {
                    console.error("[DeviceManager] recover failed:", err);
                    this._setStatus(STATUS.ERROR);
                });
                return;
            }
            this._setStatus(STATUS.ERROR);
        });

        this.device.on("registered", () => {
            if (!this._destroyed) {
                this._tokenRegenAttempted = false;
                this._setStatus(STATUS.READY);
            }
            console.log("[Twilio JS] Device registered successfully");
        });

        this.device.on("registering", () => {
            if (!this._destroyed) {
                this._setStatus(STATUS.REGISTERING);
            }
        });

        this.device.on("unregistered", () => {
            if (!this._destroyed) {
                this._setStatus(STATUS.DISCONNECTED);
            }
        });

        this.device.on("tokenWillExpire", () => {
            this._refreshToken();
        });

        this.device.on("incoming", async (call) => {
            if (this._dndEnabled) {
                try {
                    if (typeof call.reject === "function") {
                        call.reject();
                    }
                } catch (err) {
                    console.warn("[Twilio JS] DND reject failed:", err);
                }
                return;
            }
            this._activeConnection = call;
            const fromNumber = call.parameters?.From || call.parameters?.from || "Unknown";
            const callSid = call.parameters?.CallSid || call.parameters?.callSid || "";

            let toNumber = this.extractActualIncomingNumber(call);
            if (!toNumber && callSid) {
                toNumber = await this.resolveIncomingNumber(callSid);
            }

            console.log(`[Twilio JS] Incoming Call: From=${fromNumber}, To=${toNumber}, CallSid=${callSid || "N/A"}, Odoo ID=${this._activePartnerId || this._activeResId || "N/A"}`);

            // Strict Front-End Filter: Block incoming call if destination is not in this user's dropdown allocation
            if (!this.isIncomingNumberAssigned(toNumber)) {
                console.log(`[Twilio JS] Incoming call filtered: Destination ${toNumber || "Unknown"} is NOT assigned to this user's dropdown.`);
                try {
                    if (typeof call.ignore === "function") {
                        call.ignore();
                    }
                } catch (e) {}
                return;
            }
            this.activeIncomingNumber = fromNumber;
            this.activeIncomingTo = toNumber;

            this._attachCallListeners(call, callSid, fromNumber, "incoming");

            if (!this._destroyed) {
                this._setStatus(STATUS.INCOMING);
            }

            if (typeof this._onIncomingCall === "function") {
                this._onIncomingCall(call, fromNumber, callSid, toNumber);
            }
        });

        if (this._registering) {
            return;
        }
        this._registering = true;
        try {
            const registerResult = this.device.register();
            if (registerResult && typeof registerResult.then === "function") {
                await registerResult;
            }
        } catch (error) {
            this._setStatus(STATUS.ERROR);
            if (this._isAccessTokenInvalid(error)) {
                await this._recoverInvalidAccessToken(error);
                return;
            }
            throw error;
        } finally {
            this._registering = false;
        }
    }

    async disconnectAll() {
        if (this.device) {
            try {
                this.device.disconnectAll();
            } catch (err) {
                console.warn("[Twilio JS] Device disconnectAll error:", err);
            }
            this._activeConnection = null;
        }
        if (!this._destroyed) {
            this._setStatus(STATUS.READY);
        }
    }

    onIncomingCall(callback) {
        this._onIncomingCall = callback;
    }

    acceptCall() {
        if (this._activeConnection && typeof this._activeConnection.accept === "function") {
            try {
                this._activeConnection.accept();
                this._setStatus(STATUS.CONNECTED);
                return true;
            } catch (err) {
                console.error("[Twilio JS] call.accept() failed:", err);
                return false;
            }
        }
        return false;
    }

    rejectCall() {
        if (this._activeConnection) {
            try {
                if (typeof this._activeConnection.reject === "function") {
                    this._activeConnection.reject();
                } else if (typeof this._activeConnection.disconnect === "function") {
                    this._activeConnection.disconnect();
                }
            } catch (err) {
                console.error("[Twilio JS] rejectCall() failed:", err);
            }
            this._activeConnection = null;
        }
        if (!this._destroyed) {
            this._setStatus(STATUS.READY);
        }
    }

    _attachCallListeners(call, callSid, phoneNumber, direction = "outgoing") {
        if (!call || !call.on) {
            return;
        }

        call.on("accept", async () => {
            const logId = await this._syncCallLog(call, callSid, phoneNumber, "in_progress", direction);
            if (!this._destroyed) {
                this._setStatus(STATUS.CONNECTED);
            }
            console.log(`[Twilio JS] Call Connected: CallSid=${callSid || call.parameters?.CallSid || "N/A"}, Call ID=${logId || "N/A"}`);
        });

        call.on("ringing", () => {
            this._syncCallLog(call, callSid, phoneNumber, "ringing", direction);
        });

        call.on("disconnect", () => {
            this._syncCallLog(
                call,
                callSid,
                phoneNumber,
                this._getCallStatus(call, "completed"),
                direction
            );
            this._activeConnection = null;
            if (!this._destroyed) {
                this._setStatus(STATUS.READY);
            }
        });

        call.on("cancel", () => {
            this._syncCallLog(call, callSid, phoneNumber, "canceled", direction);
            this._activeConnection = null;
            if (!this._destroyed) {
                this._setStatus(STATUS.READY);
            }
        });

        call.on("reject", () => {
            this._syncCallLog(call, callSid, phoneNumber, "rejected", direction);
            this._activeConnection = null;
            if (!this._destroyed) {
                this._setStatus(STATUS.READY);
            }
        });

        call.on("error", (error) => {
            console.error("[Twilio JS] Call error:", error.message || error);
            this._syncCallLog(call, callSid, phoneNumber, "failed", direction);
            this._activeConnection = null;

            if (!this._destroyed) {
                this._setStatus(STATUS.ERROR);
            }
        });
    }

    _getCallStatus(call, fallback) {
        const statusMap = {
            "in-progress": "in_progress",
            "no-answer": "no_answer",
            "busy": "busy",
            "failed": "failed",
            "canceled": "canceled",
            "rejected": "rejected"
        };
        const callStatus = call.parameters?.CallStatus || "";
        if (callStatus && statusMap[callStatus]) {
            return statusMap[callStatus];
        }
        return fallback;
    }

    async _createCallLog(callSid, phoneNumber, partnerId = null, direction = "outgoing", retries = 3) {
        for (let attempt = 1; attempt <= retries; attempt++) {
            try {
                const res = await rpc("/twilio_dialer/call_log/create", {
                    call_sid: callSid,
                    to_number: phoneNumber,
                    from_number: direction === "incoming" ? phoneNumber : null,
                    partner_id: partnerId,
                    direction: direction,
                    res_model: this._activeResModel || null,
                    res_id: this._activeResId || null,
                    lead_id: this._activeLeadId || null,
                });
                return res?.call_log_id || res?.id || null;
            } catch (err) {
                if (attempt === retries) throw err;
                await new Promise((r) => setTimeout(r, 500 * attempt));
            }
        }
        return null;
    }

    async _syncCallLog(call, fallbackCallSid, phoneNumber, status, direction = "outgoing") {
        const callSid = call.parameters?.CallSid || call.parameters?.callSid || fallbackCallSid || this._activeConnection?.parameters?.CallSid;
        if (!callSid) {
            return null;
        }

        try {
            const logId = await this._createCallLog(callSid, phoneNumber, this._activePartnerId, direction);
            await this._updateCallLog(callSid, status);

            if (this._activeQueueLineId) {
                try {
                    await rpc("/twilio_dialer/auto_dialer/sync_line", {
                        line_id: this._activeQueueLineId,
                        status: status,
                    });
                } catch (queueErr) {
                    console.error("Failed to sync Auto Dialer queue line status:", queueErr);
                }
            }
            return logId;
        } catch (error) {
            console.error("Failed to sync Twilio call log:", error);
            return null;
        }
    }

    async _updateCallLog(callSid, status) {
        try {
            await rpc("/twilio_dialer/call_log/update", {
                call_sid: callSid,
                status,
            });
        } catch (error) {
            console.error("Failed to update Twilio call log:", error);
        }
    }

    async _refreshToken() {
        try {
            const token = await this._fetchToken(false);
            if (!this.device || this._destroyed) {
                return;
            }

            const result = this.device.updateToken(token);
            if (result && typeof result.then === "function") {
                await result;
            }
        } catch (error) {
            console.error("Failed to refresh Twilio token:", error);
            if (this._destroyed) {
                return;
            }
            if (this._isAccessTokenInvalid(error)) {
                await this._recoverInvalidAccessToken(error);
                return;
            }
            try {
                const retryToken = await this._fetchToken(true);
                if (this.device && !this._destroyed) {
                    const retryResult = this.device.updateToken(retryToken);
                    if (retryResult && typeof retryResult.then === "function") {
                        await retryResult;
                    }
                    this._setStatus(STATUS.READY);
                    return;
                }
            } catch (retryError) {
                console.error("Twilio token refresh retry failed:", retryError);
                if (this._isAccessTokenInvalid(retryError)) {
                    await this._recoverInvalidAccessToken(retryError);
                    return;
                }
            }

            this._setStatus(STATUS.ERROR);
        }
    }

    normalizePhoneNumber(phoneNumber, defaultCountryCode = "+91") {
        let cleaned = (phoneNumber || "").toString().trim().replace(/[^0-9+]/g, "");
        if (!cleaned) return "";

        if (cleaned.startsWith("+")) {
            return cleaned;
        }

        const countryDigits = defaultCountryCode.replace(/\D/g, "");
        if (countryDigits && cleaned.startsWith(countryDigits)) {
            return "+" + cleaned;
        }

        if (cleaned.startsWith("0")) {
            cleaned = cleaned.replace(/^0+/, "");
        }

        const prefix = defaultCountryCode.startsWith("+") ? defaultCountryCode : "+" + defaultCountryCode;
        return prefix + cleaned;
    }

    async makeCall(phoneNumber, customParameters = {}, callContext = {}) {
        if (!this.device || this._destroyed || !phoneNumber) {
            console.error("[DeviceManager] makeCall failed checks: device=" + !!this.device + ", destroyed=" + this._destroyed + ", phoneNumber=" + phoneNumber);
            return false;
        }

        this._setStatus(STATUS.CONNECTING);
        this._activePartnerId = callContext.partnerId || null;
        this._activeQueueLineId = callContext.queueLineId || null;
        this._activeResModel = callContext.resModel || null;
        this._activeResId = callContext.resId || null;
        this._activeLeadId = callContext.leadId || (callContext.resModel === "crm.lead" ? callContext.resId : null) || null;

        try {
            const cleanNumber = this.normalizePhoneNumber(phoneNumber);
            const fromNumber = customParameters.From || customParameters.from_number || customParameters.callerId || "";
            console.log(`[Twilio JS] Outgoing call: From=${fromNumber}, To=${cleanNumber}`);

            const connectParams = {
                To: cleanNumber,
                to: cleanNumber,
                phone: cleanNumber,
                destination: cleanNumber,
                From: fromNumber,
                from_number: fromNumber,
                callerId: fromNumber,
                ...customParameters,
            };

            const call = await this.device.connect({
                params: connectParams,
            });

            let callSid = call.parameters?.CallSid || "";
            let callLogId = null;

            if (callSid) {
                callLogId = await this._createCallLog(callSid, phoneNumber, this._activePartnerId);
            }

            console.log(`[Twilio JS] Outgoing Call: From=${fromNumber}, To=${cleanNumber}, CallSid=${callSid || "N/A"}, Call ID=${callLogId || "N/A"}, Odoo ID=${this._activeResId || this._activePartnerId || "N/A"}`);

            this._activeConnection = call;
            this._attachCallListeners(call, callSid, phoneNumber);

            return true;

        } catch (error) {
            console.error("[Twilio JS] Outgoing call failed:", error.message || error);

            if (this._isAccessTokenInvalid(error)) {
                await this._recoverInvalidAccessToken(error);
                return false;
            }
            this._setStatus(STATUS.ERROR);
            return false;
        }
    }

    disconnect() {
        if (this._destroyed) {
            return;
        }

        if (this._activeConnection) {
            this._activeConnection.disconnect();
            this._activeConnection = null;
        } else if (this.device && typeof this.device.disconnectAll === "function") {
            this.device.disconnectAll();
        }

        this._setStatus(STATUS.READY);
    }

    mute(shouldMute = true) {
        if (!this._activeConnection || typeof this._activeConnection.mute !== "function") {
            return false;
        }
        this._activeConnection.mute(!!shouldMute);
        return this.isMuted();
    }

    toggleMute() {
        return this.mute(!this.isMuted());
    }

    isMuted() {
        if (!this._activeConnection) {
            return false;
        }
        if (typeof this._activeConnection.isMuted === "function") {
            return !!this._activeConnection.isMuted();
        }
        return false;
    }

    sendDigits(digits) {
        const value = String(digits || "");
        if (!value || !this._activeConnection) {
            return false;
        }
        if (typeof this._activeConnection.sendDigits !== "function") {
            console.warn("[DeviceManager] Active call does not support DTMF sendDigits.");
            return false;
        }
        try {
            this._activeConnection.sendDigits(value);
            return true;
        } catch (error) {
            console.error("[DeviceManager] Failed to send DTMF digits:", error);
            return false;
        }
    }


    setAllowedNumbers(numbers) {
        if (!Array.isArray(numbers)) {
            this.allowedPhoneNumbers = [];
            this.isAllAllowed = false;
            return;
        }
        this.isAllAllowed = numbers.some((n) => {
            if (typeof n === "object" && n !== null) {
                return n.is_all || n.phone_number === "ALL";
            }
            return n === "ALL";
        });
        this.allowedPhoneNumbers = numbers
            .map((n) => {
                const p = typeof n === "object" && n !== null ? (n.phone_number || "") : String(n || "");
                return p !== "ALL" ? p.replace(/\D/g, "") : "";
            })
            .filter(Boolean);
        console.log("[DeviceManager] Set allowed phone numbers:", this.allowedPhoneNumbers, "isAllAllowed:", this.isAllAllowed);
    }

    async resolveIncomingNumber(callSid) {
        if (!callSid) return "";
        try {
            const res = await rpc("/twilio_dialer/call_info", { call_sid: callSid });
            if (res && res.success && res.to_number) {
                return res.to_number;
            }
        } catch (e) {
            console.warn("[DeviceManager] Failed to resolve incoming call destination:", e);
        }
        return "";
    }

    isNumberAllowed(toNumber) {
        if (this.isAllAllowed) {
            return true;
        }
        if (!this.allowedPhoneNumbers || this.allowedPhoneNumbers.length === 0) {
            return false; // Fail closed if no numbers allocated
        }
        if (!toNumber) {
            return false; // Strict fail-closed: do not allow unallocated or unknown destinations
        }
        const cleanTo = String(toNumber).replace(/\D/g, "");
        const cleanTo10 = cleanTo.length > 10 && cleanTo.startsWith("1") ? cleanTo.substring(1) : (cleanTo.length >= 10 ? cleanTo.slice(-10) : cleanTo);

        return this.allowedPhoneNumbers.some((allowed) => {
            const cleanA = allowed.replace(/\D/g, "");
            const cleanA10 = cleanA.length > 10 && cleanA.startsWith("1") ? cleanA.substring(1) : (cleanA.length >= 10 ? cleanA.slice(-10) : cleanA);
            return cleanA === cleanTo || (cleanTo10 && cleanA10 === cleanTo10);
        });
    }

    extractActualIncomingNumber(call) {
        if (!call) return "";
        let customTo = "";
        if (call.customParameters && typeof call.customParameters.get === "function") {
            customTo = call.customParameters.get("To") || call.customParameters.get("CalledNumber") || "";
        } else if (call.customParameters) {
            customTo = call.customParameters.To || call.customParameters.CalledNumber || "";
        }

        let toNumber = customTo || call.parameters?.Called || call.parameters?.called || "";
        if (!toNumber) {
            const rawTo = call.parameters?.To || call.parameters?.to || "";
            if (rawTo && !rawTo.startsWith("client:") && !rawTo.startsWith("id_odoo_") && !rawTo.startsWith("id_")) {
                toNumber = rawTo;
            }
        }
        return toNumber;
    }

    isIncomingNumberAssigned(incomingNumber) {
        return this.isNumberAllowed(incomingNumber);
    }

    destroy() {
        this._destroyed = true;
        this._dndEnabled = false;
        this._teardownDevice({ keepListeners: false });
    }
}

export const deviceManager = new DeviceManager();
export { STATUS };