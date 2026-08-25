import sys
sys.path.insert(0, r'D:\Odoo\odoo')
import odoo

odoo.tools.config.parse_config(['-c', r'D:\odoo-mcp\odoo.conf', '-d', 'odoo18'])
with odoo.registry('odoo18').cursor() as cr:
    env = odoo.api.Environment(cr, 2, {})
    service = env['mcp.ai.conversation.service']
    
    # 1. Record Scope Conversation
    rec_conv = service.get_or_create_conversation(scope='record', model_name='res.partner', res_id=92)
    print("1. Record Scope Init:", rec_conv)
    assert rec_conv['scope'] == 'record', "Scope must be record"
    assert rec_conv['title'] == 'res.partner #92', "Title must match record format"

    # 2. Module Scope Conversation
    mod_conv = service.get_or_create_conversation(scope='module', model_name='crm.lead')
    print("2. Module Scope Init:", mod_conv)
    assert mod_conv['scope'] == 'module', "Scope must be module"

    # 3. Global Scope Conversation
    glo_conv = service.get_or_create_conversation(scope='global')
    print("3. Global Scope Init:", glo_conv)
    assert glo_conv['scope'] == 'global', "Scope must be global"

    # 4. Verify scoped isolation (IDs must be distinct)
    assert rec_conv['conversation_id'] != mod_conv['conversation_id'], "Scoped conversations must be isolated"
    assert mod_conv['conversation_id'] != glo_conv['conversation_id'], "Scoped conversations must be isolated"

    cr.rollback()
    print("\nALL HYBRID SCOPE CONVERSATION VERIFICATIONS PASSED PERFECTLY!")
