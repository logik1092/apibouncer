"""
Session Management for APIBouncer.

Track projects, manage sessions, log attempts, calculate savings.
"""

import json
import uuid
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable
import os


def get_data_dir() -> Path:
    """Get the data directory for storing sessions and history."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    data_dir = base / "apibouncer"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@dataclass
class Session:
    """A project session."""
    id: str
    name: str
    created: str
    last_activity: str
    status: str = "active"  # active, warned, banned

    # API Access Control
    allowed_keys: List[str] = field(default_factory=list)

    # Model Access Control
    allowed_models: List[str] = field(default_factory=list)
    banned_models: List[str] = field(default_factory=list)
    require_model_whitelist: bool = True

    # Quality Control (for image models)
    allowed_qualities: List[str] = field(default_factory=list)
    banned_qualities: List[str] = field(default_factory=list)

    # Duration Control (for video models)
    max_duration: int = 0

    # Rate Limiting
    rate_limit: int = 0
    rate_limit_period: int = 3600

    # Provider Control
    allowed_providers: List[str] = field(default_factory=list)

    # Budget Control
    budget_limit: float = 0.0

    # Stats
    total_requests: int = 0
    blocked_requests: int = 0
    allowed_requests: int = 0
    total_cost: float = 0.0
    blocked_cost: float = 0.0

    # Warnings
    warning_count: int = 0
    ban_reason: Optional[str] = None

    # Barrier Mode (per-session override)
    barrier_mode: Optional[bool] = None  # None = use global, True/False = override


@dataclass
class Attempt:
    """A single API request attempt."""
    id: str
    session_id: str
    timestamp: str
    provider: str
    model: str
    estimated_cost: float
    status: str  # allowed, blocked, error
    reason: Optional[str] = None

    # Extended data for rich history view
    image_path: Optional[str] = None
    request_params: Optional[Dict] = None
    response_data: Optional[Dict] = None


@dataclass
class BarrierRequest:
    """A pending API request awaiting approval."""
    id: str
    session_id: str
    session_name: str
    timestamp: str
    provider: str
    model: str
    estimated_cost: float
    prompt_preview: str
    params: Dict
    approved: Optional[bool] = None  # None = pending, True = approved, False = denied


class SessionManager:
    """Manage sessions, attempts, and savings."""

    def __init__(self):
        self.data_dir = get_data_dir()
        self.sessions_file = self.data_dir / "sessions.json"
        self.history_file = self.data_dir / "history.json"
        self.settings_file = self.data_dir / "settings.json"

        self.sessions: Dict[str, Session] = {}
        self.history: List[Attempt] = []
        self.settings = {
            "auto_ban_threshold": 10,
            "warning_threshold": 5,
            "max_history": 1000,
            "panic_mode": False,
        }

        # Barrier mode - file-based queue for cross-process IPC
        self.barrier_file = self.data_dir / "barrier_queue.json"
        self.barrier_lock = threading.Lock()
        self.barrier_callback: Optional[Callable] = None  # GUI callback for new requests

        self._load()

    def is_panic_mode(self) -> bool:
        """Check if panic mode is active (all API calls blocked)."""
        return self.settings.get("panic_mode", False)

    def set_panic_mode(self, enabled: bool):
        """Enable/disable panic mode."""
        self.settings["panic_mode"] = enabled
        self._save()

    # =========================================================================
    # Barrier Mode - Request Queue System
    # =========================================================================

    def is_barrier_active(self, session_id: str = None) -> bool:
        """Check if barrier mode is active for a session or globally.

        Always reads fresh from disk to ensure cross-process consistency.
        """
        # Check session-specific override first
        if session_id:
            session = self.sessions.get(session_id)
            if session and session.barrier_mode is not None:
                return session.barrier_mode

        # Read fresh from disk to ensure cross-process consistency
        try:
            if self.settings_file.exists():
                fresh_settings = json.loads(self.settings_file.read_text())
                return fresh_settings.get("barrier_mode", False)
        except (json.JSONDecodeError, IOError):
            pass

        # Fall back to cached setting
        return self.settings.get("barrier_mode", False)

    def set_barrier_callback(self, callback: Callable):
        """Set callback to notify GUI when new requests arrive."""
        self.barrier_callback = callback

    def _load_barrier_queue(self) -> List[dict]:
        """Load barrier queue from file."""
        if self.barrier_file.exists():
            try:
                return json.loads(self.barrier_file.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return []

    def _save_barrier_queue(self, queue: List[dict]):
        """Save barrier queue to file."""
        try:
            self.barrier_file.write_text(json.dumps(queue, indent=2))
        except IOError:
            pass

    def queue_barrier_request(self, session_id: str, provider: str, model: str,
                              cost: float, params: dict = None) -> BarrierRequest:
        """Add a request to the barrier queue and return the request object."""
        session = self.sessions.get(session_id)
        session_name = session.name if session else "Unknown"

        # Extract prompt preview
        prompt_preview = ""
        if params:
            prompt = params.get("prompt", "")
            if prompt:
                prompt_preview = prompt[:150] + ("..." if len(prompt) > 150 else "")

        request = BarrierRequest(
            id=str(uuid.uuid4())[:8],
            session_id=session_id,
            session_name=session_name,
            timestamp=datetime.now().strftime("%H:%M:%S"),
            provider=provider,
            model=model,
            estimated_cost=cost,
            prompt_preview=prompt_preview,
            params=params or {},
        )

        with self.barrier_lock:
            queue = self._load_barrier_queue()
            queue.append(asdict(request))
            self._save_barrier_queue(queue)

        # Notify GUI if callback is set
        if self.barrier_callback:
            try:
                self.barrier_callback()
            except Exception:
                pass

        return request

    def get_pending_requests(self) -> List[BarrierRequest]:
        """Get all pending requests from file."""
        with self.barrier_lock:
            queue = self._load_barrier_queue()
            pending = []
            for item in queue:
                if item.get("approved") is None:
                    pending.append(BarrierRequest(**item))
            return pending

    def approve_request(self, request_id: str):
        """Approve a single request."""
        with self.barrier_lock:
            queue = self._load_barrier_queue()
            for item in queue:
                if item["id"] == request_id and item.get("approved") is None:
                    item["approved"] = True
                    break
            self._save_barrier_queue(queue)

    def deny_request(self, request_id: str):
        """Deny a single request."""
        with self.barrier_lock:
            queue = self._load_barrier_queue()
            for item in queue:
                if item["id"] == request_id and item.get("approved") is None:
                    item["approved"] = False
                    break
            self._save_barrier_queue(queue)

    def approve_all_requests(self):
        """Approve all pending requests."""
        with self.barrier_lock:
            queue = self._load_barrier_queue()
            for item in queue:
                if item.get("approved") is None:
                    item["approved"] = True
            self._save_barrier_queue(queue)

    def deny_all_requests(self):
        """Deny all pending requests."""
        with self.barrier_lock:
            queue = self._load_barrier_queue()
            for item in queue:
                if item.get("approved") is None:
                    item["approved"] = False
            self._save_barrier_queue(queue)

    def clear_completed_requests(self):
        """Remove completed (approved/denied) requests from queue."""
        with self.barrier_lock:
            queue = self._load_barrier_queue()
            queue = [item for item in queue if item.get("approved") is None]
            self._save_barrier_queue(queue)

    def get_request_status(self, request_id: str) -> Optional[bool]:
        """Check if a request has been approved/denied. Returns None if still pending."""
        with self.barrier_lock:
            queue = self._load_barrier_queue()
            for item in queue:
                if item["id"] == request_id:
                    return item.get("approved")
        return None

    def wait_for_approval(self, request_id: str, timeout: float = None, poll_interval: float = 0.3) -> bool:
        """Wait for a request to be approved or denied. Returns True if approved."""
        import time
        start = time.time()
        while True:
            status = self.get_request_status(request_id)
            if status is not None:
                return status == True

            if timeout and (time.time() - start) >= timeout:
                return False  # Timeout - treat as denied

            time.sleep(poll_interval)

    def _load(self):
        """Load data from files."""
        if self.sessions_file.exists():
            try:
                data = json.loads(self.sessions_file.read_text())
                for sid, sdata in data.items():
                    # Handle missing fields
                    defaults = {
                        'allowed_keys': [],
                        'allowed_models': [],
                        'banned_models': [],
                        'require_model_whitelist': True,
                        'rate_limit': 0,
                        'rate_limit_period': 3600,
                        'budget_limit': 0.0,
                        'allowed_qualities': [],
                        'banned_qualities': [],
                        'max_duration': 0,
                        'barrier_mode': None,
                    }
                    for key, default in defaults.items():
                        if key not in sdata:
                            sdata[key] = default
                    self.sessions[sid] = Session(**sdata)
            except (json.JSONDecodeError, TypeError):
                pass

        if self.history_file.exists():
            try:
                data = json.loads(self.history_file.read_text())
                for a in data:
                    a.setdefault('image_path', None)
                    a.setdefault('request_params', None)
                    a.setdefault('response_data', None)
                self.history = [Attempt(**a) for a in data]
            except (json.JSONDecodeError, TypeError):
                pass

        if self.settings_file.exists():
            try:
                self.settings.update(json.loads(self.settings_file.read_text()))
            except json.JSONDecodeError:
                pass

    def _save(self):
        """Save data to files."""
        sessions_data = {sid: asdict(s) for sid, s in self.sessions.items()}
        self.sessions_file.write_text(json.dumps(sessions_data, indent=2))

        history_data = [asdict(a) for a in self.history[-self.settings["max_history"]:]]
        self.history_file.write_text(json.dumps(history_data, indent=2))

        self.settings_file.write_text(json.dumps(self.settings, indent=2))

    def create_session(self, name: str, allowed_keys: List[str] = None) -> Session:
        """Create a new session for a project."""
        import secrets
        import string
        chars = string.ascii_uppercase + string.digits
        prefix = ''.join(secrets.choice(chars) for _ in range(4))
        suffix = ''.join(secrets.choice(chars) for _ in range(12))
        session_id = f"APBN-{prefix}-{suffix}"
        now = datetime.now().isoformat()

        session = Session(
            id=session_id,
            name=name,
            created=now,
            last_activity=now,
            allowed_keys=allowed_keys or [],
        )

        self.sessions[session_id] = session
        self._save()
        return session

    def update_session_keys(self, session_id: str, allowed_keys: List[str]):
        """Update which API keys a session can access."""
        session = self.sessions.get(session_id)
        if session:
            session.allowed_keys = allowed_keys
            self._save()

    def update_session_models(self, session_id: str, allowed_models: List[str], banned_models: List[str], require_whitelist: bool = True):
        """Update which models a session can use."""
        session = self.sessions.get(session_id)
        if session:
            session.allowed_models = allowed_models
            session.banned_models = banned_models
            session.require_model_whitelist = require_whitelist
            self._save()

    def update_session_budget(self, session_id: str, budget_limit: float):
        """Update a session's budget limit."""
        session = self.sessions.get(session_id)
        if session:
            session.budget_limit = float(budget_limit)
            self._save()

    def is_model_allowed(self, session_id: str, model: str) -> tuple[bool, str]:
        """Check if a model is allowed for this session."""
        session = self.sessions.get(session_id)
        if not session:
            return False, "Unknown session ID"

        global_banned = self.settings.get("global_banned_models", [])
        for banned in global_banned:
            if banned.endswith("*"):
                if model.startswith(banned[:-1]):
                    return False, f"Model '{model}' is globally banned"
            elif model == banned:
                return False, f"Model '{model}' is globally banned"

        if session.banned_models:
            for banned in session.banned_models:
                if banned.endswith("*"):
                    if model.startswith(banned[:-1]):
                        return False, f"Model '{model}' is banned (matches '{banned}')"
                elif model == banned:
                    return False, f"Model '{model}' is banned"

        if session.allowed_models:
            for allowed in session.allowed_models:
                if allowed.endswith("*"):
                    if model.startswith(allowed[:-1]):
                        return True, "OK"
                elif model == allowed:
                    return True, "OK"
            return False, f"Model '{model}' not in allowed list"

        if session.require_model_whitelist:
            return False, "No models allowed - add models to whitelist"

        return True, "OK"

    def is_quality_allowed(self, session_id: str, quality: str) -> tuple[bool, str]:
        """Check if a quality setting is allowed for this session."""
        session = self.sessions.get(session_id)
        if not session:
            return False, "Unknown session ID"

        quality = quality.lower()

        if session.banned_qualities:
            if quality in [q.lower() for q in session.banned_qualities]:
                return False, f"Quality '{quality}' is banned"

        if session.allowed_qualities:
            if quality not in [q.lower() for q in session.allowed_qualities]:
                return False, f"Quality '{quality}' not in allowed list"

        return True, "OK"

    def is_duration_allowed(self, session_id: str, duration: int) -> tuple[bool, str]:
        """Check if a video duration is allowed for this session."""
        session = self.sessions.get(session_id)
        if not session:
            return False, "Unknown session ID"

        if session.max_duration > 0 and duration > session.max_duration:
            return False, f"Duration {duration}s exceeds limit ({session.max_duration}s max)"

        return True, "OK"

    def is_rate_limited(self, session_id: str) -> tuple[bool, str, int]:
        """Check if session has exceeded its rate limit."""
        session = self.sessions.get(session_id)
        if not session:
            return True, "Unknown session ID", 0

        if session.rate_limit <= 0:
            return False, "OK", 0

        now = datetime.now()
        period_start = now - timedelta(seconds=session.rate_limit_period)

        recent_count = 0
        oldest_in_period = None
        for attempt in self.history:
            if attempt.session_id != session_id:
                continue
            if attempt.status != "allowed":
                continue
            try:
                attempt_time = datetime.fromisoformat(attempt.timestamp)
                if attempt_time >= period_start:
                    recent_count += 1
                    if oldest_in_period is None or attempt_time < oldest_in_period:
                        oldest_in_period = attempt_time
            except (ValueError, TypeError):
                continue

        if recent_count >= session.rate_limit:
            if oldest_in_period:
                reset_time = oldest_in_period + timedelta(seconds=session.rate_limit_period)
                seconds_until_reset = max(0, int((reset_time - now).total_seconds()))
            else:
                seconds_until_reset = session.rate_limit_period

            period_desc = self._format_period(session.rate_limit_period)
            return True, f"Rate limit exceeded ({session.rate_limit} per {period_desc})", seconds_until_reset

        return False, "OK", 0

    def _format_period(self, seconds: int) -> str:
        """Format period in human readable form."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}min"
        elif seconds < 86400:
            return f"{seconds // 3600}hr"
        else:
            return f"{seconds // 86400}day"

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self.sessions.get(session_id)

    def is_session_allowed(self, session_id: str) -> tuple[bool, str]:
        """Check if a session is allowed to make requests."""
        session = self.sessions.get(session_id)

        if not session:
            return False, "Unknown session ID"

        if session.status == "banned":
            return False, f"Session banned: {session.ban_reason}"

        if session.budget_limit > 0 and session.total_cost >= session.budget_limit:
            return False, f"Budget limit exceeded (${session.budget_limit:.2f})"

        return True, "OK"

    def record_attempt(
        self,
        session_id: str,
        provider: str,
        model: str,
        estimated_cost: float,
        allowed: bool,
        reason: Optional[str] = None,
        image_path: Optional[str] = None,
        request_params: Optional[Dict] = None,
        response_data: Optional[Dict] = None,
    ) -> Attempt:
        """Record an API request attempt."""
        attempt_id = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()

        attempt = Attempt(
            id=attempt_id,
            session_id=session_id,
            timestamp=now,
            provider=provider,
            model=model,
            estimated_cost=estimated_cost,
            status="allowed" if allowed else "blocked",
            reason=reason,
            image_path=image_path,
            request_params=request_params,
            response_data=response_data,
        )

        self.history.append(attempt)

        session = self.sessions.get(session_id)
        if session:
            session.last_activity = now
            session.total_requests += 1

            if allowed:
                session.allowed_requests += 1
                session.total_cost += estimated_cost
            else:
                session.blocked_requests += 1
                session.blocked_cost += estimated_cost

                if session.blocked_requests >= self.settings["auto_ban_threshold"]:
                    session.status = "banned"
                    session.ban_reason = f"Auto-banned: {session.blocked_requests} blocked requests"
                elif session.blocked_requests >= self.settings["warning_threshold"]:
                    session.status = "warned"
                    session.warning_count += 1

        self._save()
        return attempt

    def ban_session(self, session_id: str, reason: str = "Manual ban"):
        """Ban a session."""
        session = self.sessions.get(session_id)
        if session:
            session.status = "banned"
            session.ban_reason = reason
            self._save()

    def unban_session(self, session_id: str):
        """Unban a session."""
        session = self.sessions.get(session_id)
        if session:
            session.status = "active"
            session.ban_reason = None
            session.warning_count = 0
            self._save()

    def warn_session(self, session_id: str):
        """Issue a warning to a session."""
        session = self.sessions.get(session_id)
        if session:
            session.status = "warned"
            session.warning_count += 1
            self._save()

    def reset_session_stats(self, session_id: str):
        """Reset a session's statistics."""
        session = self.sessions.get(session_id)
        if session:
            session.total_requests = 0
            session.blocked_requests = 0
            session.allowed_requests = 0
            session.total_cost = 0.0
            session.blocked_cost = 0.0
            session.warning_count = 0
            self._save()

    def delete_session(self, session_id: str):
        """Delete a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._save()

    def get_total_savings(self) -> float:
        """Get total money saved across all sessions."""
        return sum(s.blocked_cost for s in self.sessions.values())

    def get_total_spent(self) -> float:
        """Get total money spent across all sessions."""
        return sum(s.total_cost for s in self.sessions.values())

    def get_recent_history(self, limit: int = 50) -> List[Attempt]:
        """Get recent attempt history."""
        return list(reversed(self.history[-limit:]))

    def get_session_history(self, session_id: str, limit: int = 50) -> List[Attempt]:
        """Get attempt history for a specific session."""
        session_history = [a for a in self.history if a.session_id == session_id]
        return list(reversed(session_history[-limit:]))

    def clear_session_history(self, session_id: str):
        """Clear all history for a specific session."""
        self.history = [a for a in self.history if a.session_id != session_id]
        self._save()

    def get_stats(self) -> dict:
        """Get overall statistics."""
        total_requests = sum(s.total_requests for s in self.sessions.values())
        total_blocked = sum(s.blocked_requests for s in self.sessions.values())
        total_allowed = sum(s.allowed_requests for s in self.sessions.values())

        return {
            "total_sessions": len(self.sessions),
            "active_sessions": sum(1 for s in self.sessions.values() if s.status == "active"),
            "warned_sessions": sum(1 for s in self.sessions.values() if s.status == "warned"),
            "banned_sessions": sum(1 for s in self.sessions.values() if s.status == "banned"),
            "total_requests": total_requests,
            "total_blocked": total_blocked,
            "total_allowed": total_allowed,
            "block_rate": (total_blocked / total_requests * 100) if total_requests > 0 else 0,
            "total_spent": self.get_total_spent(),
            "total_saved": self.get_total_savings(),
        }


# Global instance
_manager: Optional[SessionManager] = None

def get_session_manager() -> SessionManager:
    """Get the global session manager."""
    global _manager
    if _manager is None:
        _manager = SessionManager()
    return _manager
