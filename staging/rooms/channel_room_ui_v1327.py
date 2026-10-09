from pathlib import Path

# Prepared for workflow after the stable v1.3.26 UI preview.
# Keep the existing BAS KONUŞ, LiveKit client, updater and member dialog intact.
source = Path("../staging/rooms/MelehatRoomApi.kt")
if not source.exists():
    raise SystemExit("Room API source missing")
target = Path("app/src/main/java/com/saomi/telsiz/rooms/MelehatRoomApi.kt")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(source.read_text())

root = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = root.read_text()

for line in [
    "import com.saomi.telsiz.rooms.MelehatRoomApi",
    "import com.saomi.telsiz.rooms.RoomListing",
    "import com.saomi.telsiz.rooms.RoomRequest",
    "import androidx.compose.foundation.rememberScrollState",
    "import androidx.compose.foundation.verticalScroll",
]:
    if line not in s:
        eol = s.find("\n", s.find("package "))
        s = s[:eol+1] + line + "\n" + s[eol+1:]

state = '    var showCreateRoomPreview by remember { mutableStateOf(false) }'
if state not in s:
    raise SystemExit("Original room preview state not found")
s = s.replace(state, state + '''
    val roomsContext = androidx.compose.ui.platform.LocalContext.current
    val roomApi = remember(roomsContext) { MelehatRoomApi(roomsContext) }
    var roomListings by remember { mutableStateOf<List<RoomListing>>(emptyList()) }
    var roomRequests by remember { mutableStateOf<List<RoomRequest>>(emptyList()) }
    var newRoomName by remember { mutableStateOf("") }
    var roomMessage by remember { mutableStateOf("") }
    var roomBusy by remember { mutableStateOf(false) }
    var roomRefresh by remember { mutableStateOf(0) }
    var roomCommand by remember { mutableStateOf<Triple<String, String, Boolean>?>(null) }

    LaunchedEffect(showChannelRoomsPreview, roomRefresh, session?.userId) {
        val active = session ?: return@LaunchedEffect
        if (!showChannelRoomsPreview) return@LaunchedEffect
        roomBusy = true
        val messages = mutableListOf<String>()
        roomApi.listRooms(active)
            .onSuccess { roomListings = it }
            .onFailure {
                roomListings = emptyList()
                messages.add("Kanallar: " + it.message.orEmpty())
            }
        roomApi.listRequests(active)
            .onSuccess { roomRequests = it }
            .onFailure {
                roomRequests = emptyList()
                messages.add("İstekler: " + it.message.orEmpty())
            }
        if (messages.isNotEmpty()) roomMessage = messages.joinToString(" • ")
        roomBusy = false
    }
    LaunchedEffect(roomCommand) {
        val cmd = roomCommand ?: return@LaunchedEffect
        val active = session
        roomBusy = true
        val response = if (active == null) Result.failure<String>(
            IllegalStateException("Oturum bulunamadı")
        ) else when (cmd.first) {
            "create" -> roomApi.createRoom(active, cmd.second)
            "join" -> roomApi.requestJoin(active, cmd.second)
            "review" -> roomApi.reviewRequest(active, cmd.second, cmd.third)
            else -> Result.failure<String>(IllegalArgumentException("Bilinmeyen işlem"))
        }
        roomMessage = response.fold(
            onSuccess = {
                when (cmd.first) {
                    "create" -> "Yeni kanal açıldı. Kanal sahibi olarak eklendiniz."
                    "join" -> "Katılma isteğiniz kanal sahibine gönderildi."
                    else -> if (cmd.third) "Üye kabul edildi." else "Katılma isteği reddedildi."
                }
            },
            onFailure = { "İşlem yapılamadı: " + it.message.orEmpty() }
        )
        roomCommand = null
        roomBusy = false
        roomRefresh += 1
    }
''', 1)

start_marker = '            // Visual-only first look. No membership, LiveKit or PTT state changes.'
start = s.find(start_marker)
if start < 0:
    raise SystemExit("Original channel preview UI missing")
end = s.find('            if (showMembers) {', start)
if end < 0:
    raise SystemExit("Member dialog missing after preview")
replacement = '''
            TextButton(onClick = {
                roomMessage = ""
                roomRefresh += 1
                showChannelRoomsPreview = true
            }) { Text("KANALLAR  •  KANAL AÇ", color = Color(0xFF6A4CAF)) }
            if (showChannelRoomsPreview) {
                AlertDialog(
                    onDismissRequest = { showChannelRoomsPreview = false },
                    title = { Text("MELEHAT • Kanallar") },
                    text = {
                        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            if (roomBusy) Text("Sunucuyla bağlantı kuruluyor…", fontSize = 13.sp)
                            if (roomMessage.isNotBlank())
                                Text(roomMessage, color = Color(0xFF6A4CAF), fontSize = 13.sp)
                            Column(
                                Modifier.heightIn(max = 410.dp)
                                    .verticalScroll(rememberScrollState()),
                                verticalArrangement = Arrangement.spacedBy(12.dp)
                            ) {
                                Text("ORTAK KANAL • Üyelerin ortak alanı",
                                    fontWeight = FontWeight.Bold)
                                Text("Özel odalarda ses bağlantısı ayrıca etkinleştirilecek.",
                                    fontSize = 12.sp)
                                roomListings.forEach { item ->
                                    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                        Text(item.title, fontWeight = FontWeight.SemiBold)
                                        val owner = item.ownerId == session?.userId
                                        when {
                                            owner -> Text("Kanal sahibi sizsiniz", fontSize = 12.sp)
                                            item.member -> Text("Onaylı üyesiniz", fontSize = 12.sp)
                                            roomRequests.any { request ->
                                                request.roomId == item.roomId &&
                                                request.requesterId == session?.userId &&
                                                request.status == "pending"
                                            } -> Text("Katılma isteği bekliyor", fontSize = 12.sp)
                                            else -> TextButton(
                                                enabled = !roomBusy,
                                                onClick = {
                                                    roomCommand = Triple("join", item.roomId, false)
                                                }
                                            ) { Text("KATILMA İSTEĞİ GÖNDER") }
                                        }
                                    }
                                }
                                val ownedRooms = roomListings.filter {
                                    it.ownerId == session?.userId
                                }.map { it.roomId }
                                roomRequests.filter {
                                    it.status == "pending" && it.roomId in ownedRooms
                                }.forEach { request ->
                                    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                        val display = directory.firstOrNull {
                                            it.userId == request.requesterId
                                        }?.fullName ?: "Kayıtlı üye"
                                        Text(display + " • Katılım isteği")
                                        Row {
                                            TextButton(
                                                enabled = !roomBusy,
                                                onClick = {
                                                    roomCommand = Triple("review", request.id, true)
                                                }
                                            ) { Text("KABUL ET") }
                                            TextButton(
                                                enabled = !roomBusy,
                                                onClick = {
                                                    roomCommand = Triple("review", request.id, false)
                                                }
                                            ) { Text("REDDET") }
                                        }
                                    }
                                }
                                roomRequests.filter {
                                    it.requesterId == session?.userId &&
                                    it.status == "rejected"
                                }.forEach {
                                    Text("İsteğiniz kabul edilmedi.",
                                        color = Color(0xFFB00020), fontSize = 13.sp)
                                }
                            }
                        }
                    },
                    confirmButton = {
                        Row {
                            TextButton(onClick = {
                                showChannelRoomsPreview = false
                                showCreateRoomPreview = true
                            }) { Text("+ KANAL AÇ") }
                            TextButton(onClick = { roomRefresh += 1 }) { Text("YENİLE") }
                            TextButton(onClick = { showChannelRoomsPreview = false }) {
                                Text("KAPAT")
                            }
                        }
                    }
                )
            }
            if (showCreateRoomPreview) {
                AlertDialog(
                    onDismissRequest = { showCreateRoomPreview = false },
                    title = { Text("Yeni kanal aç") },
                    text = {
                        Column {
                            Text("Kanal adı (3-60 karakter)")
                            androidx.compose.material3.OutlinedTextField(
                                value = newRoomName,
                                onValueChange = { newRoomName = it },
                                singleLine = true
                            )
                            Text("Listede görünür; yeni üyelikler onay gerektirir.",
                                fontSize = 12.sp)
                        }
                    },
                    confirmButton = {
                        TextButton(
                            enabled = newRoomName.trim().length in 3..60,
                            onClick = {
                                roomCommand = Triple("create", newRoomName.trim(), false)
                                newRoomName = ""
                                showCreateRoomPreview = false
                                showChannelRoomsPreview = true
                            }
                        ) { Text("KANALI OLUŞTUR") }
                    },
                    dismissButton = {
                        TextButton(onClick = { showCreateRoomPreview = false }) {
                            Text("VAZGEÇ")
                        }
                    }
                )
            }
'''
s = s[:start] + replacement + s[end:]
root.write_text(s)
print("MELEHAT_ROOM_UI_SERVER_LINKED_STAGED")
