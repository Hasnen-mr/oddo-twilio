import subprocess

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
host = "dev.gulani@34.55.237.237"

cmd = 'sudo cat /etc/odoo/odoo.conf'
res = subprocess.run(f'ssh -i {ssh_key} {host} "{cmd}"', shell=True, capture_output=True, text=True)
print("=== /etc/odoo/odoo.conf CONTENTS ===")
print(res.stdout)
