# Phase 1 results

Complete this record against the installed game before defining any console
error signatures.

| Behavior | Command | Visible result | Exact `console_output` | Classification |
| --- | --- | --- | --- | --- |
| Silent mutation | `player.additem 0000000F 100` | Gold increased by 100 without a crash | Empty string | Executed |
| Text query | `player.getav health` | Returned the current health value | `GetActorValue: Health >> 222.00` | Executed |
| Text query | `getstage mq01` | Returned the current quest stage | `GetStage >> 150.00` | Executed |
| Malformed command | `definitely_not_a_real_command` | No gameplay change | `Script 'SysWindowCompileAndRun', line 1:` + newline + `Script command "definitely_not_a_real_command" not found.` | Stable console error |

## Environment

- Oblivion Remastered Steam build: `19115871`
- UE4SS: `3.0.1-447`
- ConsoleUtils: `1.1`
- Test date: `2026-07-27`

The native ConsoleUtils `1.1` mod was disabled after diagnosis. The successful
results use the bridge's player-context Kismet adapter and Unreal console-buffer
capture.

## First execution failure

Both `player.additem 0000000F 100` requests reached the game-side
`ReceiveTick` callback. The process then crashed inside ConsoleUtils
`main.dll` while its Lua binding was executing the native console command.
`response.json` was never written in either attempt.

The crash stack included:

```text
main
UE4SS!RC::LuaMadeSimple::process_lua_function()
UE4SS!luaB_pcall()
UE4SS!RC::script_hook()
UE4SS!RC::Unreal::HookedProcessLocalScriptFunction()
```

The exact triggering requests are preserved in:

- `artifacts/phase1-crash-request.json`
- `artifacts/phase1-mutation-crash-request.json`

The second attempt used the Nexus ConsoleUtils package with its sample hook
disabled. The native DLL was byte-for-byte identical to the GitHub release,
and the UE4SS log showed only the bridge's one `ReceiveTick` hook. This rules
out a duplicate-hook cause.

## Execution-adapter pivot

The old ConsoleUtils `1.1` native binding passes zero-valued execution context
arguments to Oblivion's internal console dispatcher. Query commands happen to
work through that seam; the tested mutating command does not.

The scratch bridge now uses Unreal's `KismetSystemLibrary.ExecuteConsoleCommand`
with the live player and controller objects. It captures only the entries added
to Unreal's console output buffer during that synchronous call. No marker,
readback, or verification commands are inserted.

The replacement passed the silent mutation, text query, and malformed-command
tests. Phase 1 is complete.
