# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any

_logger = logging.getLogger(__name__)

class LifecycleHooksManager:
    @classmethod
    def before_execute(cls, tool_name: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        return params

    @classmethod
    def after_execute(cls, tool_name: str, result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        return result

    @classmethod
    def on_error(cls, tool_name: str, exception: Exception, context: Dict[str, Any]):
        pass
