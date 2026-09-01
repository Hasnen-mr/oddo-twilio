# -*- coding: utf-8 -*-
from odoo import api, models


class IrConfigParameter(models.Model):
    _inherit = "ir.config_parameter"

    @api.model
    def get_param(self, key, default=False):
        """Compatibility shim for Odoo 19 where get_param was renamed to get_str."""
        if hasattr(self, "get_str"):
            val = self.get_str(key, default=None)
            if val is None or (val == "" and default is not False and default is not None):
                return default
            return val
        return super().get_param(key, default=default)

    @api.model
    def set_param(self, key, value):
        """Compatibility shim for Odoo 19 where set_param was renamed to set_str."""
        if hasattr(self, "set_str"):
            return self.set_str(key, str(value or ""))
        return super().set_param(key, value)
