"""
APIBouncer Provider Proxy

AI agents call these functions. They NEVER see API keys.
Keys are injected internally, requests are validated, costs are tracked.

ADDING NEW PROVIDERS:
---------------------
1. Create a class that inherits from BaseProvider
2. Set PROVIDER_NAME and DEFAULT_COSTS
3. Implement your API methods using self.validate() and self.record()

Example:
    class MyProvider(BaseProvider):
        PROVIDER_NAME = "myprovider"
        DEFAULT_COSTS = {"model-1": 0.01, "model-2": 0.05}

        def generate(self, session_id, prompt, model="model-1"):
            cost = self.get_cost(model)
            self.validate(session_id, model, cost)

            # Make your API call here
            api_key = self.get_key()
            response = requests.post(...)

            self.record(session_id, model, cost, True)
            return response
"""

import requests
import base64
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

try:
    import keyring
except ImportError:
    keyring = None

SERVICE_NAME = "apibouncer"


def _get_images_dir() -> Path:
    """Get the directory for auto-saved images."""
    from .sessions import get_data_dir
    images_dir = get_data_dir() / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    return images_dir


def _generate_image_path(session_id: str, model: str) -> Path:
    """Generate a unique path for auto-saving an image."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    session_prefix = session_id.split("-")[1] if "-" in session_id else session_id[:4]
    filename = f"{session_prefix}_{timestamp}_{unique_id}.png"
    return _get_images_dir() / filename


def _get_key(provider: str) -> str:
    """Get API key from secure storage. Never exposed to AI."""
    if not keyring:
        raise RuntimeError("keyring not installed")
    key = keyring.get_password(SERVICE_NAME, provider)
    if not key:
        raise RuntimeError(f"No API key configured for '{provider}'")
    return key


def _check_session(session_id: str):
    """Validate session is allowed."""
    from .sessions import get_session_manager
    mgr = get_session_manager()

    # PANIC MODE - Block ALL API calls immediately
    if mgr.is_panic_mode():
        raise PermissionError("PANIC MODE ACTIVE - All API calls blocked")

    allowed, msg = mgr.is_session_allowed(session_id)
    if not allowed:
        raise PermissionError(f"Session blocked: {msg}")
    return mgr


def _check_model(mgr, session_id: str, model: str):
    """Validate model is allowed."""
    allowed, msg = mgr.is_model_allowed(session_id, model)
    if not allowed:
        raise PermissionError(f"Model blocked: {msg}")


def _check_quality(mgr, session_id: str, quality: str):
    """Validate quality is allowed."""
    allowed, msg = mgr.is_quality_allowed(session_id, quality)
    if not allowed:
        raise PermissionError(f"Quality blocked: {msg}")


def _check_duration(mgr, session_id: str, duration: int):
    """Validate duration is allowed."""
    allowed, msg = mgr.is_duration_allowed(session_id, duration)
    if not allowed:
        raise PermissionError(f"Duration blocked: {msg}")


def _check_rate_limit(mgr, session_id: str):
    """Validate request is within rate limits."""
    limited, msg, reset_seconds = mgr.is_rate_limited(session_id)
    if limited:
        if reset_seconds > 0:
            raise PermissionError(f"Rate limited: {msg}. Try again in {reset_seconds}s")
        raise PermissionError(f"Rate limited: {msg}")


def _get_videos_dir() -> Path:
    """Get the directory for auto-saved videos."""
    from .sessions import get_data_dir
    videos_dir = get_data_dir() / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    return videos_dir


def _generate_video_path(session_id: str, model: str) -> Path:
    """Generate a unique path for auto-saving a video."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    session_prefix = session_id.split("-")[1] if "-" in session_id else session_id[:4]
    filename = f"{session_prefix}_{timestamp}_{unique_id}.mp4"
    return _get_videos_dir() / filename


def _get_audio_dir() -> Path:
    """Get the directory for auto-saved audio."""
    from .sessions import get_data_dir
    audio_dir = get_data_dir() / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    return audio_dir


def _generate_audio_path(session_id: str, model: str, ext: str = "mp3") -> Path:
    """Generate a unique path for auto-saving audio."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    session_prefix = session_id.split("-")[1] if "-" in session_id else session_id[:4]
    filename = f"{session_prefix}_{timestamp}_{unique_id}.{ext}"
    return _get_audio_dir() / filename


def _record(mgr, session_id: str, provider: str, model: str, cost: float, allowed: bool,
            reason: str = None, image_path: str = None, request_params: dict = None, response_data: dict = None):
    """Record the request with optional extended data for history view."""
    mgr.record_attempt(session_id, provider, model, cost, allowed, reason,
                       image_path=image_path, request_params=request_params, response_data=response_data)


# =============================================================================
# Read-Only Query API for AI Agents
# =============================================================================

class Query:
    """
    Read-only information for AI agents. NO control over settings.
    AI can see stats but cannot change anything.
    """

    @staticmethod
    def session_info(session_id: str) -> Dict[str, Any]:
        """Get session information (read-only)."""
        from .sessions import get_session_manager
        mgr = get_session_manager()
        session = mgr.get_session(session_id)
        if not session:
            return {"error": "Session not found"}

        return {
            "name": session.name,
            "status": session.status,
            "budget_limit": session.budget_limit,
            "budget_spent": session.total_cost,
            "budget_remaining": max(0, session.budget_limit - session.total_cost) if session.budget_limit > 0 else None,
            "rate_limit": getattr(session, 'rate_limit', 0),
            "rate_limit_period": getattr(session, 'rate_limit_period', 3600),
            "allowed_models": getattr(session, 'allowed_models', []),
            "allowed_qualities": getattr(session, 'allowed_qualities', []),
            "total_requests": getattr(session, 'total_requests', 0),
            "total_blocked": getattr(session, 'total_blocked', 0),
            "amount_saved": getattr(session, 'amount_saved', 0.0),
        }

    @staticmethod
    def budget_remaining(session_id: str) -> Dict[str, Any]:
        """Get budget status for a session."""
        from .sessions import get_session_manager
        mgr = get_session_manager()
        session = mgr.get_session(session_id)
        if not session:
            return {"error": "Session not found"}

        if session.budget_limit <= 0:
            return {
                "has_budget": False,
                "unlimited": True,
                "spent": session.total_cost,
            }

        remaining = max(0, session.budget_limit - session.total_cost)
        return {
            "has_budget": True,
            "unlimited": False,
            "limit": session.budget_limit,
            "spent": session.total_cost,
            "remaining": remaining,
            "percentage_used": (session.total_cost / session.budget_limit) * 100,
        }

    @staticmethod
    def history(session_id: str, limit: int = 10) -> list:
        """Get recent generation history for a session (read-only)."""
        from .sessions import get_session_manager
        mgr = get_session_manager()
        history = mgr.get_session_history(session_id, limit=limit)

        return [{
            "timestamp": h.timestamp,
            "provider": h.provider,
            "model": h.model,
            "status": h.status,
            "cost": h.estimated_cost,
            "reason": h.reason,
            "prompt": h.request_params.get("prompt", "")[:100] if h.request_params else None,
            "image_path": h.image_path,
        } for h in history]

    @staticmethod
    def prices() -> Dict[str, Any]:
        """Get current price configuration."""
        from .sessions import get_session_manager
        mgr = get_session_manager()
        return mgr.settings.get("prices", DEFAULT_PRICES.copy())


# Default prices (can be overridden in settings)
# Updated January 2026
DEFAULT_PRICES = {
    "openai": {
        # Image generation
        "gpt-image-1.5": {"low": 0.02, "medium": 0.07, "high": 0.20},
        "dall-e-3": {"standard": 0.04, "hd": 0.08},
        # Chat/completion models
        "gpt-5.2": 0.01,  # Latest
        "gpt-5.2-mini": 0.002,
        "gpt-5": 0.008,
        "gpt-4.5": 0.005,
        "gpt-4o": 0.005,
        "gpt-4o-mini": 0.0002,
        "o3": 0.015,  # Reasoning model
        "o3-mini": 0.003,
        "o1": 0.012,
        "o1-mini": 0.002,
    },
    "fal": {
        # gpt-image-1.5 via fal is cheaper than OpenAI direct
        "gpt-image-1.5": {"low": 0.013, "medium": 0.051, "high": 0.17},
        # Flux models
        "flux-dev": 0.025,
        "flux-dev-image-to-image": 0.025,
        "flux-schnell": 0.003,
        "flux-pro": 0.05,
        "flux-pro-1.1": 0.04,
        "flux-realism": 0.025,
        # Other models
        "recraft-v3": 0.04,
        "ideogram-v2": 0.08,
        "stable-diffusion-3.5": 0.035,
    },
    "minimax": {
        # Video (per video, not per second)
        "MiniMax-Hailuo-2.3-Fast-768p-6s": 0.19,
        "MiniMax-Hailuo-2.3-Fast-768p-10s": 0.32,
        "MiniMax-Hailuo-2.3-Fast-1080p-6s": 0.33,
        "MiniMax-Hailuo-2.3-768p-6s": 0.28,
        "MiniMax-Hailuo-2.3-768p-10s": 0.56,
        "MiniMax-Hailuo-2.3-1080p-6s": 0.49,
        "MiniMax-Hailuo-02-512p-6s": 0.10,
        "MiniMax-Hailuo-02-512p-10s": 0.15,
        "video-01": 0.28,  # Default/legacy
        # TTS (per character) - $60/M = $0.00006/char, $100/M = $0.0001/char
        "speech-02-turbo": 0.00006,
        "speech-2.6-turbo": 0.00006,
        "speech-02-hd": 0.0001,
        "speech-2.6-hd": 0.0001,
        "speech-01": 0.00006,  # Legacy
        # Music
        "music-2.0": 0.03,  # Per song (up to 5 min)
        # Image
        "image-01": 0.0035,
    },
    "anthropic": {
        "claude-opus-4.5": 0.015,
        "claude-sonnet-4": 0.003,
        "claude-haiku-3.5": 0.0008,
    },
    "google": {
        "gemini-2.0-flash": 0.0001,
        "gemini-2.0-pro": 0.00125,
    }
}


def _get_price(provider: str, model: str, quality: str = None) -> float:
    """Get price from settings or defaults."""
    from .sessions import get_session_manager
    mgr = get_session_manager()
    prices = mgr.settings.get("prices", DEFAULT_PRICES)

    provider_prices = prices.get(provider, DEFAULT_PRICES.get(provider, {}))
    model_price = provider_prices.get(model)

    if model_price is None:
        return 0.20  # Safe fallback

    if isinstance(model_price, dict) and quality:
        return model_price.get(quality, 0.20)
    elif isinstance(model_price, (int, float)):
        return model_price
    return 0.20


def _check_provider(mgr, session_id: str, provider: str):
    """Validate provider is allowed for this session."""
    session = mgr.get_session(session_id)
    allowed_providers = getattr(session, 'allowed_providers', [])

    if allowed_providers and provider not in allowed_providers:
        raise PermissionError(f"Provider '{provider}' not allowed. Allowed: {', '.join(allowed_providers)}")


# =============================================================================
# Base Provider Class - Inherit from this to add new providers easily
# =============================================================================

class BaseProvider:
    """
    Base class for API providers. Inherit from this to add new providers.

    Example:
        class Replicate(BaseProvider):
            PROVIDER_NAME = "replicate"
            DEFAULT_COSTS = {"sdxl": 0.01, "flux": 0.03}

            def run(self, session_id, model, prompt, **kwargs):
                cost = self.get_cost(model)
                params = {"prompt": prompt, "model": model, **kwargs}

                self.validate(session_id, model, cost, params)

                api_key = self.get_key()
                # ... make API call ...

                self.record_success(session_id, model, cost, params)
                return result
    """

    PROVIDER_NAME = "base"  # Override this
    DEFAULT_COSTS = {}  # Override this: {"model": cost} or {"model": {"low": 0.01, "high": 0.05}}

    def get_key(self) -> str:
        """Get API key for this provider."""
        return _get_key(self.PROVIDER_NAME)

    def get_cost(self, model: str, quality: str = None) -> float:
        """Get cost for a model/quality combination."""
        return _get_price(self.PROVIDER_NAME, model, quality)

    def validate(self, session_id: str, model: str, cost: float, params: dict = None):
        """
        Validate the request. Raises PermissionError if blocked.
        Call this BEFORE making API requests.
        """
        self._mgr = _check_session(session_id)
        self._session_id = session_id
        self._params = params or {}

        try:
            _check_provider(self._mgr, session_id, self.PROVIDER_NAME)
        except PermissionError as e:
            self.record_blocked(session_id, model, cost, str(e))
            raise

        try:
            _check_model(self._mgr, session_id, model)
        except PermissionError as e:
            self.record_blocked(session_id, model, cost, f"Model blocked: {model}")
            raise

        try:
            _check_rate_limit(self._mgr, session_id)
        except PermissionError as e:
            self.record_blocked(session_id, model, cost, str(e))
            raise

        # Check budget
        session = self._mgr.get_session(session_id)
        if session.budget_limit > 0 and (session.total_cost + cost) > session.budget_limit:
            remaining = max(0, session.budget_limit - session.total_cost)
            self.record_blocked(session_id, model, cost, "Would exceed budget")
            raise PermissionError(
                f"Budget exceeded. Limit: ${session.budget_limit:.2f}, "
                f"Spent: ${session.total_cost:.2f}, Remaining: ${remaining:.2f}, "
                f"Request cost: ${cost:.2f}"
            )

    def validate_quality(self, session_id: str, quality: str, model: str, cost: float):
        """Validate quality setting. Call after validate() if your provider uses quality."""
        try:
            _check_quality(self._mgr, session_id, quality)
        except PermissionError as e:
            self.record_blocked(session_id, model, cost, f"Quality '{quality}' blocked")
            raise

    def validate_duration(self, session_id: str, duration: int, model: str, cost: float):
        """Validate duration. Call after validate() if your provider uses duration (video)."""
        try:
            _check_duration(self._mgr, session_id, duration)
        except PermissionError as e:
            self.record_blocked(session_id, model, cost, str(e))
            raise

    def record_success(self, session_id: str, model: str, cost: float,
                       params: dict = None, save_path: str = None, response_data: dict = None):
        """Record a successful API call."""
        _record(self._mgr, session_id, self.PROVIDER_NAME, model, cost, True,
                image_path=save_path, request_params=params or self._params, response_data=response_data)

    def record_blocked(self, session_id: str, model: str, cost: float, reason: str):
        """Record a blocked request."""
        from .sessions import get_session_manager
        mgr = getattr(self, '_mgr', None) or get_session_manager()
        _record(mgr, session_id, self.PROVIDER_NAME, model, cost, False, reason,
                request_params=getattr(self, '_params', {}))

    def record_error(self, session_id: str, model: str, reason: str):
        """Record an API error (no cost charged)."""
        _record(self._mgr, session_id, self.PROVIDER_NAME, model, 0, False, reason,
                request_params=getattr(self, '_params', {}))

    def save_image(self, image_bytes: bytes, session_id: str, model: str) -> Path:
        """Save image bytes to the images directory. Returns the path."""
        path = _generate_image_path(session_id, model)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image_bytes)
        return path

    def save_video(self, video_bytes: bytes, session_id: str, model: str) -> Path:
        """Save video bytes to the videos directory. Returns the path."""
        path = _generate_video_path(session_id, model)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(video_bytes)
        return path


# Provider registry - add new providers here for auto-discovery
PROVIDERS = {}


# =============================================================================
# OpenAI Provider
# =============================================================================

class OpenAI:
    """OpenAI API proxy. AI never sees the key."""

    BASE_URL = "https://api.openai.com/v1"

    @staticmethod
    def image(
        session_id: str,
        prompt: str,
        model: str = "gpt-image-1.5",
        quality: Optional[str] = None,
        size: str = "1024x1536",
        n: int = 1,
        save_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate an image. Returns base64 data and optionally saves to file.

        Args:
            session_id: Your session ID
            prompt: Image description
            model: Model name (default: gpt-image-1.5)
            quality: REQUIRED if session has quality restrictions. Options: low/medium/high
            size: Image size (default: 1024x1536)
            n: Number of images (default: 1)
            save_to: Optional file path to save image

        Returns:
            {"b64_json": "...", "saved_to": "path" (if save_to provided)}

        Raises:
            PermissionError: If session/model/quality not allowed
            RuntimeError: If API call fails
        """
        est_quality = quality if quality else "high"
        est_cost = _get_price("openai", model, est_quality) * n

        req_params = {
            "prompt": prompt,
            "model": model,
            "quality": quality,
            "size": size,
            "n": n,
        }

        def record_blocked(mgr_ref, reason: str):
            if mgr_ref:
                _record(mgr_ref, session_id, "openai", model, est_cost, False, reason,
                        request_params=req_params)

        try:
            mgr = _check_session(session_id)
        except PermissionError as e:
            from .sessions import get_session_manager
            temp_mgr = get_session_manager()
            record_blocked(temp_mgr, str(e))
            raise

        try:
            _check_model(mgr, session_id, model)
        except PermissionError as e:
            record_blocked(mgr, f"Model blocked: {model}")
            raise

        try:
            _check_rate_limit(mgr, session_id)
        except PermissionError as e:
            record_blocked(mgr, str(e))
            raise

        cost = est_cost
        session = mgr.get_session(session_id)
        has_quality_restrictions = bool(session.allowed_qualities or session.banned_qualities)

        if quality is None:
            if has_quality_restrictions:
                _record(mgr, session_id, "openai", model, cost, False,
                        "Quality not specified - would default to high ($0.20)",
                        request_params=req_params)
                raise PermissionError("Quality parameter REQUIRED. Session has quality restrictions. Use quality='low'")
            else:
                quality = "low"
                cost = _get_price("openai", model, quality) * n
                req_params["quality"] = quality

        try:
            _check_quality(mgr, session_id, quality)
        except PermissionError as e:
            _record(mgr, session_id, "openai", model, cost, False, f"Quality '{quality}' blocked",
                    request_params=req_params)
            raise

        if session.budget_limit > 0 and (session.total_cost + cost) > session.budget_limit:
            remaining = max(0, session.budget_limit - session.total_cost)
            _record(mgr, session_id, "openai", model, cost, False, "Would exceed budget",
                    request_params=req_params)
            raise PermissionError(
                f"Budget exceeded. Limit: ${session.budget_limit:.2f}, "
                f"Spent: ${session.total_cost:.2f}, Remaining: ${remaining:.2f}, "
                f"Request cost: ${cost:.2f}"
            )

        api_key = _get_key("openai")

        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "size": size,
                "quality": quality,
                "n": n,
            }
            if model not in ["gpt-image-1.5"]:
                payload["response_format"] = "b64_json"

            response = requests.post(
                f"{OpenAI.BASE_URL}/images/generations",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=120
            )

            if response.status_code != 200:
                error_msg = response.text[:200]
                _record(mgr, session_id, "openai", model, 0, False, f"API error: {response.status_code}")
                raise RuntimeError(f"OpenAI API error {response.status_code}: {error_msg}")

            data = response.json()
            img_data = data["data"][0]
            response_timestamp = datetime.now().isoformat()

            result = {}
            if "b64_json" in img_data:
                result["b64_json"] = img_data["b64_json"]
                img_bytes = base64.b64decode(img_data["b64_json"])
            elif "url" in img_data:
                result["url"] = img_data["url"]
                img_response = requests.get(img_data["url"], timeout=60)
                img_bytes = img_response.content
                result["b64_json"] = base64.b64encode(img_bytes).decode()
            else:
                raise RuntimeError("No image data in response")

            if save_to:
                actual_save_path = Path(save_to).resolve()
            else:
                actual_save_path = _generate_image_path(session_id, model)

            actual_save_path.parent.mkdir(parents=True, exist_ok=True)
            actual_save_path.write_bytes(img_bytes)
            result["saved_to"] = str(actual_save_path)

            req_params = {
                "prompt": prompt,
                "model": model,
                "quality": quality,
                "size": size,
                "n": n,
            }
            resp_data = {
                "has_image": True,
                "image_path": str(actual_save_path),
                "url": img_data.get("url"),
                "url_created": response_timestamp,
                "revised_prompt": img_data.get("revised_prompt"),
                "created": data.get("created"),
            }
            _record(mgr, session_id, "openai", model, cost, True,
                    image_path=str(actual_save_path), request_params=req_params, response_data=resp_data)

            return result

        except requests.exceptions.RequestException as e:
            _record(mgr, session_id, "openai", model, 0, False, f"Network error: {str(e)}")
            raise RuntimeError(f"Network error: {str(e)}")

    @staticmethod
    def chat(
        session_id: str,
        messages: list,
        model: str = "gpt-4o-mini",
        temperature: float = 1.0,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Chat completion. Returns response content.
        """
        mgr = _check_session(session_id)
        _check_model(mgr, session_id, model)

        api_key = _get_key("openai")

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        try:
            response = requests.post(
                f"{OpenAI.BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=120
            )

            if response.status_code != 200:
                error_msg = response.text[:200]
                _record(mgr, session_id, "openai", model, 0, False, f"API error: {response.status_code}")
                raise RuntimeError(f"OpenAI API error {response.status_code}: {error_msg}")

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            total_tokens = usage.get("total_tokens", 0)
            cost = (total_tokens / 1000) * _get_price("openai", model)

            _record(mgr, session_id, "openai", model, cost, True)

            return {"content": content, "usage": usage}

        except requests.exceptions.RequestException as e:
            _record(mgr, session_id, "openai", model, 0, False, f"Network error: {str(e)}")
            raise RuntimeError(f"Network error: {str(e)}")


# =============================================================================
# Fal.ai Provider
# =============================================================================

class Fal:
    """Fal.ai API proxy. Excellent for image-to-image with references."""

    BASE_URL = "https://fal.run"

    MODELS = {
        "gpt-image-1.5": "fal-ai/gpt-image-1.5",
        "flux-dev": "fal-ai/flux/dev",
        "flux-dev-image-to-image": "fal-ai/flux/dev/image-to-image",
        "flux-schnell": "fal-ai/flux/schnell",
        "flux-pro": "fal-ai/flux-pro",
        "recraft-v3": "fal-ai/recraft-v3",
    }

    @staticmethod
    def image(
        session_id: str,
        prompt: str,
        reference_images: list = None,
        model: str = "flux-dev",
        quality: str = "low",
        size: str = "1024x1536",
        num_inference_steps: int = 28,
        guidance_scale: float = 3.5,
        strength: float = 0.95,
        save_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate an image using fal.ai.
        """
        cost = _get_price("fal", model, quality)

        req_params = {
            "prompt": prompt,
            "model": model,
            "size": size,
            "has_reference": bool(reference_images),
            "num_references": len(reference_images) if reference_images else 0,
        }

        mgr = _check_session(session_id)

        try:
            _check_provider(mgr, session_id, "fal")
        except PermissionError as e:
            _record(mgr, session_id, "fal", model, cost, False, str(e), request_params=req_params)
            raise

        try:
            _check_model(mgr, session_id, model)
        except PermissionError as e:
            _record(mgr, session_id, "fal", model, cost, False, f"Model blocked: {model}", request_params=req_params)
            raise

        try:
            _check_rate_limit(mgr, session_id)
        except PermissionError as e:
            _record(mgr, session_id, "fal", model, cost, False, str(e), request_params=req_params)
            raise

        session = mgr.get_session(session_id)
        if session.budget_limit > 0 and (session.total_cost + cost) > session.budget_limit:
            remaining = max(0, session.budget_limit - session.total_cost)
            _record(mgr, session_id, "fal", model, cost, False, "Would exceed budget", request_params=req_params)
            raise PermissionError(
                f"Budget exceeded. Limit: ${session.budget_limit:.2f}, "
                f"Spent: ${session.total_cost:.2f}, Remaining: ${remaining:.2f}, "
                f"Request cost: ${cost:.2f}"
            )

        api_key = _get_key("fal")

        if reference_images:
            endpoint = Fal.MODELS.get("flux-dev-image-to-image", "fal-ai/flux/dev/image-to-image")
        else:
            endpoint = Fal.MODELS.get(model, f"fal-ai/{model}")

        try:
            width, height = map(int, size.split("x"))
        except:
            width, height = 1024, 1536

        if model == "gpt-image-1.5":
            payload = {
                "prompt": prompt,
                "size": size,
                "quality": quality or "low",
                "num_images": 1,
                "output_format": "png",
            }
            if reference_images:
                endpoint = "fal-ai/gpt-image-1.5/edit"
                ref_urls = []
                for ref in reference_images:
                    if ref.startswith(("http://", "https://")):
                        ref_urls.append(ref)
                    else:
                        ref_path = Path(ref)
                        if ref_path.exists():
                            img_data = base64.b64encode(ref_path.read_bytes()).decode()
                            ref_urls.append(f"data:image/png;base64,{img_data}")
                if ref_urls:
                    payload["image_url"] = ref_urls[0]
        else:
            payload = {
                "prompt": prompt,
                "image_size": {"width": width, "height": height},
                "num_inference_steps": num_inference_steps,
                "guidance_scale": guidance_scale,
                "num_images": 1,
                "output_format": "png",
            }
            if reference_images:
                ref_urls = []
                for ref in reference_images:
                    if ref.startswith(("http://", "https://")):
                        ref_urls.append(ref)
                    else:
                        ref_path = Path(ref)
                        if ref_path.exists():
                            img_data = base64.b64encode(ref_path.read_bytes()).decode()
                            ref_urls.append(f"data:image/png;base64,{img_data}")
                if ref_urls:
                    payload["image_url"] = ref_urls[0]
                    payload["strength"] = strength

        try:
            response = requests.post(
                f"{Fal.BASE_URL}/{endpoint}",
                headers={
                    "Authorization": f"Key {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=120
            )

            if response.status_code != 200:
                error_msg = response.text[:200]
                _record(mgr, session_id, "fal", model, 0, False, f"API error: {response.status_code}")
                raise RuntimeError(f"Fal API error {response.status_code}: {error_msg}")

            data = response.json()
            response_timestamp = datetime.now().isoformat()

            images = data.get("images", [])
            if not images:
                raise RuntimeError("No images in fal.ai response")

            img_url = images[0].get("url")
            if not img_url:
                raise RuntimeError("No image URL in fal.ai response")

            img_response = requests.get(img_url, timeout=60)
            img_bytes = img_response.content

            if save_to:
                actual_save_path = Path(save_to).resolve()
            else:
                actual_save_path = _generate_image_path(session_id, model)

            actual_save_path.parent.mkdir(parents=True, exist_ok=True)
            actual_save_path.write_bytes(img_bytes)

            result = {
                "url": img_url,
                "saved_to": str(actual_save_path),
            }

            resp_data = {
                "has_image": True,
                "image_path": str(actual_save_path),
                "url": img_url,
                "url_created": response_timestamp,
                "seed": data.get("seed"),
            }
            _record(mgr, session_id, "fal", model, cost, True,
                    image_path=str(actual_save_path), request_params=req_params, response_data=resp_data)

            return result

        except requests.exceptions.RequestException as e:
            _record(mgr, session_id, "fal", model, 0, False, f"Network error: {str(e)}")
            raise RuntimeError(f"Network error: {str(e)}")


# =============================================================================
# MiniMax Provider
# =============================================================================

class MiniMax:
    """MiniMax API proxy for video generation."""

    BASE_URL = "https://api.minimax.chat/v1"

    COSTS = {
        "video-01": 0.05,
        "video-01-live2d": 0.04,
    }

    @staticmethod
    def video(
        session_id: str,
        prompt: str,
        model: str = "video-01",
        duration: int = 5,  # Video duration in seconds
        first_frame_image: Optional[str] = None,
        save_to: Optional[str] = None,
        poll_interval: int = 10,
        max_wait: int = 600,
    ) -> Dict[str, Any]:
        """
        Generate a video. This is an async operation - submits task and polls until complete.
        """
        import time

        cost = _get_price("minimax", model) * duration

        req_params = {
            "prompt": prompt,
            "model": model,
            "duration": duration,
            "has_first_frame": bool(first_frame_image),
        }

        # 1. Check session
        mgr = _check_session(session_id)

        # 2. Check provider
        try:
            _check_provider(mgr, session_id, "minimax")
        except PermissionError as e:
            _record(mgr, session_id, "minimax", model, cost, False, str(e), request_params=req_params)
            raise

        # 3. Check model
        try:
            _check_model(mgr, session_id, model)
        except PermissionError as e:
            _record(mgr, session_id, "minimax", model, cost, False, f"Model blocked: {model}", request_params=req_params)
            raise

        # 4. Check duration limit
        try:
            _check_duration(mgr, session_id, duration)
        except PermissionError as e:
            _record(mgr, session_id, "minimax", model, cost, False, str(e), request_params=req_params)
            raise

        # 5. Check rate limit
        try:
            _check_rate_limit(mgr, session_id)
        except PermissionError as e:
            _record(mgr, session_id, "minimax", model, cost, False, str(e), request_params=req_params)
            raise

        # 6. Check budget
        session = mgr.get_session(session_id)
        if session.budget_limit > 0 and (session.total_cost + cost) > session.budget_limit:
            remaining = max(0, session.budget_limit - session.total_cost)
            _record(mgr, session_id, "minimax", model, cost, False, "Would exceed budget", request_params=req_params)
            raise PermissionError(
                f"Budget exceeded. Limit: ${session.budget_limit:.2f}, "
                f"Spent: ${session.total_cost:.2f}, Remaining: ${remaining:.2f}, "
                f"Request cost: ${cost:.2f}"
            )

        api_key = _get_key("minimax")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "prompt": prompt,
        }

        if first_frame_image:
            img_path = Path(first_frame_image)
            if img_path.exists():
                with open(img_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()
                payload["first_frame_image"] = f"data:image/png;base64,{img_b64}"

        response_timestamp = datetime.now().isoformat()

        try:
            response = requests.post(
                f"{MiniMax.BASE_URL}/video_generation",
                headers=headers,
                json=payload,
                timeout=60
            )

            if response.status_code != 200:
                error_msg = response.text[:200]
                _record(mgr, session_id, "minimax", model, 0, False, f"API error: {response.status_code}")
                raise RuntimeError(f"MiniMax API error {response.status_code}: {error_msg}")

            data = response.json()

            if data.get("base_resp", {}).get("status_code") != 0:
                error_msg = data.get("base_resp", {}).get("status_msg", "Unknown error")
                _record(mgr, session_id, "minimax", model, 0, False, f"API rejected: {error_msg}")
                raise RuntimeError(f"MiniMax API rejected: {error_msg}")

            task_id = data.get("task_id")
            if not task_id:
                _record(mgr, session_id, "minimax", model, 0, False, "No task_id in response")
                raise RuntimeError("MiniMax API did not return task_id")

            start_time = time.time()
            video_url = None

            while time.time() - start_time < max_wait:
                time.sleep(poll_interval)

                status_response = requests.get(
                    f"{MiniMax.BASE_URL}/query/video_generation",
                    headers=headers,
                    params={"task_id": task_id},
                    timeout=30
                )

                if status_response.status_code != 200:
                    continue

                status_data = status_response.json()
                status = status_data.get("status")

                if status == "Success":
                    video_url = status_data.get("file_id")
                    if not video_url:
                        video_url = status_data.get("video_url")
                    break
                elif status == "Fail":
                    error_msg = status_data.get("base_resp", {}).get("status_msg", "Generation failed")
                    _record(mgr, session_id, "minimax", model, cost, False, f"Generation failed: {error_msg}")
                    raise RuntimeError(f"MiniMax video generation failed: {error_msg}")

            if not video_url:
                _record(mgr, session_id, "minimax", model, cost, False, "Timeout waiting for video")
                raise RuntimeError(f"Timeout waiting for video generation (waited {max_wait}s)")

            video_response = requests.get(video_url, timeout=120)
            if video_response.status_code != 200:
                _record(mgr, session_id, "minimax", model, cost, False, "Failed to download video")
                raise RuntimeError(f"Failed to download video from {video_url}")

            video_bytes = video_response.content

            if save_to:
                actual_save_path = Path(save_to).resolve()
            else:
                actual_save_path = _generate_video_path(session_id, model)

            actual_save_path.parent.mkdir(parents=True, exist_ok=True)
            actual_save_path.write_bytes(video_bytes)

            result = {
                "video_url": video_url,
                "saved_to": str(actual_save_path),
                "task_id": task_id,
            }

            req_params = {
                "prompt": prompt,
                "model": model,
                "first_frame_image": first_frame_image,
            }
            resp_data = {
                "has_video": True,
                "video_path": str(actual_save_path),
                "video_url": video_url,
                "url_created": response_timestamp,
                "task_id": task_id,
                "file_size_bytes": len(video_bytes),
            }
            _record(mgr, session_id, "minimax", model, cost, True,
                    image_path=str(actual_save_path), request_params=req_params, response_data=resp_data)

            return result

        except requests.exceptions.RequestException as e:
            _record(mgr, session_id, "minimax", model, 0, False, f"Network error: {str(e)}")
            raise RuntimeError(f"Network error: {str(e)}")

    @staticmethod
    def tts(
        session_id: str,
        text: str,
        voice_id: str = "male-qn-qingse",
        model: str = "speech-02-turbo",
        speed: float = 1.0,
        pitch: int = 0,
        save_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate speech from text using MiniMax TTS.

        Args:
            session_id: Your session ID
            text: Text to convert to speech
            voice_id: Voice to use (e.g., "male-qn-qingse", "female-shaonv", "presenter_male", etc.)
            model: TTS model ("speech-02-turbo", "speech-02-hd", "speech-2.6-turbo", "speech-2.6-hd")
            speed: Speech speed (0.5 to 2.0, default 1.0)
            pitch: Pitch adjustment (-12 to 12, default 0)
            save_to: Optional file path to save audio

        Returns:
            {"saved_to": "path", "char_count": N, "cost": X}

        Pricing:
            speech-02-turbo / speech-2.6-turbo: $0.06 per 1000 chars
            speech-02-hd / speech-2.6-hd: $0.10 per 1000 chars
        """
        # Cost based on character count
        char_count = len(text)
        cost_per_char = _get_price("minimax", model)
        cost = cost_per_char * char_count

        req_params = {
            "text_length": char_count,
            "voice_id": voice_id,
            "model": model,
            "speed": speed,
            "pitch": pitch,
        }

        # 1. Check session
        mgr = _check_session(session_id)

        # 2. Check provider
        try:
            _check_provider(mgr, session_id, "minimax")
        except PermissionError as e:
            _record(mgr, session_id, "minimax", model, cost, False, str(e), request_params=req_params)
            raise

        # 3. Check model
        try:
            _check_model(mgr, session_id, model)
        except PermissionError as e:
            _record(mgr, session_id, "minimax", model, cost, False, f"Model blocked: {model}", request_params=req_params)
            raise

        # 4. Check rate limit
        try:
            _check_rate_limit(mgr, session_id)
        except PermissionError as e:
            _record(mgr, session_id, "minimax", model, cost, False, str(e), request_params=req_params)
            raise

        # 5. Check budget
        session = mgr.get_session(session_id)
        if session.budget_limit > 0 and (session.total_cost + cost) > session.budget_limit:
            remaining = max(0, session.budget_limit - session.total_cost)
            _record(mgr, session_id, "minimax", model, cost, False, "Would exceed budget", request_params=req_params)
            raise PermissionError(
                f"Budget exceeded. Limit: ${session.budget_limit:.2f}, "
                f"Spent: ${session.total_cost:.2f}, Remaining: ${remaining:.2f}, "
                f"Request cost: ${cost:.4f} ({char_count} chars)"
            )

        api_key = _get_key("minimax")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "text": text,
            "voice_setting": {
                "voice_id": voice_id,
                "speed": speed,
                "pitch": pitch,
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
            }
        }

        response_timestamp = datetime.now().isoformat()

        try:
            response = requests.post(
                f"{MiniMax.BASE_URL}/t2a_v2",
                headers=headers,
                json=payload,
                timeout=120
            )

            if response.status_code != 200:
                error_msg = response.text[:200]
                _record(mgr, session_id, "minimax", model, 0, False, f"API error: {response.status_code}")
                raise RuntimeError(f"MiniMax TTS error {response.status_code}: {error_msg}")

            data = response.json()

            if data.get("base_resp", {}).get("status_code") != 0:
                error_msg = data.get("base_resp", {}).get("status_msg", "Unknown error")
                _record(mgr, session_id, "minimax", model, 0, False, f"API rejected: {error_msg}")
                raise RuntimeError(f"MiniMax TTS rejected: {error_msg}")

            # Get audio data (base64 encoded)
            audio_data = data.get("data", {}).get("audio")
            if not audio_data:
                # Try alternate response format
                audio_url = data.get("audio_file")
                if audio_url:
                    audio_response = requests.get(audio_url, timeout=60)
                    audio_bytes = audio_response.content
                else:
                    _record(mgr, session_id, "minimax", model, 0, False, "No audio in response")
                    raise RuntimeError("MiniMax TTS did not return audio data")
            else:
                # Decode base64 audio
                audio_bytes = base64.b64decode(audio_data)

            # Save audio
            if save_to:
                actual_save_path = Path(save_to).resolve()
            else:
                actual_save_path = _generate_audio_path(session_id, model, "mp3")

            actual_save_path.parent.mkdir(parents=True, exist_ok=True)
            actual_save_path.write_bytes(audio_bytes)

            result = {
                "saved_to": str(actual_save_path),
                "char_count": char_count,
                "cost": cost,
            }

            resp_data = {
                "has_audio": True,
                "audio_path": str(actual_save_path),
                "char_count": char_count,
                "url_created": response_timestamp,
                "file_size_bytes": len(audio_bytes),
            }
            _record(mgr, session_id, "minimax", model, cost, True,
                    image_path=str(actual_save_path), request_params=req_params, response_data=resp_data)

            return result

        except requests.exceptions.RequestException as e:
            _record(mgr, session_id, "minimax", model, 0, False, f"Network error: {str(e)}")
            raise RuntimeError(f"Network error: {str(e)}")


# =============================================================================
# Convenience aliases
# =============================================================================

openai = OpenAI()
minimax = MiniMax()
fal = Fal()
query = Query()
