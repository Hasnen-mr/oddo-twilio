import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
host = "dev.gulani@34.55.237.237"

def run_ssh_direct(cmd, label):
    print(f"=== {label} ===")
    ssh_command = ["ssh", "-i", ssh_key, host, cmd]
    res = subprocess.run(ssh_command, capture_output=True, text=True)
    print(f"Exit Code: {res.returncode}")
    if res.stdout:
        print("STDOUT:\n" + res.stdout)
    if res.stderr:
        print("STDERR:\n" + res.stderr)
    return res.returncode == 0

# 1. Update Nginx proxy_pass for /websocket from 8072 to 8069
run_ssh_direct("sudo sed -i 's/127.0.0.1:8072/127.0.0.1:8069/g' /etc/nginx/sites-available/odoo", "1. UPDATING NGINX WEBSOCKET PORT TO 8069")

# 2. Test and reload Nginx
run_ssh_direct("sudo nginx -t && sudo systemctl reload nginx", "2. TESTING AND RELOADING NGINX")

# 3. Test WebSocket endpoint
run_ssh_direct("curl -i -k -N -H 'Upgrade: websocket' -H 'Connection: Upgrade' -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' -H 'Sec-WebSocket-Version: 13' https://odoo.zantatech.com/websocket?version=18.0-7", "3. TESTING HTTPS WEBSOCKET HANDSHAKE")
