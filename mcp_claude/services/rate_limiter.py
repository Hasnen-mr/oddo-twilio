# -*- coding: utf-8 -*-
import time
import logging

_logger = logging.getLogger(__name__)

FAILED_ATTEMPTS = {}
LOCKOUT_DURATION = 900
MAX_FAILED_ATTEMPTS = 5

class RateLimiter:
    @classmethod
    def _is_whitelisted_ip(cls, ip_addr: str) -> bool:
        if not ip_addr:
            return True
        ip = str(ip_addr).strip()
        if ip in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
            return True
        if ip.startswith("10.") or ip.startswith("192.168.") or ip.startswith("172."):
            return True
        return False

    @classmethod
    def is_ip_locked(cls, ip_addr: str) -> bool:
        if cls._is_whitelisted_ip(ip_addr):
            return False
        now = time.time()
        attempts = FAILED_ATTEMPTS.get(ip_addr, [])
        recent = [t for t in attempts if now - t < LOCKOUT_DURATION]
        FAILED_ATTEMPTS[ip_addr] = recent
        return len(recent) >= MAX_FAILED_ATTEMPTS

    @classmethod
    def record_failed_attempt(cls, ip_addr: str):
        if cls._is_whitelisted_ip(ip_addr):
            return
        now = time.time()
        attempts = FAILED_ATTEMPTS.get(ip_addr, [])
        attempts.append(now)
        FAILED_ATTEMPTS[ip_addr] = attempts
        _logger.warning(f"Failed Auth attempt from IP {ip_addr}. Total recent failures: {len(attempts)}")

    @classmethod
    def reset_ip(cls, ip_addr: str):
        if ip_addr in FAILED_ATTEMPTS:
            del FAILED_ATTEMPTS[ip_addr]
