# from odoo import models, fields

# class TwilioClickToCallWizard(models.TransientModel):
#     _name = "twilio.click.to.call.wizard"
#     _description = "Twilio Dialer Wizard"

#     from_number = fields.Char(string="From Number")
#     caller_phone = fields.Char(string="Caller Phone")
#     to_number = fields.Char(string="To Number")

#     def press_1(self):
#         self.to_number = (self.to_number or '') + "1"

#     def press_2(self):
#         self.to_number = (self.to_number or '') + "2"

#     def press_3(self):
#         self.to_number = (self.to_number or '') + "3"

#     def press_4(self):
#         self.to_number = (self.to_number or '') + "4"

#     def press_5(self):
#         self.to_number = (self.to_number or '') + "5"

#     def press_6(self):
#         self.to_number = (self.to_number or '') + "6"

#     def press_7(self):
#         self.to_number = (self.to_number or '') + "7"

#     def press_8(self):
#         self.to_number = (self.to_number or '') + "8"

#     def press_9(self):
#         self.to_number = (self.to_number or '') + "9"

#     def press_0(self):
#         self.to_number = (self.to_number or '') + "0"

#     def press_star(self):
#         self.to_number = (self.to_number or '') + "*"

#     def press_hash(self):
#         self.to_number = (self.to_number or '') + "#"

#     def action_initiate_call(self):
#         pass