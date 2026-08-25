import sys
sys.path.insert(0, '/opt/odoo/odoo18')
import odoo

odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo18'])
with odoo.registry('odoo18').cursor() as cr:
    env = odoo.api.Environment(cr, 2, {})
    rec = env['mcp.api.key'].create({
        'name': 'Prod Verification Key',
        'key_prefix': 'pver1234',
        'key_hash': 'dummy_hash_for_test',
        'user_id': 2,
        'active': True
    })
    raw_token = env['mcp.api.key'].generate_opaque_connector_token('Prod Verification Key')
    cr.commit()
    print("PROD_RAW_TOKEN=" + str(raw_token))
