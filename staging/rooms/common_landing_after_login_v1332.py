from pathlib import Path

# v1.3.32 — Common lobby is the entry point after sign-in and signup.
# Only AppRoot routing/default selection is modified. LiveKit, PTT, memberships,
# owner permissions, session security, signing and updater stay unchanged.
ui = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = ui.read_text(encoding="utf-8")

anchor = '''    var roomSelection by remember { mutableStateOf<Pair<String, String>?>(null) }

    LaunchedEffect(roomSelection) {'''
if s.count(anchor) != 1:
    raise SystemExit("Common landing: room selection anchor missing or duplicated")

replacement = '''    var roomSelection by remember { mutableStateOf<Pair<String, String>?>(null) }
    var commonLandingHandledUser by remember { mutableStateOf<String?>(null) }

    // First authenticated view always opens in the shared lobby, not KANAL 1.
    // A subsequent manual selection of a private channel is never overridden
    // during the same signed-in session.
    LaunchedEffect(session?.userId, profile.isComplete) {
        val signedInUser = session?.userId
        if (signedInUser == null) {
            commonLandingHandledUser = null
            return@LaunchedEffect
        }
        if (!profile.isComplete || commonLandingHandledUser == signedInUser)
            return@LaunchedEffect

        commonLandingHandledUser = signedInUser
        val lobby = ChannelInfo("ortak", "ORTAK KANAL")
        val rememberedRoom = localStore.loadActiveChannel()
        val liveInAnotherRoom = radioOn && liveStatus == "LIVE" && liveRoomId != lobby.id
        if (rememberedRoom.id != lobby.id || liveInAnotherRoom) {
            if (radioOn) {
                // Use the existing serialized room switch; release the old
                // microphone floor before LiveKit connects to ORTAK KANAL.
                roomSelection = lobby.id to lobby.name
            } else {
                // Do not turn a manually disabled radio on during login.
                localStore.saveActiveChannel(lobby)
                activeChannel = lobby
            }
        } else {
            // Upgrade a legacy stored display name without changing room identity.
            if (rememberedRoom.name != lobby.name) {
                localStore.saveActiveChannel(lobby)
                activeChannel = lobby
            }
        }
    }

    LaunchedEffect(roomSelection) {'''

s = s.replace(anchor, replacement, 1)
assert 'roomSelection = lobby.id to lobby.name' in s
assert 'profile.isComplete' in s
assert 'commonLandingHandledUser == signedInUser' in s
assert 'ACTION_SWITCH_ROOM' in s
assert 'KANALI SİL' in s
assert '4 ÜYEYİ AKTAR' in s
ui.write_text(s, encoding="utf-8")
print("MELEHAT_1332_COMMON_LANDING_AFTER_LOGIN_OK")
