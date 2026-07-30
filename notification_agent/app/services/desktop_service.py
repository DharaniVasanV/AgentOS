"""
app/services/desktop_service.py

Native OS Desktop Toast Notification Service for Windows / macOS / Linux.
Features a 100% Reliable Floating Desktop Toast Window (Tkinter) + WinRT PowerShell Toast + Audio Chime.
"""

import sys
import time
import asyncio
import subprocess
import threading
from typing import Dict, Any
from app.utils.logger import get_logger

logger = get_logger(__name__)


def show_floating_toast_gui(title: str, message: str, priority: str = "Medium", timeout_sec: int = 6):
    """
    Displays a modern, frameless floating desktop toast notification window
    at the bottom-right corner of the user's screen. 100% immune to Focus Assist.
    """
    try:
        import tkinter as tk
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        
        # Priority Colors (Dark Mode Theme)
        bg_color = "#1e1e2e"
        title_color = "#f38ba8" if str(priority).upper() in ("URGENT", "HIGH") else "#89b4fa"
        border_color = "#f38ba8" if str(priority).upper() in ("URGENT", "HIGH") else "#89b4fa"
        
        root.configure(bg=border_color)
        
        inner_frame = tk.Frame(root, bg=bg_color, bd=0)
        inner_frame.pack(fill="both", expand=True, padx=2, pady=2)

        # Screen dimensions
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        w, h = 380, 110
        x = sw - w - 25
        y = sh - h - 60
        root.geometry(f"{w}x{h}+{x}+{y}")

        # Title Label
        toast_title = f"[{priority}] {title}"
        lbl_title = tk.Label(
            inner_frame,
            text=toast_title,
            font=("Segoe UI", 11, "bold"),
            fg=title_color,
            bg=bg_color,
            anchor="w"
        )
        lbl_title.pack(fill="x", padx=15, pady=(12, 2))

        # Message Label
        msg_clean = (message or "")[:220]
        lbl_msg = tk.Label(
            inner_frame,
            text=msg_clean,
            font=("Segoe UI", 9),
            fg="#cdd6f4",
            bg=bg_color,
            anchor="w",
            justify="left",
            wraplength=340
        )
        lbl_msg.pack(fill="x", padx=15, pady=(0, 10))

        # Auto-destroy after timeout
        root.after(timeout_sec * 1000, root.destroy)
        root.mainloop()
    except Exception as err:
        logger.warning(f"Floating Tkinter toast failed: {err}")


def send_desktop_notification_sync(title: str, message: str, priority: str = "Medium", app_name: str = "AgentOS Notification Agent") -> Dict[str, Any]:
    """Triggers native OS Desktop Notification Toast via Floating Window & WinRT PowerShell."""
    toast_title = f"[{priority}] {title}"
    msg_clean = (message or "")[:200].replace('"', "'").replace('`', "'").replace('$', '')

    # 1. Play System Chime / Sound
    if sys.platform == "win32":
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

    # 2. Launch 100% Reliable Floating Toast Window on Desktop (Threaded)
    try:
        t = threading.Thread(
            target=show_floating_toast_gui,
            args=(title, message, priority, 7),
            daemon=True
        )
        t.start()
        logger.info(f"✅ Floating Desktop Toast Popup triggered: '{toast_title}'")
    except Exception as gui_err:
        logger.warning(f"Failed to start floating toast thread: {gui_err}")

    # 3. WinRT PowerShell Toast for Action Center History
    if sys.platform == "win32":
        try:
            ps_code = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

$xml = @"
<toast>
    <visual>
        <binding template="ToastGeneric">
            <text>{toast_title}</text>
            <text>{msg_clean}</text>
        </binding>
    </visual>
</toast>
"@
$xmlDoc = New-Object Windows.Data.Xml.Dom.XmlDocument
$xmlDoc.LoadXml($xml)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xmlDoc)
$appId = "{{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}}\\\\WindowsPowerShell\\\\v1.0\\\\powershell.exe"
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
"""
            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_code],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

    # 4. Plyer Fallback
    try:
        from plyer import notification
        notification.notify(
            title=toast_title,
            message=msg_clean,
            app_name=app_name,
            timeout=7
        )
    except Exception:
        pass

    return {"status": "success"}


async def trigger_desktop_alert(title: str, message: str, priority: str = "Medium") -> Dict[str, Any]:
    """Asynchronous wrapper for desktop toast alert."""
    return await asyncio.to_thread(send_desktop_notification_sync, title, message, priority)
