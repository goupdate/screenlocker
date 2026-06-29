"""
ScreenLocker — Windows screen locker.
Fullscreen, no close/minimize buttons, hidden from taskbar/tray.
Two passwords: session (timer unlock) and exit (quit).
Python 3.12 + tkinter (stdlib).
"""
import tkinter as tk
import yaml
import sys
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # defaults
    cfg.setdefault("unlock_duration", "1h")
    return cfg

def parse_duration(s: str) -> int:
    """Parse Go-style duration string to seconds."""
    s = s.strip()
    total = 0
    num = ""
    for ch in s:
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
# LockScreen
# ---------------------------------------------------------------------------

class LockScreen:
    def __init__(self, cfg: dict):
        self.session_password = cfg["session_password"]
        self.exit_password = cfg["exit_password"]
        self.duration = parse_duration(cfg["unlock_duration"])
        
        self.session_used = False
        self.remaining = 0
        self.overlay_id = None
        
        self._build()
    
    def _build(self):
        self.root = tk.Tk()
        self.root.title("ScreenLocker")
        
        # Fullscreen on primary monitor.
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        
        # No title bar, always on top, hidden from taskbar.
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black")
        
        # Block Alt+F4, Alt+Tab via event binding.
        self.root.bind("<Alt-F4>", lambda e: "break")
        self.root.bind("<Alt-Tab>", lambda e: "break")
        
        # Main frame.
        self.frame = tk.Frame(self.root, bg="black")
        self.frame.place(relx=0.5, rely=0.5, anchor="center")
        
        # Title label.
        self.title_label = tk.Label(
            self.frame, text="Screen Locked",
            font=("Segoe UI", 48, "bold"),
            fg="white", bg="black"
        )
        self.title_label.pack(pady=(0, 20))
        
        # Prompt label.
        self.prompt_label = tk.Label(
            self.frame, text="Enter password and press Enter:",
            font=("Segoe UI", 18),
            fg="#c8c8c8", bg="black"
        )
        self.prompt_label.pack(pady=(0, 10))
        
        # Password entry.
        self.entry = tk.Entry(
            self.frame, show="•", font=("Segoe UI", 16),
            width=24, justify="center",
            bg="#1a1a1a", fg="white",
            insertbackground="white",
            relief="solid", bd=1
        )
        self.entry.pack(pady=(0, 10))
        self.entry.bind("<Return>", self._on_submit)
        
        # Submit button.
        self.btn = tk.Button(
            self.frame, text="OK", command=self._on_submit,
            font=("Segoe UI", 14),
            bg="#333", fg="white",
            activebackground="#555", activeforeground="white",
            relief="flat", padx=30
        )
        self.btn.pack()
        
        # Error label.
        self.error_label = tk.Label(
            self.frame, text="", font=("Segoe UI", 14),
            fg="#ff3c3c", bg="black"
        )
        self.error_label.pack(pady=(10, 0))
        
        # Overlay frame (hidden initially).
        self.overlay_frame = tk.Frame(self.root, bg="#222")
        self.overlay_label = tk.Label(
            self.overlay_frame, text="",
            font=("Segoe UI", 14, "bold"),
            fg="white", bg="#222"
        )
        self.overlay_label.pack(expand=True)
        
        # Focus entry.
        self.entry.focus_set()
    
    # -------------------------------------------------------------------
    # Submit
    # -------------------------------------------------------------------
    
    def _on_submit(self, event=None):
        password = self.entry.get()
        self.entry.delete(0, "end")
        
        if password == self.exit_password:
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
    
    # -------------------------------------------------------------------
    # Session / overlay
    # -------------------------------------------------------------------
    
    def _start_session(self):
        self.session_used = True
        self.remaining = self.duration
        self._show_overlay()
    
    def _show_overlay(self):
        # Hide main frame, show overlay.
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
        
        # Restore fullscreen.
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.attributes("-topmost", True)
        
        self.frame.place(relx=0.5, rely=0.5, anchor="center")
        
        self.title_label.config(text="Session Expired")
        self.prompt_label.config(text="Enter exit password and press Enter:")
        self.entry.focus_set()
    
    # -------------------------------------------------------------------
    # Run
    # -------------------------------------------------------------------
    
    def run(self):
        self.root.mainloop()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    if not os.path.exists(cfg_path):
        print(f"Config not found: {cfg_path}", file=sys.stderr)
        sys.exit(1)
    
    cfg = load_config(cfg_path)
    app = LockScreen(cfg)
    app.run()

if __name__ == "__main__":
    main()