import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
host = "dev.gulani@34.55.237.237"

def run_ssh(cmd, label):
    print(f"==========================================================")
    print(f"SSH AUDIT: {label}")
    print(f"==========================================================")
    ssh_command = f'ssh -i {ssh_key} {host} "{cmd}"'
    res = subprocess.run(ssh_command, shell=True, capture_output=True, text=True)
    print(f"Exit Code: {res.returncode}")
    if res.stdout:
        print("STDOUT:\n" + res.stdout)
    if res.stderr:
        print("STDERR:\n" + res.stderr)
    print("\n")

# 1. Audit /etc/odoo/odoo.conf
run_ssh("cat /etc/odoo/odoo.conf", "1. INSPECTING ODOO CONFIGURATION (/etc/odoo/odoo.conf)")

# 2. Audit Nginx site configs
run_ssh("cat /etc/nginx/sites-enabled/* || cat /etc/nginx/conf.d/* || cat /etc/nginx/nginx.conf", "2. INSPECTING NGINX REVERSE PROXY CONFIGURATION")

# 3. Audit Odoo logs for bus and websocket errors
run_ssh("sudo tail -n 100 /var/log/odoo/odoo.log | grep -E 'bus|websocket|longpolling|gevent|ERROR|WARNING'", "3. INSPECTING ODOO LOGS FOR BUS/WEBSOCKET ERRORS")

# 4. Audit active listening ports
run_ssh("sudo ss -tulpn | grep -E 'python|nginx'", "4. ACTIVE LISTENING PORTS")
