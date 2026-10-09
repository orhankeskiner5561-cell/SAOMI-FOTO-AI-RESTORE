from pathlib import Path

# v1.3.37: owner request-count + requester approval/denial count,
# automatic list refresh, no redundant footer "KANAL AÇ" / "YENİLE".
# Existing radio/PTT, LiveKit, video calls and signing stay untouched.
p = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = p.read_text(encoding="utf-8")

def replace_once(old, new):
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit("MELEHAT 1337 expected 1 anchor, got "+
                         str(n)+": "+old[:110])
    s=s.replace(old,new,1)

# One source of room listings for background badges and foreground dialog.
# Room-creation, review and request actions still increment roomRefresh;
# unlike a manual YENİLE tap, those changes trigger an immediate fetch.
old_effect_start = '    LaunchedEffect(showChannelRoomsPreview, roomRefresh, session?.userId) {'
old_effect_end = '    LaunchedEffect(roomCommand) {'
if s.count(old_effect_start) != 1 or s.count(old_effect_end) != 1:
    raise SystemExit("Room polling anchors changed")
start=s.index(old_effect_start)
end=s.index(old_effect_end,start)
s=s[:start]+s[end:]

replace_once(
'''    LaunchedEffect(session?.userId) {
        val currentSession = session
        if (currentSession == null) {
            roomListings = emptyList()
            roomRequests = emptyList()
            return@LaunchedEffect
        }
        while (true) {
            roomApi.listRooms(currentSession).onSuccess { roomListings = it }
            roomApi.listRequests(currentSession).onSuccess { roomRequests = it }
            kotlinx.coroutines.delay(5000)
        }
    }''',
'''    LaunchedEffect(session?.userId, roomRefresh) {
        val currentSession = session
        if (currentSession == null) {
            roomListings = emptyList()
            roomRequests = emptyList()
            return@LaunchedEffect
        }
        while (true) {
            roomApi.listRooms(currentSession).onSuccess { roomListings = it }
            roomApi.listRequests(currentSession).onSuccess { roomRequests = it }
            kotlinx.coroutines.delay(5000)
        }
    }''')

replace_once(
'''    val allPendingRequests = pendingByRoom.values.sum()''',
'''    // Results are only counted for the requesting user and remain unread
    // until the user opens AND then closes their Kanallar window.
    val unreadJoinDecisions = roomRequests.filter {
        it.requesterId == session?.userId &&
        it.status in listOf("approved", "rejected") &&
        it.resultSeenAt == null
    }
    val unreadDecisionsByRoom = unreadJoinDecisions
        .groupingBy { it.roomId }.eachCount()
    val allPendingRequests = pendingByRoom.values.sum() +
        unreadJoinDecisions.size''')

replace_once(
'''                                            val pendingForThisRoom = pendingByRoom[item.roomId] ?: 0''',
'''                                            val pendingForThisRoom =
                                                (pendingByRoom[item.roomId] ?: 0) +
                                                (unreadDecisionsByRoom[item.roomId] ?: 0)''')

replace_once(
'''                                        val owner = item.ownerId == session?.userId''',
'''                                        // Most recent request from ME, shown directly beneath
                                        // the relevant channel (never a generic footer message).
                                        val myLatestJoinRequest = roomRequests.firstOrNull {
                                            it.requesterId == session?.userId &&
                                            it.roomId == item.roomId
                                        }
                                        if (myLatestJoinRequest?.status == "approved") {
                                            Text("✓ Katılma isteğiniz KABUL EDİLDİ",
                                                color = Color(0xFF268441),
                                                fontWeight = FontWeight.Bold,
                                                fontSize = 13.sp)
                                        } else if (myLatestJoinRequest?.status == "rejected") {
                                            Text("✕ Katılma isteğiniz REDDEDİLDİ",
                                                color = Color(0xFFB00020),
                                                fontWeight = FontWeight.Bold,
                                                fontSize = 13.sp)
                                        }
                                        val owner = item.ownerId == session?.userId''')

replace_once(
'''                                roomRequests.filter {
                                    it.requesterId == session?.userId &&
                                    it.status == "rejected"
                                }.forEach {
                                    Text("İsteğiniz kabul edilmedi.",
                                        color = Color(0xFFB00020), fontSize = 13.sp)
                                }''',
'''                                // Decisions are displayed next to their own
                                // channel above; no duplicate text in footer.''')

replace_once(
'''                            TextButton(onClick = {
                                showChannelRoomsPreview = false
                                showCreateRoomPreview = true
                            }) { Text("+ KANAL AÇ") }
''',
'''                            // New rooms are created with the permanent
                            // KANAL AÇ + button on the home screen.
''')

replace_once(
'''                            TextButton(onClick = { roomRefresh += 1 }) { Text("YENİLE") }
''',
'''                            // No manual refresh required; list refreshes on
                            // every operation and periodically in the background.
''')

# Show the exact status of the just-reviewed request immediately without
# waiting for the network roundtrip, then force the single automatic fetch.
replace_once(
'''        roomCommand = null
        roomBusy = false
        roomRefresh += 1''',
'''        if (response.isSuccess && cmd.first == "review") {
            roomRequests = roomRequests.map {
                if (it.id == cmd.second)
                    it.copy(status = if (cmd.third) "approved" else "rejected")
                else it
            }
        }
        roomCommand = null
        roomBusy = false
        roomRefresh += 1''')

# A read receipt is sent when the member closes the list they inspected,
# NOT merely because a background refresh saw an approval/denial.
replace_once(
'''    var channelTrackHeightPx by remember { mutableStateOf(0) }''',
'''    var channelTrackHeightPx by remember { mutableStateOf(0) }
    var channelListViewed by remember { mutableStateOf(false) }

    LaunchedEffect(showChannelRoomsPreview, session?.userId) {
        if (showChannelRoomsPreview) {
            channelListViewed = true
        } else if (channelListViewed) {
            channelListViewed = false
            val me = session ?: return@LaunchedEffect
            val unseenIds = roomRequests.filter {
                it.requesterId == me.userId &&
                it.status in listOf("approved", "rejected") &&
                it.resultSeenAt == null
            }.map { it.id }
            if (unseenIds.isNotEmpty()) {
                roomApi.markDecisionNoticesSeen(me, unseenIds)
                    .onSuccess {
                        // Instantly clear the unread counter; reload the server
                        // data to keep decisions and membership synchronized.
                        val seen = unseenIds.toSet()
                        roomRequests = roomRequests.map { request ->
                            if (request.id in seen)
                                request.copy(resultSeenAt = "seen")
                            else request
                        }
                        roomRefresh += 1
                    }.onFailure {
                        roomMessage = "Bildirim okundu bilgisi kaydedilemedi: " +
                            it.message.orEmpty()
                    }
            }
        }
    }''')

for token in (
        'unreadJoinDecisions', 'unreadDecisionsByRoom[item.roomId]',
        'markDecisionNoticesSeen', 'Katılma isteğiniz KABUL EDİLDİ',
        'Katılma isteğiniz REDDEDİLDİ', 'LaunchedEffect(session?.userId, roomRefresh)',
        'channelListScroll.dispatchRawDelta', 'MelehatPendingRequestBadge',
        'roomSelection = createdId to cmd.second', 'showMembers = true'):
    if token not in s:
        raise SystemExit("MELEHAT 1337 protected feature missing: "+token)

p.write_text(s, encoding="utf-8")
print("MELEHAT_1337_BIDIRECTIONAL_ROOM_NOTIFICATIONS_READY")
