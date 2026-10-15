# ScreenLocker

Windows screen locker with time-limited session unlock.

- Fullscreen, always-on-top, no close/minimize buttons
- Hidden from taskbar and Alt+Tab
- Multiple session passwords, each with its own unlock duration (one use per password per day)
- Exit password to quit the program
- Session unlock shrinks window to a countdown timer in top-right corner
- Timer expires → re-locks; another unused session password can still be entered
- **Single instance** — only one locker runs at a time (named mutex)
- **Auto-scheduling** — Task Scheduler daily time + registry Run at login

## Requirements

- Python 3.10+
- `pyyaml` (`pip install pyyaml`)

## Configuration

```yaml
# config.yaml
session_passwords:          # password -> unlock duration (Go-style)
  "temp123": "1h"           # each password works once per day
  "temp456": "2h"
  "temp789": "30m"
exit_password: "master456"  # fully exits the program
schedule_time: "06:00"      # daily task scheduler time, or null
auto_start: true            # start at user login (registry Run key)
```

Each session password unlocks for its own duration and can be used **once per day**.
After a session expires the screen re-locks and any session password not yet used
today can be entered. The exit password always quits the program.

## Usage

```powershell
python screenlocker.py [config.yaml]
```

If no config path is given, `config.yaml` in the current directory is used.

## Build to EXE

```powershell
.\build.bat
```

Requires `pyinstaller`. Produces `dist\screenlocker.exe`.

## State machine

```
LOCKED ──session_password (unused today)──▶ SESSION (timer overlay, not topmost)
   │                               │
   │ exit_password                 │ timer expires
   ▼                               ▼
  EXIT                      LOCKED (any unused session password, or exit_password)
```

## License

MIT