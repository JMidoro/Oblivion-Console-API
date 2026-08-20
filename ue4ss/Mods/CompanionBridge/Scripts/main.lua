local json = require("json")
local consoleAdapter = require("console_adapter")

local protocolVersion = 1
local playerTickFunction =
    "Function /Game/Dev/PlayerBlueprints/BP_OblivionPlayerCharacter.BP_OblivionPlayerCharacter_C:ReceiveTick"
local playerClass = "BP_OblivionPlayerCharacter_C"
local playerObjectNotification = "/Script/Altar.VOblivionPlayerCharacter"

local userProfile = os.getenv("USERPROFILE")
if not userProfile then
    error("CompanionBridge could not resolve USERPROFILE")
end

local mailboxDirectory =
    userProfile
    .. "\\Documents\\My Games\\Oblivion Remastered\\Saved\\CompanionBridge\\"
local requestPath = mailboxDirectory .. "request.json"
local responsePath = mailboxDirectory .. "response.json"
local responseTemporaryPath = mailboxDirectory .. "response.json.tmp"

local hookRegistered = false
local activeBatch = nil
local lastLogMessage = nil
local freezeInMenuSubsystem = CreateInvalidObject()
local fadeWidget = CreateInvalidObject()


local function logOnce(message)
    if message == lastLogMessage then
        return
    end

    lastLogMessage = message
    print(string.format("[CompanionBridge] %s\n", message))
end


local function validObject(object)
    return object ~= nil and object:IsValid()
end


local function findByName(className, namePattern)
    local objects = FindAllOf(className) or {}
    for index = 1, #objects do
        local object = objects[index]
        if object:GetFullName():match(namePattern) then
            return object
        end
    end

    return CreateInvalidObject()
end


local function refreshLifecycleObjects()
    if not validObject(freezeInMenuSubsystem) then
        freezeInMenuSubsystem =
            findByName("VFreezeInMenuSubsystem", "Transient")
    end
    if not validObject(fadeWidget) then
        fadeWidget = findByName("WBP_AltarHud_Fade_C", "Persistent")
    end
end


local function executionIsAvailable()
    refreshLifecycleObjects()
    if not validObject(freezeInMenuSubsystem)
        or not validObject(fadeWidget) then
        return false
    end

    local readFade, fadeIsVisible = pcall(function()
        return fadeWidget:IsVisible()
    end)
    if not readFade or fadeIsVisible then
        return false
    end

    local readFreeze, gameIsFrozen = pcall(function()
        return freezeInMenuSubsystem:IsFreezing()
    end)
    return readFreeze and not gameIsFrozen
end


local function fileExists(path)
    local handle = io.open(path, "rb")
    if not handle then
        return false
    end

    handle:close()
    return true
end


local function readFile(path)
    local handle, openError = io.open(path, "rb")
    if not handle then
        error(string.format("Could not open %s: %s", path, openError))
    end

    local contents = handle:read("*a")
    handle:close()
    return contents
end


local function writeFileAtomically(path, temporaryPath, contents)
    local handle, openError = io.open(temporaryPath, "wb")
    if not handle then
        error(string.format("Could not open %s: %s", temporaryPath, openError))
    end

    local writeSucceeded, writeError = handle:write(contents)
    if not writeSucceeded then
        handle:close()
        error(string.format("Could not write %s: %s", temporaryPath, writeError))
    end

    handle:flush()
    handle:close()

    os.remove(path)
    local renamed, renameError = os.rename(temporaryPath, path)
    if not renamed then
        error(
            string.format(
                "Could not rename %s to %s: %s",
                temporaryPath,
                path,
                renameError
            )
        )
    end
end


local function validRequest(request)
    if type(request) ~= "table"
        or request.protocol_version ~= protocolVersion
        or type(request.request_id) ~= "string"
        or request.request_id == ""
        or type(request.commands) ~= "table"
        or #request.commands == 0 then
        return false
    end

    for index = 1, #request.commands do
        if type(request.commands[index]) ~= "string" then
            return false
        end
    end

    return true
end


local function decodeRequest()
    local decoded, request = pcall(function()
        return json.decode(readFile(requestPath))
    end)
    if not decoded then
        return nil, "Could not decode request.json: " .. tostring(request)
    end
    if not validRequest(request) then
        return nil, "Ignoring an invalid request.json"
    end

    return request
end


local function requestIsStillOwned(requestId)
    if not fileExists(requestPath) then
        return false
    end

    local request = decodeRequest()
    return request ~= nil and request.request_id == requestId
end


local function addResult(command, status, output)
    table.insert(activeBatch.results, {
        command = command,
        status = status,
        console_output = output,
    })
end


local function markRemainingUnattempted()
    for index = activeBatch.nextCommand + 1, #activeBatch.commands do
        addResult(activeBatch.commands[index], "unattempted", "")
    end
end


local function queueFinalResponse(status)
    activeBatch.finalResponse = {
        protocol_version = protocolVersion,
        request_id = activeBatch.requestId,
        status = status,
        results = activeBatch.results,
    }
end


local function commitFinalResponse()
    if fileExists(responsePath) then
        return
    end
    if not requestIsStillOwned(activeBatch.requestId) then
        activeBatch = nil
        return
    end

    local encoded, responseJson = pcall(json.encode, activeBatch.finalResponse)
    if not encoded then
        logOnce("Could not encode response.json: " .. tostring(responseJson))
        return
    end

    local written, writeError = pcall(
        writeFileAtomically,
        responsePath,
        responseTemporaryPath,
        responseJson
    )
    if not written then
        logOnce("Could not write response.json: " .. tostring(writeError))
        return
    end

    if requestIsStillOwned(activeBatch.requestId) then
        os.remove(requestPath)
    end

    print(string.format(
        "[CompanionBridge] Completed batch %s with status %s\n",
        activeBatch.requestId,
        activeBatch.finalResponse.status
    ))
    activeBatch = nil
    lastLogMessage = nil
end


local function isKnownConsoleError(output)
    return output:find("Script command \"", 1, true) ~= nil
        and output:find("\" not found.", 1, true) ~= nil
end


local function beginBatch()
    if fileExists(responsePath) or not fileExists(requestPath) then
        return
    end

    local request, requestError = decodeRequest()
    if not request then
        logOnce(requestError)
        return
    end

    activeBatch = {
        requestId = request.request_id,
        commands = request.commands,
        nextCommand = 1,
        results = {},
        commandDispatched = false,
        finalResponse = nil,
    }
    lastLogMessage = nil
    print(string.format(
        "[CompanionBridge] Started batch %s with %d command(s)\n",
        activeBatch.requestId,
        #activeBatch.commands
    ))
end


local function processActiveBatch()
    if activeBatch.finalResponse ~= nil then
        commitFinalResponse()
        return
    end
    if not activeBatch.commandDispatched
        and not requestIsStillOwned(activeBatch.requestId) then
        activeBatch = nil
        return
    end

    local command = activeBatch.commands[activeBatch.nextCommand]
    local execution = consoleAdapter.execute(command)

    if execution.state == "unavailable" then
        logOnce("Waiting to dispatch: " .. execution.error)
        return
    end
    if execution.state == "pending" then
        activeBatch.commandDispatched = true
        if execution.dispatched then
            print(string.format(
                "[CompanionBridge] Dispatched command %d/%d: %s\n",
                activeBatch.nextCommand,
                #activeBatch.commands,
                command
            ))
        end
        return
    end

    activeBatch.commandDispatched = false
    lastLogMessage = nil

    if execution.state == "failed" then
        addResult(command, "bridge_error", execution.error)
        markRemainingUnattempted()
        queueFinalResponse("failed")
        return
    end

    if isKnownConsoleError(execution.output) then
        addResult(command, "console_error", execution.output)
        markRemainingUnattempted()
        queueFinalResponse("failed")
        return
    end

    addResult(command, "executed", execution.output)
    if activeBatch.nextCommand == #activeBatch.commands then
        queueFinalResponse("completed")
        return
    end

    activeBatch.nextCommand = activeBatch.nextCommand + 1
end


local function tick()
    -- The player ReceiveTick hook is the game-thread execution seam. If a
    -- future UE4SS build invokes it elsewhere, leave the request untouched.
    if GetCurrentThread and GetGameThread
        and GetCurrentThread() ~= GetGameThread() then
        return
    end

    if not executionIsAvailable() then
        if activeBatch ~= nil or fileExists(requestPath) then
            logOnce("Waiting for a playable game state")
        end
        return
    end

    if activeBatch == nil then
        beginBatch()
    end
    if activeBatch ~= nil then
        processActiveBatch()
    end
end


local function registerPlayerTickHook()
    if hookRegistered then
        return
    end

    RegisterHook(playerTickFunction, function(_player)
        tick()
    end)
    hookRegistered = true
    print("[CompanionBridge] Player ReceiveTick hook registered\n")
end


local player = FindFirstOf(playerClass) or CreateInvalidObject()

freezeInMenuSubsystem =
    findByName("VFreezeInMenuSubsystem", "Transient")
fadeWidget = findByName("WBP_AltarHud_Fade_C", "Persistent")

NotifyOnNewObject(
    "/Script/Altar.VFreezeInMenuSubsystem",
    function(subsystem)
        freezeInMenuSubsystem = subsystem
    end
)
NotifyOnNewObject("/Script/Altar.VFadeWidget", function(fade)
    fadeWidget = fade
end)

if player:IsValid() then
    registerPlayerTickHook()
else
    NotifyOnNewObject(playerObjectNotification, function()
        registerPlayerTickHook()
    end)
end
