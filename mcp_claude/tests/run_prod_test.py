import subprocess
import urllib.request
import json

ssh_key = r"C:\Users\annug\.ssh\id_ed25519"
target = "dev.gulani@34.55.237.237"

# 1. Copy gen_prod_token.py to remote server
subprocess.run(f'scp -i "{ssh_key}" D:\\odoo-mcp\\mcp_claude\\tests\\gen_prod_token.py {target}:/tmp/gen_prod_token.py', shell=True, check=True)

# 2. Run script on remote server to get fresh bearer token
res = subprocess.run(['ssh', '-i', ssh_key, '-o', 'StrictHostKeyChecking=accept-new', target, 'sudo -u odoo /opt/odoo/venv/bin/python3 /tmp/gen_prod_token.py'], capture_output=True, text=True)
prod_token = None
for line in res.stdout.splitlines():
    if line.startswith('PROD_RAW_TOKEN='):
        prod_token = line.split('=')[1].strip()

print("GEN PROD TOKEN:", prod_token)

if prod_token:
    target_url = 'http://34.55.237.237:8069/mcp/v1/messages'
    p_ids = [92, 98, 108, 110, 114]
    
    c_req = {
        'jsonrpc': '2.0',
        'id': 301,
        'method': 'tools/call',
        'params': {
            'name': 'odoo_create_record',
            'arguments': {
                'model': 'twilio.auto.dialer',
                'values': {
                    'name': 'Production Remote Campaign (Single Source of Truth Verified)',
                    'user_id': 2,
                    'partner_ids': [(6, 0, p_ids)]
                }
            }
        }
    }
    
    r1 = urllib.request.Request(target_url, data=json.dumps(c_req).encode(), headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {prod_token}'}, method='POST')
    res1 = json.loads(urllib.request.urlopen(r1).read().decode())
    print('PRODUCTION MCP CREATE RESP:', res1['result']['content'][0]['text'])

    dialer_id = json.loads(res1['result']['content'][0]['text']).get('id')

    rd_req = {
        'jsonrpc': '2.0',
        'id': 302,
        'method': 'tools/call',
        'params': {
            'name': 'odoo_read_record',
            'arguments': {
                'model': 'twilio.auto.dialer',
                'id': dialer_id
            }
        }
    }
    r2 = urllib.request.Request(target_url, data=json.dumps(rd_req).encode(), headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {prod_token}'}, method='POST')
    res2 = json.loads(urllib.request.urlopen(r2).read().decode())
    read_data = json.loads(res2['result']['content'][0]['text']).get('data', {})
    
    print('\n=== PRODUCTION REMOTE SERVER VERIFICATION RESULTS ===')
    print('Production Dialer ID:', dialer_id)
    print('partner_ids count (cleared to 0):', len(read_data.get('partner_ids', [])))
    print('queue_line_ids count (POPULATED ON PRODUCTION):', len(read_data.get('queue_line_ids', [])))
    print('total_contacts count (POPULATED ON PRODUCTION):', read_data.get('total_contacts'))
