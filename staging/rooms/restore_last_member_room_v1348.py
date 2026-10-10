from pathlib import Path

# MELEHAT v1.3.48: first-time members enter ORTAK KANAL.
# Returning members return to THEIR LAST successfully joined channel.
# No changes to LiveKit media, PTT floor, routing security or channel rights.
root=Path("app/src/main/java/com/saomi/telsiz")
src=Path("../staging/rooms/LastRoomPreference.kt")
target=root/"rooms/LastRoomPreference.kt"
assert src.exists() and target.parent.exists()
target.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

ui=root/"ui/AppRoot.kt"
s=ui.read_text(encoding="utf-8")
start=s.index("    // First authenticated view always opens in the shared lobby, not KANAL 1.")
end=s.index("    LaunchedEffect(roomSelection) {", start)
block='''    // Each member owns their own saved room. A new account starts in ORTAK
    // KANAL; existing accounts resume the room they last selected.
    // Never override a user's later manual selection during this login.
    LaunchedEffect(session?.userId, profile.isComplete) {
        val signedInUser = session?.userId
        if (signedInUser == null) {
            commonLandingHandledUser = null
            return@LaunchedEffect
        }
        if (!profile.isComplete || commonLandingHandledUser == signedInUser)
            return@LaunchedEffect

        commonLandingHandledUser = signedInUser
        val lastRoom = com.saomi.telsiz.rooms.LastRoomPreference(roomsContext)
            .loadOrInitialize(signedInUser, localStore.loadActiveChannel())
        val current = localStore.loadActiveChannel()
        val wrongConnection =
            radioOn && liveStatus == "LIVE" && liveRoomId != lastRoom.id
        if (radioOn) {
            if (current.id != lastRoom.id ||
                current.name != lastRoom.name || wrongConnection) {
                // Let the radio service switch rooms and release its floor
                // before replacing LocalStore's currently connected room.
                roomSelection = lastRoom.id to lastRoom.name
            }
        } else {
            // Preserve the user-chosen OFF state; don't turn the radio on
            // just because we restored a saved room selection.
            if (current.id != lastRoom.id || current.name != lastRoom.name) {
                localStore.saveActiveChannel(lastRoom)
                activeChannel = lastRoom
            }
        }
    }

'''
s=s[:start]+block+s[end:]
# The room-selection effect already serializes room switch through the
# working radio service. If radio is OFF, save explicit selection immediately.
anchor='''            localStore.saveActiveChannel(selected)
            activeChannel = selected'''
if s.count(anchor)!=1:raise SystemExit("MELEHAT1348: OFF radio room-change anchor mismatched")
s=s.replace(anchor,'''            localStore.saveActiveChannel(selected)
            com.saomi.telsiz.rooms.LastRoomPreference(roomsContext)
                .remember(session?.userId.orEmpty(), selected)
            activeChannel = selected''',1)

# Initialize the right account's room before the foreground service begins
# to connect. A new login cannot inherit another member's private room.
main=root/"MainActivity.kt"
m=main.read_text(encoding="utf-8")
anchor='''        localStore.migrateDefaultRoomToCommonOnce()
        if (localStore.isRadioEnabled()) {'''
if m.count(anchor)!=1:raise SystemExit("MELEHAT1348: MainActivity launch anchor changed")
m=m.replace(anchor,'''        localStore.migrateDefaultRoomToCommonOnce()
        com.saomi.telsiz.data.SessionStore(this).load()?.userId?.let { currentUser ->
            val preferred = com.saomi.telsiz.rooms.LastRoomPreference(this)
                .loadOrInitialize(currentUser, localStore.loadActiveChannel())
            localStore.saveActiveChannel(preferred)
        }
        if (localStore.isRadioEnabled()) {''',1)
main.write_text(m,encoding="utf-8")

service=root/"service/PttForegroundService.kt"
p=service.read_text(encoding="utf-8")
# When Android recreates the FGS with null intent, use the current logged-in
# member's stored preference (never a previously logged-in member's room).
anchor='''            ACTION_START -> {
'''
if p.count(anchor)!=1:raise SystemExit("MELEHAT1348: service start action mismatch")
p=p.replace(anchor,'''            ACTION_START -> {
                sessions.load()?.userId?.let { currentUser ->
                    val preferred = com.saomi.telsiz.rooms.LastRoomPreference(this)
                        .loadOrInitialize(currentUser, store.loadActiveChannel())
                    // This applies on (re)start, not in the middle of PTT.
                    if (!started) store.saveActiveChannel(preferred)
                }
''',1)
# Only a successfully connected, authorized private-room change may become
# the member's last room. A failed move keeps their previously saved room.
anchor='''                                    store.saveActiveChannel(target)
                                    updateNotification("$roomName • Bas-konuş hazır")'''
if p.count(anchor)!=1:raise SystemExit("MELEHAT1348: service confirmed switch missing")
p=p.replace(anchor,'''                                    store.saveActiveChannel(target)
                                    sessions.load()?.userId?.let { currentUser ->
                                        com.saomi.telsiz.rooms.LastRoomPreference(this@PttForegroundService)
                                            .remember(currentUser, target)
                                    }
                                    updateNotification("$roomName • Bas-konuş hazır")''',1)
service.write_text(p, encoding="utf-8")
ui.write_text(s,encoding="utf-8")

for fragment in (
    "LastRoomPreference(roomsContext)", "loadOrInitialize(signedInUser",
    "commonLandingHandledUser == signedInUser", "roomSelection = lastRoom.id to lastRoom.name",
    "pointerInput(radioOn)", "KANAL AÇ  +", "GÖRÜNTÜLÜ ARA", "activeRoomByUser"
):
    assert fragment in s, "Lost protected UI requirement: " + fragment
assert "roomSelection = lobby.id to lobby.name" not in s
assert 'LastRoomPreference(this@PttForegroundService)' in p
assert 'ACTION_SWITCH_ROOM' in p and 'ptt.connect(store.loadProfile(), target)' in p
assert 'roomSwitching || !ptt.isConnectedTo(channel.id)' in p
assert 'VideoCallMonitor.start(applicationContext)' in p
print("MELEHAT_1348_ACCOUNT_OWNED_LAST_ROOM_RESTORATION_OK")
