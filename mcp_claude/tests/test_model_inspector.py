# -*- coding: utf-8 -*-
"""
Unit Test Suite for ModelInspector Utility (Phase 1-5 Capability Matrix Verification)
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, r"D:\Odoo\odoo")
sys.path.insert(0, r"D:\odoo-mcp")

import odoo
import odoo.addons
if r"D:\odoo-mcp" not in odoo.addons.__path__:
    odoo.addons.__path__.append(r"D:\odoo-mcp")

from odoo.addons.mcp_claude.utils.model_inspector import ModelInspector

class TestModelInspector(unittest.TestCase):

    def test_detect_model_type_persistent(self):
        model = MagicMock()
        model._abstract = False
        model._transient = False
        self.assertEqual(ModelInspector.detect_model_type(model), 'persistent')

    def test_detect_model_type_abstract(self):
        model = MagicMock()
        model._abstract = True
        model._transient = False
        self.assertEqual(ModelInspector.detect_model_type(model), 'abstract')

    def test_detect_model_type_transient(self):
        model = MagicMock()
        model._abstract = False
        model._transient = True
        self.assertEqual(ModelInspector.detect_model_type(model), 'transient')

    def test_detect_mixins(self):
        model = MagicMock()
        model._inherit = ['mail.thread', 'mail.activity.mixin', 'custom.mixin']
        mixins = ModelInspector.detect_mixins(model)
        self.assertIn('mail.thread', mixins)
        self.assertIn('mail.activity.mixin', mixins)
        self.assertNotIn('custom.mixin', mixins)

    def test_abstract_model_capabilities(self):
        model = MagicMock()
        model._abstract = True
        model.check_access.return_value = False
        caps = ModelInspector.get_model_capabilities(model)
        self.assertFalse(caps['search'])
        self.assertFalse(caps['read'])
        self.assertFalse(caps['create'])
        self.assertFalse(caps['write'])
        self.assertFalse(caps['unlink'])
        self.assertTrue(caps['explain'])

    def test_persistent_model_capabilities(self):
        model = MagicMock()
        model._abstract = False
        model._transient = False
        model.check_access.return_value = True
        caps = ModelInspector.get_model_capabilities(model)
        self.assertTrue(caps['search'])
        self.assertTrue(caps['read'])
        self.assertTrue(caps['create'])
        self.assertTrue(caps['write'])
        self.assertTrue(caps['unlink'])

    def test_get_safe_fields_filters_chatter_and_sensitive(self):
        model = MagicMock()
        model._name = 'test.model'
        
        f_id = MagicMock(type='integer', store=True, compute=None, attachment=False, groups=None)
        f_name = MagicMock(type='char', store=True, compute=None, attachment=False, groups=None)
        f_pass = MagicMock(type='char', store=True, compute=None, attachment=False, groups=None)
        f_secret = MagicMock(type='char', store=True, compute=None, attachment=False, groups=None)
        f_msg = MagicMock(type='boolean', store=False, compute='_compute_msg', attachment=False, groups=None)
        f_avatar = MagicMock(type='binary', store=True, compute=None, attachment=False, groups=None)

        model._fields = {
            'id': f_id,
            'name': f_name,
            'password': f_pass,
            'secret': f_secret,
            'message_has_error': f_msg,
            'avatar': f_avatar,
        }
        
        safe_fields = ModelInspector.get_safe_fields(model)
        self.assertIn('id', safe_fields)
        self.assertIn('name', safe_fields)
        self.assertNotIn('password', safe_fields)
        self.assertNotIn('secret', safe_fields)
        self.assertNotIn('message_has_error', safe_fields)
        self.assertNotIn('avatar', safe_fields)

if __name__ == '__main__':
    unittest.main()
