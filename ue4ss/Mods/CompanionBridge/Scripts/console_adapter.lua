-- Console execution and output capture for the Companion Bridge.
--
-- The execution seam and UConsole layout are adapted from dicene/OblivionMods
-- ConsoleUtils (GPL-3.0). This bridge deliberately does not use that module's
-- marker-command callback protocol: the bridge must never add commands that
-- were not supplied by its caller.

local UEHelpers = require("UEHelpers")

local ConsoleAdapter = {}

local consoleInstance = CreateInvalidObject()
local pendingExecution = nil


PropertyTypes.ArrayProperty.Size = 0x10

RegisterCustomProperty({
    Name = "CompanionBridgeOutputBuffer",
    Type = PropertyTypes.ArrayProperty,
    BelongsToClass = "/Script/Engine.Console",
    OffsetInternal = 0x50,
    ArrayProperty = {
        Type = PropertyTypes.StrProperty,
    },
})

RegisterCustomProperty({
    Name = "CompanionBridgeOutputBufferSize",
    Type = PropertyTypes.IntProperty,
    BelongsToClass = "/Script/Engine.Console",
    OffsetInternal = 0x58,
})


local function validObject(object)
    return object ~= nil and object:IsValid()
end


local function getConsole()
    if not validObject(consoleInstance) then
        consoleInstance = FindFirstOf("Console") or CreateInvalidObject()
    end

    if not validObject(consoleInstance) then
        return nil, "Unreal Console object is not available"
    end

    return consoleInstance
end


local function getExecutionObjects()
    local playerController =
        UEHelpers.GetPlayerController() or CreateInvalidObject()
    if not validObject(playerController) then
        return nil, nil, "Player controller is not available"
    end

    local kismetSystemLibrary =
        StaticFindObject("/Script/Engine.Default__KismetSystemLibrary")
        or CreateInvalidObject()
    if not validObject(kismetSystemLibrary) then
        return nil, nil, "KismetSystemLibrary is not available"
    end

    return playerController, kismetSystemLibrary
end


local function readOutputCount(console)
    local succeeded, value = pcall(function()
        return console.CompanionBridgeOutputBufferSize
    end)
    if not succeeded then
        return nil, tostring(value)
    end
    if type(value) ~= "number" or value < 0 then
        return nil, "Console output buffer returned an invalid size"
    end

    return value
end


local function readOutputEntry(console, zeroBasedIndex)
    local succeeded, value = pcall(function()
        return console.CompanionBridgeOutputBuffer[zeroBasedIndex + 1]
    end)
    if not succeeded then
        return nil, tostring(value)
    end
    if value == nil then
        return nil, "Console output buffer returned a nil entry"
    end
    if type(value) == "string" then
        return value
    end

    local converted, text = pcall(function()
        return value:ToString()
    end)
    if not converted then
        return nil, tostring(text)
    end

    return text
end


local function collectPendingOutput(console)
    local command = pendingExecution.command
    local outputEnd, endError = readOutputCount(console)
    if outputEnd == nil then
        pendingExecution = nil
        return {
            state = "failed",
            error = "Could not read console output after dispatch: "
                .. endError,
        }
    end
    if outputEnd < pendingExecution.outputStart then
        pendingExecution = nil
        return {
            state = "failed",
            error = "Console output buffer changed unexpectedly during dispatch",
        }
    end

    local lines = {}
    for index = pendingExecution.outputStart, outputEnd - 1 do
        local line, lineError = readOutputEntry(console, index)
        if line == nil then
            pendingExecution = nil
            return {
                state = "failed",
                error = string.format(
                    "Could not read console output entry %d: %s",
                    index,
                    lineError
                ),
            }
        end
        if line ~= "" then
            table.insert(lines, line)
        end
    end

    pendingExecution = nil
    return {
        state = "executed",
        command = command,
        output = table.concat(lines, "\n"),
    }
end


function ConsoleAdapter.execute(command)
    local console, consoleError = getConsole()
    if not console then
        return {
            state = "unavailable",
            error = consoleError,
        }
    end

    -- Console output can be appended after ExecuteConsoleCommand unwinds back
    -- into the player tick. Collect on the next tick rather than assuming the
    -- output buffer has already settled.
    if pendingExecution ~= nil then
        if pendingExecution.command ~= command then
            local pendingCommand = pendingExecution.command
            pendingExecution = nil
            return {
                state = "failed",
                error = string.format(
                    "Pending command changed from %q to %q",
                    pendingCommand,
                    command
                ),
            }
        end

        return collectPendingOutput(console)
    end

    local playerController, kismetSystemLibrary, executionError =
        getExecutionObjects()
    if not playerController then
        return {
            state = "unavailable",
            error = executionError,
        }
    end

    local outputStart, startError = readOutputCount(console)
    if outputStart == nil then
        return {
            state = "failed",
            error = "Could not read console output before dispatch: "
                .. startError,
        }
    end

    local dispatched, dispatchError = pcall(function()
        kismetSystemLibrary:ExecuteConsoleCommand(
            playerController.player,
            command,
            playerController,
            false
        )
    end)
    if not dispatched then
        return {
            state = "failed",
            error = "Kismet console dispatch failed: "
                .. tostring(dispatchError),
        }
    end

    pendingExecution = {
        command = command,
        outputStart = outputStart,
    }

    return {
        state = "pending",
        dispatched = true,
    }
end


return ConsoleAdapter
