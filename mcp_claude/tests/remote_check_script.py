mods = env['ir.module.module'].search([('name', 'like', 'twilio')], order='name asc')
for m in mods:
    print('PROD_MOD=' + m.name + '=' + m.state)
