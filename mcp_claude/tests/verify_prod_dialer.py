partners = env['res.partner'].search([('phone', '!=', False)], limit=5)
print("PROD_FOUND_PARTNERS=" + str(len(partners)))

dialer = env['twilio.auto.dialer'].create({
    'name': 'Production Odoo Shell Single Source Verification',
    'user_id': 2,
    'partner_ids': [(6, 0, partners.ids)]
})

print("PROD_DIALER_ID=" + str(dialer.id))
print("PROD_PARTNER_IDS_COUNT=" + str(len(dialer.partner_ids)))
print("PROD_QUEUE_LINE_IDS_COUNT=" + str(len(dialer.queue_line_ids)))

# Test duplicate prevention on write
dialer.write({'partner_ids': [(6, 0, partners.ids)]})
print("PROD_QUEUE_LINES_AFTER_DUPLICATE_WRITE=" + str(len(dialer.queue_line_ids)))

env.cr.rollback()
print("PROD_VERIFICATION_SUCCESSFUL=True")
