# ScreenLocker

Windows screen locker with time-limited session unlock.

- Fullscreen, always-on-top, no close/minimize buttons
- Hidden from taskbar and Alt+Tab
- Two passwords: **session** (timer unlock) and **exit** (quit)
- Session unlock shrinks window to a countdown timer in top-right corner
- Timer expires → re-locks, session password no longer works

## Requirements

- Python 3.10+
- `pyyaml` (`pip install pyyaml`)

## Configuration

```yaml
# config.yaml
session_password: "temp123"
exit_password: "master456"
unlock_duration: "1h"   # Go-style: 1h, 30m, 1h30m, 90m, 10s
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
LOCKED ──session_password──▶ SESSION (timer overlay)
   │                               │
   │ exit_password                 │ timer expires
   ▼                               ▼
  EXIT                      LOCKED (only exit_password)
```

## License

MIT