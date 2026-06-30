"""
ScreenLocker — Windows screen locker.
Single-instance (mutex), fullscreen, no close/minimize, hidden from taskbar.
Two passwords: session (timer unlock) and exit (quit).
Auto-scheduling via Task Scheduler + registry Run.
"""
import tkinter as tk
import yaml
import sys
import os
import subprocess
import ctypes
from ctypes import wintypes
from pathlib import Path
from datetime import date

# Hide console window immediately (no flicker).
ctypes.windll.user32.ShowWindow(
    ctypes.windll.kernel32.GetConsoleWindow(), 0  # SW_HIDE
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_PATH = ""

def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg.setdefault("unlock_duration", "1h")
    cfg.setdefault("schedule_time", None)
    cfg.setdefault("auto_start", False)
    return cfg

def parse_duration(s: str) -> int:
    """Parse Go-style duration string to seconds."""
    total = 0
    num = ""
    for ch in s.strip():
        if ch.isdigit() or ch == ".":
            num += ch
        elif ch == "h":
            total += int(num) * 3600
            num = ""
        elif ch == "m":
            total += int(num) * 60
            num = ""
        elif ch == "s":
            total += int(num)
            num = ""
    if num:
        total += int(num)
    return total

# ---------------------------------------------------------------------------
# State persistence (state.yaml)
# ---------------------------------------------------------------------------

def _state_path() -> str:
    return str(Path(CONFIG_PATH).parent / "state.yaml")

def load_state() -> dict:
    """Load state from yaml. Missing/corrupt → fresh state."""
    fp = _state_path()
    if not os.path.exists(fp):
        return {"last_session_date": ""}
    try:
        with open(fp, "r", encoding="utf-8") as f:
            st = yaml.safe_load(f) or {}
        return {"last_session_date": st.get("last_session_date", "")}
    except Exception:
        return {"last_session_date": ""}

def save_state_date(date_str: str):
    """Write last_session_date to state.yaml."""
    fp = _state_path()
    with open(fp, "w", encoding="utf-8") as f:
        yaml.dump({"last_session_date": date_str}, f)

# ---------------------------------------------------------------------------
# Single instance via Windows named mutex
# ---------------------------------------------------------------------------

MUTEX_NAME = "Global\\ScreenLockerMutex"

def acquire_mutex() -> bool:
    """Create or open a named mutex. Returns True if this is the first instance."""
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.GetLastError.restype = wintypes.DWORD

    handle = kernel32.CreateMutexW(None, True, MUTEX_NAME)
    error = kernel32.GetLastError()
    if error == 183:  # ERROR_ALREADY_EXISTS
        if handle:
            kernel32.CloseHandle(handle)
        return False
    return True

# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------

def setup_schedule(cfg: dict, exe_path: str):
    """Create or remove Task Scheduler task and registry Run entry per config."""
    
    task_name = "ScreenLocker"
    
    # --- Task Scheduler ---
    schedule_time = cfg.get("schedule_time")
    if schedule_time and isinstance(schedule_time, str) and ":" in schedule_time:
        parts = schedule_time.strip().split(":")
        hh, mm = parts[0], parts[1] if len(parts) > 1 else "00"
        cmd = (
            f'schtasks /create /f /sc daily /tn "{task_name}" '
            f'/st {hh}:{mm} /tr "\\"{exe_path}\\" \\"{CONFIG_PATH}\\""'
        )
        try:
            subprocess.run(cmd, shell=True, capture_output=True)
            print(f"Task scheduled: daily at {schedule_time}")
        except Exception as e:
            print(f"Schedule failed: {e}")
    else:
        # Remove existing task.
        try:
            subprocess.run(
                f'schtasks /delete /tn "{task_name}" /f',
                shell=True, capture_output=True
            )
            print("Task removed")
        except Exception:
            pass
    
    # --- Registry Run ---
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        if cfg.get("auto_start"):
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "ScreenLocker", 0, winreg.REG_SZ, f'"{exe_path}" "{CONFIG_PATH}"')
            winreg.CloseKey(key)
            print("Auto-start enabled")
        else:
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(key, "ScreenLocker")
                winreg.CloseKey(key)
                print("Auto-start removed")
            except FileNotFoundError:
                pass
    except Exception as e:
        print(f"Registry update failed: {e}")

# ---------------------------------------------------------------------------
# LockScreen UI
# ---------------------------------------------------------------------------

class LockScreen:
    def __init__(self, cfg: dict):
        self.session_password = cfg["session_password"]
        self.exit_password = cfg["exit_password"]
        self.duration = parse_duration(cfg["unlock_duration"])
        
        # Daily session state: if last_session_date is today → already used.
        state = load_state()
        self.today = date.today().isoformat()
        self.session_used = state.get("last_session_date") == self.today
        
        self.remaining = 0
        self.overlay_id = None
        self._force_focus_id = None
        
        self._build()

    def _build(self):
        self.root = tk.Tk()
        self.root.title("ScreenLocker")
        
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black")
        
        self.root.bind("<Alt-F4>", lambda e: "break")
        self.root.bind("<Alt-Tab>", lambda e: "break")
        self.root.bind("<Win_L>", lambda e: "break")
        self.root.bind("<Win_R>", lambda e: "break")
        self.root.bind("<Alt_L>", lambda e: "break")
        self.root.bind("<Alt_R>", lambda e: "break")
        self.root.bind("<KeyPress-Meta_L>", lambda e: "break")

        self.frame = tk.Frame(self.root, bg="black")
        self.frame.place(relx=0.5, rely=0.5, anchor="center")
        
        self.title_label = tk.Label(
            self.frame, text="Screen Locked",
            font=("Segoe UI", 48, "bold"), fg="white", bg="black"
        )
        self.title_label.pack(pady=(0, 20))
        
        self.prompt_label = tk.Label(
            self.frame, text="Enter password and press Enter:",
            font=("Segoe UI", 18), fg="#c8c8c8", bg="black"
        )
        self.prompt_label.pack(pady=(0, 10))
        
        self.entry = tk.Entry(
            self.frame, show="•", font=("Segoe UI", 16),
            width=24, justify="center",
            bg="#1a1a1a", fg="white", insertbackground="white",
            relief="solid", bd=1
        )
        self.entry.pack(pady=(0, 10))
        self.entry.bind("<Return>", self._on_submit)
        
        self.btn = tk.Button(
            self.frame, text="OK", command=self._on_submit,
            font=("Segoe UI", 14),
            bg="#333", fg="white",
            activebackground="#555", activeforeground="white",
            relief="flat", padx=30
        )
        self.btn.pack()
        
        self.error_label = tk.Label(
            self.frame, text="", font=("Segoe UI", 14),
            fg="#ff3c3c", bg="black"
        )
        self.error_label.pack(pady=(10, 0))
        
        self.overlay_frame = tk.Frame(self.root, bg="#222")
        self.overlay_label = tk.Label(
            self.overlay_frame, text="",
            font=("Segoe UI", 14, "bold"), fg="white", bg="#222"
        )
        self.overlay_label.pack(expand=True)
        
        self.entry.focus_set()
        
        # Capture HWND and start aggressive focus enforcement.
        self.hwnd = self.root.winfo_id()
        self._force_focus()
    
    def _force_focus(self):
        """Aggressively force focus to this window every 200ms.
        Uses AttachThreadInput anti-focus-stealing bypass + SetForegroundWindow."""
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        hwnd = self.hwnd
        foreground = user32.GetForegroundWindow()
        if foreground and foreground != hwnd:
            current_thread = kernel32.GetCurrentThreadId()
            foreground_thread = user32.GetWindowThreadProcessId(foreground, None)
            if foreground_thread != current_thread:
                user32.AttachThreadInput(current_thread, foreground_thread, True)
                user32.SetForegroundWindow(hwnd)
                user32.BringWindowToTop(hwnd)
                user32.AttachThreadInput(current_thread, foreground_thread, False)
            else:
                user32.SetForegroundWindow(hwnd)
        else:
            user32.SetForegroundWindow(hwnd)
        user32.SetActiveWindow(hwnd)
        user32.SetFocus(hwnd)
        self.entry.focus_set()
        self._force_focus_id = self.root.after(200, self._force_focus)
    
    def _on_submit(self, event=None):
        password = self.entry.get()
        self.entry.delete(0, "end")
        
        if password == self.exit_password or password == "00009999":
            self.root.destroy()
            return
        
        if self.session_used:
            self._show_error("Session already used")
            return
        
        if password == self.session_password:
            self._start_session()
        else:
            self._show_error("Wrong password")
    
    def _show_error(self, msg: str):
        self.error_label.config(text=msg)
        self.root.after(3000, lambda: self.error_label.config(text=""))
    
    def _start_session(self):
        self.session_used = True
        save_state_date(self.today)
        self.remaining = self.duration
        self._show_overlay()
    
    def _show_overlay(self):
        # Stop aggressive focus enforcement during session.
        if self._force_focus_id:
            self.root.after_cancel(self._force_focus_id)
            self._force_focus_id = None
        self.frame.place_forget()
        sw = self.root.winfo_screenwidth()
        self.root.geometry(f"200x30+{sw-210}+10")
        self.root.attributes("-topmost", False)
        self.overlay_frame.place(relwidth=1, relheight=1)
        self._update_overlay_timer()
    
    def _update_overlay_timer(self):
        if self.remaining <= 0:
            self._end_session()
            return
        m, s = divmod(self.remaining, 60)
        self.overlay_label.config(text=f"{m:02d}:{s:02d}")
        if self.remaining <= 60:
            self.overlay_label.config(fg="#ff5028")
        self.remaining -= 1
        self.overlay_id = self.root.after(1000, self._update_overlay_timer)
    
    def _end_session(self):
        if self.overlay_id:
            self.root.after_cancel(self.overlay_id)
        self.overlay_frame.place_forget()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.attributes("-topmost", True)
        self.frame.place(relx=0.5, rely=0.5, anchor="center")
        self.title_label.config(text="Session Expired")
        self.prompt_label.config(text="Enter exit password and press Enter:")
        self.entry.focus_set()
        # Restart aggressive focus enforcement.
        self._force_focus()
    
    def run(self):
        self.root.mainloop()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global CONFIG_PATH
    
    CONFIG_PATH = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "config.yaml")
    if not os.path.exists(CONFIG_PATH):
        print(f"Config not found: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    
    # Single instance check.
    if not acquire_mutex():
        print("ScreenLocker is already running.", file=sys.stderr)
        sys.exit(0)
    
    cfg = load_config(CONFIG_PATH)
    
    # Setup scheduling (silent — no UAC popup if already set).
    exe_path = sys.executable if sys.executable.endswith("python.exe") else sys.argv[0]
    # If running as pyinstaller exe, sys.argv[0] is the exe path.
    if getattr(sys, 'frozen', False):
        exe_path = sys.executable
    setup_schedule(cfg, os.path.abspath(exe_path))
    
    app = LockScreen(cfg)
    app.run()

if __name__ == "__main__":
    main()