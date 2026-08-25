# -*- coding: utf-8 -*-
"""
ModelInspector Utility Class
Stateless model introspection engine for Odoo 18.
Uses native ORM field metadata (store, compute, groups, attachment, type) for classification.
"""

import logging
from typing import Dict, Any, List, Optional

_logger = logging.getLogger(__name__)

# Documented Last-Resort Fallback: Odoo ORM uses standard 'char' field type for security credentials.
# Name-based fallback is strictly used for password/secret credential masking.
SENSITIVE_FIELD_NAMES = {
    'password', 'secret', 'api_key', 'access_token', 'refresh_token',
    'client_secret', 'private_key', 'auth_token', 'app_secret'
}

class ModelInspector:

    @classmethod
    def detect_model_type(cls, model_obj: Any) -> str:
        """
        Detect Odoo Model Type using native ORM attributes.
        Returns:
            'abstract'   for models.AbstractModel (_abstract = True)
            'transient'  for models.TransientModel (_transient = True)
            'persistent' for models.Model (_abstract = False, _transient = False)
        """
        if getattr(model_obj, '_abstract', False):
            return 'abstract'
        if getattr(model_obj, '_transient', False):
            return 'transient'
        return 'persistent'

    @classmethod
    def detect_mixins(cls, model_obj: Any) -> List[str]:
        """Detect mixin inheritance using model ORM inheritance hierarchy."""
        inherits = getattr(model_obj, '_inherit', [])
        if isinstance(inherits, str):
            inherits = [inherits]
        inherits = inherits or []
        mixins = [i for i in inherits if i in (
            'mail.thread', 'mail.activity.mixin', 'portal.mixin',
            'website.mixin', 'image.mixin', 'rating.mixin'
        )]
        return mixins

    @classmethod
    def check_model_access(cls, model_obj: Any, operation: str) -> bool:
        """
        Check if current user context has ORM access rights for the given operation.
        Uses native Odoo 18 check_access API.
        """
        mode_map = {
            'search': 'read',
            'search_read': 'read',
            'read': 'read',
            'create': 'create',
            'write': 'write',
            'unlink': 'unlink',
            'aggregate': 'read',
            'explain': 'read',
            'call_method': 'read'
        }
        mode = mode_map.get(operation, 'read')
        try:
            if hasattr(model_obj, 'check_access'):
                model_obj.check_access(mode)
                return True
            return True
        except Exception:
            return False

    @classmethod
    def get_model_capabilities(cls, model_obj: Any) -> Dict[str, bool]:
        """
        Build technical & permission capability matrix for the given Odoo model.
        Returns dictionary mapping operations to boolean capability.
        """
        m_type = cls.detect_model_type(model_obj)
        
        if m_type == 'abstract':
            return {
                'search': False,
                'search_read': False,
                'read': False,
                'create': False,
                'write': False,
                'unlink': False,
                'aggregate': False,
                'explain': True,
                'call_method': True
            }
        elif m_type == 'transient':
            has_read = cls.check_model_access(model_obj, 'read')
            has_create = cls.check_model_access(model_obj, 'create')
            has_write = cls.check_model_access(model_obj, 'write')
            return {
                'search': has_read,
                'search_read': has_read,
                'read': has_read,
                'create': has_create,
                'write': has_write,
                'unlink': False,  # Prevent unlinking wizard transient context
                'aggregate': False,
                'explain': True,
                'call_method': True
            }
        else: # persistent models.Model
            has_read = cls.check_model_access(model_obj, 'read')
            has_create = cls.check_model_access(model_obj, 'create')
            has_write = cls.check_model_access(model_obj, 'write')
            has_unlink = cls.check_model_access(model_obj, 'unlink')
            return {
                'search': has_read,
                'search_read': has_read,
                'read': has_read,
                'create': has_create,
                'write': has_write,
                'unlink': has_unlink,
                'aggregate': has_read,
                'explain': True,
                'call_method': True
            }

    @classmethod
    def get_safe_fields(cls, model_obj: Any, requested_fields: Optional[List[str]] = None) -> List[str]:
        """
        Metadata-driven safe field classifier.
        Uses native Odoo Field instance attributes (_fields) as primary detection mechanism.
        """
        fields_dict = getattr(model_obj, '_fields', {})
        if not fields_dict:
            try:
                fields_meta = model_obj.fields_get()
                return list(fields_meta.keys())
            except Exception:
                return ['id', 'display_name']

        safe_fields = []
        for fname, ffield in fields_dict.items():
            if requested_fields and fname not in requested_fields:
                continue

            # 1. Type Metadata Check (Binary, HTML, Reference payloads)
            ftype = getattr(ffield, 'type', '')
            if ftype in ('binary', 'html', 'reference'):
                continue

            # 2. Attachment-Backed Field Metadata Check
            if getattr(ffield, 'attachment', False):
                continue

            # 3. Security Groups Metadata Check (Restricted admin/system fields)
            fgroups = getattr(ffield, 'groups', None)
            if fgroups and ('base.group_system' in fgroups or 'base.group_erp_manager' in fgroups):
                continue

            # 4. Unstored Computed Field Check (Chatter & Activity mixin computed fields)
            # Unstored computed fields require runtime session computation (e.g. mail_thread message_has_error).
            is_stored = getattr(ffield, 'store', True)
            is_computed = bool(getattr(ffield, 'compute', None))
            if is_computed and not is_stored and fname not in ('id', 'name', 'display_name'):
                continue

            # 5. Documented Last-Resort Name Fallback for Security Credentials
            # Rationale: Odoo ORM uses standard 'char' field type for API keys and passwords.
            # Name matching ensures credential privacy.
            if fname in SENSITIVE_FIELD_NAMES:
                continue

            safe_fields.append(fname)

        if 'id' not in safe_fields and 'id' in fields_dict:
            safe_fields.insert(0, 'id')
        if 'display_name' not in safe_fields and 'display_name' in fields_dict:
            safe_fields.append('display_name')

        return safe_fields
