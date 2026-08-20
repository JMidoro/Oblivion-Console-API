# Oblivion Remastered Companion Bridge: Focused Implementation Roadmap

## Goal

Build a private, local bridge that lets the existing companion send unrestricted Oblivion console commands into a running Steam installation of *The Elder Scrolls IV: Oblivion Remastered*.

The companion already has screen capture, player communication, and tool calling. This work only gives it access to the game console.

The finished integration consists of:

```text
Companion
    ↓ HTTP
Local web service
    ↓ fixed filesystem mailbox
UE4SS Lua mod
    ↓
Player-context Unreal console adapter
    ↓
Oblivion console
```

The local service is started manually before play. Oblivion launches normally through Steam. The bridge does not notify the player of agent interventions.

## Minimum playable integration

The integration is playable when:

* The companion can submit any Oblivion console command without filtering.
* One HTTP request can contain one command or an ordered batch.
* Commands execute strictly in submission order.
* Each command completes before the next begins.
* A batch stops when the bridge can establish that a command failed.
* The HTTP request remains open until the batch completes or times out.
* The response contains the captured console output for every attempted command.
* Empty console output is valid and does not imply failure.
* Requests submitted while the game cannot execute them wait until execution becomes available or the service times out.
* If the game or mod is unavailable, the HTTP call returns an error.
* No automatic verification commands are added.
* No structured game-state API or curated action catalog is required.

A response reports what the bridge actually knows. `executed` means the command was dispatched successfully on the game thread. It does not promise that the command had the intended gameplay effect.

## Chosen modding path

Use UE4SS as the in-game runtime and execute through Unreal's
`KismetSystemLibrary.ExecuteConsoleCommand` with the live player and controller
objects.

Capture only the entries appended to Unreal's console output buffer by the
caller-supplied command. Do not insert marker or verification commands.

The originally planned native ConsoleUtils `1.1` adapter was rejected during
Phase 1: read-only commands worked, but `player.additem` reproducibly crashed
inside its native dispatcher. The player-context Unreal path passed mutation,
query-output, and malformed-command tests.

UE4SS Lua mods live beneath `ue4ss\Mods\<ModName>\Scripts\main.lua`. Hooks must be registered only after their target Unreal functions exist in memory.

Archipelago remains a reference implementation. Its current Oblivion integration uses UE4SS and an `.esp`, exchanges information through files beneath the Oblivion save directory, and performs recurring processing from a player `ReceiveTick` hook registered after game fade-in. We reuse that communication and lifecycle pattern without adopting its client, session model, randomizer logic, or `.esp`.

OBSE64 is not required for this implementation. It remains relevant to the broader Oblivion Remastered modding environment and to Archipelago’s packaged installation, but unrestricted console execution is already available through UE4SS and Unreal's console function. The separate OBSE64 UE4SS loader primarily exists for OBSE and mod-manager configurations and requires disabling UE4SS’s normal proxy loader.

---

## Phase 1: Validate the complete pipe manually

This is the initial plumbing test. It is deliberately disposable and is not the finished setup.

### Install the runtime

From a fresh Steam installation:

1. Launch Oblivion Remastered normally once.
2. Create or load a disposable save.
3. Install the Oblivion-compatible UE4SS package using its normal direct loader.
4. Install the bridge's Lua console adapter beneath:

```text
OblivionRemastered\Binaries\Win64\
    ue4ss\Mods\CompanionBridgeTest\Scripts\console_adapter.lua
```

5. Confirm both appear in the UE4SS log.
6. Create a temporary Lua mod:

```text
ue4ss\Mods\CompanionBridgeTest\
    Scripts\
        main.lua
```

### Reproduce the Archipelago seam

The scratch Lua mod should:

1. Wait until a save has loaded.
2. attach to the player character’s `ReceiveTick`.
3. Look for a fixed `request.json`.
4. Read one console command.
5. Execute it through the player-context Unreal console adapter.
6. Write the returned text to `response.json`.

Use this mailbox:

```text
%USERPROFILE%\Documents\My Games\
    Oblivion Remastered\Saved\CompanionBridge\
```

Use atomic writes through temporary sibling files:

```text
request.json.tmp → request.json
response.json.tmp → response.json
```

### Manual test commands

Test three behaviors:

* A silent mutation, such as adding gold.
* A query that produces console text.
* An intentionally malformed command.

Record the exact output produced by each. This determines which console error strings, if any, can reliably be classified as failures.

### Phase 1 exit condition

A manually created request file causes a visible game change, and the Lua mod writes a response file containing the captured console output.

Nothing beyond this point should depend on Archipelago.

---

## Phase 2: Build the synchronous local web service

Use a small Python FastAPI service bound only to `127.0.0.1`.

It needs one companion-facing endpoint:

```text
POST /v1/commands
```

A single command is represented as a one-element array:

```json
{
  "commands": [
    "player.additem 0000000F 100"
  ]
}
```

A batch uses the same shape:

```json
{
  "commands": [
    "player.placeatme <form-id> 20",
    "tgm"
  ]
}
```

### Request lifecycle

The service should:

1. Accept the HTTP request.
2. Enter one global FIFO.
3. Wait until the filesystem mailbox is free.
4. Write the entire request to `request.json`.
5. Wait for the matching `response.json`.
6. Return the complete result in the same HTTP response.

The web stack may accept multiple HTTP connections, but only one request enters the mailbox at a time. There is no parallel command execution.

The mailbox therefore remains intentionally small:

```text
CompanionBridge\
    request.json
    response.json
```

Each request contains a generated ID so stale responses cannot be confused with new ones.

### Successful response

```json
{
  "status": "completed",
  "results": [
    {
      "command": "player.additem 0000000F 100",
      "status": "executed",
      "console_output": ""
    }
  ]
}
```

`console_output` is always returned as a string. An empty string means Oblivion printed nothing.

### Partial batch failure

```json
{
  "status": "failed",
  "results": [
    {
      "command": "first command",
      "status": "executed",
      "console_output": ""
    },
    {
      "command": "bad command",
      "status": "console_error",
      "console_output": "..."
    },
    {
      "command": "later command",
      "status": "unattempted",
      "console_output": ""
    }
  ]
}
```

The bridge only declares a command failure when it has evidence:

* A Lua or filesystem error.
* The game-side console adapter refuses execution.
* The console returns an error signature validated during Phase 1.

Empty output alone is never failure.

### Unavailable game

If no response arrives before the service’s configured timeout, the HTTP call returns an availability or timeout error. The caller does not supply its own timeout, and there is no separate game-status endpoint.

The service does not start Oblivion and does not manage its launch.

### Phase 2 exit condition

Automated tests can submit single commands and batches against a fake mailbox consumer and receive correctly ordered synchronous responses.

---

## Phase 3: Replace the scratch Lua bridge with the playable mod

Create the permanent UE4SS mod:

```text
ue4ss\Mods\CompanionBridge\
    Scripts\
        main.lua
        json.lua
```

Use a small vendored Lua JSON parser rather than inventing a custom request format.

### Game lifecycle

The mod should:

1. Load without requiring OBSE64 or an `.esp`.
2. Wait for Oblivion to enter a playable save.
3. Register or restore its player tick hook after game fade-in.
4. Leave requests untouched while no valid game-thread execution point exists.
5. Resume processing after menus or loading transitions when execution becomes available again.

This follows the useful portion of Archipelago’s lifecycle while discarding its gameplay-specific machinery.

### Batch execution

When `request.json` appears:

1. Read and validate the request ID and command array.
2. Execute one command at a time on eligible game ticks.
3. Capture the returned console string.
4. Append the result to the in-memory batch response.
5. Continue only after the previous command returns.
6. Stop on the first established failure.
7. Mark all later commands as unattempted.
8. Atomically write the finished `response.json`.
9. Remove the consumed request.

Executing one command per eligible tick keeps the game responsive while still completing ordinary batches quickly.

### Scope boundary

The Lua mod should not:

* Filter console commands.
* Maintain a catalog of approved effects.
* Add automatic readback commands.
* Inspect or expose structured game state.
* Notify the player.
* Start or supervise the web service.
* Attempt to protect the save from destructive commands.

Its job is console transport, execution, and response.

### Phase 3 exit condition

With the real game running, the HTTP endpoint can:

* Add gold.
* Spawn an actor.
* alter a player value.
* Run a query and return its text.
* Execute a mixed batch in order.
* Stop a batch after a detectable malformed command.
* Return empty output for a successful silent mutation.
* Wait through a temporary loading transition.
* Return an error when the game-side mod remains unavailable.

At this point, the integration is playable.

---

## Phase 4: Connect the existing companion and harden the workflow

Expose one tool to the companion:

```text
oblivion_console(commands)
```

The tool accepts an ordered array of raw console-command strings and returns the service response unchanged.

Its description should stay mechanical:

> Execute one or more Oblivion console commands in order. Commands stop after the first detected failure. Console output may be empty.

Do not add a status tool, verification tool, inventory tool, spawn tool, or game-state tool. Those would duplicate the console surface and make the low-latency model choose among unnecessary abstractions.

### Codex-driven testing

Codex should implement and maintain:

* Unit tests for request validation and response serialization.
* FIFO tests for simultaneous HTTP callers.
* Batch ordering and stop-on-failure tests.
* Empty-output tests.
* Timeout and unavailable-game tests.
* Atomic mailbox-write tests.
* A minimal fake mailbox consumer for service testing.
* Lua request parsing and response-generation fixtures.
* A repeatable in-game smoke-test checklist.
* Installation documentation for a fresh Steam copy.

The in-game checklist should cover:

1. One silent mutation.
2. One visible spawned entity.
3. One query with output.
4. One valid multi-command batch.
5. One malformed command in the middle of a batch.
6. One request submitted during loading.
7. One request submitted while the game is closed.
8. Confirmation that no bridge-generated player notification appears.

## Final operating procedure

For ordinary play:

1. Start the local web service manually.
2. Launch Oblivion Remastered normally through Steam.
3. Load a save.
4. Start or connect the existing companion.
5. The companion calls `POST /v1/commands` through its single Oblivion tool.

That is the complete setup. No launcher wrapper, Archipelago client, OBSE64 dependency, command catalog, safety layer, state service, or companion-behavior system is part of the build.
