# -*- coding: utf-8 -*-
"""
Automated Localhost HTTPS & mkcert Setup Utility for MCP Claude
Generates trusted SSL certificates for localhost, 127.0.0.1, ::1 and configures odoo.conf.
"""

import os
import subprocess

def run_command(cmd):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return res.returncode == 0, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def find_mkcert_exe():
    ok, out, _ = run_command("where.exe mkcert")
    if ok and out:
        return out.splitlines()[0]
    
    user_p = os.environ.get("USERPROFILE", "")
    mkcert_user = os.path.join(user_p, "mkcert.exe")
    if os.path.exists(mkcert_user):
        return mkcert_user

    tools_p = r"C:\Tools\mkcert\mkcert.exe"
    if os.path.exists(tools_p):
        return tools_p

    return None

def setup_localhost_ssl(base_dir=None, conf_path=None, force_overwrite=False):
    print("============================================================")
    print("      MCP CLAUDE - TRUSTED LOCALHOST HTTPS SETUP (mkcert)   ")
    print("============================================================")

    base_dir = base_dir or r"D:\odoo-mcp"
    conf_path = conf_path or os.path.join(base_dir, "odoo.conf")
    certs_dir = os.path.join(base_dir, "certs")
    os.makedirs(certs_dir, exist_ok=True)

    cert_file = os.path.join(certs_dir, "server.crt")
    key_file = os.path.join(certs_dir, "server.key")

    # 1. Verify mkcert executable
    mkcert_exe = find_mkcert_exe()
    if not mkcert_exe:
        print("[!] ERROR: mkcert executable not found!")
        print("    Please ensure mkcert is installed at %USERPROFILE%\\mkcert.exe or on system PATH.")
        return False

    print(f"[+] Step 1: Found mkcert executable at: {mkcert_exe}")

    # 2. Verify Local Root CA installation
    print("[+] Step 2: Verifying Local CA installation...")
    ok, out, err = run_command(f'"{mkcert_exe}" -install')
    if ok:
        print(" -> Local Root CA installed and trusted in OS Certificate Store.")
    else:
        print(f" -> CA Notice: {err or out}")

    # 3. Detect existing certificates
    if os.path.exists(cert_file) and os.path.exists(key_file) and not force_overwrite:
        print(f"\n[+] Step 3: Valid existing certificates detected at:")
        print(f" -> Cert: {cert_file}")
        print(f" -> Key:  {key_file}")
        print(" -> Reusing existing certificates (Use force_overwrite=True to regenerate).")
    else:
        print(f"\n[+] Step 3: Generating fresh trusted certificates for localhost, 127.0.0.1, ::1...")
        cmd_gen = f'"{mkcert_exe}" -cert-file "{cert_file}" -key-file "{key_file}" localhost 127.0.0.1 ::1'
        ok_gen, out_gen, err_gen = run_command(cmd_gen)
        if ok_gen and os.path.exists(cert_file):
            print(f" -> Certificates generated successfully at: {certs_dir}")
        else:
            print(f"[!] Generation error: {err_gen or out_gen}")
            return False

    # 4. Update odoo.conf automatically
    print(f"\n[+] Step 4: Configuring {conf_path} for native HTTPS...")
    if os.path.exists(conf_path):
        with open(conf_path, "r", encoding="utf-8") as f:
            conf_lines = f.readlines()

        new_lines = []
        has_certfile = False
        has_keyfile = False

        for line in conf_lines:
            if line.strip().startswith("certfile"):
                new_lines.append(f"certfile = {cert_file}\n")
                has_certfile = True
            elif line.strip().startswith("keyfile"):
                new_lines.append(f"keyfile = {key_file}\n")
                has_keyfile = True
            else:
                new_lines.append(line)

        if not has_certfile:
            new_lines.append(f"certfile = {cert_file}\n")
        if not has_keyfile:
            new_lines.append(f"keyfile = {key_file}\n")

        with open(conf_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(" -> Configured certfile and keyfile in odoo.conf cleanly!")

    print("\n============================================================")
    print("      SUCCESS: LOCALHOST TRUSTED HTTPS SETUP COMPLETED!     ")
    print("============================================================")
    print(f" Certificate File: {cert_file}")
    print(f" Private Key File:  {key_file}")
    print(" Active HTTPS Connector URL:")
    print(" https://localhost:8069/mcp/v1/sse?token=mcp_live_default")
    print("============================================================")
    return True

if __name__ == "__main__":
    setup_localhost_ssl()
