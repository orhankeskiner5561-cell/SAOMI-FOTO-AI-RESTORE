from pathlib import Path

# MELEHAT 1.3.33 - one active channel per member.
# Audio, hold-to-talk, floor lease, signing and update system remain unchanged.
root = Path("app/src/main/java/com/saomi/telsiz")
reporter = root / "voice/RoomPresenceReporter.kt"
reporter.write_text(r'''package com.saomi.telsiz.voice

import android.content.Context
import com.saomi.telsiz.BuildConfig
import com.saomi.telsiz.auth.SessionRefresher
import com.saomi.telsiz.data.SessionStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/** Updates one server-side room per user, only when LiveKit is actually connected. */
class RoomPresenceReporter(context: Context) {
    private val sessions = SessionStore(context.applicationContext)
    private val refresher = SessionRefresher(context.applicationContext)
    private val client = OkHttpClient.Builder().callTimeout(4, TimeUnit.SECONDS).build()
    private val url = BuildConfig.SUPABASE_URL.trimEnd('/') +
        "/rest/v1/rpc/melehat_report_room_presence"

    suspend fun report(roomId: String, active: Boolean): Boolean =
        withContext(Dispatchers.IO) {
            if (roomId != "ortak" && !roomId.matches(Regex("kanal-[a-z0-9-]{1,64}")))
                return@withContext false
            var session = sessions.load() ?: return@withContext false
            val payload = JSONObject()
                .put("p_room_id", roomId)
                .put("p_active", active)
                .toString().toRequestBody("application/json".toMediaType())
            for (attempt in 0..1) {
                val req = Request.Builder().url(url)
                    .header("apikey", BuildConfig.SUPABASE_PUBLISHABLE_KEY)
                    .header("Authorization", "Bearer " + session.accessToken)
                    .post(payload).build()
                val code = runCatching {
                    client.newCall(req).execute().use { response -> response.code }
                }.getOrDefault(0)
                if (code in 200..299) return@withContext true
                if (code != 401 || attempt != 0) return@withContext false
                val renewed = refresher.refresh() ?: return@withContext false
                if (renewed.userId != session.userId) return@withContext false
                session = renewed
            }
            false
        }
}
''', encoding="utf-8")

lk = root / "voice/LiveKitPttClient.kt"
s = lk.read_text(encoding="utf-8")
def lk_replace(needle, replacement):
    global s
    if s.count(needle) != 1:
        raise SystemExit("Presence LiveKit anchor incorrect (" +
                         str(s.count(needle)) + "): " + needle[:95])
    s = s.replace(needle, replacement, 1)

lk_replace("    private var eventJob: Job? = null",
'''    private var eventJob: Job? = null
    private val presenceReporter = RoomPresenceReporter(context)
    private var presenceJob: Job? = null

    private fun beginPresenceFor(roomId: String) {
        presenceJob?.cancel()
        presenceJob = eventScope.launch {
            // A member may belong to many rooms but has one transmitting /
            // listening LiveKit connection. Publish only that connection.
            while (connectedChannelId == roomId) {
                if (connected) presenceReporter.report(roomId, true)
                kotlinx.coroutines.delay(4000)
            }
        }
    }''')

lk_replace('''            LiveChannelUiState.roomId(channel.id)
            connected = true''',
'''            LiveChannelUiState.roomId(channel.id)
            connected = true
            beginPresenceFor(channel.id)''')

lk_replace('''    suspend fun disconnect() {
''', '''    suspend fun disconnect() {
        val previousRoom = connectedChannelId
        presenceJob?.cancel()
        presenceJob = null
        // Server deletes the record ONLY if it still matches the old room.
        // Late disconnect callbacks cannot remove another room's presence.
        if (previousRoom != null) {
            eventScope.launch { presenceReporter.report(previousRoom, false) }
        }
''')

# Stop advertising after unplanned LiveKit transport loss. Its database entry
# expires automatically after 20 seconds, even if no disconnect RPC arrives.
lk.write_text(s, encoding="utf-8")

ui = root / "ui/AppRoot.kt"
s = ui.read_text(encoding="utf-8")
def ui_replace(needle, replacement):
    global s
    if s.count(needle) != 1:
        raise SystemExit("Presence UI anchor incorrect (" +
                         str(s.count(needle)) + "): " + needle[:105])
    s = s.replace(needle, replacement, 1)

ui_replace('''    val roomApi = remember(roomsContext) { MelehatRoomApi(roomsContext) }''',
'''    val roomApi = remember(roomsContext) { MelehatRoomApi(roomsContext) }
    var activeRoomByUser by remember { mutableStateOf<Map<String, String>>(emptyMap()) }

    LaunchedEffect(session?.userId) {
        val currentSession = session ?: return@LaunchedEffect
        while (true) {
            roomApi.activeRoomByUser(currentSession)
                .onSuccess { activeRoomByUser = it }
                .onFailure { activeRoomByUser = emptyMap() }
            kotlinx.coroutines.delay(3000)
        }
    }''')

ui_replace('''                                        Text(item.title, fontWeight = FontWeight.SemiBold)''',
'''                                        Text(item.title, fontWeight = FontWeight.SemiBold)
                                        Text(
                                            "Şu anda aktif: " +
                                                activeRoomByUser.values.count { it == item.roomId },
                                            fontSize = 12.sp
                                        )''')

ui_replace('''                                val online = radioOn && liveStatus == "LIVE" &&
                                    liveParticipants.any { it.identity == member.userId }''',
'''                                val online =
                                    activeRoomByUser[member.userId] == selectedRoomId ||
                                    (radioOn && liveStatus == "LIVE" &&
                                     selectedRoomId == liveRoomId &&
                                     liveParticipants.any { it.identity == member.userId })''')

# Check foundational behaviors weren't removed by the presence-only change.
for check in ("4 ÜYEYİ AKTAR", "KANALI SİL", "ORTAK KANALA GİR",
              "roomSelection = lobby.id to lobby.name", "selectedRoomMembers",
              "pointerInput(radioOn)"):
    if check not in s:
        raise SystemExit("Protected UI feature missing: " + check)
ui.write_text(s, encoding="utf-8")
print("MELEHAT_1333_PER_ROOM_LIVE_PRESENCE_READY")
