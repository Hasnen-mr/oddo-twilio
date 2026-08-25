# -*- coding: utf-8 -*-
"""
Stateless Cryptographic & Security Utilities for mcp_claude
Zero ORM dependencies for maximum performance and unit testability.
"""

import hmac
import hashlib
import secrets
import base64

def generate_random_secret(length: int = 32) -> str:
    """Generate a cryptographically secure random hex string."""
    return secrets.token_hex(length)

def compare_digests(val1: str, val2: str) -> bool:
    """Constant-time string comparison to prevent timing attacks."""
    if not val1 or not val2:
        return False
    return hmac.compare_digest(str(val1).strip(), str(val2).strip())

def compute_hmac_signature(secret: str, message: str) -> str:
    """Compute HMAC-SHA256 signature for a message given a secret."""
    key = secret.encode('utf-8')
    msg = message.encode('utf-8')
    return hmac.new(key, msg, hashlib.sha256).hexdigest()

def verify_pkce_challenge(code_verifier: str, code_challenge: str, method: str = 'S256') -> bool:
    """Verify OAuth 2.0 PKCE challenge (RFC 7636)."""
    if not code_verifier or not code_challenge:
        return False
    if method == 'plain':
        return compare_digests(code_verifier, code_challenge)
    elif method == 'S256':
        digest = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        computed_challenge = base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')
        return compare_digests(computed_challenge, code_challenge)
    return False
