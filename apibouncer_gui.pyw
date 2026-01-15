"""
APIBouncer Control Center

Full dashboard for:
- Secure API key management
- Session tracking and control
- Cost savings monitoring
- Request history and analytics
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
from datetime import datetime
from pathlib import Path

# Optional: PIL for thumbnails
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Optional: System tray support
try:
    import pystray
    from PIL import ImageDraw
    HAS_TRAY = HAS_PIL  # Requires PIL
except ImportError:
    HAS_TRAY = False

# Optional: Windows notifications
try:
    from plyer import notification
    HAS_NOTIFICATIONS = True
except ImportError:
    HAS_NOTIFICATIONS = False

try:
    import keyring
except ImportError:
    keyring = None

# Secure encrypted keystore (preferred over keyring)
try:
    from apibouncer.keystore import get_keystore
    HAS_KEYSTORE = True
except ImportError:
    HAS_KEYSTORE = False

if not HAS_KEYSTORE and not keyring:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Missing Dependency", "Run: pip install cryptography")
    sys.exit(1)

# Windows: Set unique AppUserModelID so taskbar shows our icon, not Python's
try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('APIBouncer.ControlCenter.1.0')
except Exception:
    pass  # Not Windows or missing API

def force_taskbar_visibility(window):
    """Force a tkinter window to appear in Windows taskbar."""
    try:
        import ctypes
        from ctypes import wintypes

        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080

        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if hwnd == 0:
            hwnd = window.winfo_id()

        # Get current style
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        # Remove toolwindow, add appwindow
        style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

        # Force redraw
        window.withdraw()
        window.after(10, window.deiconify)
    except Exception:
        pass  # Not Windows or API issue

# Add apibouncer to path
sys.path.insert(0, str(__file__).replace("apibouncer_gui.pyw", ""))

try:
    from apibouncer.sessions import get_session_manager, SessionManager
except ImportError:
    # Fallback - create minimal session manager
    class SessionManager:
        def __init__(self):
            self.sessions = {}
            self.history = []
        def get_stats(self):
            return {"total_saved": 0, "total_spent": 0, "total_sessions": 0,
                    "active_sessions": 0, "warned_sessions": 0, "banned_sessions": 0,
                    "total_requests": 0, "total_blocked": 0, "block_rate": 0}
        def get_recent_history(self, limit=50):
            return []
        def create_session(self, name):
            return None
        def ban_session(self, sid, reason=""):
            pass
        def unban_session(self, sid):
            pass
        def delete_session(self, sid):
            pass

    def get_session_manager():
        return SessionManager()

SERVICE_NAME = "apibouncer"


# =============================================================================
# Secure Key Management (encrypted keystore with keyring fallback)
# =============================================================================

def secure_get_key(provider: str) -> str:
    """Get API key from secure storage."""
    key = None
    if HAS_KEYSTORE:
        try:
            key = get_keystore().get_key(provider)
        except Exception:
            pass
    if not key and keyring:
        key = keyring.get_password(SERVICE_NAME, provider)
    return key


def secure_set_key(provider: str, api_key: str):
    """Store API key in secure encrypted storage."""
    if HAS_KEYSTORE:
        get_keystore().set_key(provider, api_key)
    elif keyring:
        keyring.set_password(SERVICE_NAME, provider, api_key)


def secure_delete_key(provider: str):
    """Delete API key from secure storage."""
    if HAS_KEYSTORE:
        try:
            get_keystore().delete_key(provider)
        except Exception:
            pass
    if keyring:
        try:
            keyring.delete_password(SERVICE_NAME, provider)
        except Exception:
            pass


def secure_has_key(provider: str) -> bool:
    """Check if API key exists in secure storage."""
    return secure_get_key(provider) is not None


def mask_session_id(session_id: str) -> str:
    """Mask session ID for display. Shows APBN-XXXX-**** format.

    Full ID is only shown once at creation time.
    """
    if session_id.startswith("APBN-") and len(session_id) > 10:
        # Format: APBN-XXXX-XXXXXXXXXXXX -> APBN-XXXX-****
        parts = session_id.split("-")
        if len(parts) >= 3:
            return f"{parts[0]}-{parts[1]}-****"
    # Legacy short IDs - show first 4 chars
    return f"{session_id[:4]}****" if len(session_id) > 4 else session_id


# Version history
APP_VERSION = "1.7.0"
VERSION_HISTORY = [
    ("1.7.0", "2026-01-15", "Barrier Mode: queue-based approval window, per-session override"),
    ("1.6.1", "2026-01-14", "Enhanced monitor: settings panel, thumbnails, prompt preview"),
    ("1.6.0", "2026-01-14", "Real-time session monitor, rate limiting, MiniMax video"),
    ("1.5.2", "2026-01-14", "PANIC: instant enable, confirm disable, red UI overlay"),
    ("1.5.1", "2026-01-14", "Window icon/favicon, analytics tab"),
    ("1.5.0", "2026-01-14", "AI handoff instructions on session create"),
    ("1.4.0", "2026-01-14", "PANIC BUTTON - Stop all API calls instantly"),
    ("1.3.3", "2026-01-14", "Cleaner history layout, larger main window"),
    ("1.3.2", "2026-01-14", "Masked session IDs, better dialog sizing"),
    ("1.3.1", "2026-01-14", "Blocked calls now track savings, URL in response"),
    ("1.3.0", "2026-01-14", "Thumbnails + detailed history view on click"),
    ("1.2.1", "2026-01-14", "Clearer quality whitelist/blacklist UI"),
    ("1.2.0", "2026-01-14", "Secure proxy - AI never sees API keys"),
    ("1.1.9", "2026-01-14", "Improved history layout, cleaner dashboard"),
    ("1.1.8", "2026-01-14", "Quality/duration limits, fixed dashboard stats"),
    ("1.1.7", "2026-01-14", "Optional: System tray, desktop notifications"),
    ("1.1.6", "2026-01-14", "Fixed infinite dashboard rendering bug"),
    ("1.1.5", "2026-01-14", "Budget limits per session, CSV export, live search filter"),
    ("1.1.4", "2026-01-14", "Global model bans on API Keys screen"),
    ("1.1.3", "2026-01-14", "Rate limiting per session"),
    ("1.1.2", "2026-01-14", "Fixed font rendering issues, stronger session IDs (APBN-XXXX-XXXX...)"),
    ("1.1.1", "2026-01-14", "Session IDs hidden from display for security"),
    ("1.1.0", "2026-01-14", "Model whitelist/blacklist with wildcard support"),
    ("1.0.0", "2026-01-14", "Initial release - secure key storage, sessions"),
]

# Modern color scheme
COLORS = {
    "bg": "#0f0f1a",
    "bg_secondary": "#1a1a2e",
    "card": "#16213e",
    "card_hover": "#1f3460",
    "accent": "#4361ee",
    "accent_hover": "#3a56d4",
    "success": "#00d26a",
    "warning": "#ffc107",
    "danger": "#ef476f",
    "text": "#ffffff",
    "text_secondary": "#8b8fa3",
    "text_muted": "#5c5f73",
    "border": "#2a2d3e",
}

# Default API Keys (user can add more)
# Format: (id, name, base_url, notes)
DEFAULT_API_KEYS = [
    {"id": "openai", "name": "OpenAI", "url": "https://api.openai.com/v1", "notes": ""},
    {"id": "anthropic", "name": "Anthropic", "url": "https://api.anthropic.com/v1", "notes": ""},
    {"id": "fal", "name": "Fal.ai", "url": "https://fal.run", "notes": ""},
    {"id": "minimax", "name": "MiniMax", "url": "https://api.minimax.chat/v1", "notes": ""},
]

def _get_config_path():
    import os
    from pathlib import Path
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "apibouncer" / "api_keys_config.json"

def get_api_keys_list():
    """Get user's configured API key list from settings."""
    import json
    keys_file = _get_config_path()

    if keys_file.exists():
        try:
            data = json.loads(keys_file.read_text())
            # Return list of tuples for backward compatibility
            return [(k["id"], k["name"]) for k in data.get("keys", [])]
        except:
            pass

    return [(k["id"], k["name"]) for k in DEFAULT_API_KEYS]

def get_api_keys_full():
    """Get full API config including URLs and notes."""
    import json
    keys_file = _get_config_path()

    if keys_file.exists():
        try:
            data = json.loads(keys_file.read_text())
            return data.get("keys", [])
        except:
            pass

    return DEFAULT_API_KEYS.copy()

def save_api_keys_full(keys):
    """Save full API config."""
    import json
    keys_file = _get_config_path()
    keys_file.parent.mkdir(parents=True, exist_ok=True)
    data = {"keys": keys}
    keys_file.write_text(json.dumps(data, indent=2))

def save_api_keys_list(keys):
    """Save user's API key list to settings (legacy support)."""
    # Convert tuples to full format
    full_keys = []
    existing = {k["id"]: k for k in get_api_keys_full()}

    for k in keys:
        if isinstance(k, tuple):
            key_id, name = k
            if key_id in existing:
                full_keys.append(existing[key_id])
            else:
                full_keys.append({"id": key_id, "name": name, "url": "", "notes": ""})
        else:
            full_keys.append(k)

    save_api_keys_full(full_keys)


class ModernApp:
    def __init__(self, root):
        self.root = root
        self.root.title("APIBouncer Control Center")
        self.root.geometry("1000x700")
        self.root.configure(bg=COLORS["bg"])
        self.root.minsize(900, 650)

        # Set window icon
        self._icon_ref = None
        try:
            base_path = Path(__file__).parent
            # Prefer .ico for Windows taskbar, fallback to .png
            ico_path = base_path / "icon.ico"
            png_path = base_path / "icon.png"

            if ico_path.exists():
                # Use .ico for Windows - shows properly in taskbar
                self.root.iconbitmap(str(ico_path))
            elif png_path.exists():
                # Fallback to PNG with iconphoto
                icon_img = Image.open(png_path)
                icon_photo = ImageTk.PhotoImage(icon_img)
                self.root.iconphoto(True, icon_photo)
                self._icon_ref = icon_photo  # Keep reference
        except Exception:
            pass  # Icon is optional

        # DPI awareness
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass

        self.session_mgr = get_session_manager()
        self.current_tab = "dashboard"

        # Load optional feature settings
        self.enable_tray = self.session_mgr.settings.get("enable_tray", False)
        self.enable_notifications = self.session_mgr.settings.get("enable_notifications", False)
        self.tray_icon = None

        # Barrier mode window
        self.barrier_window = None
        self.barrier_indicator = None
        self.session_mgr.set_barrier_callback(self.on_barrier_request)

        self.create_ui()
        self.show_tab("dashboard")

        # Force taskbar visibility on Windows
        self.root.after(100, lambda: force_taskbar_visibility(self.root))

        # Setup system tray if enabled
        if self.enable_tray and HAS_TRAY:
            self.setup_tray()
            self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        else:
            self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Auto-refresh every 30 seconds
        self.auto_refresh()

    def auto_refresh(self):
        # Reload data from disk in case external changes (proxy calls, etc.)
        self.session_mgr._load()
        # Use show_tab to properly clear content before refreshing
        if self.current_tab in ("dashboard", "history"):
            self.show_tab(self.current_tab)
        self.root.after(30000, self.auto_refresh)

    def open_media_file(self, path):
        """Open a media file with the default application."""
        import os
        import subprocess
        try:
            if os.path.exists(path):
                os.startfile(path)  # Windows
            else:
                messagebox.showwarning("File Not Found", f"File not found:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file: {e}")

    def open_file_location(self, path):
        """Open file explorer with the file selected."""
        import os
        import subprocess
        try:
            if os.path.exists(path):
                # Windows: open explorer with file selected
                subprocess.run(['explorer', '/select,', path])
            else:
                # If file doesn't exist, open the parent directory
                parent = os.path.dirname(path)
                if os.path.exists(parent):
                    os.startfile(parent)
                else:
                    messagebox.showwarning("Location Not Found", f"Location not found:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open location: {e}")

    def on_close(self):
        """Handle window close."""
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()

    def setup_tray(self):
        """Setup system tray icon."""
        if not HAS_TRAY:
            return

        # Load tray icon
        def get_icon():
            # Try to load custom icon
            icon_path = Path(__file__).parent / "icon.png"
            if icon_path.exists():
                try:
                    img = Image.open(icon_path)
                    img = img.resize((64, 64), Image.Resampling.LANCZOS)
                    # Convert to RGB if needed
                    if img.mode == 'RGBA':
                        rgb_img = Image.new('RGB', (64, 64), color=(15, 15, 26))
                        rgb_img.paste(img, mask=img.split()[3])
                        return rgb_img
                    return img
                except Exception:
                    pass

            # Fallback: simple shield
            img = Image.new('RGB', (64, 64), color=(15, 15, 26))
            draw = ImageDraw.Draw(img)
            draw.polygon([(32, 5), (55, 15), (55, 40), (32, 58), (9, 40), (9, 15)],
                        fill=(0, 210, 106))
            return img

        def show_window(icon, item):
            self.root.after(0, self.root.deiconify)

        def quit_app(icon, item):
            icon.stop()
            self.root.after(0, self.root.destroy)

        menu = pystray.Menu(
            pystray.MenuItem("Show", show_window, default=True),
            pystray.MenuItem("Quit", quit_app)
        )

        self.tray_icon = pystray.Icon(
            "APIBouncer",
            get_icon(),
            "APIBouncer Control Center",
            menu
        )

        # Run tray icon in separate thread
        import threading
        tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        tray_thread.start()

    def minimize_to_tray(self):
        """Minimize to system tray instead of closing."""
        self.root.withdraw()
        if self.enable_notifications and HAS_NOTIFICATIONS:
            self.send_notification("APIBouncer", "Minimized to system tray")

    def send_notification(self, title, message, timeout=5):
        """Send a desktop notification."""
        if not self.enable_notifications or not HAS_NOTIFICATIONS:
            return
        try:
            notification.notify(
                title=title,
                message=message,
                app_name="APIBouncer",
                timeout=timeout
            )
        except Exception:
            pass  # Notifications are optional, don't crash

    # =========================================================================
    # Barrier Mode - Request Approval Window
    # =========================================================================

    def on_barrier_request(self):
        """Callback when new barrier requests arrive. Called from worker threads."""
        # Schedule UI update on main thread
        try:
            self.root.after(0, self._handle_barrier_request)
        except Exception:
            pass

    def _handle_barrier_request(self):
        """Handle new barrier request on main thread."""
        self.update_barrier_indicator()
        # Auto-open barrier window if requests are pending
        pending = self.session_mgr.get_pending_requests()
        if pending and not self.barrier_window:
            self.show_barrier_window()
        elif pending and self.barrier_window:
            self.refresh_barrier_list()

    def update_barrier_indicator(self):
        """Update the barrier indicator in sidebar."""
        if not self.barrier_indicator:
            return

        try:
            # Read fresh from disk for cross-process consistency
            barrier_active = self.session_mgr.is_barrier_active()
            pending = len(self.session_mgr.get_pending_requests())

            if barrier_active:
                if pending > 0:
                    self.barrier_indicator.configure(
                        text=f"🛡️ Barrier: {pending} pending",
                        fg="#ff6600", bg="#3d2000"
                    )
                else:
                    self.barrier_indicator.configure(
                        text="🛡️ Barrier: Active",
                        fg="#00ff88", bg=COLORS["card"]
                    )
            else:
                self.barrier_indicator.configure(
                    text="🛡️ Barrier: Off",
                    fg=COLORS["text_muted"], bg=COLORS["card"]
                )
        except Exception:
            pass

    def show_barrier_window(self):
        """Show the barrier approval window."""
        if self.barrier_window:
            self.barrier_window.lift()
            self.barrier_window.focus_force()
            self.refresh_barrier_list()
            return

        self.barrier_window = tk.Toplevel(self.root)
        self.barrier_window.title("🛡️ Barrier Mode - Pending Requests")
        self.barrier_window.geometry("700x500")
        self.barrier_window.configure(bg=COLORS["bg"])
        self.barrier_window.transient(self.root)

        # Keep on top
        self.barrier_window.attributes('-topmost', True)

        # Handle close
        def on_close():
            self.barrier_window.destroy()
            self.barrier_window = None
        self.barrier_window.protocol("WM_DELETE_WINDOW", on_close)

        # Header
        header = tk.Frame(self.barrier_window, bg=COLORS["card"], pady=15, padx=20)
        header.pack(fill="x")

        tk.Label(header, text="🛡️ Pending API Requests",
                font=("Arial", 14, "bold"),
                fg=COLORS["text"], bg=COLORS["card"]).pack(side="left")

        # Bulk action buttons
        btn_frame = tk.Frame(header, bg=COLORS["card"])
        btn_frame.pack(side="right")

        approve_all_btn = tk.Label(btn_frame, text="✓ Approve All",
                                  font=("Arial", 10, "bold"),
                                  fg="#000000", bg="#00ff88",
                                  padx=12, pady=6, cursor="hand2")
        approve_all_btn.pack(side="left", padx=5)
        approve_all_btn.bind("<Button-1>", lambda e: self.approve_all_barrier())

        deny_all_btn = tk.Label(btn_frame, text="✗ Deny All",
                               font=("Arial", 10, "bold"),
                               fg="#ffffff", bg="#ff4444",
                               padx=12, pady=6, cursor="hand2")
        deny_all_btn.pack(side="left", padx=5)
        deny_all_btn.bind("<Button-1>", lambda e: self.deny_all_barrier())

        turn_off_btn = tk.Label(btn_frame, text="⏻ Turn Off",
                               font=("Arial", 10, "bold"),
                               fg="#ffffff", bg="#666666",
                               padx=12, pady=6, cursor="hand2")
        turn_off_btn.pack(side="left", padx=5)
        turn_off_btn.bind("<Button-1>", lambda e: self.turn_off_barrier_mode())

        # Status
        self.barrier_status = tk.Label(header, text="",
                                       font=("Arial", 9),
                                       fg=COLORS["text_muted"], bg=COLORS["card"])
        self.barrier_status.pack(side="right", padx=20)

        # Request list container with scrollbar
        list_container = tk.Frame(self.barrier_window, bg=COLORS["bg"])
        list_container.pack(fill="both", expand=True, padx=10, pady=10)

        canvas = tk.Canvas(list_container, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(list_container, orient="vertical", command=canvas.yview)
        self.barrier_list_frame = tk.Frame(canvas, bg=COLORS["bg"])

        self.barrier_list_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.barrier_list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Store canvas reference for refresh
        self.barrier_canvas = canvas

        # Populate list
        self.refresh_barrier_list()

        # Auto-refresh every 2 seconds (500ms was too fast, caused flickering)
        self._barrier_refresh_job = None
        def auto_refresh():
            if self.barrier_window:
                self.refresh_barrier_list()
                self._barrier_refresh_job = self.barrier_window.after(2000, auto_refresh)
        auto_refresh()

    def refresh_barrier_list(self):
        """Refresh the list of pending requests (only if changed)."""
        if not self.barrier_window or not self.barrier_list_frame:
            return

        pending = self.session_mgr.get_pending_requests()
        pending_ids = [r.id for r in pending]

        # Check if anything changed - skip rebuild if same
        if hasattr(self, '_last_pending_ids') and self._last_pending_ids == pending_ids:
            return  # No change, skip refresh to prevent flickering

        self._last_pending_ids = pending_ids

        # Clear existing items
        for widget in self.barrier_list_frame.winfo_children():
            widget.destroy()

        if not pending:
            tk.Label(self.barrier_list_frame,
                    text="No pending requests",
                    font=("Arial", 12),
                    fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(pady=50)
            if hasattr(self, 'barrier_status') and self.barrier_status:
                self.barrier_status.configure(text="Waiting for requests...")
            return

        if hasattr(self, 'barrier_status') and self.barrier_status:
            self.barrier_status.configure(text=f"{len(pending)} request(s) awaiting approval")

        for req in pending:
            self._create_request_card(req)

        self.update_barrier_indicator()

    def _create_request_card(self, req):
        """Create a card for a single pending request."""
        card = tk.Frame(self.barrier_list_frame, bg=COLORS["card"], pady=10, padx=15)
        card.pack(fill="x", pady=5, padx=5)

        # Top row: Session, Provider, Model, Cost
        top_row = tk.Frame(card, bg=COLORS["card"])
        top_row.pack(fill="x")

        tk.Label(top_row, text=f"[{req.session_name}]",
                font=("Arial", 10, "bold"),
                fg="#00aaff", bg=COLORS["card"]).pack(side="left")

        tk.Label(top_row, text=f"  {req.provider}",
                font=("Arial", 10),
                fg="#ff00ff", bg=COLORS["card"]).pack(side="left")

        tk.Label(top_row, text=f" → {req.model}",
                font=("Arial", 10),
                fg=COLORS["text"], bg=COLORS["card"]).pack(side="left")

        tk.Label(top_row, text=f"${req.estimated_cost:.4f}",
                font=("Arial", 10, "bold"),
                fg="#ffaa00", bg=COLORS["card"]).pack(side="right")

        tk.Label(top_row, text=req.timestamp,
                font=("Arial", 9),
                fg=COLORS["text_muted"], bg=COLORS["card"]).pack(side="right", padx=10)

        # Prompt preview (if any)
        if req.prompt_preview:
            prompt_frame = tk.Frame(card, bg="#1a1a2e", padx=8, pady=5)
            prompt_frame.pack(fill="x", pady=(8, 0))

            tk.Label(prompt_frame, text=req.prompt_preview,
                    font=("Arial", 9),
                    fg=COLORS["text_secondary"], bg="#1a1a2e",
                    wraplength=600, justify="left").pack(anchor="w")

        # Action buttons
        btn_row = tk.Frame(card, bg=COLORS["card"])
        btn_row.pack(fill="x", pady=(10, 0))

        approve_btn = tk.Label(btn_row, text="✓ Approve",
                              font=("Arial", 9, "bold"),
                              fg="#000000", bg="#00ff88",
                              padx=10, pady=4, cursor="hand2")
        approve_btn.pack(side="left", padx=(0, 5))
        approve_btn.bind("<Button-1>", lambda e, r=req: self.approve_barrier_request(r.id))

        deny_btn = tk.Label(btn_row, text="✗ Deny",
                           font=("Arial", 9, "bold"),
                           fg="#ffffff", bg="#ff4444",
                           padx=10, pady=4, cursor="hand2")
        deny_btn.pack(side="left")
        deny_btn.bind("<Button-1>", lambda e, r=req: self.deny_barrier_request(r.id))

    def approve_barrier_request(self, request_id):
        """Approve a single request."""
        self.session_mgr.approve_request(request_id)
        self.refresh_barrier_list()
        self.update_barrier_indicator()

    def deny_barrier_request(self, request_id):
        """Deny a single request."""
        self.session_mgr.deny_request(request_id)
        self.refresh_barrier_list()
        self.update_barrier_indicator()

    def approve_all_barrier(self):
        """Approve all pending requests."""
        self.session_mgr.approve_all_requests()
        self.refresh_barrier_list()
        self.update_barrier_indicator()

    def deny_all_barrier(self):
        """Deny all pending requests."""
        self.session_mgr.deny_all_requests()
        self.refresh_barrier_list()
        self.update_barrier_indicator()

    def turn_off_barrier_mode(self):
        """Turn off barrier mode globally and release any pending requests."""
        self.session_mgr.settings["barrier_mode"] = False
        self.session_mgr._save()
        # Auto-approve any pending requests so they're not stuck waiting
        self.session_mgr.approve_all_requests()
        self.update_barrier_indicator()
        # Close the barrier window
        if self.barrier_window:
            self.barrier_window.destroy()
            self.barrier_window = None
        messagebox.showinfo("Barrier Mode", "Barrier mode has been turned OFF.\nAny pending requests have been auto-approved.")

    def create_ui(self):
        # Main container
        self.main = tk.Frame(self.root, bg=COLORS["bg"])
        self.main.pack(fill="both", expand=True)

        # Sidebar
        self.sidebar = tk.Frame(self.main, bg=COLORS["bg_secondary"], width=200)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo
        logo_frame = tk.Frame(self.sidebar, bg=COLORS["bg_secondary"], pady=25)
        logo_frame.pack(fill="x")

        logo = tk.Label(logo_frame, text="APIBouncer",
                       font=("Arial", 16, "bold"),
                       fg=COLORS["text"], bg=COLORS["bg_secondary"])
        logo.pack()

        version_label = tk.Label(logo_frame, text=f"v{APP_VERSION}",
                          font=("Arial", 9),
                          fg=COLORS["text_muted"], bg=COLORS["bg_secondary"],
                          cursor="hand2")
        version_label.pack()
        version_label.bind("<Button-1>", lambda e: self.show_version_history())

        # Nav items
        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "📊 Dashboard"),
            ("analytics", "📈 Analytics"),
            ("sessions", "🔑 Sessions"),
            ("history", "📜 History"),
            ("keys", "🔐 API Keys"),
            ("settings", "⚙️ Settings"),
        ]

        for tab_id, label in nav_items:
            btn = tk.Label(self.sidebar, text=label,
                          font=("Segoe UI", 11),
                          fg=COLORS["text_secondary"],
                          bg=COLORS["bg_secondary"],
                          pady=12, padx=20, anchor="w",
                          cursor="hand2")
            btn.pack(fill="x")
            btn.bind("<Button-1>", lambda e, t=tab_id: self.show_tab(t))
            btn.bind("<Enter>", lambda e, b=btn: self.nav_hover(b, True))
            btn.bind("<Leave>", lambda e, b=btn: self.nav_hover(b, False))
            self.nav_buttons[tab_id] = btn

        # BARRIER MODE INDICATOR - Above panic button
        barrier_frame = tk.Frame(self.sidebar, bg=COLORS["bg_secondary"])
        barrier_frame.pack(side="bottom", fill="x", padx=15, pady=(0, 5))

        self.barrier_indicator = tk.Label(barrier_frame, text="🛡️ Barrier: 0 pending",
                                         font=("Arial", 10),
                                         fg=COLORS["text_muted"], bg=COLORS["card"],
                                         pady=8, cursor="hand2")
        self.barrier_indicator.pack(fill="x")
        self.barrier_indicator.bind("<Button-1>", lambda e: self.show_barrier_window())

        # Update indicator based on barrier mode status
        self.update_barrier_indicator()

        # PANIC BUTTON - Bottom of sidebar
        panic_frame = tk.Frame(self.sidebar, bg=COLORS["bg_secondary"])
        panic_frame.pack(side="bottom", fill="x", pady=20, padx=15)

        self.panic_btn = tk.Label(panic_frame, text="🚨 PANIC",
                                 font=("Arial", 12, "bold"),
                                 fg="#ffffff", bg="#cc0000",
                                 pady=10, cursor="hand2")
        self.panic_btn.pack(fill="x")
        self.panic_btn.bind("<Button-1>", lambda e: self.toggle_panic())

        self.panic_status = tk.Label(panic_frame, text="",
                                    font=("Arial", 8),
                                    fg=COLORS["text_muted"], bg=COLORS["bg_secondary"])
        self.panic_status.pack()

        # Content area (must be created before update_panic_status)
        self.content = tk.Frame(self.main, bg=COLORS["bg"])
        self.content.pack(side="right", fill="both", expand=True)

        # Now safe to update panic status (needs self.content)
        self.update_panic_status()

    def show_version_history(self):
        """Show version history dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Version History")
        dialog.geometry("450x350")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=COLORS["bg"], padx=25, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text=f"APIBouncer v{APP_VERSION}",
                font=("Arial", 16, "bold"),
                fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w")

        tk.Label(frame, text="Version History",
                font=("Arial", 11),
                fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(anchor="w", pady=(5, 15))

        # Changelog
        for version, date, changes in VERSION_HISTORY:
            row = tk.Frame(frame, bg=COLORS["bg"])
            row.pack(fill="x", pady=3)

            ver_color = "#00ffaa" if version == APP_VERSION else COLORS["text_muted"]
            tk.Label(row, text=f"v{version}",
                    font=("Arial", 10, "bold"),
                    fg=ver_color, bg=COLORS["bg"], width=8, anchor="w").pack(side="left")

            tk.Label(row, text=changes,
                    font=("Arial", 10),
                    fg=COLORS["text"], bg=COLORS["bg"]).pack(side="left", padx=10)

        # Close button
        close_btn = tk.Label(frame, text="  Close  ",
                            font=("Arial", 11, "bold"),
                            fg="#000000", bg=COLORS["accent"],
                            padx=20, pady=8, cursor="hand2")
        close_btn.pack(pady=(20, 0))
        close_btn.bind("<Button-1>", lambda e: dialog.destroy())

    def toggle_panic(self):
        """Toggle panic mode - block all API calls."""
        is_active = self.session_mgr.is_panic_mode()

        if is_active:
            # Confirm to DISABLE (resume spending)
            if messagebox.askyesno("Disable Panic Mode",
                                   "Resume normal API operations?\n\nThis will allow API calls (and spending) again."):
                self.session_mgr.set_panic_mode(False)
                self.update_panic_status()
        else:
            # NO confirmation to ENABLE - immediate protection
            self.session_mgr.set_panic_mode(True)
            self.update_panic_status()

    def update_panic_status(self):
        """Update panic button and UI appearance based on current state."""
        is_active = self.session_mgr.is_panic_mode()

        if is_active:
            # Button shows deactivate option
            self.panic_btn.config(text="🛑 CLICK TO DISABLE", bg="#ff0000", fg="#ffffff")
            self.panic_status.config(text="", fg="#ff4444")
            # Red background on main content area
            self.content.config(bg="#4a0000")
            self.main.config(bg="#4a0000")
            # Show panic banner if not already shown
            if not hasattr(self, 'panic_banner') or not self.panic_banner.winfo_exists():
                self.panic_banner = tk.Frame(self.content, bg="#cc0000")
                self.panic_banner.pack(fill="x", side="top")
                tk.Label(self.panic_banner,
                        text="🚨 PANIC MODE ENABLED - NO MONEY WILL BE SPENT 🚨",
                        font=("Arial", 14, "bold"),
                        fg="#ffffff", bg="#cc0000",
                        pady=15).pack()
                tk.Label(self.panic_banner,
                        text="All API calls are blocked. Click PANIC button to resume.",
                        font=("Arial", 10),
                        fg="#ffcccc", bg="#cc0000").pack(pady=(0, 10))
        else:
            # Normal state
            self.panic_btn.config(text="🚨 PANIC", bg="#cc0000", fg="#ffffff")
            self.panic_status.config(text="Click to stop all calls", fg=COLORS["text_muted"])
            # Restore normal background
            self.content.config(bg=COLORS["bg"])
            self.main.config(bg=COLORS["bg"])
            # Remove panic banner if exists
            if hasattr(self, 'panic_banner') and self.panic_banner.winfo_exists():
                self.panic_banner.destroy()

    def nav_hover(self, btn, enter):
        if btn.cget("bg") != COLORS["accent"]:
            btn.config(bg=COLORS["card"] if enter else COLORS["bg_secondary"])

    def show_tab(self, tab_id):
        self.current_tab = tab_id

        # Update nav styling
        for tid, btn in self.nav_buttons.items():
            if tid == tab_id:
                btn.config(bg=COLORS["accent"], fg=COLORS["text"])
            else:
                btn.config(bg=COLORS["bg_secondary"], fg=COLORS["text_secondary"])

        # Clear content (including panic banner)
        for widget in self.content.winfo_children():
            widget.destroy()

        # Re-add panic banner if active (before tab content)
        if self.session_mgr.is_panic_mode():
            self.panic_banner = tk.Frame(self.content, bg="#cc0000")
            self.panic_banner.pack(fill="x", side="top")
            tk.Label(self.panic_banner,
                    text="🚨 PANIC MODE ENABLED - NO MONEY WILL BE SPENT 🚨",
                    font=("Arial", 14, "bold"),
                    fg="#ffffff", bg="#cc0000",
                    pady=15).pack()
            tk.Label(self.panic_banner,
                    text="All API calls are blocked. Click PANIC button to resume.",
                    font=("Arial", 10),
                    fg="#ffcccc", bg="#cc0000").pack(pady=(0, 10))
            self.content.config(bg="#4a0000")

        # Show appropriate content
        if tab_id == "dashboard":
            self.show_dashboard()
        elif tab_id == "analytics":
            self.show_analytics()
        elif tab_id == "sessions":
            self.show_sessions()
        elif tab_id == "history":
            self.show_history()
        elif tab_id == "keys":
            self.show_keys()
        elif tab_id == "settings":
            self.show_settings()

    def show_dashboard(self):
        """Show main dashboard with stats."""
        stats = self.session_mgr.get_stats()

        # Header
        header = tk.Frame(self.content, bg=COLORS["bg"], pady=20, padx=30)
        header.pack(fill="x")

        title = tk.Label(header, text="Dashboard",
                        font=("Segoe UI", 24, "bold"),
                        fg=COLORS["text"], bg=COLORS["bg"])
        title.pack(anchor="w")

        subtitle = tk.Label(header, text="Monitor your API usage and savings",
                           font=("Segoe UI", 11),
                           fg=COLORS["text_secondary"], bg=COLORS["bg"])
        subtitle.pack(anchor="w")

        # Stats cards row 1 - Money
        cards1 = tk.Frame(self.content, bg=COLORS["bg"], padx=30)
        cards1.pack(fill="x", pady=(0, 15))

        self.create_stat_card(cards1, "Money Saved", f"${stats['total_saved']:.2f}",
                             COLORS["success"], "From blocked requests")
        self.create_stat_card(cards1, "Money Spent", f"${stats['total_spent']:.2f}",
                             COLORS["warning"], "On allowed requests")
        # Protection rate - how much of potential spending was blocked
        total_potential = stats['total_saved'] + stats['total_spent']
        protection_pct = (stats['total_saved'] / total_potential * 100) if total_potential > 0 else 0
        self.create_stat_card(cards1, "Protected", f"{protection_pct:.0f}%",
                             COLORS["success"] if protection_pct > 50 else COLORS["accent"],
                             "Of potential spending blocked")

        # Stats cards row 2 - Sessions
        cards2 = tk.Frame(self.content, bg=COLORS["bg"], padx=30)
        cards2.pack(fill="x", pady=(0, 15))

        self.create_stat_card(cards2, "Active Sessions", str(stats['active_sessions']),
                             COLORS["success"], "Currently active project sessions")
        self.create_stat_card(cards2, "Warned", str(stats['warned_sessions']),
                             COLORS["warning"], "Sessions with warnings")
        self.create_stat_card(cards2, "Banned", str(stats['banned_sessions']),
                             COLORS["danger"], "Blocked sessions")

        # Stats cards row 3 - Requests
        cards3 = tk.Frame(self.content, bg=COLORS["bg"], padx=30)
        cards3.pack(fill="x", pady=(0, 20))

        self.create_stat_card(cards3, "Total Requests", str(stats['total_requests']),
                             COLORS["text"], "All API requests")
        self.create_stat_card(cards3, "Blocked", str(stats['total_blocked']),
                             COLORS["danger"], "Requests that were blocked")
        self.create_stat_card(cards3, "Block Rate", f"{stats['block_rate']:.1f}%",
                             COLORS["warning"] if stats['block_rate'] > 20 else COLORS["success"],
                             "Percentage of requests blocked")

        # Support message (only show if user has saved money)
        if stats['total_saved'] > 0:
            support_frame = tk.Frame(self.content, bg="#1a1a2e", padx=20, pady=12)
            support_frame.pack(fill="x", padx=30, pady=(0, 15))

            support_text = tk.Label(support_frame,
                text=f"APIBouncer saved you ${stats['total_saved']:.2f}. If it's been useful, consider supporting development.",
                font=("Segoe UI", 10),
                fg="#888899", bg="#1a1a2e")
            support_text.pack(side="left")

            donate_btn = tk.Label(support_frame, text="$logik109",
                font=("Segoe UI", 10, "bold"),
                fg="#00ff88", bg="#1a1a2e", cursor="hand2")
            donate_btn.pack(side="left", padx=(10, 0))
            donate_btn.bind("<Button-1>", lambda e: __import__('webbrowser').open("https://cash.app/$logik109"))

        # Recent activity
        activity_frame = tk.Frame(self.content, bg=COLORS["bg"], padx=30)
        activity_frame.pack(fill="both", expand=True)

        activity_title = tk.Label(activity_frame, text="Recent Activity",
                                 font=("Segoe UI", 14, "bold"),
                                 fg=COLORS["text"], bg=COLORS["bg"])
        activity_title.pack(anchor="w", pady=(0, 10))

        # Activity list
        activity_list = tk.Frame(activity_frame, bg=COLORS["card"])
        activity_list.pack(fill="both", expand=True)

        history = self.session_mgr.get_recent_history(10)
        if history:
            for attempt in history:
                self.create_activity_row(activity_list, attempt)
        else:
            empty = tk.Label(activity_list, text="No activity yet",
                           font=("Segoe UI", 11),
                           fg=COLORS["text_muted"], bg=COLORS["card"],
                           pady=30)
            empty.pack()

    def create_stat_card(self, parent, title, value, color, tooltip=""):
        """Create a statistics card."""
        card = tk.Frame(parent, bg=COLORS["card"], padx=20, pady=15)
        card.pack(side="left", fill="x", expand=True, padx=(0, 10))

        val = tk.Label(card, text=value,
                      font=("Segoe UI", 28, "bold"),
                      fg=color, bg=COLORS["card"])
        val.pack(anchor="w")

        lbl = tk.Label(card, text=title,
                      font=("Segoe UI", 10),
                      fg=COLORS["text_secondary"], bg=COLORS["card"])
        lbl.pack(anchor="w")

    def create_activity_row(self, parent, attempt):
        """Create an activity row."""
        row = tk.Frame(parent, bg=COLORS["card"], pady=8, padx=15)
        row.pack(fill="x")

        # Status indicator
        status_color = COLORS["success"] if attempt.status == "allowed" else COLORS["danger"]
        status = tk.Label(row, text="●", font=("Segoe UI", 10),
                         fg=status_color, bg=COLORS["card"])
        status.pack(side="left", padx=(0, 10))

        # Details
        details = tk.Frame(row, bg=COLORS["card"])
        details.pack(side="left", fill="x", expand=True)

        provider_model = tk.Label(details, text=f"{attempt.provider} / {attempt.model}",
                                 font=("Segoe UI", 10),
                                 fg=COLORS["text"], bg=COLORS["card"])
        provider_model.pack(anchor="w")

        session_time = tk.Label(details,
                               text=f"Session: {mask_session_id(attempt.session_id)} • {attempt.timestamp[:16]}",
                               font=("Segoe UI", 9),
                               fg=COLORS["text_muted"], bg=COLORS["card"])
        session_time.pack(anchor="w")

        # Cost
        cost = tk.Label(row, text=f"${attempt.estimated_cost:.4f}",
                       font=("Segoe UI", 10, "bold"),
                       fg=status_color, bg=COLORS["card"])
        cost.pack(side="right")

    def show_analytics(self):
        """Show analytics with provider health checks."""
        import threading
        import urllib.request
        import ssl
        import time

        header = tk.Frame(self.content, bg=COLORS["bg"], pady=20, padx=30)
        header.pack(fill="x")

        tk.Label(header, text="Analytics",
                font=("Arial", 24, "bold"),
                fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w")

        tk.Label(header, text="Provider health and cost breakdown",
                font=("Arial", 11),
                fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(anchor="w")

        # Provider Health Section
        health_frame = tk.Frame(self.content, bg=COLORS["bg"], padx=30)
        health_frame.pack(fill="x", pady=(10, 20))

        tk.Label(health_frame, text="🏥 Provider Health",
                font=("Arial", 14, "bold"),
                fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w", pady=(0, 10))

        health_row = tk.Frame(health_frame, bg=COLORS["card"], padx=20, pady=15)
        health_row.pack(fill="x")

        # Provider endpoints to check
        providers = {
            "OpenAI": "https://api.openai.com/v1/models",
            "Anthropic": "https://api.anthropic.com/v1/messages",
            "MiniMax": "https://api.minimax.chat/v1",
            "Fal.ai": "https://fal.run",
        }

        health_labels = {}

        for prov in providers:
            prov_frame = tk.Frame(health_row, bg=COLORS["card"], padx=15)
            prov_frame.pack(side="left", expand=True)

            tk.Label(prov_frame, text=prov,
                    font=("Arial", 10, "bold"),
                    fg=COLORS["text"], bg=COLORS["card"]).pack()

            status_lbl = tk.Label(prov_frame, text="● CHECKING...",
                    font=("Arial", 9),
                    fg=COLORS["text_muted"], bg=COLORS["card"])
            status_lbl.pack()

            latency_lbl = tk.Label(prov_frame, text="--ms",
                    font=("Arial", 8),
                    fg=COLORS["text_muted"], bg=COLORS["card"])
            latency_lbl.pack()

            health_labels[prov] = (status_lbl, latency_lbl)

        # Async health check function
        def check_health(provider, url, status_lbl, latency_lbl):
            try:
                ctx = ssl.create_default_context()
                start = time.time()
                req = urllib.request.Request(url, method='HEAD')
                req.add_header('User-Agent', 'APIBouncer-HealthCheck/1.0')
                urllib.request.urlopen(req, timeout=5, context=ctx)
                latency = int((time.time() - start) * 1000)
                status = "healthy"
            except urllib.error.HTTPError as e:
                latency = int((time.time() - start) * 1000)
                status = "healthy" if e.code in [401, 403, 405] else "degraded"
            except Exception:
                latency = 0
                status = "offline"

            def update_ui():
                # Check if widgets still exist before updating
                try:
                    if not status_lbl.winfo_exists() or not latency_lbl.winfo_exists():
                        return
                    colors = {"healthy": COLORS["success"], "degraded": COLORS["warning"], "offline": COLORS["danger"]}
                    status_lbl.config(text=f"● {status.upper()}", fg=colors.get(status, COLORS["text_muted"]))
                    latency_lbl.config(text=f"{latency}ms" if latency > 0 else "N/A")
                except tk.TclError:
                    pass  # Widget was destroyed

            self.root.after(0, update_ui)

        # Start health checks in threads
        for prov, url in providers.items():
            s_lbl, l_lbl = health_labels[prov]
            t = threading.Thread(target=check_health, args=(prov, url, s_lbl, l_lbl), daemon=True)
            t.start()

        # Cost by Provider
        cost_frame = tk.Frame(self.content, bg=COLORS["bg"], padx=30)
        cost_frame.pack(fill="x", pady=(0, 20))

        tk.Label(cost_frame, text="💰 Cost by Provider",
                font=("Arial", 14, "bold"),
                fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w", pady=(0, 10))

        # Calculate costs from history
        provider_costs = {}
        provider_counts = {}
        for attempt in self.session_mgr.history:
            if attempt.status == "allowed":
                prov = attempt.provider
                provider_costs[prov] = provider_costs.get(prov, 0) + attempt.estimated_cost
                provider_counts[prov] = provider_counts.get(prov, 0) + 1

        if provider_costs:
            cost_row = tk.Frame(cost_frame, bg=COLORS["card"], padx=20, pady=15)
            cost_row.pack(fill="x")

            max_cost = max(provider_costs.values()) if provider_costs else 1
            for prov, cost in provider_costs.items():
                prov_frame = tk.Frame(cost_row, bg=COLORS["card"])
                prov_frame.pack(fill="x", pady=5)

                tk.Label(prov_frame, text=prov.upper(),
                        font=("Arial", 10, "bold"),
                        fg=COLORS["accent"], bg=COLORS["card"], width=12, anchor="w").pack(side="left")

                # Bar
                bar_width = int((cost / max_cost) * 200) if max_cost > 0 else 0
                bar_frame = tk.Frame(prov_frame, bg=COLORS["success"], width=bar_width, height=20)
                bar_frame.pack(side="left", padx=10)
                bar_frame.pack_propagate(False)

                tk.Label(prov_frame, text=f"${cost:.4f} ({provider_counts.get(prov, 0)} calls)",
                        font=("Arial", 10),
                        fg=COLORS["text"], bg=COLORS["card"]).pack(side="left")
        else:
            tk.Label(cost_frame, text="No cost data yet",
                    font=("Arial", 10),
                    fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(anchor="w")

        # Savings breakdown
        savings_frame = tk.Frame(self.content, bg=COLORS["bg"], padx=30)
        savings_frame.pack(fill="x", pady=(0, 20))

        tk.Label(savings_frame, text="🛡️ Savings Breakdown",
                font=("Arial", 14, "bold"),
                fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w", pady=(0, 10))

        savings_row = tk.Frame(savings_frame, bg=COLORS["card"], padx=20, pady=15)
        savings_row.pack(fill="x")

        stats = self.session_mgr.get_stats()
        savings_items = [
            ("Total Saved", f"${stats['total_saved']:.2f}", COLORS["success"]),
            ("Total Spent", f"${stats['total_spent']:.2f}", COLORS["warning"]),
            ("Block Rate", f"{stats['block_rate']:.1f}%", COLORS["accent"]),
            ("Total Blocked", str(stats['total_blocked']), COLORS["danger"]),
        ]

        for label, value, color in savings_items:
            item_frame = tk.Frame(savings_row, bg=COLORS["card"], padx=15)
            item_frame.pack(side="left", expand=True)

            tk.Label(item_frame, text=value,
                    font=("Arial", 18, "bold"),
                    fg=color, bg=COLORS["card"]).pack()
            tk.Label(item_frame, text=label,
                    font=("Arial", 9),
                    fg=COLORS["text_muted"], bg=COLORS["card"]).pack()

    def show_sessions(self):
        """Show sessions management."""
        header = tk.Frame(self.content, bg=COLORS["bg"], pady=20, padx=30)
        header.pack(fill="x")

        title = tk.Label(header, text="Sessions",
                        font=("Segoe UI", 24, "bold"),
                        fg=COLORS["text"], bg=COLORS["bg"])
        title.pack(side="left")

        # New session button
        new_btn = tk.Label(header, text="+ New Session",
                          font=("Segoe UI", 11, "bold"),
                          fg=COLORS["bg"], bg=COLORS["accent"],
                          padx=15, pady=8, cursor="hand2")
        new_btn.pack(side="right")
        new_btn.bind("<Button-1>", lambda e: self.create_session_dialog())

        # Sessions list
        list_frame = tk.Frame(self.content, bg=COLORS["bg"], padx=30)
        list_frame.pack(fill="both", expand=True)

        # Headers
        headers = tk.Frame(list_frame, bg=COLORS["bg"])
        headers.pack(fill="x", pady=(0, 10))

        for text, width in [("Session", 120), ("Status", 80), ("Requests", 80),
                           ("Blocked", 80), ("Saved", 100), ("Actions", 150)]:
            tk.Label(headers, text=text, font=("Segoe UI", 9, "bold"),
                    fg=COLORS["text_muted"], bg=COLORS["bg"],
                    width=width//8, anchor="w").pack(side="left", padx=5)

        # Session rows
        sessions_container = tk.Frame(list_frame, bg=COLORS["card"])
        sessions_container.pack(fill="both", expand=True)

        if self.session_mgr.sessions:
            for session in self.session_mgr.sessions.values():
                self.create_session_row(sessions_container, session)
        else:
            empty = tk.Label(sessions_container,
                           text="No sessions yet. Create one to start tracking.",
                           font=("Segoe UI", 11),
                           fg=COLORS["text_muted"], bg=COLORS["card"],
                           pady=40)
            empty.pack()

    def create_session_row(self, parent, session):
        """Create a session row."""
        row = tk.Frame(parent, bg=COLORS["card"], pady=15, padx=20)
        row.pack(fill="x", pady=5)
        row.bind("<Enter>", lambda e: row.config(bg=COLORS["card_hover"]))
        row.bind("<Leave>", lambda e: row.config(bg=COLORS["card"]))

        # Session name only - ID is secret, never show it
        name_label = tk.Label(row, text=session.name,
                font=("Arial", 14, "bold"),
                fg="#00ffff", bg=COLORS["card"],
                padx=10, pady=8, width=15, anchor="w")
        name_label.pack(side="left")

        # Status
        status_colors = {"active": "#00ff00", "warned": "#ffff00", "banned": "#ff4444"}
        status_label = tk.Label(row, text=session.status.upper(),
                font=("Arial", 11, "bold"),
                fg=status_colors.get(session.status, "#ffffff"),
                bg=COLORS["card"], width=10, pady=5)
        status_label.pack(side="left", padx=10)

        # Stats - requests
        tk.Label(row, text=str(session.total_requests),
                font=("Arial", 12, "bold"),
                fg="#ffffff", bg=COLORS["card"], width=8, pady=5).pack(side="left", padx=5)

        # Stats - blocked
        tk.Label(row, text=str(session.blocked_requests),
                font=("Arial", 12, "bold"),
                fg="#ffffff", bg=COLORS["card"], width=8, pady=5).pack(side="left", padx=5)

        # Stats - saved
        tk.Label(row, text=f"${session.blocked_cost:.2f}",
                font=("Arial", 12, "bold"),
                fg="#00ff00", bg=COLORS["card"], width=10, pady=5).pack(side="left", padx=5)

        # Actions
        actions = tk.Frame(row, bg=COLORS["card"])
        actions.pack(side="right")

        # Monitor button (real-time view)
        monitor_btn = tk.Label(actions, text="[Monitor]",
                              font=("Arial", 10, "bold"),
                              fg="#00ffaa", bg=COLORS["card"],
                              cursor="hand2", padx=8, pady=3)
        monitor_btn.pack(side="left")
        monitor_btn.bind("<Button-1>", lambda e, s=session: self.open_session_monitor(s))

        # Edit permissions button
        edit_btn = tk.Label(actions, text="[Keys]",
                           font=("Arial", 10, "bold"),
                           fg="#4488ff", bg=COLORS["card"],
                           cursor="hand2", padx=8, pady=3)
        edit_btn.pack(side="left")
        edit_btn.bind("<Button-1>", lambda e, s=session: self.edit_session_permissions(s))

        # Model restrictions button
        models_btn = tk.Label(actions, text="[Models]",
                             font=("Arial", 10, "bold"),
                             fg="#ffaa00", bg=COLORS["card"],
                             cursor="hand2", padx=8, pady=3)
        models_btn.pack(side="left")
        models_btn.bind("<Button-1>", lambda e, s=session: self.edit_model_restrictions(s))

        # Budget button
        budget_text = f"[${session.budget_limit:.0f}]" if session.budget_limit > 0 else "[Budget]"
        budget_color = "#ff4444" if session.budget_limit > 0 and session.total_cost >= session.budget_limit else "#00ffaa"
        budget_btn = tk.Label(actions, text=budget_text,
                             font=("Arial", 10, "bold"),
                             fg=budget_color, bg=COLORS["card"],
                             cursor="hand2", padx=8, pady=3)
        budget_btn.pack(side="left")
        budget_btn.bind("<Button-1>", lambda e, s=session: self.edit_session_budget(s))

        if session.status != "banned":
            ban_btn = tk.Label(actions, text="[Ban]",
                              font=("Arial", 10, "bold"),
                              fg="#ff4444", bg=COLORS["card"],
                              cursor="hand2", padx=8, pady=3)
            ban_btn.pack(side="left")
            ban_btn.bind("<Button-1>", lambda e, s=session: self.ban_session(s.id))
        else:
            unban_btn = tk.Label(actions, text="[Unban]",
                                font=("Arial", 10, "bold"),
                                fg="#00ff00", bg=COLORS["card"],
                                cursor="hand2", padx=8, pady=3)
            unban_btn.pack(side="left")
            unban_btn.bind("<Button-1>", lambda e, s=session: self.unban_session(s.id))

        delete_btn = tk.Label(actions, text="[Delete]",
                             font=("Arial", 10),
                             fg="#888888", bg=COLORS["card"],
                             cursor="hand2", padx=8, pady=3)
        delete_btn.pack(side="left")
        delete_btn.bind("<Button-1>", lambda e, s=session: self.delete_session(s.id))

    def create_session_dialog(self):
        """Dialog to create a new session with API key selection."""
        dialog = tk.Toplevel(self.root)
        dialog.title("New Session")
        dialog.geometry("550x550")
        dialog.minsize(480, 480)
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=COLORS["bg"], padx=30, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Create New Session",
                font=("Segoe UI", 16, "bold"),
                fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w")

        # Warning about one-time display
        warning = tk.Frame(frame, bg=COLORS["danger"], pady=8, padx=10)
        warning.pack(fill="x", pady=(10, 15))

        tk.Label(warning, text="⚠️ IMPORTANT: The Session ID will only be shown ONCE!",
                font=("Segoe UI", 10, "bold"),
                fg=COLORS["text"], bg=COLORS["danger"]).pack(anchor="w")
        tk.Label(warning, text="Treat it like an API key. If you lose it, create a new session.",
                font=("Segoe UI", 9),
                fg=COLORS["text"], bg=COLORS["danger"]).pack(anchor="w")

        # Session name
        tk.Label(frame, text="Session Name",
                font=("Segoe UI", 10),
                fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(anchor="w", pady=(10, 5))

        name_entry = tk.Entry(frame, font=("Segoe UI", 12),
                             bg=COLORS["card"], fg=COLORS["text"],
                             insertbackground=COLORS["text"], relief="flat")
        name_entry.pack(fill="x", ipady=8)
        name_entry.focus_set()

        # API Key Access
        tk.Label(frame, text="API Key Access",
                font=("Segoe UI", 10),
                fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(anchor="w", pady=(20, 5))

        tk.Label(frame, text="Select which API keys this session can access:",
                font=("Segoe UI", 9),
                fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(anchor="w")

        # Checkboxes for each API
        checks_frame = tk.Frame(frame, bg=COLORS["card"], pady=10, padx=15)
        checks_frame.pack(fill="x", pady=(5, 15))

        api_keys = get_api_keys_list()
        check_vars = {}

        for key_id, display_name in api_keys:
            var = tk.BooleanVar(value=True)  # Default all checked
            check_vars[key_id] = var

            cb = tk.Checkbutton(checks_frame, text=display_name,
                               variable=var,
                               font=("Segoe UI", 10),
                               fg=COLORS["text"], bg=COLORS["card"],
                               selectcolor=COLORS["bg"],
                               activebackground=COLORS["card"],
                               activeforeground=COLORS["text"])
            cb.pack(anchor="w", pady=2)

        def create():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("Required", "Please enter a session name")
                return

            # Get selected APIs
            allowed_keys = [k for k, v in check_vars.items() if v.get()]
            if not allowed_keys:
                messagebox.showwarning("Required", "Select at least one API key")
                return

            session = self.session_mgr.create_session(name, allowed_keys)
            if session:
                # Auto-copy to clipboard
                self.root.clipboard_clear()
                self.root.clipboard_append(session.id)
                self.root.update()

                dialog.destroy()

                # Show the session ID in a special one-time dialog
                self.show_session_id_once(session.id, name, allowed_keys)

        btn = tk.Label(frame, text="Create Session",
                      font=("Segoe UI", 11, "bold"),
                      fg=COLORS["bg"], bg=COLORS["accent"],
                      padx=20, pady=10, cursor="hand2")
        btn.pack(pady=(10, 0))
        btn.bind("<Button-1>", lambda e: create())

    def show_session_id_once(self, session_id, name, allowed_keys):
        """Show session ID ONE TIME with AI handoff instructions."""
        dialog = tk.Toplevel(self.root)
        dialog.title("🤖 AI Session Created")
        dialog.geometry("700x600")
        dialog.minsize(600, 500)
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=COLORS["bg"], padx=30, pady=20)
        frame.pack(fill="both", expand=True)

        # Header
        tk.Label(frame, text=f"Session: {name}",
                font=("Segoe UI", 18, "bold"),
                fg=COLORS["accent"], bg=COLORS["bg"]).pack()

        tk.Label(frame, text="Copy the instructions below and give them to your AI",
                font=("Segoe UI", 11),
                fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(pady=(5, 10))

        # IMPORTANT: Next step warning
        next_step = tk.Frame(frame, bg="#ff6b35", pady=8, padx=12)
        next_step.pack(fill="x", pady=(0, 10))
        tk.Label(next_step, text="⚠️ NEXT STEP REQUIRED",
                font=("Segoe UI", 10, "bold"),
                fg="#ffffff", bg="#ff6b35").pack(anchor="w")
        tk.Label(next_step, text="After closing this dialog, configure ALLOWED MODELS in session settings.",
                font=("Segoe UI", 9),
                fg="#ffffff", bg="#ff6b35").pack(anchor="w")
        tk.Label(next_step, text="By default, NO models are allowed and all requests will be blocked.",
                font=("Segoe UI", 9),
                fg="#ffffff", bg="#ff6b35").pack(anchor="w")

        # Generate AI instructions
        ai_instructions = f'''# APIBouncer Session - {name}

## Your Session ID (keep this secret)
{session_id}

## How to make API calls

You have access to a SECURE PROXY. You never see API keys directly.
Import and use the proxy functions:

```python
from apibouncer import openai

# Generate an image (MUST specify quality='low' for this session)
result = openai.image(
    session_id="{session_id}",
    prompt="Your image description here",
    model="gpt-image-1.5",
    quality="low",  # REQUIRED - do not omit
    size="1024x1536",
    save_to="output.png"
)

# The image is saved to output.png
# result contains: {{"saved_to": "output.png", "b64_json": "..."}}
```

## Rules
- Always specify quality="low" (required by session restrictions)
- Always specify model="gpt-image-1.5"
- Always provide save_to path to save images
- Your session tracks costs and can be revoked if abused

## Available APIs: {", ".join(allowed_keys) if allowed_keys else "All"}
'''

        # Instructions text area
        text_frame = tk.Frame(frame, bg="#1e1e2e", pady=10, padx=15)
        text_frame.pack(fill="both", expand=True)

        text = tk.Text(text_frame, font=("Consolas", 10),
                      fg="#a6e3a1", bg="#1e1e2e",
                      wrap="word", height=15,
                      insertbackground="#a6e3a1",
                      selectbackground="#45475a")
        text.pack(fill="both", expand=True)
        text.insert("1.0", ai_instructions)
        text.config(state="disabled")  # Read-only

        # Buttons
        btn_frame = tk.Frame(frame, bg=COLORS["bg"])
        btn_frame.pack(fill="x", pady=(15, 0))

        def copy_instructions():
            self.root.clipboard_clear()
            self.root.clipboard_append(ai_instructions)
            self.root.update()
            copy_btn.config(text="✓ Copied!", bg=COLORS["success"])
            self.root.after(2000, lambda: copy_btn.config(text="📋 Copy AI Instructions", bg=COLORS["accent"]))

        copy_btn = tk.Label(btn_frame, text="📋 Copy AI Instructions",
                           font=("Segoe UI", 11, "bold"),
                           fg=COLORS["bg"], bg=COLORS["accent"],
                           padx=20, pady=10, cursor="hand2")
        copy_btn.pack(side="left", padx=(0, 10))
        copy_btn.bind("<Button-1>", lambda e: copy_instructions())

        def confirm():
            dialog.destroy()
            self.show_tab("sessions")
            # Auto-open model restrictions so user configures allowed models
            session = self.session_mgr.get_session(session_id)
            if session:
                self.root.after(100, lambda: self.edit_model_restrictions(session))

        done_btn = tk.Label(btn_frame, text="Configure Models",
                           font=("Segoe UI", 11, "bold"),
                           fg=COLORS["text"], bg=COLORS["card"],
                           padx=20, pady=10, cursor="hand2")
        done_btn.pack(side="left")
        done_btn.bind("<Button-1>", lambda e: confirm())

    def edit_session_permissions(self, session):
        """Edit which API keys a session can access."""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"API Keys - {session.name}")
        dialog.geometry("350x320")
        dialog.minsize(300, 280)
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=COLORS["bg"], padx=20, pady=15)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text=f"API Keys: {session.name}",
                font=("Arial", 13, "bold"),
                fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w")

        tk.Label(frame, text="Select which APIs this session can use:",
                font=("Arial", 10),
                fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(anchor="w", pady=(3, 10))

        # Checkboxes
        checks_frame = tk.Frame(frame, bg=COLORS["card"], pady=10, padx=15)
        checks_frame.pack(fill="x")

        api_keys = get_api_keys_list()
        check_vars = {}

        for key_id, display_name in api_keys:
            is_allowed = not session.allowed_keys or key_id in session.allowed_keys
            var = tk.BooleanVar(value=is_allowed)
            check_vars[key_id] = var

            cb = tk.Checkbutton(checks_frame, text=display_name,
                               variable=var,
                               font=("Arial", 11),
                               fg=COLORS["text"], bg=COLORS["card"],
                               selectcolor=COLORS["bg"],
                               activebackground=COLORS["card"],
                               activeforeground=COLORS["text"])
            cb.pack(anchor="w", pady=1)

        def save():
            allowed_keys = [k for k, v in check_vars.items() if v.get()]
            if not allowed_keys:
                messagebox.showwarning("Required", "Select at least one API key")
                return
            self.session_mgr.update_session_keys(session.id, allowed_keys)
            dialog.destroy()
            self.show_tab("sessions")

        btn = tk.Label(frame, text="  SAVE  ",
                      font=("Arial", 12, "bold"),
                      fg="#000000", bg="#4488ff",
                      padx=30, pady=8, cursor="hand2")
        btn.pack(pady=(15, 10))
        btn.bind("<Button-1>", lambda e: save())

    def edit_model_restrictions(self, session):
        """Edit which models a session can use (allow/ban list)."""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Restrictions - {session.name}")
        dialog.geometry("550x700")
        dialog.minsize(480, 580)
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        # Scrollable frame
        canvas = tk.Canvas(dialog, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg=COLORS["bg"], padx=20, pady=15)

        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw", width=490)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        tk.Label(frame, text=f"Restrictions: {session.name}",
                font=("Arial", 13, "bold"),
                fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w")

        # Require whitelist checkbox
        require_var = tk.BooleanVar(value=getattr(session, 'require_model_whitelist', True))
        require_cb = tk.Checkbutton(frame, text="Require whitelist (block ALL if empty)",
                                   variable=require_var,
                                   font=("Arial", 10, "bold"),
                                   fg="#ffaa00", bg=COLORS["bg"],
                                   selectcolor=COLORS["card"],
                                   activebackground=COLORS["bg"],
                                   activeforeground="#ffaa00")
        require_cb.pack(anchor="w", pady=(5, 10))

        # Allowed Models Section
        tk.Label(frame, text="ALLOWED MODELS (one per line)",
                font=("Arial", 10, "bold"),
                fg="#00ff00", bg=COLORS["bg"]).pack(anchor="w")
        tk.Label(frame, text="Examples: gpt-image-1.5, flux-dev, flux-schnell, video-01, dall-e-3",
                font=("Consolas", 9),
                fg="#888888", bg=COLORS["bg"]).pack(anchor="w")

        allowed_text = tk.Text(frame, height=3, font=("Consolas", 10),
                              bg=COLORS["card"], fg=COLORS["text"],
                              insertbackground=COLORS["text"], relief="flat")
        allowed_text.pack(fill="x", pady=(3, 5))
        if session.allowed_models:
            allowed_text.insert("1.0", "\n".join(session.allowed_models))

        # Warning about exact match
        warn_frame = tk.Frame(frame, bg="#332200", padx=8, pady=5)
        warn_frame.pack(fill="x", pady=(0, 10))
        tk.Label(warn_frame, text="⚠️ Names must be EXACT. Wrong name = blocked (free, no image).",
                font=("Arial", 9, "bold"),
                fg="#ffaa00", bg="#332200").pack(anchor="w")
        tk.Label(warn_frame, text="Use * as wildcard: flux-* matches flux-dev, flux-schnell, etc.",
                font=("Arial", 8),
                fg="#cc8800", bg="#332200").pack(anchor="w")

        # Banned Models Section
        tk.Label(frame, text="BANNED MODELS (always blocked)",
                font=("Arial", 10, "bold"),
                fg="#ff4444", bg=COLORS["bg"]).pack(anchor="w")
        tk.Label(frame, text="Examples: dall-e-2, gpt-4o (block expensive/unwanted models)",
                font=("Consolas", 9),
                fg="#888888", bg=COLORS["bg"]).pack(anchor="w")

        banned_text = tk.Text(frame, height=2, font=("Consolas", 10),
                             bg=COLORS["card"], fg=COLORS["text"],
                             insertbackground=COLORS["text"], relief="flat")
        banned_text.pack(fill="x", pady=(3, 8))
        if session.banned_models:
            banned_text.insert("1.0", "\n".join(session.banned_models))

        # Quality Control Section
        tk.Label(frame, text="─── QUALITY CONTROL (Images) ───",
                font=("Arial", 10, "bold"),
                fg="#00ffaa", bg=COLORS["bg"]).pack(anchor="w", pady=(15, 5))
        tk.Label(frame, text="Valid values: low, medium, high, standard, hd",
                font=("Consolas", 9),
                fg="#888888", bg=COLORS["bg"]).pack(anchor="w")

        tk.Label(frame, text="Allowed (comma-separated):",
                font=("Arial", 9),
                fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(anchor="w", pady=(5, 0))

        quality_allowed = tk.Entry(frame, font=("Consolas", 10),
                                  bg=COLORS["card"], fg=COLORS["text"],
                                  insertbackground=COLORS["text"], relief="flat")
        quality_allowed.pack(fill="x", pady=3, ipady=4)
        if getattr(session, 'allowed_qualities', []):
            quality_allowed.insert(0, ", ".join(session.allowed_qualities))

        tk.Label(frame, text="Example: low  (only cheap generations allowed)",
                font=("Arial", 8),
                fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(anchor="w")

        tk.Label(frame, text="Banned (comma-separated):",
                font=("Arial", 9),
                fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(anchor="w", pady=(8, 0))

        quality_banned = tk.Entry(frame, font=("Consolas", 10),
                                 bg=COLORS["card"], fg=COLORS["text"],
                                 insertbackground=COLORS["text"], relief="flat")
        quality_banned.pack(fill="x", pady=3, ipady=4)
        if getattr(session, 'banned_qualities', []):
            quality_banned.insert(0, ", ".join(session.banned_qualities))

        tk.Label(frame, text="Example: high, medium  (block expensive options)",
                font=("Arial", 8),
                fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(anchor="w")

        tk.Label(frame, text="Tip: Proxy defaults to 'low' if AI forgets to specify quality",
                font=("Arial", 8, "italic"),
                fg="#00aa00", bg=COLORS["bg"]).pack(anchor="w", pady=(5, 0))

        # Duration Control Section (for video models)
        tk.Label(frame, text="─── DURATION CONTROL (Video) ───",
                font=("Arial", 10, "bold"),
                fg="#ff00ff", bg=COLORS["bg"]).pack(anchor="w", pady=(15, 5))

        tk.Label(frame, text="Max duration (0 = unlimited):",
                font=("Arial", 9),
                fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(anchor="w")

        duration_frame = tk.Frame(frame, bg=COLORS["bg"])
        duration_frame.pack(fill="x", pady=3)

        duration_entry = tk.Entry(duration_frame, font=("Arial", 11), width=6,
                                 bg=COLORS["card"], fg=COLORS["text"],
                                 insertbackground=COLORS["text"], relief="flat")
        duration_entry.pack(side="left", ipady=4)
        duration_entry.insert(0, str(getattr(session, 'max_duration', 0)))

        tk.Label(duration_frame, text="seconds",
                font=("Arial", 9),
                fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(side="left", padx=8)

        tk.Label(frame, text="e.g., 6 = MiniMax 2.3 fast only (no HD 10s)",
                font=("Arial", 8),
                fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(anchor="w")

        # Rate Limiting Section
        tk.Label(frame, text="─── RATE LIMIT ───",
                font=("Arial", 10, "bold"),
                fg="#ffaa00", bg=COLORS["bg"]).pack(anchor="w", pady=(15, 5))

        rate_frame = tk.Frame(frame, bg=COLORS["bg"])
        rate_frame.pack(fill="x", pady=3)

        rate_entry = tk.Entry(rate_frame, font=("Arial", 11), width=6,
                             bg=COLORS["card"], fg=COLORS["text"],
                             insertbackground=COLORS["text"], relief="flat")
        rate_entry.pack(side="left", ipady=4)
        rate_entry.insert(0, str(getattr(session, 'rate_limit', 0)))

        tk.Label(rate_frame, text="requests per hour (0 = unlimited)",
                font=("Arial", 9),
                fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(side="left", padx=8)

        # Provider Control Section
        tk.Label(frame, text="─── PROVIDERS ───",
                font=("Arial", 10, "bold"),
                fg="#00aaff", bg=COLORS["bg"]).pack(anchor="w", pady=(15, 5))

        tk.Label(frame, text="Allowed providers (empty = all allowed):",
                font=("Arial", 9),
                fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(anchor="w")

        providers_entry = tk.Entry(frame, font=("Consolas", 10),
                                  bg=COLORS["card"], fg=COLORS["text"],
                                  insertbackground=COLORS["text"], relief="flat")
        providers_entry.pack(fill="x", pady=3, ipady=4)
        if getattr(session, 'allowed_providers', []):
            providers_entry.insert(0, ", ".join(session.allowed_providers))

        tk.Label(frame, text="Options: openai, fal, minimax",
                font=("Arial", 8),
                fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(anchor="w")

        tk.Label(frame, text="e.g., 'fal' = only fal.ai allowed for this session",
                font=("Arial", 8),
                fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(anchor="w")

        # Barrier Mode Section (per-session override)
        tk.Label(frame, text="─── BARRIER MODE ───",
                font=("Arial", 10, "bold"),
                fg="#ff6600", bg=COLORS["bg"]).pack(anchor="w", pady=(15, 5))

        tk.Label(frame, text="Override global barrier mode for this session:",
                font=("Arial", 9),
                fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(anchor="w")

        barrier_frame = tk.Frame(frame, bg=COLORS["card"], padx=10, pady=8)
        barrier_frame.pack(fill="x", pady=5)

        # Current value: None = use global, True = force on, False = force off
        current_barrier = getattr(session, 'barrier_mode', None)
        barrier_var = tk.StringVar(value="global" if current_barrier is None else ("on" if current_barrier else "off"))

        tk.Radiobutton(barrier_frame, text="Use Global Setting",
                      variable=barrier_var, value="global",
                      font=("Arial", 10),
                      fg=COLORS["text"], bg=COLORS["card"],
                      selectcolor=COLORS["bg"],
                      activebackground=COLORS["card"]).pack(anchor="w")

        tk.Radiobutton(barrier_frame, text="Force ON (require approval for this session)",
                      variable=barrier_var, value="on",
                      font=("Arial", 10),
                      fg="#00ff88", bg=COLORS["card"],
                      selectcolor=COLORS["bg"],
                      activebackground=COLORS["card"]).pack(anchor="w")

        tk.Radiobutton(barrier_frame, text="Force OFF (no approval needed for this session)",
                      variable=barrier_var, value="off",
                      font=("Arial", 10),
                      fg="#ff6666", bg=COLORS["card"],
                      selectcolor=COLORS["bg"],
                      activebackground=COLORS["card"]).pack(anchor="w")

        def save():
            allowed_raw = allowed_text.get("1.0", "end").strip()
            banned_raw = banned_text.get("1.0", "end").strip()
            allowed_models = [m.strip() for m in allowed_raw.split("\n") if m.strip()]
            banned_models = [m.strip() for m in banned_raw.split("\n") if m.strip()]
            self.session_mgr.update_session_models(session.id, allowed_models, banned_models, require_var.get())

            # Save quality restrictions
            allowed_q = [q.strip() for q in quality_allowed.get().split(",") if q.strip()]
            banned_q = [q.strip() for q in quality_banned.get().split(",") if q.strip()]
            session.allowed_qualities = allowed_q
            session.banned_qualities = banned_q

            # Save duration limit
            try:
                session.max_duration = max(0, int(duration_entry.get()))
            except ValueError:
                session.max_duration = 0

            # Save rate limit
            try:
                rate = int(rate_entry.get())
                session.rate_limit = max(0, rate)
            except ValueError:
                session.rate_limit = 0

            # Save allowed providers
            providers_raw = providers_entry.get().strip()
            allowed_p = [p.strip().lower() for p in providers_raw.split(",") if p.strip()]
            session.allowed_providers = allowed_p

            # Save barrier mode override
            barrier_choice = barrier_var.get()
            if barrier_choice == "global":
                session.barrier_mode = None
            elif barrier_choice == "on":
                session.barrier_mode = True
            else:
                session.barrier_mode = False

            # ALWAYS save - this was the bug (was inside try block)
            self.session_mgr._save()
            dialog.destroy()
            self.show_tab("sessions")

        btn = tk.Label(frame, text="  SAVE  ",
                      font=("Arial", 12, "bold"),
                      fg="#000000", bg="#ffaa00",
                      padx=30, pady=8, cursor="hand2")
        btn.pack(pady=(15, 10))
        btn.bind("<Button-1>", lambda e: save())

    def edit_session_budget(self, session):
        """Edit a session's budget limit."""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Budget - {session.name}")
        dialog.geometry("380x280")
        dialog.minsize(350, 260)
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=COLORS["bg"], padx=25, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text=f"Budget: {session.name}",
                font=("Arial", 14, "bold"),
                fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w")

        # Current spending
        spent_color = "#ff4444" if session.budget_limit > 0 and session.total_cost >= session.budget_limit else "#00ff00"
        tk.Label(frame, text=f"Current spending: ${session.total_cost:.4f}",
                font=("Arial", 11),
                fg=spent_color, bg=COLORS["bg"]).pack(anchor="w", pady=(5, 15))

        # Budget limit entry
        tk.Label(frame, text="Budget Limit (0 = unlimited)",
                font=("Arial", 10),
                fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(anchor="w")

        budget_frame = tk.Frame(frame, bg=COLORS["bg"])
        budget_frame.pack(fill="x", pady=5)

        tk.Label(budget_frame, text="$",
                font=("Arial", 14, "bold"),
                fg=COLORS["text"], bg=COLORS["bg"]).pack(side="left")

        budget_entry = tk.Entry(budget_frame, font=("Arial", 14), width=10,
                               bg=COLORS["card"], fg=COLORS["text"],
                               insertbackground=COLORS["text"], relief="flat")
        budget_entry.pack(side="left", padx=5, ipady=5)
        budget_entry.insert(0, str(session.budget_limit))
        budget_entry.focus_set()

        # Reset stats option
        reset_var = tk.BooleanVar(value=False)
        reset_cb = tk.Checkbutton(frame, text="Reset spending to $0",
                                 variable=reset_var,
                                 font=("Arial", 10),
                                 fg="#ffaa00", bg=COLORS["bg"],
                                 selectcolor=COLORS["card"],
                                 activebackground=COLORS["bg"])
        reset_cb.pack(anchor="w", pady=(15, 0))

        def save():
            try:
                budget = float(budget_entry.get())
                self.session_mgr.update_session_budget(session.id, max(0, budget))
                if reset_var.get():
                    self.session_mgr.reset_session_stats(session.id)
                dialog.destroy()
                self.show_tab("sessions")
            except ValueError:
                messagebox.showwarning("Invalid", "Enter a valid number")

        btn = tk.Label(frame, text="  SAVE  ",
                      font=("Arial", 12, "bold"),
                      fg="#000000", bg="#00ffaa",
                      padx=30, pady=8, cursor="hand2")
        btn.pack(pady=(20, 0))
        btn.bind("<Button-1>", lambda e: save())

    def ban_session(self, session_id):
        masked = mask_session_id(session_id)
        if messagebox.askyesno("Ban Session", f"Ban session {masked}?\n\nThis will block all API requests from this session."):
            self.session_mgr.ban_session(session_id, "Manual ban from Control Center")
            self.show_tab("sessions")

    def unban_session(self, session_id):
        self.session_mgr.unban_session(session_id)
        self.show_tab("sessions")

    def delete_session(self, session_id):
        masked = mask_session_id(session_id)
        if messagebox.askyesno("Delete Session", f"Delete session {masked}?\n\nThis cannot be undone."):
            self.session_mgr.delete_session(session_id)
            self.show_tab("sessions")

    def open_session_monitor(self, session):
        """Open real-time monitoring window for a session."""
        monitor = tk.Toplevel(self.root)
        monitor.title(f"Live Monitor - {session.name}")
        monitor.geometry("1100x700")
        monitor.minsize(1000, 600)
        monitor.configure(bg="#0a0a12")

        # Store reference to keep updating
        monitor.session_id = session.id
        monitor.is_running = True

        # Header with session info
        header = tk.Frame(monitor, bg="#1a1a2e", pady=15, padx=20)
        header.pack(fill="x")

        tk.Label(header, text=f"📡 LIVE MONITOR: {session.name}",
                font=("Segoe UI", 18, "bold"),
                fg="#00ffaa", bg="#1a1a2e").pack(side="left")

        # Status indicator
        status_frame = tk.Frame(header, bg="#1a1a2e")
        status_frame.pack(side="right")

        monitor.status_dot = tk.Label(status_frame, text="●",
                                     font=("Arial", 20),
                                     fg="#00ff00", bg="#1a1a2e")
        monitor.status_dot.pack(side="left", padx=(0, 5))

        monitor.status_text = tk.Label(status_frame, text="MONITORING",
                                      font=("Arial", 12, "bold"),
                                      fg="#00ff00", bg="#1a1a2e")
        monitor.status_text.pack(side="left")

        # Main content - split into left (settings) and right (history)
        main_content = tk.Frame(monitor, bg="#0a0a12")
        main_content.pack(fill="both", expand=True, padx=10, pady=10)

        # === LEFT PANEL: Settings & Stats ===
        left_panel = tk.Frame(main_content, bg="#12121f", width=320)
        left_panel.pack(side="left", fill="y", padx=(0, 10))
        left_panel.pack_propagate(False)

        # Stats section
        stats_frame = tk.Frame(left_panel, bg="#12121f", padx=15, pady=15)
        stats_frame.pack(fill="x")

        tk.Label(stats_frame, text="📊 STATISTICS",
                font=("Arial", 11, "bold"),
                fg="#00ffaa", bg="#12121f").pack(anchor="w")

        monitor.stat_labels = {}
        stats_grid = tk.Frame(stats_frame, bg="#12121f")
        stats_grid.pack(fill="x", pady=(10, 0))

        for i, (stat_name, stat_color) in enumerate([
            ("Requests", "#ffffff"), ("Allowed", "#00ff00"),
            ("Blocked", "#ff4444"), ("Spent", "#ffaa00"),
            ("Saved", "#00ffaa"), ("Block %", "#ff00ff")
        ]):
            row, col = i // 2, i % 2
            cell = tk.Frame(stats_grid, bg="#0a0a12", padx=10, pady=8)
            cell.grid(row=row, column=col, padx=3, pady=3, sticky="ew")
            stats_grid.columnconfigure(col, weight=1)

            tk.Label(cell, text=stat_name, font=("Arial", 8),
                    fg="#666666", bg="#0a0a12").pack()
            monitor.stat_labels[stat_name] = tk.Label(cell, text="0",
                    font=("Arial", 14, "bold"),
                    fg=stat_color, bg="#0a0a12")
            monitor.stat_labels[stat_name].pack()

        # Separator
        tk.Frame(left_panel, bg="#333355", height=1).pack(fill="x", padx=15, pady=10)

        # Settings section
        settings_frame = tk.Frame(left_panel, bg="#12121f", padx=15, pady=5)
        settings_frame.pack(fill="x")

        tk.Label(settings_frame, text="⚙️ SESSION SETTINGS",
                font=("Arial", 11, "bold"),
                fg="#00ffaa", bg="#12121f").pack(anchor="w", pady=(0, 10))

        monitor.settings_labels = {}

        def add_setting(parent, label, value, color="#ffffff"):
            row = tk.Frame(parent, bg="#12121f")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, font=("Arial", 9),
                    fg="#888888", bg="#12121f", width=14, anchor="w").pack(side="left")
            lbl = tk.Label(row, text=value, font=("Arial", 9, "bold"),
                          fg=color, bg="#12121f", anchor="w")
            lbl.pack(side="left", fill="x", expand=True)
            return lbl

        # Budget
        budget_val = f"${session.budget_limit:.2f}" if session.budget_limit > 0 else "Unlimited"
        monitor.settings_labels["budget"] = add_setting(settings_frame, "Budget:", budget_val,
            "#ff4444" if session.budget_limit > 0 else "#00ff00")

        # Rate limit
        if session.rate_limit > 0:
            period = session.rate_limit_period
            period_str = f"{period}s" if period < 60 else f"{period//60}min" if period < 3600 else f"{period//3600}hr"
            rate_val = f"{session.rate_limit} per {period_str}"
        else:
            rate_val = "Unlimited"
        monitor.settings_labels["rate"] = add_setting(settings_frame, "Rate Limit:", rate_val,
            "#ffaa00" if session.rate_limit > 0 else "#00ff00")

        # Allowed models
        if session.allowed_models:
            models_val = ", ".join(session.allowed_models[:3])
            if len(session.allowed_models) > 3:
                models_val += f" +{len(session.allowed_models)-3}"
        else:
            models_val = "None (blocked)" if session.require_model_whitelist else "All"
        monitor.settings_labels["models"] = add_setting(settings_frame, "Models:", models_val, "#00ffff")

        # Banned models
        if session.banned_models:
            banned_val = ", ".join(session.banned_models[:2])
            if len(session.banned_models) > 2:
                banned_val += f" +{len(session.banned_models)-2}"
        else:
            banned_val = "None"
        add_setting(settings_frame, "Banned:", banned_val, "#ff4444" if session.banned_models else "#666666")

        # Quality restrictions
        if session.allowed_qualities:
            qual_val = ", ".join(session.allowed_qualities)
        elif session.banned_qualities:
            qual_val = f"Not: {', '.join(session.banned_qualities)}"
        else:
            qual_val = "All"
        add_setting(settings_frame, "Quality:", qual_val, "#ffaa00")

        # Max duration
        dur_val = f"{session.max_duration}s max" if session.max_duration > 0 else "Unlimited"
        add_setting(settings_frame, "Duration:", dur_val,
            "#ff00ff" if session.max_duration > 0 else "#666666")

        # Provider restrictions
        providers = getattr(session, 'allowed_providers', [])
        if providers:
            prov_val = ", ".join(providers)
        else:
            prov_val = "All"
        add_setting(settings_frame, "Providers:", prov_val,
            "#00aaff" if providers else "#666666")

        # Separator
        tk.Frame(left_panel, bg="#333355", height=1).pack(fill="x", padx=15, pady=10)

        # Quick actions
        actions_frame = tk.Frame(left_panel, bg="#12121f", padx=15, pady=5)
        actions_frame.pack(fill="x")

        tk.Label(actions_frame, text="⚡ QUICK CONTROLS",
                font=("Arial", 11, "bold"),
                fg="#00ffaa", bg="#12121f").pack(anchor="w", pady=(0, 10))

        # --- Budget Control ---
        budget_row = tk.Frame(actions_frame, bg="#12121f")
        budget_row.pack(fill="x", pady=3)

        tk.Label(budget_row, text="Budget $", font=("Arial", 9),
                fg="#888888", bg="#12121f").pack(side="left")

        monitor.budget_entry = tk.Entry(budget_row, font=("Arial", 10), width=7,
                                        bg="#0a0a12", fg="#ffaa00",
                                        insertbackground="#ffaa00", relief="flat")
        monitor.budget_entry.pack(side="left", padx=3, ipady=2)
        monitor.budget_entry.insert(0, f"{session.budget_limit:.2f}")

        def apply_budget():
            try:
                new_budget = float(monitor.budget_entry.get())
                s = self.session_mgr.get_session(session.id)
                s.budget_limit = max(0, new_budget)
                self.session_mgr._save()
                self.update_monitor(monitor)
            except ValueError:
                pass

        budget_btn = tk.Label(budget_row, text="Set", font=("Arial", 8, "bold"),
                             fg="#000", bg="#ffaa00", padx=6, pady=1, cursor="hand2")
        budget_btn.pack(side="left", padx=2)
        budget_btn.bind("<Button-1>", lambda e: apply_budget())

        # --- Rate Limit Control ---
        rate_row = tk.Frame(actions_frame, bg="#12121f")
        rate_row.pack(fill="x", pady=3)

        tk.Label(rate_row, text="Rate", font=("Arial", 9),
                fg="#888888", bg="#12121f").pack(side="left")

        monitor.rate_entry = tk.Entry(rate_row, font=("Arial", 10), width=4,
                                      bg="#0a0a12", fg="#00ffff",
                                      insertbackground="#00ffff", relief="flat")
        monitor.rate_entry.pack(side="left", padx=3, ipady=2)
        monitor.rate_entry.insert(0, str(session.rate_limit))

        tk.Label(rate_row, text="/hr", font=("Arial", 9),
                fg="#666666", bg="#12121f").pack(side="left")

        def apply_rate():
            try:
                new_rate = int(monitor.rate_entry.get())
                s = self.session_mgr.get_session(session.id)
                s.rate_limit = max(0, new_rate)
                self.session_mgr._save()
                self.update_monitor(monitor)
            except ValueError:
                pass

        rate_btn = tk.Label(rate_row, text="Set", font=("Arial", 8, "bold"),
                           fg="#000", bg="#00ffff", padx=6, pady=1, cursor="hand2")
        rate_btn.pack(side="left", padx=2)
        rate_btn.bind("<Button-1>", lambda e: apply_rate())

        # Separator
        tk.Frame(actions_frame, bg="#333355", height=1).pack(fill="x", pady=8)

        # --- Action Buttons ---
        # Clear History
        def clear_session_history():
            if messagebox.askyesno("Clear History",
                                   f"Clear all history for {session.name}?\n\nThis resets spending to $0."):
                s = self.session_mgr.get_session(session.id)
                s.total_cost = 0.0
                s.total_requests = 0
                s.total_blocked = 0
                s.amount_saved = 0.0
                self.session_mgr.clear_session_history(session.id)
                self.session_mgr._save()
                self.update_monitor(monitor)

        clear_btn = tk.Label(actions_frame, text="🗑️ Clear History & Reset",
                            font=("Arial", 9, "bold"),
                            fg="#ffffff", bg="#444466",
                            padx=10, pady=6, cursor="hand2")
        clear_btn.pack(fill="x", pady=2)
        clear_btn.bind("<Button-1>", lambda e: clear_session_history())

        # Panic button in monitor
        panic_btn = tk.Label(actions_frame, text="🚨 PANIC STOP ALL",
                            font=("Arial", 10, "bold"),
                            fg="#ffffff", bg="#cc0000",
                            padx=10, pady=8, cursor="hand2")
        panic_btn.pack(fill="x", pady=2)
        panic_btn.bind("<Button-1>", lambda e: self.monitor_panic_toggle(monitor))

        # === RIGHT PANEL: Live History ===
        right_panel = tk.Frame(main_content, bg="#0f0f1a")
        right_panel.pack(side="right", fill="both", expand=True)

        # History header
        hist_header = tk.Frame(right_panel, bg="#0f0f1a", pady=10, padx=15)
        hist_header.pack(fill="x")

        tk.Label(hist_header, text="📜 LIVE ACTIVITY",
                font=("Arial", 11, "bold"),
                fg="#00ffaa", bg="#0f0f1a").pack(side="left")

        tk.Label(hist_header, text="Auto-refresh: 2s",
                font=("Arial", 8),
                fg="#666666", bg="#0f0f1a").pack(side="right")

        # Scrollable history list
        history_container = tk.Frame(right_panel, bg="#0f0f1a")
        history_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Canvas for scrolling
        canvas = tk.Canvas(history_container, bg="#0f0f1a", highlightthickness=0)
        scrollbar = tk.Scrollbar(history_container, orient="vertical", command=canvas.yview)
        monitor.history_frame = tk.Frame(canvas, bg="#0f0f1a")

        monitor.history_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=monitor.history_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        monitor.canvas = canvas
        monitor.history_items = []

        # Footer
        footer = tk.Frame(monitor, bg="#1a1a2e", pady=10, padx=20)
        footer.pack(fill="x")

        close_btn = tk.Label(footer, text="Close Monitor",
                            font=("Arial", 10, "bold"),
                            fg="#ffffff", bg="#555555",
                            padx=15, pady=5, cursor="hand2")
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda e: self.close_monitor(monitor))

        # Initial update
        self.update_monitor(monitor)

        # Handle window close
        monitor.protocol("WM_DELETE_WINDOW", lambda: self.close_monitor(monitor))

    def monitor_panic_toggle(self, monitor):
        """Toggle panic mode from monitor window."""
        if self.session_mgr.is_panic_mode():
            if messagebox.askyesno("Disable Panic Mode",
                                   "Resume API operations?"):
                self.session_mgr.set_panic_mode(False)
        else:
            self.session_mgr.set_panic_mode(True)
        self.update_panic_status()
        self.update_monitor(monitor)

    def close_monitor(self, monitor):
        """Close the monitor window and stop updates."""
        monitor.is_running = False
        monitor.destroy()

    def update_monitor(self, monitor):
        """Update the monitor window with latest data."""
        if not monitor.is_running or not monitor.winfo_exists():
            return

        try:
            # Reload data from disk
            self.session_mgr._load()

            session = self.session_mgr.get_session(monitor.session_id)
            if not session:
                monitor.status_text.config(text="SESSION DELETED", fg="#ff4444")
                return

            # Update stats
            monitor.stat_labels["Requests"].config(text=str(session.total_requests))
            monitor.stat_labels["Allowed"].config(text=str(session.allowed_requests))
            monitor.stat_labels["Blocked"].config(text=str(session.blocked_requests))
            monitor.stat_labels["Spent"].config(text=f"${session.total_cost:.2f}")
            monitor.stat_labels["Saved"].config(text=f"${session.blocked_cost:.2f}")

            # Calculate block rate
            if session.total_requests > 0:
                rate = (session.blocked_requests / session.total_requests) * 100
                monitor.stat_labels["Block %"].config(text=f"{rate:.0f}%")
            else:
                monitor.stat_labels["Block %"].config(text="0%")

            # Update status based on session state
            if self.session_mgr.is_panic_mode():
                monitor.status_dot.config(fg="#ff0000")
                monitor.status_text.config(text="PANIC MODE", fg="#ff0000")
            elif session.status == "banned":
                monitor.status_dot.config(fg="#ff4444")
                monitor.status_text.config(text="BANNED", fg="#ff4444")
            elif session.status == "warned":
                monitor.status_dot.config(fg="#ffff00")
                monitor.status_text.config(text="WARNED", fg="#ffff00")
            else:
                monitor.status_dot.config(fg="#00ff00")
                monitor.status_text.config(text="MONITORING", fg="#00ff00")

            # Get recent history for this session
            history = self.session_mgr.get_session_history(monitor.session_id, limit=30)

            # Check if we have new items
            current_ids = {a.id for a in history}
            existing_ids = set(monitor.history_items)

            if current_ids != existing_ids:
                # Clear and rebuild history
                for widget in monitor.history_frame.winfo_children():
                    widget.destroy()
                monitor.history_items = []

                for attempt in history:
                    self.create_monitor_history_row(monitor, attempt)
                    monitor.history_items.append(attempt.id)

            # Flash status dot to show activity
            current_color = monitor.status_dot.cget("fg")
            monitor.status_dot.config(fg="#333333")
            monitor.after(100, lambda: monitor.status_dot.config(fg=current_color) if monitor.winfo_exists() else None)

        except Exception as e:
            pass  # Don't crash monitor on errors

        # Schedule next update (every 2 seconds)
        if monitor.is_running and monitor.winfo_exists():
            monitor.after(2000, lambda: self.update_monitor(monitor))

    def create_monitor_history_row(self, monitor, attempt):
        """Create a history row in the monitor with thumbnail support."""
        row_bg = "#1a1a2e" if attempt.status == "allowed" else "#2e1a1a"

        row = tk.Frame(monitor.history_frame, bg=row_bg, pady=8, padx=10)
        row.pack(fill="x", pady=2)

        # Left side: thumbnail (if image exists)
        if HAS_PIL and attempt.image_path:
            try:
                thumb_frame = tk.Frame(row, bg=row_bg, width=60, height=60)
                thumb_frame.pack(side="left", padx=(0, 10))
                thumb_frame.pack_propagate(False)

                img_path = Path(attempt.image_path)
                if img_path.exists():
                    img = Image.open(img_path)
                    img.thumbnail((56, 56))
                    photo = ImageTk.PhotoImage(img)
                    thumb_label = tk.Label(thumb_frame, image=photo, bg=row_bg)
                    thumb_label.image = photo  # Keep reference
                    thumb_label.pack(expand=True)
            except Exception:
                pass

        # Middle: Info
        info_frame = tk.Frame(row, bg=row_bg)
        info_frame.pack(side="left", fill="both", expand=True)

        # Top row: status, model, cost
        top_row = tk.Frame(info_frame, bg=row_bg)
        top_row.pack(fill="x")

        status_icon = "✓" if attempt.status == "allowed" else "✗"
        status_color = "#00ff00" if attempt.status == "allowed" else "#ff4444"

        tk.Label(top_row, text=status_icon,
                font=("Arial", 12, "bold"),
                fg=status_color, bg=row_bg).pack(side="left")

        tk.Label(top_row, text=attempt.model,
                font=("Arial", 10, "bold"),
                fg="#00ffff", bg=row_bg).pack(side="left", padx=(8, 0))

        tk.Label(top_row, text=f"${attempt.estimated_cost:.2f}",
                font=("Arial", 10, "bold"),
                fg="#ffaa00", bg=row_bg).pack(side="right")

        # Bottom row: time and reason
        bottom_row = tk.Frame(info_frame, bg=row_bg)
        bottom_row.pack(fill="x", pady=(3, 0))

        try:
            ts = datetime.fromisoformat(attempt.timestamp)
            time_str = ts.strftime("%H:%M:%S")
        except:
            time_str = "??:??:??"

        tk.Label(bottom_row, text=time_str,
                font=("Arial", 9),
                fg="#666666", bg=row_bg).pack(side="left")

        if attempt.reason:
            reason_text = attempt.reason[:50] + "..." if len(attempt.reason) > 50 else attempt.reason
            tk.Label(bottom_row, text=reason_text,
                    font=("Arial", 9),
                    fg="#ff6666" if attempt.status == "blocked" else "#888888",
                    bg=row_bg).pack(side="left", padx=(10, 0))

        # Show prompt preview if available
        if attempt.request_params and attempt.request_params.get("prompt"):
            prompt = attempt.request_params["prompt"]
            prompt_preview = prompt[:60] + "..." if len(prompt) > 60 else prompt
            prompt_row = tk.Frame(info_frame, bg=row_bg)
            prompt_row.pack(fill="x", pady=(3, 0))
            tk.Label(prompt_row, text=f'"{prompt_preview}"',
                    font=("Arial", 8, "italic"),
                    fg="#888888", bg=row_bg).pack(side="left")

        # Click to show details - bind recursively to all descendants
        def bind_click(widget, attempt):
            widget.bind("<Button-1>", lambda e, a=attempt: self.show_attempt_details(a))
            widget.config(cursor="hand2")
            for child in widget.winfo_children():
                bind_click(child, attempt)

        bind_click(row, attempt)

    def show_history(self):
        """Show request history with search and export."""
        header = tk.Frame(self.content, bg=COLORS["bg"], pady=20, padx=30)
        header.pack(fill="x")

        title_row = tk.Frame(header, bg=COLORS["bg"])
        title_row.pack(fill="x")

        tk.Label(title_row, text="Request History",
                font=("Segoe UI", 24, "bold"),
                fg=COLORS["text"], bg=COLORS["bg"]).pack(side="left")

        # Export CSV button
        export_btn = tk.Label(title_row, text="[Export CSV]",
                             font=("Arial", 10, "bold"),
                             fg="#00ffaa", bg=COLORS["bg"],
                             cursor="hand2", padx=10)
        export_btn.pack(side="right")
        export_btn.bind("<Button-1>", lambda e: self.export_history_csv())

        # Search bar
        search_frame = tk.Frame(header, bg=COLORS["bg"])
        search_frame.pack(fill="x", pady=(10, 0))

        tk.Label(search_frame, text="Filter:",
                font=("Arial", 10),
                fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(side="left")

        self.history_search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, font=("Arial", 11), width=30,
                               bg=COLORS["card"], fg=COLORS["text"],
                               insertbackground=COLORS["text"], relief="flat",
                               textvariable=self.history_search_var)
        search_entry.pack(side="left", padx=10, ipady=4)

        tk.Label(search_frame, text="(session, provider, or model)",
                font=("Arial", 9),
                fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(side="left")

        # Bind search to filter with debounce (300ms delay)
        self.history_filter_job = None
        def debounced_filter(*args):
            if self.history_filter_job:
                self.root.after_cancel(self.history_filter_job)
            self.history_filter_job = self.root.after(300, self.filter_history)
        self.history_search_var.trace("w", debounced_filter)

        # History list with scrollbar
        list_frame = tk.Frame(self.content, bg=COLORS["bg"], padx=30)
        list_frame.pack(fill="both", expand=True)
        self.history_list_frame = list_frame

        # Create canvas for scrolling
        canvas = tk.Canvas(list_frame, bg=COLORS["card"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=COLORS["card"])

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw", width=canvas.winfo_reqwidth())
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Populate history (limit to 50 for performance)
        history = self.session_mgr.get_recent_history(50)
        if history:
            for attempt in history:
                self.create_history_row(scrollable, attempt)
        else:
            tk.Label(scrollable, text="No request history yet",
                    font=("Segoe UI", 11),
                    fg=COLORS["text_muted"], bg=COLORS["card"],
                    pady=40).pack()

        # Mouse wheel scrolling
        def on_mousewheel(event):
            try:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except:
                pass
        canvas.bind("<MouseWheel>", on_mousewheel)
        scrollable.bind("<MouseWheel>", on_mousewheel)

        # Store references for filtering
        self.history_canvas = canvas
        self.history_scrollable = scrollable

    def filter_history(self):
        """Filter history based on search term."""
        search_term = self.history_search_var.get().lower().strip()

        # Clear current history display
        for widget in self.history_scrollable.winfo_children():
            widget.destroy()

        history = self.session_mgr.get_recent_history(50)

        if search_term:
            history = [a for a in history if
                      search_term in a.session_id.lower() or
                      search_term in a.provider.lower() or
                      search_term in a.model.lower()]

        if history:
            for attempt in history:
                self.create_history_row(self.history_scrollable, attempt)
        else:
            tk.Label(self.history_scrollable, text="No matching results",
                    font=("Segoe UI", 11),
                    fg=COLORS["text_muted"], bg=COLORS["card"],
                    pady=40).pack()

    def export_history_csv(self):
        """Export history to CSV file."""
        from tkinter import filedialog
        import csv

        history = self.session_mgr.get_recent_history(1000)
        if not history:
            messagebox.showinfo("Export", "No history to export")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfilename=f"apibouncer_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if filename:
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Timestamp', 'Session ID', 'Provider', 'Model', 'Cost', 'Status', 'Reason'])
                    for a in history:
                        writer.writerow([a.timestamp, a.session_id, a.provider, a.model,
                                        f"${a.estimated_cost:.4f}", a.status, a.reason or ""])
                messagebox.showinfo("Export", f"Exported {len(history)} records to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

    def create_history_row(self, parent, attempt):
        """Create a history row with thumbnail and click-to-view details."""
        row = tk.Frame(parent, bg=COLORS["card"], pady=8, padx=15, cursor="hand2")
        row.pack(fill="x", pady=2)

        status_color = COLORS["success"] if attempt.status == "allowed" else COLORS["danger"]

        # Make row clickable
        def on_click(e):
            self.show_attempt_details(attempt)
        row.bind("<Button-1>", on_click)

        # Hover effect
        def on_enter(e):
            row.config(bg=COLORS["card_hover"])
            for child in row.winfo_children():
                try:
                    child.config(bg=COLORS["card_hover"])
                except:
                    pass
        def on_leave(e):
            row.config(bg=COLORS["card"])
            for child in row.winfo_children():
                try:
                    child.config(bg=COLORS["card"])
                except:
                    pass
        row.bind("<Enter>", on_enter)
        row.bind("<Leave>", on_leave)

        # Left side - Thumbnail or status indicator
        thumb_frame = tk.Frame(row, bg=COLORS["card"], width=50, height=50)
        thumb_frame.pack(side="left", padx=(0, 12))
        thumb_frame.pack_propagate(False)
        thumb_frame.bind("<Button-1>", on_click)

        # Try to load thumbnail if image exists
        has_thumb = False
        image_path = getattr(attempt, 'image_path', None)
        if image_path and HAS_PIL:
            try:
                from pathlib import Path
                if Path(image_path).exists():
                    img = Image.open(image_path)
                    img.thumbnail((50, 50))
                    photo = ImageTk.PhotoImage(img)
                    thumb_label = tk.Label(thumb_frame, image=photo, bg=COLORS["card"])
                    thumb_label.image = photo  # Keep reference
                    thumb_label.pack(expand=True)
                    thumb_label.bind("<Button-1>", on_click)
                    has_thumb = True
            except Exception:
                pass

        if not has_thumb:
            # Fallback to status indicator
            tk.Label(thumb_frame, text="●" if attempt.status == "allowed" else "✗",
                    font=("Arial", 20),
                    fg=status_color, bg=COLORS["card"]).pack(expand=True)

        # Main content area
        content = tk.Frame(row, bg=COLORS["card"])
        content.pack(side="left", fill="x", expand=True)
        content.bind("<Button-1>", on_click)

        # Top line: Provider/Model and Status
        top_line = tk.Frame(content, bg=COLORS["card"])
        top_line.pack(fill="x")
        top_line.bind("<Button-1>", on_click)

        model_lbl = tk.Label(top_line, text=f"{attempt.provider} / {attempt.model}",
                font=("Arial", 11, "bold"),
                fg=COLORS["text"], bg=COLORS["card"])
        model_lbl.pack(side="left")
        model_lbl.bind("<Button-1>", on_click)

        status_lbl = tk.Label(top_line, text=attempt.status.upper(),
                font=("Arial", 9, "bold"),
                fg=status_color, bg=COLORS["card"])
        status_lbl.pack(side="left", padx=15)
        status_lbl.bind("<Button-1>", on_click)

        # Show prompt snippet if available
        req_params = getattr(attempt, 'request_params', None)
        if req_params and req_params.get('prompt'):
            prompt_snippet = req_params['prompt'][:60] + "..." if len(req_params['prompt']) > 60 else req_params['prompt']
            prompt_lbl = tk.Label(top_line, text=f'"{prompt_snippet}"',
                    font=("Arial", 9, "italic"),
                    fg=COLORS["text_muted"], bg=COLORS["card"])
            prompt_lbl.pack(side="left", padx=10)
            prompt_lbl.bind("<Button-1>", on_click)

        # Bottom line: Session ID and Time
        bottom_line = tk.Frame(content, bg=COLORS["card"])
        bottom_line.pack(fill="x")
        bottom_line.bind("<Button-1>", on_click)

        # Show masked session ID (security - hide secret portion)
        masked_id = mask_session_id(attempt.session_id)
        id_lbl = tk.Label(bottom_line, text=masked_id,
                font=("Consolas", 9),
                fg=COLORS["accent"], bg=COLORS["card"])
        id_lbl.pack(side="left")
        id_lbl.bind("<Button-1>", on_click)

        time_lbl = tk.Label(bottom_line, text=f"  {attempt.timestamp[:16].replace('T', ' ')}",
                font=("Arial", 9),
                fg=COLORS["text_muted"], bg=COLORS["card"])
        time_lbl.pack(side="left")
        time_lbl.bind("<Button-1>", on_click)

        # Right side - Cost
        right_frame = tk.Frame(row, bg=COLORS["card"], width=80)
        right_frame.pack(side="right", padx=(10, 0))
        right_frame.pack_propagate(False)
        right_frame.bind("<Button-1>", on_click)

        cost_lbl = tk.Label(right_frame, text=f"${attempt.estimated_cost:.2f}",
                font=("Arial", 12, "bold"),
                fg=status_color, bg=COLORS["card"])
        cost_lbl.pack(expand=True)
        cost_lbl.bind("<Button-1>", on_click)

    def show_attempt_details(self, attempt):
        """Show detailed view of an API request attempt."""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Request Details - {attempt.id}")
        dialog.geometry("750x750")
        dialog.minsize(650, 600)
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        # Main frame with scrolling
        canvas = tk.Canvas(dialog, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg=COLORS["bg"], padx=25, pady=20)

        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw", width=620)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        status_color = COLORS["success"] if attempt.status == "allowed" else COLORS["danger"]

        # Header
        tk.Label(frame, text=f"{attempt.provider} / {attempt.model}",
                font=("Arial", 18, "bold"),
                fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w")

        tk.Label(frame, text=f"{attempt.status.upper()} - ${attempt.estimated_cost:.4f}",
                font=("Arial", 14, "bold"),
                fg=status_color, bg=COLORS["bg"]).pack(anchor="w", pady=(5, 15))

        # Image preview if available
        image_path = getattr(attempt, 'image_path', None)
        if image_path and HAS_PIL:
            try:
                from pathlib import Path
                if Path(image_path).exists():
                    tk.Label(frame, text="Generated Image:",
                            font=("Arial", 11, "bold"),
                            fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(anchor="w")

                    img = Image.open(image_path)
                    # Scale to fit dialog (max 400px wide)
                    max_width = 400
                    if img.width > max_width:
                        ratio = max_width / img.width
                        img = img.resize((max_width, int(img.height * ratio)), Image.Resampling.LANCZOS)

                    photo = ImageTk.PhotoImage(img)
                    img_label = tk.Label(frame, image=photo, bg=COLORS["bg"])
                    img_label.image = photo
                    img_label.pack(anchor="w", pady=10)

                    # Path info with clickable link
                    path_frame = tk.Frame(frame, bg=COLORS["bg"])
                    path_frame.pack(anchor="w", fill="x")

                    tk.Label(path_frame, text="Saved to:",
                            font=("Arial", 9),
                            fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(side="left")

                    path_link = tk.Label(path_frame, text=image_path,
                            font=("Consolas", 9, "underline"),
                            fg="#00ffff", bg=COLORS["bg"], cursor="hand2")
                    path_link.pack(side="left", padx=5)
                    path_link.bind("<Button-1>", lambda e, p=image_path: self.open_file_location(p))

                    open_btn = tk.Label(path_frame, text="📂 Open",
                            font=("Arial", 9, "bold"),
                            fg="#000", bg="#00ffaa", padx=8, pady=2, cursor="hand2")
                    open_btn.pack(side="left", padx=10)
                    open_btn.bind("<Button-1>", lambda e, p=image_path: self.open_media_file(p))

            except Exception as e:
                tk.Label(frame, text=f"Could not load image: {e}",
                        font=("Arial", 9),
                        fg=COLORS["danger"], bg=COLORS["bg"]).pack(anchor="w")

        # Request parameters
        req_params = getattr(attempt, 'request_params', None)
        if req_params:
            tk.Label(frame, text="Request Parameters:",
                    font=("Arial", 11, "bold"),
                    fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(anchor="w", pady=(15, 5))

            params_frame = tk.Frame(frame, bg=COLORS["card"], padx=15, pady=10)
            params_frame.pack(fill="x")

            for key, value in req_params.items():
                row = tk.Frame(params_frame, bg=COLORS["card"])
                row.pack(fill="x", pady=2)
                tk.Label(row, text=f"{key}:",
                        font=("Arial", 10, "bold"),
                        fg=COLORS["accent"], bg=COLORS["card"], width=12, anchor="w").pack(side="left")
                # Wrap long values
                val_text = str(value) if len(str(value)) < 80 else str(value)[:80] + "..."
                tk.Label(row, text=val_text,
                        font=("Consolas", 10),
                        fg=COLORS["text"], bg=COLORS["card"]).pack(side="left")

        # Response data
        resp_data = getattr(attempt, 'response_data', None)
        if resp_data:
            tk.Label(frame, text="Response Data:",
                    font=("Arial", 11, "bold"),
                    fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(anchor="w", pady=(15, 5))

            resp_frame = tk.Frame(frame, bg=COLORS["card"], padx=15, pady=10)
            resp_frame.pack(fill="x")

            # Special handling for URL - show full URL with copy button
            url = resp_data.get("url") or resp_data.get("video_url")
            url_created = resp_data.get("url_created")

            if url:
                url_section = tk.Frame(resp_frame, bg=COLORS["card"])
                url_section.pack(fill="x", pady=(0, 10))

                tk.Label(url_section, text="🔗 Recovery URL:",
                        font=("Arial", 10, "bold"),
                        fg="#00ffaa", bg=COLORS["card"]).pack(anchor="w")

                # URL display (selectable text)
                url_text = tk.Text(url_section, height=2, font=("Consolas", 9),
                                  bg="#1a1a2e", fg="#00ffff",
                                  wrap="char", relief="flat", padx=5, pady=5)
                url_text.pack(fill="x", pady=(3, 5))
                url_text.insert("1.0", url)
                url_text.config(state="disabled")

                # URL info and copy button row
                url_info_row = tk.Frame(url_section, bg=COLORS["card"])
                url_info_row.pack(fill="x")

                # Expiry warning
                if url_created:
                    try:
                        created_time = datetime.fromisoformat(url_created)
                        elapsed = (datetime.now() - created_time).total_seconds()
                        remaining = max(0, 3600 - elapsed)  # 60 min expiry
                        if remaining > 0:
                            mins = int(remaining // 60)
                            expiry_text = f"⏱ Expires in ~{mins} min" if mins > 0 else "⚠️ URL may have expired"
                            expiry_color = "#ffaa00" if mins > 10 else "#ff4444"
                        else:
                            expiry_text = "⚠️ URL likely expired (>60 min old)"
                            expiry_color = "#ff4444"
                    except:
                        expiry_text = "⏱ URL expires ~60 min after creation"
                        expiry_color = "#888888"

                    tk.Label(url_info_row, text=expiry_text,
                            font=("Arial", 9),
                            fg=expiry_color, bg=COLORS["card"]).pack(side="left")

                # Copy URL button
                def copy_url():
                    dialog.clipboard_clear()
                    dialog.clipboard_append(url)
                    dialog.update()
                    copy_btn.config(text="✓ Copied!")
                    dialog.after(2000, lambda: copy_btn.config(text="📋 Copy"))

                copy_btn = tk.Label(url_info_row, text="📋 Copy",
                                   font=("Arial", 9, "bold"),
                                   fg="#000000", bg="#00ffaa",
                                   padx=8, pady=3, cursor="hand2")
                copy_btn.pack(side="right", padx=(5, 0))
                copy_btn.bind("<Button-1>", lambda e: copy_url())

                # Open URL in browser button
                def open_url():
                    import webbrowser
                    webbrowser.open(url)

                open_url_btn = tk.Label(url_info_row, text="🌐 Open in Browser",
                                       font=("Arial", 9, "bold"),
                                       fg="#000000", bg="#00ffff",
                                       padx=8, pady=3, cursor="hand2")
                open_url_btn.pack(side="right", padx=(5, 0))
                open_url_btn.bind("<Button-1>", lambda e: open_url())

            # Other response data
            for key, value in resp_data.items():
                if key in ("url", "video_url", "url_created") or value is None:
                    continue  # Already handled URL above
                row = tk.Frame(resp_frame, bg=COLORS["card"])
                row.pack(fill="x", pady=2)
                tk.Label(row, text=f"{key}:",
                        font=("Arial", 10, "bold"),
                        fg=COLORS["success"], bg=COLORS["card"], width=15, anchor="w").pack(side="left")

                # Make file paths clickable
                if key in ("image_path", "video_path") and value:
                    path_link = tk.Label(row, text=str(value),
                            font=("Consolas", 10, "underline"),
                            fg="#00ffff", bg=COLORS["card"], cursor="hand2")
                    path_link.pack(side="left")
                    path_link.bind("<Button-1>", lambda e, p=str(value): self.open_media_file(p))

                    open_btn = tk.Label(row, text="📂",
                            font=("Arial", 10),
                            fg="#00ffaa", bg=COLORS["card"], cursor="hand2")
                    open_btn.pack(side="left", padx=5)
                    open_btn.bind("<Button-1>", lambda e, p=str(value): self.open_file_location(p))
                else:
                    val_text = str(value) if len(str(value)) < 70 else str(value)[:70] + "..."
                    tk.Label(row, text=val_text,
                            font=("Consolas", 10),
                            fg=COLORS["text"], bg=COLORS["card"]).pack(side="left")

        # Metadata
        tk.Label(frame, text="Metadata:",
                font=("Arial", 11, "bold"),
                fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(anchor="w", pady=(15, 5))

        meta_frame = tk.Frame(frame, bg=COLORS["card"], padx=15, pady=10)
        meta_frame.pack(fill="x")

        meta_items = [
            ("Attempt ID", attempt.id),
            ("Session ID", mask_session_id(attempt.session_id)),  # Masked for security
            ("Timestamp", attempt.timestamp.replace("T", " ")),
            ("Reason", attempt.reason or "N/A"),
        ]

        for label, value in meta_items:
            row = tk.Frame(meta_frame, bg=COLORS["card"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"{label}:",
                    font=("Arial", 10, "bold"),
                    fg=COLORS["warning"], bg=COLORS["card"], width=12, anchor="w").pack(side="left")
            tk.Label(row, text=value,
                    font=("Consolas", 10),
                    fg=COLORS["text"], bg=COLORS["card"]).pack(side="left")

        # Close button
        close_btn = tk.Label(frame, text="  Close  ",
                            font=("Arial", 11, "bold"),
                            fg="#000000", bg=COLORS["accent"],
                            padx=20, pady=8, cursor="hand2")
        close_btn.pack(pady=(20, 10))
        close_btn.bind("<Button-1>", lambda e: dialog.destroy())

    def show_keys(self):
        """Show API keys management."""
        # Title
        tk.Label(self.content, text="API Keys",
                font=("Arial", 20, "bold"),
                fg="#ffffff", bg=COLORS["bg"],
                padx=30, pady=15).pack(anchor="w")

        # Keys list - directly in content
        self.api_keys_full = get_api_keys_full()
        for api in self.api_keys_full:
            self.create_key_row_full(self.content, api)

        # Global Model Bans at bottom
        ban_frame = tk.Frame(self.content, bg=COLORS["card"], pady=10, padx=15)
        ban_frame.pack(fill="x", padx=30, pady=15)

        tk.Label(ban_frame, text="GLOBAL MODEL BANS (blocked for ALL sessions)",
                font=("Arial", 10, "bold"),
                fg="#ff4444", bg=COLORS["card"]).pack(anchor="w")

        global_banned = self.session_mgr.settings.get("global_banned_models", [])
        self.banned_text = tk.Text(ban_frame, height=2, font=("Consolas", 10),
                             bg=COLORS["bg"], fg=COLORS["text"],
                             insertbackground=COLORS["text"], relief="flat")
        self.banned_text.pack(fill="x", pady=5)
        if global_banned:
            self.banned_text.insert("1.0", ", ".join(global_banned))

        def save_bans():
            raw = self.banned_text.get("1.0", "end").strip()
            models = [m.strip() for m in raw.replace(",", "\n").split("\n") if m.strip()]
            self.session_mgr.settings["global_banned_models"] = models
            self.session_mgr._save()

        tk.Label(ban_frame, text="[Save Bans]",
                font=("Arial", 10, "bold"),
                fg="#ffffff", bg="#ff4444",
                padx=10, pady=3, cursor="hand2").pack(anchor="e")
        ban_frame.winfo_children()[-1].bind("<Button-1>", lambda e: save_bans())

    def create_key_row_full(self, parent, api):
        """Create a full API key management row with URL info."""
        key_id = api.get("id", "")
        display_name = api.get("name", key_id)
        url = api.get("url", "")
        notes = api.get("notes", "")
        has_key = secure_has_key(key_id)

        row = tk.Frame(parent, bg=COLORS["card"], pady=12, padx=20)
        row.pack(fill="x", pady=4, padx=30)

        # Status indicator
        status_color = "#00ff00" if has_key else "#666666"
        status_char = "[OK]" if has_key else "[--]"
        tk.Label(row, text=status_char,
                font=("Arial", 10, "bold"),
                fg=status_color, bg=COLORS["card"],
                padx=5, pady=5).pack(side="left")

        # Name and info
        info_frame = tk.Frame(row, bg=COLORS["card"])
        info_frame.pack(side="left", fill="x", expand=True, padx=10)

        tk.Label(info_frame, text=display_name,
                font=("Arial", 13, "bold"),
                fg="#ffffff", bg=COLORS["card"],
                pady=3).pack(anchor="w")

        status_text = "Key configured" if has_key else "No key set"
        tk.Label(info_frame, text=f"{key_id} - {status_text}",
                font=("Arial", 9),
                fg="#888888", bg=COLORS["card"]).pack(anchor="w")

        # Right side - actions
        actions = tk.Frame(row, bg=COLORS["card"])
        actions.pack(side="right")

        # Key actions
        if has_key:
            update_btn = tk.Label(actions, text="[Update]",
                                 font=("Arial", 10, "bold"),
                                 fg="#ffaa00", bg=COLORS["card"],
                                 cursor="hand2", padx=8, pady=3)
            update_btn.pack(side="left")
            update_btn.bind("<Button-1>", lambda e, k=key_id, n=display_name: self.edit_key(k, n))

            clear_btn = tk.Label(actions, text="[Clear]",
                                 font=("Arial", 10),
                                 fg="#ff4444", bg=COLORS["card"],
                                 cursor="hand2", padx=5, pady=3)
            clear_btn.pack(side="left")
            clear_btn.bind("<Button-1>", lambda e, k=key_id, n=display_name: self.remove_key(k, n))
        else:
            add_btn = tk.Label(actions, text="[+ Set Key]",
                              font=("Arial", 10, "bold"),
                              fg="#00ff00", bg=COLORS["card"],
                              cursor="hand2", padx=8, pady=3)
            add_btn.pack(side="left")
            add_btn.bind("<Button-1>", lambda e, k=key_id, n=display_name: self.edit_key(k, n))

    def edit_api_config(self, api):
        """Edit an API's configuration (name, URL, notes)."""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit API - {api.get('name', '')}")
        dialog.geometry("500x420")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=COLORS["bg"], padx=30, pady=25)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text=f"Edit: {api.get('name', '')}",
                font=("Segoe UI", 14, "bold"),
                fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w")

        # Name
        tk.Label(frame, text="Display Name",
                font=("Segoe UI", 10),
                fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(anchor="w", pady=(15, 3))

        name_entry = tk.Entry(frame, font=("Segoe UI", 11),
                             bg=COLORS["card"], fg=COLORS["text"],
                             insertbackground=COLORS["text"], relief="flat")
        name_entry.insert(0, api.get("name", ""))
        name_entry.pack(fill="x", ipady=6)

        # URL
        tk.Label(frame, text="Base URL / Endpoint",
                font=("Segoe UI", 10),
                fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(anchor="w", pady=(15, 3))

        url_entry = tk.Entry(frame, font=("Segoe UI", 11),
                            bg=COLORS["card"], fg=COLORS["text"],
                            insertbackground=COLORS["text"], relief="flat")
        url_entry.insert(0, api.get("url", ""))
        url_entry.pack(fill="x", ipady=6)

        # Notes
        tk.Label(frame, text="Notes / Instructions",
                font=("Segoe UI", 10),
                fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(anchor="w", pady=(15, 3))

        notes_entry = tk.Text(frame, font=("Segoe UI", 10),
                             bg=COLORS["card"], fg=COLORS["text"],
                             insertbackground=COLORS["text"], relief="flat",
                             height=4, wrap="word")
        notes_entry.insert("1.0", api.get("notes", ""))
        notes_entry.pack(fill="x")

        def save():
            keys = get_api_keys_full()
            for k in keys:
                if k["id"] == api["id"]:
                    k["name"] = name_entry.get().strip() or api["id"]
                    k["url"] = url_entry.get().strip()
                    k["notes"] = notes_entry.get("1.0", "end-1c").strip()
                    break
            save_api_keys_full(keys)
            dialog.destroy()
            self.show_tab("keys")

        btn = tk.Label(frame, text="Save Changes",
                      font=("Segoe UI", 11, "bold"),
                      fg=COLORS["bg"], bg=COLORS["accent"],
                      padx=20, pady=10, cursor="hand2")
        btn.pack(pady=(20, 0))
        btn.bind("<Button-1>", lambda e: save())

    def create_key_row(self, parent, key_id, display_name):
        """Create a key management row (legacy)."""
        has_key = secure_has_key(key_id)

        row = tk.Frame(parent, bg=COLORS["card"], pady=15, padx=20)
        row.pack(fill="x", pady=2)

        # Status
        status_color = COLORS["success"] if has_key else COLORS["text_muted"]
        tk.Label(row, text="●" if has_key else "○",
                font=("Segoe UI", 14),
                fg=status_color, bg=COLORS["card"]).pack(side="left", padx=(0, 15))

        # Name
        tk.Label(row, text=display_name,
                font=("Segoe UI", 12),
                fg=COLORS["text"], bg=COLORS["card"]).pack(side="left")

        tk.Label(row, text=f"({key_id})" if key_id != display_name.lower().replace(" ", "_").replace(".", "") else "",
                font=("Segoe UI", 9),
                fg=COLORS["text_muted"], bg=COLORS["card"]).pack(side="left", padx=5)

        tk.Label(row, text="Configured" if has_key else "Not configured",
                font=("Segoe UI", 10),
                fg=COLORS["text_secondary"], bg=COLORS["card"]).pack(side="left", padx=10)

        # Delete API button (removes from list entirely)
        delete_btn = tk.Label(row, text="🗑️",
                             font=("Segoe UI", 10),
                             fg=COLORS["text_muted"], bg=COLORS["card"],
                             cursor="hand2")
        delete_btn.pack(side="right", padx=5)
        delete_btn.bind("<Button-1>", lambda e, k=key_id, n=display_name: self.delete_api(k, n))

        # Actions
        if has_key:
            update_btn = tk.Label(row, text="Update",
                                 font=("Segoe UI", 10),
                                 fg=COLORS["accent"], bg=COLORS["card"],
                                 cursor="hand2")
            update_btn.pack(side="right", padx=10)
            update_btn.bind("<Button-1>", lambda e, k=key_id, n=display_name: self.edit_key(k, n))

            clear_btn = tk.Label(row, text="Clear",
                                 font=("Segoe UI", 10),
                                 fg=COLORS["danger"], bg=COLORS["card"],
                                 cursor="hand2")
            clear_btn.pack(side="right", padx=10)
            clear_btn.bind("<Button-1>", lambda e, k=key_id, n=display_name: self.remove_key(k, n))
        else:
            add_btn = tk.Label(row, text="+ Set Key",
                              font=("Segoe UI", 10, "bold"),
                              fg=COLORS["success"], bg=COLORS["card"],
                              cursor="hand2")
            add_btn.pack(side="right", padx=10)
            add_btn.bind("<Button-1>", lambda e, k=key_id, n=display_name: self.edit_key(k, n))

    def add_api_dialog(self):
        """Dialog to add a new API to track."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add API")
        dialog.geometry("500x450")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        # Scrollable frame
        canvas = tk.Canvas(dialog, bg=COLORS["bg"], highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        frame = tk.Frame(canvas, bg=COLORS["bg"], padx=30, pady=25)
        canvas.create_window((0, 0), window=frame, anchor="nw", width=480)

        tk.Label(frame, text="Add New API",
                font=("Segoe UI", 16, "bold"),
                fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w")

        tk.Label(frame, text="Add any API service - custom endpoints supported",
                font=("Segoe UI", 10),
                fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(anchor="w", pady=(5, 15))

        # Name field
        tk.Label(frame, text="Display Name *",
                font=("Segoe UI", 10, "bold"),
                fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(anchor="w")
        tk.Label(frame, text="e.g., 'Google AI', 'My Custom API'",
                font=("Segoe UI", 9),
                fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(anchor="w")

        name_entry = tk.Entry(frame, font=("Segoe UI", 11),
                             bg=COLORS["card"], fg=COLORS["text"],
                             insertbackground=COLORS["text"], relief="flat")
        name_entry.pack(fill="x", pady=(5, 12), ipady=6)
        name_entry.focus_set()

        # ID field
        tk.Label(frame, text="Key ID *",
                font=("Segoe UI", 10, "bold"),
                fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(anchor="w")
        tk.Label(frame, text="Lowercase, no spaces - e.g., 'google_ai'",
                font=("Segoe UI", 9),
                fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(anchor="w")

        id_entry = tk.Entry(frame, font=("Segoe UI", 11),
                           bg=COLORS["card"], fg=COLORS["text"],
                           insertbackground=COLORS["text"], relief="flat")
        id_entry.pack(fill="x", pady=(5, 12), ipady=6)

        # Base URL field
        tk.Label(frame, text="Base URL / Endpoint",
                font=("Segoe UI", 10, "bold"),
                fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(anchor="w")
        tk.Label(frame, text="e.g., 'https://api.example.com/v1' (optional but recommended)",
                font=("Segoe UI", 9),
                fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(anchor="w")

        url_entry = tk.Entry(frame, font=("Segoe UI", 11),
                            bg=COLORS["card"], fg=COLORS["text"],
                            insertbackground=COLORS["text"], relief="flat")
        url_entry.pack(fill="x", pady=(5, 12), ipady=6)

        # Notes field
        tk.Label(frame, text="Notes / Instructions",
                font=("Segoe UI", 10, "bold"),
                fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(anchor="w")
        tk.Label(frame, text="Any info about how to use this API (headers, params, etc.)",
                font=("Segoe UI", 9),
                fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(anchor="w")

        notes_entry = tk.Text(frame, font=("Segoe UI", 10),
                             bg=COLORS["card"], fg=COLORS["text"],
                             insertbackground=COLORS["text"], relief="flat",
                             height=3, wrap="word")
        notes_entry.pack(fill="x", pady=(5, 15))

        def add():
            name = name_entry.get().strip()
            key_id = id_entry.get().strip().lower().replace(" ", "_")
            url = url_entry.get().strip()
            notes = notes_entry.get("1.0", "end-1c").strip()

            if name and key_id:
                # Add to list
                keys = get_api_keys_full()
                if not any(k["id"] == key_id for k in keys):
                    keys.append({
                        "id": key_id,
                        "name": name,
                        "url": url,
                        "notes": notes
                    })
                    save_api_keys_full(keys)
                    dialog.destroy()
                    self.show_tab("keys")
                else:
                    messagebox.showwarning("Exists", f"API '{key_id}' already exists")
            else:
                messagebox.showwarning("Required", "Name and Key ID are required")

        btn = tk.Label(frame, text="Add API",
                      font=("Segoe UI", 11, "bold"),
                      fg=COLORS["bg"], bg=COLORS["accent"],
                      padx=20, pady=10, cursor="hand2")
        btn.pack(pady=(5, 0))
        btn.bind("<Button-1>", lambda e: add())

    def delete_api(self, key_id, display_name):
        """Remove an API from the tracked list."""
        if messagebox.askyesno("Remove API",
                              f"Remove '{display_name}' from your API list?\n\nThis will also delete the stored key."):
            # Remove from secure storage
            secure_delete_key(key_id)

            # Remove from list
            keys = get_api_keys_list()
            keys = [(k, n) for k, n in keys if k != key_id]
            save_api_keys_list(keys)
            self.show_tab("keys")

    def edit_key(self, key_id, display_name):
        """Dialog to add/edit a key."""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit {display_name}")
        dialog.geometry("450x220")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=COLORS["bg"], padx=30, pady=25)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text=f"Enter {display_name} API Key",
                font=("Segoe UI", 14, "bold"),
                fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w")

        tk.Label(frame, text="Key will be stored in encrypted local storage",
                font=("Segoe UI", 10),
                fg=COLORS["text_secondary"], bg=COLORS["bg"]).pack(anchor="w", pady=(5, 15))

        entry_frame = tk.Frame(frame, bg=COLORS["card"])
        entry_frame.pack(fill="x", pady=(0, 20))

        entry = tk.Entry(entry_frame, font=("Consolas", 11),
                        bg=COLORS["card"], fg=COLORS["text"],
                        insertbackground=COLORS["text"], relief="flat",
                        show="●")
        entry.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        entry.focus_set()

        showing = [False]
        toggle = tk.Label(entry_frame, text="Show",
                         font=("Segoe UI", 9),
                         fg=COLORS["accent"], bg=COLORS["card"],
                         cursor="hand2", padx=10)
        toggle.pack(side="right", pady=10)

        def toggle_show(e=None):
            showing[0] = not showing[0]
            entry.config(show="" if showing[0] else "●")
            toggle.config(text="Hide" if showing[0] else "Show")
        toggle.bind("<Button-1>", toggle_show)

        def save():
            value = entry.get().strip()
            if value:
                secure_set_key(key_id, value)
                dialog.destroy()
                self.show_tab("keys")

        btn = tk.Label(frame, text="Save Key",
                      font=("Segoe UI", 11, "bold"),
                      fg=COLORS["bg"], bg=COLORS["success"],
                      padx=20, pady=10, cursor="hand2")
        btn.pack()
        btn.bind("<Button-1>", lambda e: save())
        entry.bind("<Return>", lambda e: save())

    def remove_key(self, key_id, display_name):
        if messagebox.askyesno("Remove Key", f"Remove {display_name} API key?"):
            secure_delete_key(key_id)
            self.show_tab("keys")

    def show_settings(self):
        """Show settings."""
        header = tk.Frame(self.content, bg=COLORS["bg"], pady=20, padx=30)
        header.pack(fill="x")

        tk.Label(header, text="Settings",
                font=("Segoe UI", 24, "bold"),
                fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w")

        settings_frame = tk.Frame(self.content, bg=COLORS["bg"], padx=30)
        settings_frame.pack(fill="both", expand=True)

        # Auto-ban threshold
        self.create_setting_row(settings_frame, "Auto-ban Threshold",
                               "Ban sessions after this many blocked requests",
                               "auto_ban_threshold", self.session_mgr.settings.get("auto_ban_threshold", 10))

        # Warning threshold
        self.create_setting_row(settings_frame, "Warning Threshold",
                               "Warn sessions after this many blocked requests",
                               "warning_threshold", self.session_mgr.settings.get("warning_threshold", 5))

        # Max history
        self.create_setting_row(settings_frame, "History Limit",
                               "Maximum number of requests to keep in history",
                               "max_history", self.session_mgr.settings.get("max_history", 1000))

        # Global Model Bans Section
        ban_frame = tk.Frame(settings_frame, bg=COLORS["card"], pady=15, padx=20)
        ban_frame.pack(fill="x", pady=(20, 5))

        tk.Label(ban_frame, text="GLOBAL MODEL BANS",
                font=("Arial", 12, "bold"),
                fg="#ff4444", bg=COLORS["card"]).pack(anchor="w")

        tk.Label(ban_frame, text="These models are blocked for ALL sessions (one per line, * = wildcard)",
                font=("Arial", 10),
                fg=COLORS["text_secondary"], bg=COLORS["card"]).pack(anchor="w", pady=(2, 8))

        global_banned = self.session_mgr.settings.get("global_banned_models", [])
        banned_text = tk.Text(ban_frame, height=4, font=("Consolas", 10),
                             bg=COLORS["bg"], fg=COLORS["text"],
                             insertbackground=COLORS["text"], relief="flat")
        banned_text.pack(fill="x", pady=5)
        if global_banned:
            banned_text.insert("1.0", "\n".join(global_banned))

        def save_global_bans():
            raw = banned_text.get("1.0", "end").strip()
            models = [m.strip() for m in raw.split("\n") if m.strip()]
            self.session_mgr.settings["global_banned_models"] = models
            self.session_mgr._save()

        save_btn = tk.Label(ban_frame, text="Save Global Bans",
                           font=("Arial", 10, "bold"),
                           fg="#000000", bg="#ff4444",
                           padx=15, pady=5, cursor="hand2")
        save_btn.pack(anchor="w", pady=(5, 0))
        save_btn.bind("<Button-1>", lambda e: save_global_bans())

        # Optional Features Section
        opt_frame = tk.Frame(settings_frame, bg=COLORS["card"], pady=15, padx=20)
        opt_frame.pack(fill="x", pady=(20, 5))

        tk.Label(opt_frame, text="OPTIONAL FEATURES",
                font=("Arial", 12, "bold"),
                fg="#00ffaa", bg=COLORS["card"]).pack(anchor="w")

        # System Tray toggle
        tray_available = " (requires: pip install pystray pillow)" if not HAS_TRAY else ""
        tray_var = tk.BooleanVar(value=self.enable_tray)
        tray_cb = tk.Checkbutton(opt_frame, text=f"Minimize to System Tray{tray_available}",
                                variable=tray_var,
                                font=("Arial", 10),
                                fg=COLORS["text"] if HAS_TRAY else COLORS["text_muted"],
                                bg=COLORS["card"],
                                selectcolor=COLORS["bg"],
                                activebackground=COLORS["card"],
                                state="normal" if HAS_TRAY else "disabled")
        tray_cb.pack(anchor="w", pady=(8, 2))

        # Notifications toggle
        notif_available = " (requires: pip install plyer)" if not HAS_NOTIFICATIONS else ""
        notif_var = tk.BooleanVar(value=self.enable_notifications)
        notif_cb = tk.Checkbutton(opt_frame, text=f"Desktop Notifications{notif_available}",
                                 variable=notif_var,
                                 font=("Arial", 10),
                                 fg=COLORS["text"] if HAS_NOTIFICATIONS else COLORS["text_muted"],
                                 bg=COLORS["card"],
                                 selectcolor=COLORS["bg"],
                                 activebackground=COLORS["card"],
                                 state="normal" if HAS_NOTIFICATIONS else "disabled")
        notif_cb.pack(anchor="w", pady=2)

        # Barrier Mode toggle - read fresh from disk
        barrier_var = tk.BooleanVar(value=self.session_mgr.is_barrier_active())
        barrier_cb = tk.Checkbutton(opt_frame, text="🛡️ Barrier Mode (require approval for each API call)",
                                   variable=barrier_var,
                                   font=("Arial", 10),
                                   fg="#ff6600", bg=COLORS["card"],
                                   selectcolor=COLORS["bg"],
                                   activebackground=COLORS["card"])
        barrier_cb.pack(anchor="w", pady=2)

        tk.Label(opt_frame, text="    When enabled, every API call shows a popup requiring your approval",
                font=("Arial", 9),
                fg=COLORS["text_muted"], bg=COLORS["card"]).pack(anchor="w")

        tk.Label(opt_frame, text="Note: Barrier mode takes effect immediately. Tray/notifications require restart.",
                font=("Arial", 9),
                fg=COLORS["text_muted"], bg=COLORS["card"]).pack(anchor="w", pady=(5, 0))

        def save_optional():
            self.session_mgr.settings["enable_tray"] = tray_var.get()
            self.session_mgr.settings["enable_notifications"] = notif_var.get()
            self.session_mgr.settings["barrier_mode"] = barrier_var.get()
            self.session_mgr._save()
            # Barrier mode takes effect immediately, others need restart
            if barrier_var.get():
                messagebox.showinfo("Saved", "Barrier Mode ENABLED - every API call will require your approval.\n\nTray/notification changes require app restart.")
            else:
                messagebox.showinfo("Saved", "Optional features saved. Restart app to apply changes.")

        save_opt_btn = tk.Label(opt_frame, text="Save Options",
                               font=("Arial", 10, "bold"),
                               fg="#000000", bg="#00ffaa",
                               padx=15, pady=5, cursor="hand2")
        save_opt_btn.pack(anchor="w", pady=(10, 0))
        save_opt_btn.bind("<Button-1>", lambda e: save_optional())

        # Price Configuration Section
        price_frame = tk.Frame(settings_frame, bg=COLORS["card"], pady=15, padx=20)
        price_frame.pack(fill="x", pady=(20, 5))

        tk.Label(price_frame, text="💰 PRICE CONFIGURATION",
                font=("Arial", 12, "bold"),
                fg="#ffaa00", bg=COLORS["card"]).pack(anchor="w")

        tk.Label(price_frame, text="Adjust API costs as prices change (used for budget tracking)",
                font=("Arial", 10),
                fg=COLORS["text_secondary"], bg=COLORS["card"]).pack(anchor="w", pady=(2, 8))

        # Get current prices or defaults
        from apibouncer.proxy import DEFAULT_PRICES
        current_prices = self.session_mgr.settings.get("prices", DEFAULT_PRICES.copy())

        price_entries = {}

        # OpenAI Images
        openai_frame = tk.Frame(price_frame, bg=COLORS["bg"], padx=10, pady=8)
        openai_frame.pack(fill="x", pady=3)

        tk.Label(openai_frame, text="OpenAI gpt-image-1.5:",
                font=("Arial", 9, "bold"),
                fg="#00ffff", bg=COLORS["bg"]).pack(anchor="w")

        openai_row = tk.Frame(openai_frame, bg=COLORS["bg"])
        openai_row.pack(fill="x", pady=3)

        for quality in ["low", "medium", "high"]:
            cell = tk.Frame(openai_row, bg=COLORS["bg"])
            cell.pack(side="left", padx=(0, 15))
            tk.Label(cell, text=f"{quality}:", font=("Arial", 8),
                    fg="#888888", bg=COLORS["bg"]).pack(side="left")
            entry = tk.Entry(cell, font=("Arial", 9), width=6,
                           bg="#1a1a2e", fg="#ffaa00",
                           insertbackground="#ffaa00", relief="flat")
            entry.pack(side="left", padx=2)
            price = current_prices.get("openai", {}).get("gpt-image-1.5", {}).get(quality, 0.02)
            entry.insert(0, f"{price:.3f}")
            price_entries[f"openai.gpt-image-1.5.{quality}"] = entry

        # MiniMax Videos
        minimax_frame = tk.Frame(price_frame, bg=COLORS["bg"], padx=10, pady=8)
        minimax_frame.pack(fill="x", pady=3)

        tk.Label(minimax_frame, text="MiniMax Videos (per second):",
                font=("Arial", 9, "bold"),
                fg="#ff00ff", bg=COLORS["bg"]).pack(anchor="w")

        minimax_row = tk.Frame(minimax_frame, bg=COLORS["bg"])
        minimax_row.pack(fill="x", pady=3)

        for model in ["video-01", "video-01-live2d"]:
            cell = tk.Frame(minimax_row, bg=COLORS["bg"])
            cell.pack(side="left", padx=(0, 15))
            tk.Label(cell, text=f"{model}:", font=("Arial", 8),
                    fg="#888888", bg=COLORS["bg"]).pack(side="left")
            entry = tk.Entry(cell, font=("Arial", 9), width=6,
                           bg="#1a1a2e", fg="#ffaa00",
                           insertbackground="#ffaa00", relief="flat")
            entry.pack(side="left", padx=2)
            price = current_prices.get("minimax", {}).get(model, 0.05)
            entry.insert(0, f"{price:.3f}")
            price_entries[f"minimax.{model}"] = entry

        def save_prices():
            try:
                new_prices = {
                    "openai": {
                        "gpt-image-1.5": {
                            "low": float(price_entries["openai.gpt-image-1.5.low"].get()),
                            "medium": float(price_entries["openai.gpt-image-1.5.medium"].get()),
                            "high": float(price_entries["openai.gpt-image-1.5.high"].get()),
                        },
                        "dall-e-3": current_prices.get("openai", {}).get("dall-e-3", {"standard": 0.04, "hd": 0.08}),
                        "gpt-4o": current_prices.get("openai", {}).get("gpt-4o", 0.005),
                        "gpt-4o-mini": current_prices.get("openai", {}).get("gpt-4o-mini", 0.0002),
                    },
                    "minimax": {
                        "video-01": float(price_entries["minimax.video-01"].get()),
                        "video-01-live2d": float(price_entries["minimax.video-01-live2d"].get()),
                    }
                }
                self.session_mgr.settings["prices"] = new_prices
                self.session_mgr._save()
                messagebox.showinfo("Saved", "Price configuration saved!")
            except ValueError:
                messagebox.showerror("Error", "Invalid price value. Use decimal numbers (e.g., 0.02)")

        save_price_btn = tk.Label(price_frame, text="Save Prices",
                                 font=("Arial", 10, "bold"),
                                 fg="#000000", bg="#ffaa00",
                                 padx=15, pady=5, cursor="hand2")
        save_price_btn.pack(anchor="w", pady=(10, 0))
        save_price_btn.bind("<Button-1>", lambda e: save_prices())

    def create_setting_row(self, parent, title, description, key, current_value):
        """Create a settings row."""
        row = tk.Frame(parent, bg=COLORS["card"], pady=15, padx=20)
        row.pack(fill="x", pady=5)

        left = tk.Frame(row, bg=COLORS["card"])
        left.pack(side="left", fill="x", expand=True)

        tk.Label(left, text=title,
                font=("Segoe UI", 12),
                fg=COLORS["text"], bg=COLORS["card"]).pack(anchor="w")

        tk.Label(left, text=description,
                font=("Segoe UI", 10),
                fg=COLORS["text_secondary"], bg=COLORS["card"]).pack(anchor="w")

        entry = tk.Entry(row, font=("Segoe UI", 12), width=10,
                        bg=COLORS["bg"], fg=COLORS["text"],
                        insertbackground=COLORS["text"], relief="flat",
                        justify="center")
        entry.insert(0, str(current_value))
        entry.pack(side="right", padx=10, ipady=5)

        def save(e=None):
            try:
                self.session_mgr.settings[key] = int(entry.get())
                self.session_mgr._save()
            except ValueError:
                pass

        entry.bind("<FocusOut>", save)
        entry.bind("<Return>", save)


def main():
    root = tk.Tk()
    app = ModernApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
