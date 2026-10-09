from pathlib import Path

# MELEHAT v1.3.36: an independent pending-request count for the header
# and each OWNED channel, with a draggable scrollbar in the channel dialog.
# Voice service, PTT, membership and authentication stay unchanged.
p = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = p.read_text(encoding="utf-8")

for imp in (
    "import androidx.compose.foundation.background",
    "import androidx.compose.foundation.gestures.detectVerticalDragGestures",
    "import androidx.compose.ui.layout.onSizeChanged",
    "import androidx.compose.ui.platform.LocalDensity",
    "import androidx.compose.ui.input.pointer.pointerInput",
    "import androidx.compose.foundation.layout.offset",
):
    if imp not in s:
        pos = s.find("\n", s.find("package "))
        s = s[:pos+1] + imp + "\n" + s[pos+1:]

def sub(old, new):
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit("Channel badge anchor missing / ambiguous ("+str(n)+"): "+old[:100])
    s = s.replace(old, new, 1)

sub(
    '    var roomRefresh by remember { mutableStateOf(0) }',
    '''    var roomRefresh by remember { mutableStateOf(0) }
    // Every unreviewed joining request counts once, only for rooms I own.
    val myRoomIds = roomListings.filter { it.ownerId == session?.userId }
        .map { it.roomId }.toSet()
    val pendingByRoom = roomRequests
        .filter { it.status == "pending" && it.roomId in myRoomIds }
        .groupingBy { it.roomId }.eachCount()
    val allPendingRequests = pendingByRoom.values.sum()
    val channelListScroll = rememberScrollState()
    val channelDensity = LocalDensity.current
    var channelTrackHeightPx by remember { mutableStateOf(0) }

    // Refresh badges even when the KANALLAR dialog is closed; do not use
    // global member-directory counts or unapproved requests in other rooms.
    LaunchedEffect(session?.userId) {
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
    }'''
)

sub(
    'Text("KANALLAR  ☷", fontSize = 14.sp, maxLines = 1)',
    '''Box(Modifier.fillMaxWidth()) {
                    Text("KANALLAR  ☷", fontSize = 14.sp, maxLines = 1,
                        modifier = Modifier.align(Alignment.CenterStart))
                    if (allPendingRequests > 0) {
                        MelehatPendingRequestBadge(
                            allPendingRequests,
                            Modifier.align(Alignment.CenterEnd)
                        )
                    }
                }'''
)

sub(
    '                                        Text(item.title, fontWeight = FontWeight.SemiBold)',
    '''                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            verticalAlignment = Alignment.CenterVertically,
                                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                                        ) {
                                            Text(item.title,
                                                modifier = Modifier.weight(1f),
                                                fontWeight = FontWeight.SemiBold)
                                            val pendingForThisRoom = pendingByRoom[item.roomId] ?: 0
                                            if (pendingForThisRoom > 0) {
                                                MelehatPendingRequestBadge(pendingForThisRoom)
                                            }
                                        }'''
)

sub(
    '''                            Column(
                                Modifier.heightIn(max = 410.dp)
                                    .verticalScroll(rememberScrollState()),
                                verticalArrangement = Arrangement.spacedBy(12.dp)
                            ) {''',
    '''                            Box(Modifier.fillMaxWidth().heightIn(max = 410.dp)) {
                                Column(
                                    Modifier.fillMaxWidth().heightIn(max = 410.dp)
                                        .padding(end = 16.dp)
                                        .verticalScroll(channelListScroll),
                                    verticalArrangement = Arrangement.spacedBy(12.dp)
                                ) {'''
)

sub(
    '''                                roomRequests.filter {
                                    it.requesterId == session?.userId &&
                                    it.status == "rejected"
                                }.forEach {
                                    Text("İsteğiniz kabul edilmedi.",
                                        color = Color(0xFFB00020), fontSize = 13.sp)
                                }
                            }
                        }
                    },''',
    '''                                roomRequests.filter {
                                    it.requesterId == session?.userId &&
                                    it.status == "rejected"
                                }.forEach {
                                    Text("İsteğiniz kabul edilmedi.",
                                        color = Color(0xFFB00020), fontSize = 13.sp)
                                }
                                } // scrolling channel list
                                if (channelListScroll.maxValue > 0) {
                                    Box(
                                        Modifier.align(Alignment.CenterEnd)
                                            .width(10.dp).fillMaxHeight()
                                            .onSizeChanged { channelTrackHeightPx = it.height }
                                            .background(Color(0xFFE5DCEC), RoundedCornerShape(8.dp))
                                            .pointerInput(channelListScroll.maxValue,
                                                channelTrackHeightPx) {
                                                detectVerticalDragGestures { change, dy ->
                                                    change.consume()
                                                    val track =
                                                        channelTrackHeightPx.toFloat().coerceAtLeast(1f)
                                                    val fraction = track /
                                                        (track + channelListScroll.maxValue)
                                                    val thumb = (track * fraction)
                                                        .coerceAtLeast(with(channelDensity) { 36.dp.toPx() })
                                                        .coerceAtMost(track)
                                                    val travel = (track - thumb).coerceAtLeast(1f)
                                                    channelListScroll.dispatchRawDelta(
                                                        dy * channelListScroll.maxValue / travel
                                                    )
                                                }
                                            }
                                    ) {
                                        val maxScroll = channelListScroll.maxValue
                                        val fraction = channelTrackHeightPx.toFloat() /
                                            (channelTrackHeightPx + maxScroll).coerceAtLeast(1)
                                        val thumbHeightPx = (fraction * channelTrackHeightPx)
                                            .coerceAtLeast(with(channelDensity) { 36.dp.toPx() })
                                            .coerceAtMost(channelTrackHeightPx.toFloat())
                                        val available = (channelTrackHeightPx - thumbHeightPx)
                                            .coerceAtLeast(0f)
                                        val thumbOffset = if (maxScroll > 0)
                                            available * channelListScroll.value / maxScroll else 0f
                                        Box(
                                            Modifier.offset(y = with(channelDensity) {
                                                thumbOffset.toDp()
                                            })
                                                .fillMaxWidth()
                                                .height(with(channelDensity) {
                                                    thumbHeightPx.toDp()
                                                })
                                                .background(Color(0xFF7455AC),
                                                    RoundedCornerShape(8.dp))
                                        )
                                    }
                                }
                            } // scrollbar and channel list
                        }
                    },'''
)

# Bottom bar stays accessible while the list scrolls. The red badge is
# deliberately not added to rooms the viewer doesn't own.
s += '''

@Composable
private fun MelehatPendingRequestBadge(
    count: Int,
    modifier: Modifier = Modifier
) {
    if (count <= 0) return
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(50),
        color = Color(0xFFD92D42)
    ) {
        Text(
            if (count > 99) "99+" else count.toString(),
            modifier = Modifier.padding(horizontal = 7.dp, vertical = 2.dp),
            color = Color.White,
            fontSize = 12.sp,
            maxLines = 1
        )
    }
}
'''

for marker in ('allPendingRequests', 'pendingByRoom[item.roomId]',
               'detectVerticalDragGestures', 'MelehatPendingRequestBadge',
               'channelListScroll.dispatchRawDelta', 'roomCommand = Triple("review"'):
    if marker not in s:
        raise SystemExit("Badge validation missing: "+marker)
p.write_text(s, encoding="utf-8")
print("MELEHAT_1336_CHANNEL_SCROLL_AND_REQUEST_BADGES_READY")
