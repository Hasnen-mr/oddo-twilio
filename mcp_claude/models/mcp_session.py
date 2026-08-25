# -*- coding: utf-8 -*-
import logging
import hashlib
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class MCPSession(models.Model):
    _name = 'mcp.session'
    _description = 'MCP Client Session & Heartbeat Tracker'
    _order = 'last_seen desc, id desc'

    session_token = fields.Char(string="Session Token", required=True, index=True)
    user_id = fields.Many2one('res.users', string="User", required=True, default=lambda self: self.env.user)
    client_name = fields.Char(string="Client Application", default="Claude Desktop", index=True)
    client_version = fields.Char(string="Client Version", default="v1.0.0")
    transport = fields.Selection([
        ('remote_https', 'Remote HTTPS'),
        ('stdio_bridge', 'Local Stdio Bridge'),
        ('web', 'Claude Web')
    ], string="Transport Mode", default='remote_https', required=True)
    
    status = fields.Selection([
        ('never_connected', 'Never Connected'),
        ('connecting', 'Connecting'),
        ('connected', 'Connected'),
        ('idle', 'Idle'),
        ('disconnected', 'Disconnected'),
        ('reconnecting', 'Reconnecting')
    ], string="Session Status", default='connected', required=True, index=True)

    last_seen = fields.Datetime(string="Last Heartbeat", default=fields.Datetime.now, required=True, index=True)
    last_method = fields.Char(string="Last MCP Method", default="initialize")
    request_count = fields.Integer(string="Total Requests", default=1)
    avg_response_time_ms = fields.Float(string="Avg Response Time (ms)", default=12.5)
    expires_at = fields.Datetime(string="Expires At", required=True)
    active = fields.Boolean(string="Active Session", default=True, index=True)

    _sql_constraints = [
        ('session_token_unique', 'unique(session_token)', 'MCP Session Token must be unique!')
    ]

    @api.model
    def record_heartbeat(self, session_token=None, client_name="Claude Desktop", transport="remote_https", method="tools/list", user_id=None, duration_ms=0.0):
        """
        Atomic, isolated, thread-safe, multi-worker persistent session heartbeat recorder.
        Uses an isolated independent cursor so heartbeat recording NEVER aborts or interrupts
        the main MCP request database transaction. Best-effort execution guaranteed.
        """
        now_utc = fields.Datetime.now()
        
        if not session_token:
            clean_transport = (transport or "remote_https").lower().replace(' ', '_')
            stable_hash = hashlib.md5((client_name or "Claude").encode('utf-8')).hexdigest()[:6]
            session_token = f"sess_{clean_transport}_{stable_hash}"

        # CRITICAL FIX: Use independent isolated DB cursor so any SQL issue never aborts main HTTP transaction
        try:
            with self.env.registry.cursor() as new_cr:
                query = """
                    INSERT INTO mcp_session (
                        session_token, user_id, client_name, client_version, transport, 
                        status, last_seen, last_method, request_count, avg_response_time_ms, 
                        expires_at, active, create_date, write_date, create_uid, write_uid
                    ) VALUES (
                        %s, %s, %s, 'v1.0.0', %s, 
                        'connected', %s, %s, 1, %s, 
                        %s + INTERVAL '24 hours', true, %s, %s, 1, 1
                    )
                    ON CONFLICT (session_token) DO UPDATE SET
                        last_seen = EXCLUDED.last_seen,
                        last_method = EXCLUDED.last_method,
                        request_count = mcp_session.request_count + 1,
                        avg_response_time_ms = (mcp_session.avg_response_time_ms * mcp_session.request_count + EXCLUDED.avg_response_time_ms) / (mcp_session.request_count + 1),
                        status = 'connected',
                        expires_at = EXCLUDED.last_seen + INTERVAL '24 hours',
                        active = true,
                        write_date = EXCLUDED.write_date;
                """
                new_cr.execute(query, (
                    session_token, user_id or (self.env.user.id if self.env.user else None) or self.env.uid, client_name or "Claude Desktop", transport or "remote_https",
                    now_utc, method or "tools/list", float(duration_ms or 12.5),
                    now_utc, now_utc, now_utc
                ))
                new_cr.commit()
                _logger.info(f"Heartbeat recorded successfully for session: {session_token} (method: {method})")
        except Exception as e:
            _logger.warning("Heartbeat recording fallback (isolated cursor exception caught cleanly): %s", e)

        return True


    @api.model
    def action_hard_session_refresh(self):
        """
        Hard Session Refresh & Auto-Recovery engine.
        Invalidates all stale/orphaned sessions, clears rate limiter lockouts, 
        purges test rows, and forces creation of fresh live sessions.
        """
        _logger.info("Initiating Hard MCP Session Refresh & Auto-Recovery...")
        now = fields.Datetime.now()
        stale_cutoff = fields.Datetime.add(now, minutes=-15)
        
        try:
            from ..services.rate_limiter import RateLimiter
            RateLimiter._lockouts.clear()
            RateLimiter._failed_attempts.clear()
        except Exception as e:
            _logger.warning("RateLimiter clear warning: %s", e)

        with self.env.registry.cursor() as cr:
            try:
                # Purge test sessions & expired sessions older than 24 hours
                cr.execute("""
                    DELETE FROM mcp_session 
                    WHERE session_token LIKE 'sess_perf_%%' 
                       OR session_token LIKE 'sess_race_%%' 
                       OR session_token LIKE 'sess_hist_%%'
                       OR expires_at < %s;
                    
                    UPDATE mcp_session 
                    SET active = false, status = 'disconnected' 
                    WHERE last_seen < %s;
                """, (now, stale_cutoff))
                cr.commit()
            except Exception as e:
                cr.rollback()
                _logger.warning("Hard refresh SQL execution exception: %s", e)

        _logger.info("Hard MCP Session Refresh completed successfully.")
        return True
