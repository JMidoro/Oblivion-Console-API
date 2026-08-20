# Oblivion Remastered Companion Bridge

This private local bridge gives an existing AI companion one mechanical tool:
submit one or more raw Oblivion console commands and wait for their results.

The bridge intentionally does not filter commands, verify their gameplay effects,
expose structured game state, or decide how the companion should behave.

The minimum playable integration and its bounded live smoke-test finish line
are complete.

## Development setup

From PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pytest
```

## Run the service

```powershell
.\.venv\Scripts\Activate.ps1
oblivion-bridge
```

The service binds to `127.0.0.1:8765` and exposes:

```text
POST /v1/commands
```

The default mailbox is:

```text
%USERPROFILE%\Documents\My Games\Oblivion Remastered\Saved\CompanionBridge
```

Configuration is available through environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `OBLIVION_BRIDGE_MAILBOX_DIR` | Path above | Shared mailbox directory |
| `OBLIVION_BRIDGE_TIMEOUT_SECONDS` | `60` | Total HTTP request deadline |
| `OBLIVION_BRIDGE_POLL_INTERVAL_SECONDS` | `0.05` | Mailbox polling interval |
| `OBLIVION_BRIDGE_PORT` | `8765` | Loopback HTTP port |

The HTTP request remains open while its request waits in the global FIFO and while
the game executes the batch. It returns only when the complete response is
available or the configured deadline expires.

## API contract

The generated OpenAPI handoff artifact is committed at
`docs/openapi.json`. Regenerate it with:

```powershell
.\.venv\Scripts\python scripts\export_openapi.py
```

## Game-side mod

The permanent UE4SS mod lives at:

```text
ue4ss\Mods\CompanionBridge
```

It executes one caller-supplied command per eligible game tick through
Unreal's player-context console function. It captures the console-buffer delta
without adding marker, readback, or verification commands.

See:

- `docs/installation.md`
- `docs/agent-console-guide.md`
- `docs/in-game-smoke-test.md`
- `docs/phase-1-results.md`

The normal `oblivion-bridge` command is a persistent service and keeps its
terminal occupied until stopped with `Ctrl+C`.
