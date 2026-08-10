/** @odoo-module **/

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
            if (this._destroyed || !token) return;

            this._setStatus(STATUS.REGISTERING);
            await this._createDevice(token);
        } catch (error) {
            console.info("[DeviceManager] initialize(): Twilio unconfigured or waiting for settings:", error.message || error);
            this._setStatus(STATUS.DISCONNECTED);
            return;
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
            if (data.configured === false) {
                console.info("[DeviceManager] Twilio credentials unconfigured:", data.message);
                this._setStatus(STATUS.DISCONNECTED);
                return null;
            }
            throw new Error(data.message || "Token request failed");
        }
        this.token = data.token;

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

        this.device = new Twilio.Device(token, {
            codecPreferences: ["opus", "pcmu"],
            fakeLocalDTMF: true,
            enableRingingState: true,
        });

        this.device.on("error", (error) => {
            console.group("Twilio Device Error");

            console.error("Full Error:", error);
            console.log("Code:", error.code);
            console.log("Message:", error.message);
            console.log("Explanation:", error.explanation);
            console.log("Causes:", error.causes);
            console.log("Solutions:", error.solutions);

            console.groupEnd();

            if (this._destroyed) {
                return;
            }
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

        this.device.on("incoming", (call) => {
            console.log("[Twilio JS] device.on('incoming') event fired!", call);
            if (this._dndEnabled) {
                console.log("[Twilio JS] DND enabled — rejecting incoming call");
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
            const toNumber = call.parameters?.To || call.parameters?.to || "";
            const callSid = call.parameters?.CallSid || "";

            this._attachCallListeners(call, callSid, fromNumber);

            if (!this._destroyed) {
                this._setStatus(STATUS.INCOMING);
            }

            if (typeof this._onIncomingCall === "function") {
                this._onIncomingCall(call, fromNumber, callSid, toNumber);
            }
        });

        console.log("[Twilio JS] Creating Twilio Device with token identity");

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
            console.error("[Twilio JS] device.register() failed:", error);
            if (this._isAccessTokenInvalid(error)) {
                await this._recoverInvalidAccessToken(error);
                return;
            }
            throw error;
        } finally {
            this._registering = false;
        }
    }

    onIncomingCall(callback) {
        this._onIncomingCall = callback;
    }

    acceptCall() {
        if (this._activeConnection && typeof this._activeConnection.accept === "function") {
            console.log("[Twilio JS] acceptCall() -> call.accept() executing");
            try {
                this._activeConnection.accept();
                this._setStatus(STATUS.CONNECTED);
                return true;
            } catch (err) {
                console.error("[Twilio JS] call.accept() failed:", err);
                return false;
            }
        }
        console.warn("[Twilio JS] acceptCall() failed: no active incoming connection");
        return false;
    }

    rejectCall() {
        if (this._activeConnection) {
            console.log("[Twilio JS] rejectCall() -> call.reject() executing");
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

    _attachCallListeners(call, callSid, phoneNumber) {
        if (!call || !call.on) {
            return;
        }

        const logState = (event) => {
            console.log(`[Twilio Call Event: ${event}]`, {
                timestamp: new Date().toISOString(),
                callSid: call.parameters?.CallSid || callSid,
                deviceManagerStatus: this.status,
                activeQueueLineId: this._activeQueueLineId,
                callState: typeof call.status === "function" ? call.status() : "unknown"
            });
        };

        call.on("accept", () => {
            logState("accept");
            this._syncCallLog(call, callSid, phoneNumber, "in_progress");
            if (!this._destroyed) {
                this._setStatus(STATUS.CONNECTED);
            }
            console.log("Call Accepted");
            console.log(call.parameters);
        });

        call.on("ringing", () => {
            logState("ringing");
            this._syncCallLog(call, callSid, phoneNumber, "ringing");
            console.log(" Ringing");
            console.log(call.parameters);
        });

        call.on("disconnect", () => {
            logState("disconnect");
            this._syncCallLog(
                call,
                callSid,
                phoneNumber,
                this._getCallStatus(call, "completed")
            );
            this._activeConnection = null;
            if (!this._destroyed) {
                this._setStatus(STATUS.READY);
            }
            console.log(" Call Disconnected");
            console.log(call.parameters);
        });

        call.on("cancel", () => {
            logState("cancel");
            this._syncCallLog(call, callSid, phoneNumber, "canceled");
            this._activeConnection = null;
            if (!this._destroyed) {
                this._setStatus(STATUS.READY);
            }
        });

        call.on("reject", () => {
            logState("reject");
            this._syncCallLog(call, callSid, phoneNumber, "rejected");
            this._activeConnection = null;
            if (!this._destroyed) {
                this._setStatus(STATUS.READY);
            }
        });

        call.on("error", (error) => {
            console.group("Twilio Call Error");
            console.error("Full Error:", error);
            console.log("Code:", error.code);
            console.log("Message:", error.message);
            console.groupEnd();

            logState(`error (code: ${error.code}, msg: ${error.message})`);

            this._syncCallLog(call, callSid, phoneNumber, "failed");
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

    async _createCallLog(callSid, phoneNumber, partnerId = null, retries = 3) {
        for (let attempt = 1; attempt <= retries; attempt++) {
            try {
                await rpc("/twilio_dialer/call_log/create", {
                    call_sid: callSid,
                    to_number: phoneNumber,
                    partner_id: partnerId,
                });
                return;
            } catch (err) {
                console.warn(`[DeviceManager] _createCallLog attempt ${attempt}/${retries} failed:`, err);
                if (attempt === retries) throw err;
                await new Promise((r) => setTimeout(r, 500 * attempt));
            }
        }
    }

    async _syncCallLog(call, fallbackCallSid, phoneNumber, status) {
        const callSid = call.parameters?.CallSid || call.parameters?.callSid || fallbackCallSid || this._activeConnection?.parameters?.CallSid;
        if (!callSid) {
            console.warn("[DeviceManager] Twilio Call SID is not available yet for call log update. Skipping transient sync.");
            return;
        }

        try {
            await this._createCallLog(callSid, phoneNumber, this._activePartnerId);
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
        } catch (error) {
            console.error("Failed to create Twilio call log:", error);
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

        try {
            // Normalize destination phone number to clean E.164 using shared helper
            const cleanNumber = this.normalizePhoneNumber(phoneNumber);
            const fromNumber = customParameters.From || customParameters.from_number || customParameters.callerId || "";

            console.log("[DeviceManager] makeCall trace:", {
                phoneNumber: cleanNumber,
                customParameters: customParameters,
                callContext: callContext,
                selectedCaller: fromNumber
            });

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

            if (window.TWILIO_DIALER_DEBUG) {
                console.log("[DEBUG TRACE] device.connect params:", JSON.stringify(connectParams, null, 2));
            }

            const call = await this.device.connect({
                params: connectParams,
            });

            console.group("Call Debug");

            console.log("Call:", call);
            console.log("Parameters:", call.parameters);
            console.log("CallSid:", call.parameters?.CallSid);
            console.log("Status:", call.status?.());
            console.log("Direction:", call.direction);

            console.dir(call);

            console.groupEnd();

            let callSid = call.parameters?.CallSid;

            if (!callSid) {
                console.warn("Call SID not available yet.");
            } else {
                await this._createCallLog(callSid, phoneNumber, this._activePartnerId);
            }

            this._activeConnection = call;
            this._attachCallListeners(call, callSid, phoneNumber);

            return true;

        } catch (error) {
            console.group("CONNECT FAILED");

            console.error(error);
            console.log("Code:", error.code);
            console.log("Message:", error.message);
            console.log("Explanation:", error.explanation);
            console.log("Causes:", error.causes);
            console.log("Solutions:", error.solutions);

            console.groupEnd();

            if (this._isAccessTokenInvalid(error)) {
                await this._recoverInvalidAccessToken(error);
                return false;
            }

            this._setStatus(STATUS.ERROR);
            return false;
        }
    }

    disconnect() {
        console.error("[DEBUG TRACE] deviceManager.disconnect() requested!");
        console.trace("[DEBUG TRACE] Stack trace for deviceManager.disconnect:");
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

    destroy() {
        this._destroyed = true;
        this._dndEnabled = false;
        this._teardownDevice({ keepListeners: false });
    }
}

export const deviceManager = new DeviceManager();
export { STATUS };
