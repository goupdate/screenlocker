# ScreenLocker

Windows screen locker with time-limited session unlock.

- Fullscreen, always-on-top, no close/minimize buttons
- Hidden from taskbar and Alt+Tab
- Two passwords: **session** (timer unlock) and **exit** (quit)
- Session unlock shrinks window to a countdown timer in top-right corner
- Timer expires → re-locks, session password no longer works
- **Single instance** — only one locker runs at a time (named mutex)
- **Auto-scheduling** — Task Scheduler daily time + registry Run at login

## Requirements

- Python 3.10+
- `pyyaml` (`pip install pyyaml`)

## Configuration

```yaml
# config.yaml
session_password: "temp123"
exit_password: "master456"
unlock_duration: "1h"       # Go-style: 1h, 30m, 1h30m, 90m, 10s
schedule_time: "06:00"      # daily task scheduler time, or null
auto_start: true            # start at user login (registry Run key)
```

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
LOCKED ──session_password──▶ SESSION (timer overlay, not topmost)
   │                               │
   │ exit_password                 │ timer expires
   ▼                               ▼
  EXIT                      LOCKED (only exit_password)
```

## License

MIT