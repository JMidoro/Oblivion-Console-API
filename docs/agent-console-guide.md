# Agent console guide

This guide accompanies `docs/openapi.json`. It explains the bridge mechanically;
it does not prescribe the companion's character, goals, or willingness to help
the player.

## What the tool does

`oblivion_console(commands)` sends an ordered array of raw Oblivion console
commands. The HTTP call remains open until the entire batch finishes or the
service times out.

The bridge:

- Does not filter or approve commands.
- Does not add verification or readback commands.
- Does not protect the save or prevent softlocks.
- Does not distinguish a closed game from loading or a broken game-side mod.
- Does not expose structured game state.

## Reading results

- `executed`: dispatch returned on the game thread. This does **not** prove the
  intended gameplay effect occurred.
- `console_error`: the console produced a validated error signature.
- `bridge_error`: Lua, console dispatch, or mailbox processing established an
  execution failure.
- `unattempted`: an earlier command failed, so this command was not dispatched.
- Empty `console_output` is normal for many successful mutations.
- HTTP `504` means no complete game-side response arrived before the deadline.
  Use visible screen context to decide whether the game is loading, closed, or
  otherwise unavailable.

Console output is evidence, not a universal success oracle. A command can work
while printing warnings, and it can dispatch without producing its intended
gameplay effect.

## Command-selection heuristic

1. Use Oblivion or Oblivion Remastered command syntax, not syntax assumed from
   another Bethesda game.
2. Use separate array entries when order matters. A later entry runs only after
   the previous entry completes.
3. Batch commands that form one ordered intervention. Use separate calls when
   later decisions depend on observing the screen or interpreting earlier
   output.
4. Use a console query when textual confirmation is genuinely useful. The
   bridge itself will not add one automatically.
5. For commands that require IDs, distinguish base IDs from placed reference
   IDs. `placeatme` and `additem` normally consume base IDs; target-specific
   commands may require a reference.
6. Treat `executed` plus empty output as successful transport, then use console
   output or the visible game when the gameplay effect matters.
7. On `console_error` or `bridge_error`, inspect the returned text and revise
   the command. On `504`, wait or retry according to visible game state.

## Validated observations

These are examples that establish bridge semantics, not an action catalog:

- `player.additem 0000000F 100` mutated inventory and returned empty output.
- `player.getav health` returned a textual actor value.
- `player.placeatme 0003154F 1` spawned one deer while also printing harmless
  `is not an Interior` warnings.
- `modpca luck 1` changed Luck; `player.modav luck 1` dispatched but did not
  change the displayed value.
- An unknown command produced `Script command "..." not found.`, which the
  bridge classifies as `console_error` and uses to stop the batch.

Do not infer that untested commands are unsupported. Command availability and
behavior belong to Oblivion; the bridge transports raw commands.
