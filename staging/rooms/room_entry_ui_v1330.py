from pathlib import Path

# Android v1.3.30: one focused microphone route for a server-authorized room.
p = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = p.read_text(encoding="utf-8")
def sub(old,new,num=1):
    global s
    if s.count(old)!=num: raise SystemExit("UI anchor mismatch "+str(s.count(old))+": "+old[:110])
    s=s.replace(old,new,num)

sub('''    val liveStatus by LiveChannelUiState.status.collectAsState()''',
'''    val liveStatus by LiveChannelUiState.status.collectAsState()
    val liveRoomName by LiveChannelUiState.roomName.collectAsState()''')
sub('''"🟢 KANAL 1 • CANLI"''','''"🟢 ${liveRoomName} • CANLI"''')
sub('''    var roomCommand by remember { mutableStateOf<Triple<String, String, Boolean>?>(null) }''',
'''    var roomCommand by remember { mutableStateOf<Triple<String, String, Boolean>?>(null) }
    var roomSelection by remember { mutableStateOf<Pair<String, String>?>(null) }

    LaunchedEffect(roomSelection) {
        val target = roomSelection ?: return@LaunchedEffect
        roomSelection = null
        if (session == null) {
            roomMessage = "Önce giriş yapın."
            return@LaunchedEffect
        }
        if (radioOn) {
            val i = android.content.Intent(
                roomsContext,
                com.saomi.telsiz.service.PttForegroundService::class.java
            ).apply {
                action = com.saomi.telsiz.service.PttForegroundService.ACTION_SWITCH_ROOM
                putExtra(com.saomi.telsiz.service.PttForegroundService.EXTRA_ROOM_ID, target.first)
                putExtra(com.saomi.telsiz.service.PttForegroundService.EXTRA_ROOM_NAME, target.second)
            }
            runCatching { roomsContext.startService(i) }
                .onFailure { roomMessage = "Kanal geçişi yapılamadı: " + it.message.orEmpty() }
        } else {
            val selected = ChannelInfo(target.first, target.second)
            localStore.saveActiveChannel(selected)
            activeChannel = selected
            radioOn = true
            localStore.setRadioEnabled(true)
            onRadioToggle(true)
        }
        showChannelRoomsPreview = false
    }''')

sub('''                                Text("ORTAK KANAL • Üyelerin ortak alanı",
                                    fontWeight = FontWeight.Bold)
                                Text("Özel odalarda ses bağlantısı ayrıca etkinleştirilecek.",
                                    fontSize = 12.sp)''',
'''                                Text("ORTAK KANAL • Üyelerin ortak alanı",
                                    fontWeight = FontWeight.Bold)
                                TextButton(
                                    enabled = !roomBusy,
                                    onClick = { roomSelection = "ortak" to "ORTAK KANAL" }
                                ) { Text("ORTAK KANALA GİR") }
                                Text("Her odanın konuşması yalnız kendi dinleyicilerine gider.",
                                    fontSize = 12.sp)''')
sub('''                                            owner -> Text("Kanal sahibi sizsiniz", fontSize = 12.sp)
                                            item.member -> Text("Onaylı üyesiniz", fontSize = 12.sp)''',
'''                                            owner -> {
                                                Text("Kanal sahibi sizsiniz", fontSize = 12.sp)
                                                TextButton(
                                                    enabled = !roomBusy,
                                                    onClick = {
                                                        roomSelection = item.roomId to item.title
                                                    }
                                                ) { Text("KANALA GİR") }
                                            }
                                            item.member -> {
                                                Text("Onaylı üyesiniz", fontSize = 12.sp)
                                                TextButton(
                                                    enabled = !roomBusy,
                                                    onClick = {
                                                        roomSelection = item.roomId to item.title
                                                    }
                                                ) { Text("KANALA GİR") }
                                            }''')
sub('''            Button(
                onClick = {
                    val c = ChannelInfo(
                        id = slug(channelText.ifBlank { "KANAL 1" }),
                        name = channelText.ifBlank { "KANAL 1" }
                    )
                    activeChannel = c
                    localStore.saveActiveChannel(c)
                    scope.launch { backend.joinChannel(session!!, c) }
                },
                modifier = Modifier.fillMaxWidth()
            ) { Text("Kanala Gir") }''',
'''            Button(
                onClick = {
                    val current = localStore.loadActiveChannel()
                    roomSelection = current.id to current.name
                },
                modifier = Modifier.fillMaxWidth()
            ) { Text("Kanala Gir") }''')
legacy='''                            TextButton(onClick = {
                                showLegacyChannelPicker = !showLegacyChannelPicker
                                showChannelRoomsPreview = false
                            }) { Text("KANAL SEÇ") }'''
if legacy in s: s=s.replace(legacy,"",1)
if 'ACTION_SWITCH_ROOM' not in s or 'ORTAK KANALA GİR' not in s:
    raise SystemExit("New channel-select events not injected")
if 'backend.joinChannel(session!!, c)' in s:
    raise SystemExit("Unsafe free-text join remains")
p.write_text(s,encoding="utf-8")
print("MELEHAT_1330_AUTHORIZED_ROOM_ENTRY_UI_OK")
