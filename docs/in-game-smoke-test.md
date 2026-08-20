# In-game smoke test

Run these checks against a disposable save. Announce the exact expected visible
effect before submitting any mutating command.

Multiple observable changes may share a conversation turn when every final
state remains independently verifiable. Do not mutate the same stateful value
twice in one turn: doing so can hide an intermediate result from a user who was
not watching live.

## Completed on 2026-07-27

| Check | Commands | Result |
| --- | --- | --- |
| Silent mutation | `player.additem 0000000F 100` | Gold increased by exactly 100; empty console output |
| Query output | `player.getav health` | `GetActorValue: Health >> 222.00` |
| Malformed command | `definitely_not_a_real_command` | Stable `Script command ... not found.` output |
| Valid HTTP batch | `player.additem 0000000F 1`, `player.getav health` | Completed in order; gold increased by 1; health output captured |
| Stop on error | health query, malformed command, add 1 gold | Batch failed at command 2; command 3 was `unattempted` and was absent from the UE4SS dispatch log |
| Spawn entity | `player.placeatme 0003154F 1` | Exactly one male deer appeared; command returned two harmless `is not an Interior` lines |
| Alter player value | `modpca luck 1`, then query Luck | Luck changed once from 50 to 51; final query returned `GetActorValue: Luck >> 51.00` |
| Loading/resume | Submit health query at main menu, then load a save | Mod logged `Waiting for a playable game state`, held the request for about 39 seconds, then returned health `222.00` after gameplay resumed |
| Closed-game timeout | Submit health query with game process absent and a 5-second deadline | HTTP `504` returned `{"status":"timed_out","results":[]}`; no mailbox or listener artifacts remained |
| No bridge UI | Observe live tests and inspect Lua source | No bridge-generated player notification appeared; the mod contains no notification call |
| Cleanup | Inspect mailbox and temporary HTTP listener | No request, response, or temporary listener remained |

## Finish line

All live transport and lifecycle checks are complete. Do not sample additional
command families: that would test Oblivion's command catalog rather than the
bridge.

For a bounded live request, use:

```powershell
.\.venv\Scripts\python.exe scripts\live_http_request.py `
  "player.getav health" `
  --timeout 15
```

This helper starts a temporary loopback HTTP server, submits one real request,
prints the complete result, and stops the server.
