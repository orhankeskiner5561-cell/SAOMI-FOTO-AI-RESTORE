from pathlib import Path
import re

# V1.2.0: real LiveKit room presence/UI on top of v0.27 audio/PTT.
# No heartbeat/last_seen/channel_floor is used for online presence.

state = Path("app/src/main/java/com/saomi/telsiz/voice/LiveChannelUiState.kt")
state.write_text(r'''package com.saomi.telsiz.voice

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

data class LiveMember(val identity: String, val name: String)

object LiveChannelUiState {
    private val _status = MutableStateFlow("OFFLINE")
    val status: StateFlow<String> = _status

    private val _members = MutableStateFlow<List<LiveMember>>(emptyList())
    val members: StateFlow<List<LiveMember>> = _members

    private val _notice = MutableStateFlow("")
    val notice: StateFlow<String> = _notice

    fun status(value: String) { _status.value = value }
    fun members(value: List<LiveMember>) { _members.value = value.distinctBy { it.identity } }
    fun notice(value: String) { _notice.value = value }
    fun clearNotice() { _notice.value = "" }
}
''')

# Replace LiveKit client while preserving the v0.27 microphone publish path.
lk = Path("app/src/main/java/com/saomi/telsiz/voice/LiveKitPttClient.kt")
lk.write_text(r'''package com.saomi.telsiz.voice

import android.content.Context
import com.saomi.telsiz.data.SessionStore
import com.saomi.telsiz.model.ChannelInfo
import com.saomi.telsiz.model.UserProfile
import io.livekit.android.LiveKit
import io.livekit.android.events.RoomEvent
import io.livekit.android.events.collect
import io.livekit.android.room.Room
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

class LiveKitPttClient(private val context: Context) {
    private var room: Room? = null
    @Volatile private var connected = false
    private var lastProfile: UserProfile? = null
    private var lastChannel: ChannelInfo? = null
    private val tokenClient = TokenClient(context)
    private val eventScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var eventJob: Job? = null

    private fun identityText(value: Any?): String =
        value?.toString()?.removePrefix("Identity(value=")?.removeSuffix(")") ?: ""

    private fun publishMembers(r: Room) {
        val session = SessionStore(context).load()
        val profile = lastProfile
        val list = mutableListOf<LiveMember>()
        if (connected && session != null) {
            list += LiveMember(session.userId, profile?.fullName.orEmpty().ifBlank { "Ben" })
        }
        r.remoteParticipants.forEach { (identity, participant) ->
            val id = identityText(identity)
            val name = participant.name.ifBlank { id }
            list += LiveMember(id, name)
        }
        LiveChannelUiState.members(list)
    }

    private fun attachEvents(r: Room) {
        eventJob?.cancel()
        eventJob = eventScope.launch {
            r.events.collect { event ->
                when (event) {
                    is RoomEvent.ParticipantConnected -> {
                        publishMembers(r)
                        val name = event.participant.name.ifBlank { identityText(event.participant.identity) }
                        LiveChannelUiState.notice("$name Kanal 1'e katıldı")
                    }
                    is RoomEvent.ParticipantDisconnected -> {
                        val name = event.participant.name.ifBlank { identityText(event.participant.identity) }
                        publishMembers(r)
                        LiveChannelUiState.notice("$name Kanal 1'den ayrıldı")
                    }
                    is RoomEvent.Reconnecting -> {
                        connected = false
                        LiveChannelUiState.status("CONNECTING")
                    }
                    is RoomEvent.Reconnected -> {
                        connected = true
                        LiveChannelUiState.status("LIVE")
                        publishMembers(r)
                    }
                    is RoomEvent.Disconnected -> {
                        connected = false
                        LiveChannelUiState.status("CONNECTING")
                        LiveChannelUiState.members(emptyList())
                    }
                    else -> Unit
                }
            }
        }
    }

    suspend fun connect(profile: UserProfile, channel: ChannelInfo): Boolean {
        lastProfile = profile
        lastChannel = channel
        if (connected && room != null) return true
        if (!profile.isComplete) return false

        val session = SessionStore(context).load() ?: return false
        val identity = session.userId
        LiveChannelUiState.status("CONNECTING")

        val credentials = tokenClient.fetch(
            roomName = channel.id,
            participantName = profile.fullName,
            participantIdentity = identity
        ) ?: return false

        val r = LiveKit.create(context)
        attachEvents(r)
        return runCatching {
            r.connect(credentials.serverUrl, credentials.participantToken)
            // v0.27 behavior: connected to room, microphone remains muted until PTT.
            r.localParticipant.setMicrophoneEnabled(false)
            room = r
            connected = true
            LiveChannelUiState.status("LIVE")
            publishMembers(r)
            true
        }.getOrElse {
            connected = false
            LiveChannelUiState.status("CONNECTING")
            runCatching { r.disconnect() }
            false
        }
    }

    suspend fun setTransmitting(enabled: Boolean): Boolean {
        val r = room ?: return false
        return runCatching {
            // Preserve v0.27 real microphone/audio-track path.
            r.localParticipant.setMicrophoneEnabled(enabled)
            true
        }.getOrDefault(false)
    }

    suspend fun disconnect() {
        runCatching { room?.localParticipant?.setMicrophoneEnabled(false) }
        runCatching { room?.disconnect() }
        eventJob?.cancel()
        eventJob = null
        room = null
        connected = false
        LiveChannelUiState.status("OFFLINE")
        LiveChannelUiState.members(emptyList())
    }

    suspend fun ensureConnected(): Boolean {
        if (connected && room != null) return true
        val p = lastProfile ?: return false
        val c = lastChannel ?: return false
        runCatching { room?.disconnect() }
        room = null
        connected = false
        return connect(p, c)
    }

    fun isConnected(): Boolean = connected
}
''')

# Add registered profiles fetch. Online still comes only from LiveKit.
backend = Path("app/src/main/java/com/saomi/telsiz/data/BackendApi.kt")
b = backend.read_text()
if "data class MemberDirectoryProfile" not in b:
    b = b.replace("class BackendApi(private val context: Context) {",
'''data class MemberDirectoryProfile(val userId: String, val fullName: String, val photoUrl: String)

class BackendApi(private val context: Context) {''', 1)
    insert = r'''
    suspend fun fetchMemberDirectory(session: AuthSession): Result<List<MemberDirectoryProfile>> =
        withContext(Dispatchers.IO) {
            runCatching {
                val request = Request.Builder()
                    .url("${base()}/rest/v1/profiles?select=user_id,full_name,photo_url&order=full_name.asc")
                    .addHeader("apikey", key())
                    .addHeader("Authorization", "Bearer ${session.accessToken}")
                    .get().build()
                http.newCall(request).execute().use { r ->
                    val raw = r.body?.string().orEmpty()
                    if (!r.isSuccessful) error("Üyeler okunamadı: ${r.code}")
                    val arr = JSONArray(raw)
                    buildList {
                        for (i in 0 until arr.length()) {
                            val o = arr.getJSONObject(i)
                            add(MemberDirectoryProfile(
                                o.optString("user_id"),
                                o.optString("full_name").ifBlank { "Üye" },
                                o.optString("photo_url")
                            ))
                        }
                    }
                }
            }
        }

'''
    b = b.replace("\n    suspend fun acquireFloor(", "\n"+insert+"    suspend fun acquireFloor(", 1)
backend.write_text(b)

# UI: bind directly to process-local state populated by real LiveKit events.
ui = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = ui.read_text()
imports = [
"import com.saomi.telsiz.voice.LiveChannelUiState",
"import com.saomi.telsiz.data.MemberDirectoryProfile",
]
for line in imports:
    if line not in s:
        pos=s.find("\n", s.find("package "))
        s=s[:pos+1]+line+"\n"+s[pos+1:]

anchor='    var channelText by remember { mutableStateOf(activeChannel.name) }'
extra=r'''
    val liveStatus by LiveChannelUiState.status.collectAsState()
    val liveParticipants by LiveChannelUiState.members.collectAsState()
    val liveNotice by LiveChannelUiState.notice.collectAsState()
    var directory by remember { mutableStateOf<List<MemberDirectoryProfile>>(emptyList()) }
    var showMembers by remember { mutableStateOf(false) }

    LaunchedEffect(session?.userId) {
        val active = session ?: return@LaunchedEffect
        backend.fetchMemberDirectory(active).onSuccess { directory = it }
    }
    LaunchedEffect(liveNotice) {
        if (liveNotice.isNotBlank()) {
            delay(3500)
            LiveChannelUiState.clearNotice()
        }
    }
'''
if extra.strip() not in s:
    s=s.replace(anchor, anchor+"\n"+extra, 1)

old='''                Column {
                    Text("Telsiz durumu", fontWeight = FontWeight.SemiBold)
                    Text(if (radioOn) "AÇIK • ${activeChannel.name}" else "KAPALI")
                }'''
new='''                Column {
                    Text("Telsiz durumu", fontWeight = FontWeight.SemiBold)
                    Text(
                        when {
                            !radioOn -> "⚪ TELSİZ KAPALI"
                            liveStatus == "LIVE" -> "🟢 KANAL 1 • CANLI"
                            else -> "🟠 BAĞLANIYOR…"
                        }
                    )
                }'''
s=s.replace(old,new,1)

# Remove stale v0.26 card and replace with real live membership UI.
pattern=r'''            Surface\(
                Modifier\.fillMaxWidth\(\),
                shape = RoundedCornerShape\(16\.dp\),
                color = Color\(0xFFF2F2F7\)
            \) \{
                Column\(Modifier\.padding\(16\.dp\)\) \{
                    Text\("MELEHAT TELSİZ v0\.26", fontWeight = FontWeight\.Bold\)
                    Text\("• SMS ve Twilio yok"\)
                    Text\("• E-postaya 6 haneli güvenlik kodu"\)
                    Text\("• Aynı cihazda oturum hatırlanır"\)
                    Text\("• Yeni telefonda aynı e-postaya yeni 6 haneli kod gönderilir"\)
                    Text\("• Kayıtlı telefon numarası eşleşmelidir"\)
                    Text\("• Profil fotoğrafı zorunlu"\)
                \}
            \)'''
replacement=r'''            if (liveNotice.isNotBlank()) {
                Surface(
                    Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    color = Color(0xFFE8F5E9)
                ) {
                    Text(liveNotice, Modifier.padding(12.dp), fontWeight = FontWeight.SemiBold)
                }
            }

            Button(
                onClick = { showMembers = true },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("ÜYELER: ${directory.size}")
            }

            if (showMembers) {
                AlertDialog(
                    onDismissRequest = { showMembers = false },
                    title = { Text("Kanal 1 Üyeleri") },
                    text = {
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            directory.forEach { member ->
                                val online = radioOn && liveStatus == "LIVE" &&
                                    liveParticipants.any { it.identity == member.userId }
                                Text((if (online) "🟢 " else "⚪ ") + member.fullName +
                                    if (online) " — Aktif" else " — Çevrimdışı")
                            }
                        }
                    },
                    confirmButton = {
                        TextButton(onClick = { showMembers = false }) { Text("KAPAT") }
                    }
                )
            }'''
s2,n=re.subn(pattern,replacement,s,count=1)
if n != 1:
    raise SystemExit("old v0.26 card not found")
s=s2
s=s.replace("1.1 • CANLI KANAL 1 • v0.27 SES/PTT","1.2 • GERÇEK CANLI KANAL 1 • v0.27 SES/PTT",1)
ui.write_text(s)

# Service: state must be truthful and keep reconnecting while radio is ON.
svc=Path("app/src/main/java/com/saomi/telsiz/service/PttForegroundService.kt")
t=svc.read_text()
if "LiveChannelUiState" not in t:
    t=t.replace("import com.saomi.telsiz.voice.LiveKitPttClient","import com.saomi.telsiz.voice.LiveKitPttClient\nimport com.saomi.telsiz.voice.LiveChannelUiState")
t=t.replace('startAsForeground("Bağlanıyor…")','LiveChannelUiState.status("CONNECTING")\n                startAsForeground("Kanal 1 • Bağlanıyor…")',1)
t=t.replace('if (ok) "Kanal dinlemede • Bas-konuş hazır"','if (ok) "Kanal 1 CANLI • Bas-konuş hazır"',1)
t=t.replace('if (started) updateNotification("İNTERNET YOK • Yeniden bağlanacak")','if (started) { LiveChannelUiState.status("CONNECTING"); updateNotification("İNTERNET YOK • Yeniden bağlanacak") }',1)
t=t.replace('stopForeground(STOP_FOREGROUND_REMOVE)','LiveChannelUiState.status("OFFLINE")\n        stopForeground(STOP_FOREGROUND_REMOVE)',1)
svc.write_text(t)

# Version only; package remains permanent com.melehat.telsiz.
g=Path("app/build.gradle.kts")
w=g.read_text()
w=re.sub(r'versionCode\s*=\s*\d+','versionCode = 120',w,count=1)
w=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "1.2.0"',w,count=1)
if 'applicationId = "com.melehat.telsiz"' not in w:
    raise SystemExit("permanent applicationId changed unexpectedly")
g.write_text(w)

print("REAL_LIVE_SYSTEM_V120_OK")
