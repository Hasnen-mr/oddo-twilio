import os

target_files = [
    r"D:\Odoo\custom_addons\twilio_dialer\static\src\js\device_manager.js",
    r"D:\Odoo\custom_addons\oddo-twilio-18.0\twilio_dialer\static\src\js\device_manager.js",
]

for tf in target_files:
    if not os.path.exists(tf): continue
    with open(tf, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Update _fetchToken to handle data.configured === false
    old_token_check = """        if (!data.success) {
            throw new Error(data.message || "Token request failed");
        }"""
    
    new_token_check = """        if (!data.success) {
            if (data.configured === false) {
                console.info("[DeviceManager] Twilio credentials unconfigured:", data.message);
                this._setStatus(STATUS.DISCONNECTED);
                return null;
            }
            throw new Error(data.message || "Token request failed");
        }"""

    if old_token_check in content:
        content = content.replace(old_token_check, new_token_check)

    # 2. Update initialize() token check & error handling
    old_init = """            const token = await this._fetchToken(false);
            if (this._destroyed) return;"""
    
    new_init = """            const token = await this._fetchToken(false);
            if (this._destroyed || !token) return;"""

    if old_init in content:
        content = content.replace(old_init, new_init)

    old_init_catch = """        } catch (error) {
            console.error("[DeviceManager] initialize() failed:", error);"""

    new_init_catch = """        } catch (error) {
            console.info("[DeviceManager] initialize(): Twilio unconfigured or waiting for settings:", error.message || error);
            this._setStatus(STATUS.DISCONNECTED);
            return;"""

    if old_init_catch in content:
        content = content.replace(old_init_catch, new_init_catch)

    with open(tf, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"UPDATED: {tf}")
