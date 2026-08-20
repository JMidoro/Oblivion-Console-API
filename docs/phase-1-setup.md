# Phase 1: Manual pipe validation

Phase 1 proves the real game-side execution seam before the permanent Lua mod
is built. It uses the disposable `CompanionBridgeTest` mod in this repository.

## Pinned components

- Oblivion-specific UE4SS `3.0.1-447`
- Steam Oblivion Remastered

The originally tested native ConsoleUtils `1.1` archive had SHA-256:

```text
DEDDFAE41CB7FC8B7D932F1D7F04691E2C4DA08396D751C2A98ECBD90EACBFF5
```

## Installation destination

The Steam game is installed at:

```text
C:\Program Files (x86)\Steam\steamapps\common\Oblivion Remastered
```

UE4SS, ConsoleUtils, and the scratch mod ultimately belong under:

```text
C:\Program Files (x86)\Steam\steamapps\common\Oblivion Remastered\
    OblivionRemastered\Binaries\Win64
```

Do not install the generic UE4SS release. Use the package adapted for Oblivion
Remastered.

## Manual download required

1. Close Oblivion Remastered.
2. Open the
   [UE4SS for OblivionRemastered files page](https://www.nexusmods.com/oblivionremastered/mods/32?tab=files).
3. Under **Update files**, find **UE4SS**, version `3.0.1-447`.
4. Choose **Manual download**. The file description states that this update can
   be installed standalone.
5. Leave the downloaded archive in the normal Windows Downloads directory.
6. Tell Codex the archive filename. Codex can then inspect the layout and request
   permission to install it, ConsoleUtils, and `CompanionBridgeTest` into the
   Steam directory.

That native adapter crashes this game build on the tested mutating command and
is no longer enabled. The scratch bridge instead uses the same Unreal
`KismetSystemLibrary.ExecuteConsoleCommand` seam used by current Oblivion
UE4SS mods, with a live player/controller context.

## In-game validation

After installation, Codex will inspect the UE4SS log while you:

1. Launch Oblivion Remastered normally through Steam.
2. Load a disposable save.
3. Leave the game running in a playable state.

The three manual mailbox commands will then be:

```text
player.additem 0000000F 100
player.getav health
definitely_not_a_real_command
```

Submit a command from the project directory with:

```powershell
.\.venv\Scripts\python.exe scripts\phase1_request.py "player.getav health"
```

The helper writes one atomic `request.json`, keeps waiting, prints the matching
`response.json`, and removes the consumed response. It does not use HTTP, so
this test isolates the filesystem and in-game portions of the pipe.

Record the exact returned console text in `docs/phase-1-results.md`.
