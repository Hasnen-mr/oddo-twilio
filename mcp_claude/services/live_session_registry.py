# -*- coding: utf-8 -*-
import time
import logging
from datetime import datetime, timezone

_logger = logging.getLogger(__name__)

class LiveSessionRegistry:
    """
    In-Memory High-Performance Live MCP Session Registry & Heartbeat Tracker.
    Determines real-time connection state for Claude AI connections.
    """
    _sessions = {} # { session_id: { 'client': str, 'transport': str, 'last_seen': float, 'last_method': str, 'request_count': int, 'connected_since': float, 'user': str } }

    @classmethod
    def record_heartbeat(cls, session_id=None, client_name="Claude Desktop", transport="Remote HTTPS", method="tools/list", user_name="Admin"):
        now = time.time()
        if not session_id:
            clean_mode = transport.lower().replace(' ', '_')
            session_id = f"sess_{clean_mode}_{abs(hash(client_name)) % 10000:04d}"
        
        if session_id not in cls._sessions:
            cls._sessions[session_id] = {
                "session_id": session_id,
                "client": client_name,
                "transport": transport,
                "connected_since": now,
                "connected_since_dt": datetime.now(),
                "request_count": 0,
                "user": user_name
            }
        
        sess = cls._sessions[session_id]
        sess["last_seen"] = now
        sess["last_seen_dt"] = datetime.now()
        sess["last_method"] = method
        sess["request_count"] += 1
        sess["client"] = client_name
        sess["transport"] = transport
        return session_id

    @classmethod
    def get_live_status(cls, env=None):
        now = time.time()
        
        # Clean up expired stale sessions (> 10 mins inactive)
        stale_ids = [sid for sid, s in cls._sessions.items() if (now - s["last_seen"]) > 600]
        for sid in stale_ids:
            del cls._sessions[sid]

        # If no active in-memory session exists, check recent DB audit logs to recover active session
        if not cls._sessions and env is not None:
            try:
                last_log = env['mcp.audit.log'].sudo().search([], order='id desc', limit=1)
                if last_log and last_log.create_date:
                    db_dt = last_log.create_date
                    db_delta = max(0, int((datetime.now() - db_dt).total_seconds()))
                    total_logs = env['mcp.audit.log'].sudo().search_count([])
                    if total_logs > 0:
                        has_oauth = env['mcp.oauth.client'].sudo().search_count([]) > 0
                        mode = "Remote HTTPS" if has_oauth else "Local Stdio Bridge"
                        cls.record_heartbeat(
                            client_name="Claude Desktop",
                            transport=mode,
                            method=last_log.action_type or "tools/call",
                            user_name=last_log.user_id.name if last_log.user_id else "Admin"
                        )
                        active_sess = list(cls._sessions.values())[0]
                        active_sess["last_seen"] = now - db_delta
                        active_sess["request_count"] = total_logs
            except Exception as e:
                _logger.warning("Error recovering session from DB audit log: %s", e)

        if not cls._sessions:
            return {
                "active_session": None,
                "active_sessions_count": 0,
                "status": "never_connected",
                "connected": False,
                "status_label": "Never Connected",
                "status_subtitle": "No live heartbeat or transport session detected",
                "badge_class": "bg-secondary text-white",
                "icon_symbol": "⚫",
                "mode": "Not Available",
                "last_activity_text": "Never",
                "last_activity_iso": ""
            }

        sorted_sessions = sorted(cls._sessions.values(), key=lambda s: s["last_seen"], reverse=True)
        active_sess = sorted_sessions[0]
        delta_sec = max(0, int(now - active_sess["last_seen"]))

        # Real-time connection timeout state machine:
        # <= 120s: Connected (🟢)
        # 120s - 300s: Idle (🔵)
        # > 300s: Disconnected (🔴)
        if delta_sec <= 120:
            status = "connected"
            status_label = "Connected"
            status_subtitle = "Live MCP Heartbeat Active"
            badge_class = "bg-success text-white"
            icon_symbol = "🟢"
            connected = True
        elif delta_sec <= 300:
            status = "idle"
            status_label = "Idle"
            status_subtitle = "Claude connected, no heartbeat in > 2 min"
            badge_class = "bg-info text-white"
            icon_symbol = "🔵"
            connected = True
        else:
            status = "disconnected"
            status_label = "Disconnected"
            status_subtitle = "Heartbeat timed out (> 5 min)"
            badge_class = "bg-danger text-white"
            icon_symbol = "🔴"
            connected = False

        if delta_sec < 10:
            last_act_text = "Just now"
        elif delta_sec < 60:
            last_act_text = f"{delta_sec} seconds ago"
        elif delta_sec < 3600:
            mins = max(1, delta_sec // 60)
            last_act_text = f"{mins} minute{'s' if mins > 1 else ''} ago"
        else:
            hours = delta_sec // 3600
            last_act_text = f"{hours} hour{'s' if hours > 1 else ''} ago"

        conn_since_sec = max(0, int(now - active_sess["connected_since"]))
        if conn_since_sec < 60:
            conn_since_text = f"{conn_since_sec}s ago"
        elif conn_since_sec < 3600:
            conn_since_text = f"{conn_since_sec // 60}m ago"
        else:
            conn_since_text = f"{conn_since_sec // 3600}h ago"

        return {
            "active_session": {
                "session_id": active_sess["session_id"],
                "client": active_sess["client"],
                "transport": active_sess["transport"],
                "request_count": active_sess["request_count"],
                "last_method": active_sess["last_method"],
                "connected_since_text": conn_since_text
            },
            "active_sessions_count": len(cls._sessions),
            "status": status,
            "connected": connected,
            "status_label": status_label,
            "status_subtitle": status_subtitle,
            "badge_class": badge_class,
            "icon_symbol": icon_symbol,
            "mode": active_sess["transport"],
            "last_activity_text": last_act_text,
            "last_activity_iso": datetime.fromtimestamp(active_sess["last_seen"], timezone.utc).isoformat(),
            "client_name": active_sess["client"],
            "client_version": "v1.0.0"
        }
