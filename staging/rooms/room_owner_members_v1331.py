from pathlib import Path

# MELEHAT 1.3.31: room-specific rosters, guarded owner removal, owner import.
# No modifications to microphone, LiveKit transport, foreground PTT or signing.
root = Path("app/src/main/java/com/saomi/telsiz")
state = root / "voice/LiveChannelUiState.kt"
s = state.read_text(encoding="utf-8")
anchor = '    private val _roomName = MutableStateFlow("ORTAK KANAL")'
assert s.count(anchor) == 1, "Room name state missing"
s = s.replace(anchor, '''    private val _roomId = MutableStateFlow("ortak")
    val roomId: StateFlow<String> = _roomId
    fun roomId(value: String) { _roomId.value = value }

''' + anchor, 1)
state.write_text(s, encoding="utf-8")

live = root / "voice/LiveKitPttClient.kt"
s = live.read_text(encoding="utf-8")
anchor = '            connectedChannelId = channel.id\n            connected = true'
assert s.count(anchor) == 1, "Active LiveKit room anchor missing"
s = s.replace(anchor, '            connectedChannelId = channel.id\n            LiveChannelUiState.roomId(channel.id)\n            connected = true', 1)
live.write_text(s, encoding="utf-8")

ui = root / "ui/AppRoot.kt"
s = ui.read_text(encoding="utf-8")
def replace_once(a, b):
    global s
    count = s.count(a)
    if count != 1: raise SystemExit("MELEHAT 1331 missing/ambiguous anchor (" + str(count) + "): " + a[:95])
    s = s.replace(a, b, 1)

replace_once('    val liveRoomName by LiveChannelUiState.roomName.collectAsState()',
'''    val liveRoomName by LiveChannelUiState.roomName.collectAsState()
    val liveRoomId by LiveChannelUiState.roomId.collectAsState()''')

replace_once('    var roomCommand by remember { mutableStateOf<Triple<String, String, Boolean>?>(null) }',
'''    var roomCommand by remember { mutableStateOf<Triple<String, String, Boolean>?>(null) }
    var deleteTarget by remember { mutableStateOf<RoomListing?>(null) }
    var selectedRoomMembers by remember { mutableStateOf<Set<String>>(emptySet()) }
    var roomRosterLoaded by remember { mutableStateOf(false) }
    val selectedRoomId = if (radioOn && liveStatus == "LIVE") liveRoomId
        else localStore.loadActiveChannel().id
    val selectedRoomTitle = if (radioOn && liveStatus == "LIVE") liveRoomName
        else localStore.loadActiveChannel().name
    val commonRoomSelected = selectedRoomId == "ortak"
    val visibleMemberIds = if (commonRoomSelected) liveParticipants.map { it.identity }.toSet()
        else selectedRoomMembers
    val selectedMemberCount = if (commonRoomSelected) {
        if (radioOn && liveStatus == "LIVE") liveParticipants.size else 0
    } else selectedRoomMembers.size

    LaunchedEffect(session?.userId, selectedRoomId, roomRefresh) {
        selectedRoomMembers = emptySet()
        roomRosterLoaded = commonRoomSelected
        val active = session ?: return@LaunchedEffect
        if (commonRoomSelected) return@LaunchedEffect
        while (true) {
            roomApi.listRoomMemberIds(active, selectedRoomId)
                .onSuccess { selectedRoomMembers = it; roomRosterLoaded = true }
                .onFailure { roomRosterLoaded = false }
            kotlinx.coroutines.delay(6000)
        }
    }''')

replace_once('''            "review" -> roomApi.reviewRequest(active, cmd.second, cmd.third)''',
'''            "review" -> roomApi.reviewRequest(active, cmd.second, cmd.third)
            "delete" -> roomApi.deleteRoom(active, cmd.second)
            "import" -> roomApi.importLegacyMembers(active, cmd.second)''')

replace_once('''                    "join" -> "Katılma isteğiniz kanal sahibine gönderildi."
                    else -> if (cmd.third) "Üye kabul edildi." else "Katılma isteği reddedildi."''',
'''                    "join" -> "Katılma isteğiniz kanal sahibine gönderildi."
                    "delete" -> {
                        if (selectedRoomId == cmd.second)
                            roomSelection = "ortak" to "ORTAK KANAL"
                        "Kanal ve üyelikleri silindi."
                    }
                    "import" -> it
                    else -> if (cmd.third) "Üye kabul edildi." else "Katılma isteği reddedildi."''')

replace_once('''                                                ) { Text("KANALA GİR") }
                                            }
                                            item.member -> {''',
'''                                                ) { Text("KANALA GİR") }
                                                Row {
                                                    TextButton(
                                                        enabled = !roomBusy,
                                                        onClick = { deleteTarget = item }
                                                    ) { Text("KANALI SİL", color = Color(0xFFB00020)) }
                                                    if (item.roomId == "kanal-74170df4-f887-4319-a111-f0268598844a") {
                                                        TextButton(
                                                            enabled = !roomBusy,
                                                            onClick = {
                                                                roomCommand = Triple("import", item.roomId, false)
                                                            }
                                                        ) { Text("4 ÜYEYİ AKTAR") }
                                                    }
                                                }
                                            }
                                            item.member -> {''')

anchor = '            if (showCreateRoomPreview) {'
replace_once(anchor, '''            if (deleteTarget != null) {
                val target = deleteTarget!!
                AlertDialog(
                    onDismissRequest = { deleteTarget = null },
                    title = { Text("Kanal silinsin mi?") },
                    text = {
                        Text(target.title + " kanalı ve bu kanala ait üyelikler silinecek. Bu işlem geri alınamaz.")
                    },
                    confirmButton = {
                        TextButton(enabled = !roomBusy, onClick = {
                            roomCommand = Triple("delete", target.roomId, false)
                            deleteTarget = null
                        }) { Text("EVET, KANALI SİL", color = Color(0xFFB00020)) }
                    },
                    dismissButton = {
                        TextButton(onClick = { deleteTarget = null }) { Text("VAZGEÇ") }
                    }
                )
            }
''' + anchor)

# The old counter was global profile count. Now count active common-room
# LiveKit participants, or the approved membership of the chosen private room.
if '${directory.size}' not in s and 'directory.size.toString()' not in s:
    raise SystemExit("Original global roster counter missing")
s = s.replace('${directory.size}', '${selectedMemberCount}')
s = s.replace('directory.size.toString()', 'selectedMemberCount.toString()')

dialog = s.find('            if (showMembers) {')
if dialog < 0: raise SystemExit("Member dialog missing")
before, after = s[:dialog], s[dialog:]
if 'Text("Kanal 1 Üyeleri")' not in after or 'directory.forEach { member ->' not in after:
    raise SystemExit("Member dialog structure changed")
after = after.replace('Text("Kanal 1 Üyeleri")',
                      'Text(selectedRoomTitle + " • Üyeler")', 1)
after = after.replace('directory.forEach { member ->',
                      'directory.filter { it.userId in visibleMemberIds }.forEach { member ->', 1)
s = before + after
ui.write_text(s, encoding="utf-8")
print("MELEHAT_1331_OWNER_DELETE_AND_ROOM_MEMBERS_OK")
