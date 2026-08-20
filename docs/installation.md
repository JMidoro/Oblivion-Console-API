# Installation

This is the private local setup for the tested Steam build. It does not require
OBSE64, an `.esp`, the native ConsoleUtils DLL, or a launcher wrapper.

## Components

- Steam Oblivion Remastered
- Oblivion-specific UE4SS `3.0.1-447`
- Python `3.11`
- The project-local `.venv`
- The `CompanionBridge` UE4SS Lua mod in this repository

The tested Steam executable directory is:

```text
C:\Program Files (x86)\Steam\steamapps\common\Oblivion Remastered\
    OblivionRemastered\Binaries\Win64
```

## Game-side files

Install the Oblivion-specific UE4SS package into the executable directory, then
copy this repository directory:

```text
ue4ss\Mods\CompanionBridge
```

to:

```text
OblivionRemastered\Binaries\Win64\ue4ss\Mods\CompanionBridge
```

The resulting mod must contain:

```text
CompanionBridge\
    enabled.txt
    Scripts\
        main.lua
        console_adapter.lua
        json.lua
```

Do not enable the old native ConsoleUtils `1.1` mod alongside the bridge. That
DLL crashed the tested game build when executing a mutating command. The
bridge contains its own player-context console adapter.

## Python service

From the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pytest
```

Start the service in its own terminal:

```powershell
.\.venv\Scripts\Activate.ps1
oblivion-bridge
```

The command intentionally keeps that terminal occupied while the service is
running. Stop it with `Ctrl+C`.

The service listens only on:

```text
http://127.0.0.1:8765
```

## Ordinary play

1. Start `oblivion-bridge` in its own terminal.
2. Launch Oblivion Remastered normally through Steam.
3. Load a save.
4. Start or connect the companion.
5. Send ordered command arrays to `POST /v1/commands`.

The generated companion handoff contract is `docs/openapi.json`.
