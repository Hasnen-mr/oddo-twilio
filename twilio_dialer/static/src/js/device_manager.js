/** @odoo-module **/

import { loadJS } from "@web/core/assets";
import { rpc } from "@web/core/network/rpc";

const TWILIO_SDK_PATH = "/twilio_dialer/static/lib/twilio/twilio.min.js";

const STATUS = Object.freeze({
    INITIALIZING: "initializing",
    FETCHING_TOKEN: "fetching_token",
    REGISTERING: "registering",
    READY: "ready",
    CONNECTING: "connecting",
    CONNECTED: "connected",
    DISCONNECTED: "disconnected",
    ERROR: "error",
});

class DeviceManager {
    constructor() {
        this.device = null;
        this.token = null;
        this._onStatusChange = null;
        this._destroyed = false;
        this._activeConnection = null;
    }

    _setStatus(status) {
        if (!this._destroyed && this._onStatusChange) {
            this._onStatusChange(status);
        }
    }

    async initialize(onStatusChange) {
        this._onStatusChange = onStatusChange;
        this._destroyed = false;

        try {
            this._setStatus(STATUS.INITIALIZING);
            this._setStatus(STATUS.FETCHING_TOKEN);

            const token = await this._fetchToken();
            if (this._destroyed) return;

            this._setStatus(STATUS.REGISTERING);
            await this._createDevice(token);
        } catch (error) {
            console.error("[DeviceManager] initialize() failed:", error);
            this._setStatus(STATUS.ERROR);
        }
    }

    async _fetchToken() {
        const response = await fetch("/twilio_dialer/token", {
            method: "GET",
            credentials: "same-origin",
        });

        if (!response.ok) {
            throw new Error("Unable to fetch token");
        }

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.message || "Token request failed");
        }
        this.token = data.token;

        console.log("JWT received");
        console.log(this.token);

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

    async _createDevice(token) {
        if (this._destroyed) return;

        const Twilio = await this._ensureTwilioSdk();
        if (this._destroyed) return;

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

            if (!this._destroyed) {
                this._setStatus(STATUS.ERROR);
            }
        });

        this.device.on("registered", () => {
            if (!this._destroyed) {
                this._setStatus(STATUS.READY);
            }

        console.log("Twilio Device registered successfully");
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

        console.log("Creating Twilio Device");
        console.log(this.device);

        this.device.register();
    }

    _attachCallListeners(call, callSid, phoneNumber) {
        if (!call || !call.on) {
            return;
        }

        call.on("accept", () => {
            this._syncCallLog(call, callSid, phoneNumber, "in_progress");
            if (!this._destroyed) {
                this._setStatus(STATUS.CONNECTED);
            }
            console.log("Call Accepted");
            console.log(call.parameters);
        });

        call.on("ringing", () => {
            this._syncCallLog(call, callSid, phoneNumber, "ringing");
            console.log(" Ringing");
            console.log(call.parameters);
        });

        call.on("disconnect", () => {
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
            this._syncCallLog(call, callSid, phoneNumber, "canceled");
            this._activeConnection = null;
            if (!this._destroyed) {
                this._setStatus(STATUS.READY);
            }
        });

        call.on("reject", () => {
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
            console.log("Explanation:", error.explanation);
            console.log("Causes:", error.causes);
            console.log("Solutions:", error.solutions);
            console.log("Original Error:", error.originalError);

            console.groupEnd();

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
        };
        return statusMap[call.parameters?.CallStatus] || call.parameters?.CallStatus || fallback;
    }

    async _createCallLog(callSid, phoneNumber, partnerId = null) {
        await rpc("/twilio_dialer/call_log/create", {
            call_sid: callSid,
            to_number: phoneNumber,
            partner_id: partnerId,
        });
    }

    async _syncCallLog(call, fallbackCallSid, phoneNumber, status) {
        const callSid = call.parameters?.CallSid || fallbackCallSid;
        if (!callSid) {
            console.warn("Twilio Call SID is not available for call log update.");
            return;
        }

        try {
            await this._createCallLog(callSid, phoneNumber, this._activePartnerId);
            await this._updateCallLog(callSid, status);
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
            const token = await this._fetchToken();
            if (!this.device || this._destroyed) {
                return;
            }

            const result = this.device.updateToken(token);
            if (result && typeof result.then === "function") {
                await result;
            }
        } catch (error) {
            console.error("Failed to refresh Twilio token:", error);
            if (!this._destroyed) {
                try {
                    const retryToken = await this._fetchToken();
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
                }

                try {
                    if (this.device && typeof this.device.register === "function") {
                        this.device.register();
                    }
                } catch (registerError) {
                    console.error("Twilio device re-register failed:", registerError);
                }

                this._setStatus(STATUS.ERROR);
            }
        }
    }

    async makeCall(phoneNumber, customParameters = {}, callContext = {}) {
        if (!this.device || this._destroyed || !phoneNumber) {
            return false;
        }

        this._setStatus(STATUS.CONNECTING);
        this._activePartnerId = callContext.partnerId || null;

        try {
            console.log("Dialing:", phoneNumber);

            const call = await this.device.connect({
                params: {
                    To: phoneNumber,
                    ...customParameters,
                },
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

    destroy() {
        this._destroyed = true;
        if (this.device) {
            this.device.destroy();
            this.device = null;
        }
        this.token = null;
        this._activeConnection = null;
        this._onStatusChange = null;
    }
}

export const deviceManager = new DeviceManager();
export { STATUS };
