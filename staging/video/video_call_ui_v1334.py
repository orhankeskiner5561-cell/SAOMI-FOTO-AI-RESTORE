from pathlib import Path

base = Path("app/src/main/java/com/saomi/telsiz")
target = base / "ui/AppRoot.kt"
s = target.read_text(encoding="utf-8")

def replace_once(a, b):
    global s
    if s.count(a) != 1:
        raise SystemExit("Video UI anchor missing/duplicated ("+str(s.count(a))+"): "+a[:95])
    s = s.replace(a, b, 1)

for imp in ("import com.saomi.telsiz.video.VideoCallApi",
            "import com.saomi.telsiz.video.VideoCallActivity",
            "import com.saomi.telsiz.video.MelehatVideoCall",
            "import androidx.compose.runtime.DisposableEffect"):
    if imp not in s:
        pos = s.find("\n",s.find("package "))
        s = s[:pos+1] + imp+"\n"+s[pos+1:]

replace_once('    var showVideoCallInfo by remember { mutableStateOf(false) }',
'''    var showVideoCallInfo by remember { mutableStateOf(false) }
    val callContext = androidx.compose.ui.platform.LocalContext.current
    val videoApi = remember(callContext) { VideoCallApi(callContext) }
    var incomingVideoCall by remember { mutableStateOf<MelehatVideoCall?>(null) }
    var callBusy by remember { mutableStateOf(false) }
    var videoError by remember { mutableStateOf("") }

    LaunchedEffect(session?.userId) {
        if (session == null) { incomingVideoCall = null; return@LaunchedEffect }
        while (true) {
            runCatching { videoApi.poll() }
                .onSuccess { all ->
                    val pending = all.firstOrNull {
                        it.myState == "pending" &&
                        (it.state == "ringing" || it.state == "active")
                    }
                    if (pending != null && incomingVideoCall?.id != pending.id) {
                        showMembers = false
                        showVideoCallInfo = false
                    }
                    incomingVideoCall = pending
                }
            kotlinx.coroutines.delay(2000)
        }
    }
    DisposableEffect(incomingVideoCall?.id) {
        val ringing = incomingVideoCall
        val sound = if (ringing != null) {
            runCatching {
                android.media.RingtoneManager.getRingtone(
                    callContext,
                    android.media.RingtoneManager.getDefaultUri(
                        android.media.RingtoneManager.TYPE_RINGTONE
                    )
                ).also { it?.play() }
            }.getOrNull()
        } else null
        onDispose { sound?.stop() }
    }''')

old='''            if (showVideoCallInfo) {
                AlertDialog(
                    onDismissRequest = { showVideoCallInfo = false },
                    title = { Text("Özel görüntülü görüşme") },
                    text = { Text(selectedVideoMemberName + " ile görüntülü arama bağlantısı hazırlanıyor. Henüz arama başlatılmadı.") },
                    confirmButton = {
                        TextButton(onClick = { showVideoCallInfo = false }) { Text("TAMAM") }
                    }
                )
            }'''
new='''            if (showVideoCallInfo) {
                AlertDialog(
                    onDismissRequest = { showVideoCallInfo = false },
                    title = { Text("Özel görüntülü görüşme") },
                    text = { Text(selectedVideoMemberName + " kişisini görüntülü aramak istiyor musunuz?") },
                    confirmButton = {
                        TextButton(enabled = !callBusy, onClick = {
                            callBusy = true
                            scope.launch {
                                runCatching { videoApi.dial(selectedVideoMemberId) }
                                    .onSuccess { id ->
                                        showVideoCallInfo = false
                                        callContext.startActivity(android.content.Intent(
                                            callContext, VideoCallActivity::class.java
                                        ).apply {
                                            putExtra(VideoCallActivity.EXTRA_CALL_ID, id)
                                            putExtra(VideoCallActivity.EXTRA_HOST, true)
                                        })
                                    }.onFailure { videoError = it.message ?: "Arama başlatılamadı." }
                                callBusy = false
                            }
                        }) { Text("GÖRÜNTÜLÜ ARA") }
                    },
                    dismissButton = {
                        TextButton(onClick = { showVideoCallInfo = false }) { Text("VAZGEÇ") }
                    }
                )
            }
            if (incomingVideoCall != null) {
                val incoming = incomingVideoCall!!
                val fromName = directory.firstOrNull { it.userId == incoming.callerId }
                    ?.fullName ?: "MELEHAT üyesi"
                AlertDialog(
                    onDismissRequest = { },
                    title = { Text("Gelen görüntülü arama") },
                    text = { Text(fromName + " sizi görüntülü arıyor. Görüşmeye katılmak ister misiniz?") },
                    confirmButton = {
                        TextButton(enabled = !callBusy, onClick = {
                            callBusy = true
                            scope.launch {
                                runCatching { videoApi.answer(incoming.id, true) }
                                    .onSuccess {
                                        incomingVideoCall = null
                                        callContext.startActivity(android.content.Intent(
                                            callContext, VideoCallActivity::class.java
                                        ).apply {
                                            putExtra(VideoCallActivity.EXTRA_CALL_ID, incoming.id)
                                            putExtra(VideoCallActivity.EXTRA_HOST, false)
                                        })
                                    }.onFailure { videoError = it.message ?: "Arama açılamadı." }
                                callBusy = false
                            }
                        }) { Text("AÇ / KABUL ET") }
                    },
                    dismissButton = {
                        TextButton(enabled = !callBusy, onClick = {
                            callBusy = true
                            scope.launch {
                                runCatching { videoApi.answer(incoming.id, false) }
                                    .onFailure { videoError = it.message ?: "Arama reddedilemedi." }
                                incomingVideoCall = null
                                callBusy = false
                            }
                        }) { Text("REDDET / KAPAT") }
                    }
                )
            }
            if (videoError.isNotBlank()) {
                AlertDialog(
                    onDismissRequest = { videoError = "" },
                    title = { Text("Görüntülü arama") },
                    text = { Text(videoError) },
                    confirmButton = { TextButton(onClick = { videoError = "" }) { Text("TAMAM") } }
                )
            }'''
replace_once(old, new)

# When room creation succeeds, immediately switch from the common/private
# channel to the new room using the existing serialized PTT room route.
replace_once('''                    "create" -> "Yeni kanal açıldı. Kanal sahibi olarak eklendiniz."''',
'''                    "create" -> {
                        val createdId = it.trim()
                        if (createdId.matches(Regex("kanal-[a-z0-9-]{1,64}"))) {
                            roomSelection = createdId to cmd.second
                            "Kanal açıldı. Yeni kanalınıza bağlanılıyor."
                        } else "Kanal oluşturuldu, bağlantı bilgisi alınamadı."
                    }''')

for token in ("roomSelection = createdId to cmd.second", "incomingVideoCall",
    'Text("GÖRÜNTÜLÜ ARA")','Text("AÇ / KABUL ET")','Text("REDDET / KAPAT")',
    "roomSwitching", "MELEHAT_UPDATE_MANIFEST"):
    if token not in s and token != "roomSwitching":
        raise SystemExit("Video source missing: "+token)
target.write_text(s,encoding="utf-8")
print("MELEHAT_VIDEO_1334_CALL_UI_AND_AUTOJOIN_READY")
