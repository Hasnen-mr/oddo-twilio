# -*- coding: utf-8 -*-
"""
Integration Test Suite for Representative Odoo 18 Models (Requirement 6)
Executes real ORM search_read and capability checks on core, enterprise, and third-party models.
"""

import sys
import os

sys.path.insert(0, r"D:\Odoo\odoo")

import odoo
odoo.tools.config.parse_config(['-c', r'D:\odoo-mcp\odoo.conf', '-d', 'odoo18'])

import unittest
from odoo.addons.mcp_claude.utils.model_inspector import ModelInspector
from odoo.addons.mcp_claude.registry.tools import ToolRegistry

REPRESENTATIVE_MODELS = [
    'res.partner',
    'res.users',
    'crm.lead',
    'mail.message',
    'mail.activity',
    'ir.attachment',
    'ir.config_parameter',
    'res.config.settings',
    'calendar.event',
    'twilio.call.log',
    'twilio.ai.service',
    'mcp.tool',
    'mcp.api.key'
]

class TestRepresentativeModelsIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.registry = odoo.registry('odoo18')

    def test_representative_models_runtime_execution(self):
        with self.registry.cursor() as cr:
            env = odoo.api.Environment(cr, 2, {})
            
            print("\n" + "="*85)
            print(f"{'MODEL TECHNICAL NAME':<25} | {'CLASSIFICATION':<15} | {'PERMITTED OPS':<25} | {'STATUS':<6}")
            print("="*85)

            for model_name in REPRESENTATIVE_MODELS:
                if model_name not in env:
                    print(f"{model_name:<25} | Not Installed   | Skipped                   | SKIP")
                    continue

                model_obj = env[model_name]
                m_type = ModelInspector.detect_model_type(model_obj)
                caps = ModelInspector.get_model_capabilities(model_obj)
                safe_fields = ModelInspector.get_safe_fields(model_obj)
                
                if m_type == 'abstract':
                    self.assertFalse(caps['search'])
                    self.assertFalse(caps['read'])
                    self.assertTrue(caps['explain'])
                    print(f"{model_name:<25} | AbstractModel    | Explain/Services Only     | PASS")
                
                elif m_type in ('persistent', 'transient'):
                    records = model_obj.sudo().search_read([], fields=safe_fields[:10], limit=2)
                    self.assertIsInstance(records, list)
                    permitted_ops = [k for k, v in caps.items() if v]
                    ops_str = ",".join(permitted_ops[:4])
                    print(f"{model_name:<25} | {m_type.capitalize():<16} | {ops_str:<25} | PASS")

            print("="*85 + "\n")

if __name__ == '__main__':
    unittest.main()
