from pathlib import Path

# MELEHAT v1.3.30: launch an authenticated common audio room without rewriting
# the trusted LiveKit v0.27 PTT implementation.
root = Path("app/src/main/java/com/saomi/telsiz")
token = root / "voice/RoomTokenClient.kt"
token.write_text(r'''package com.saomi.telsiz.voice

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

/**
 * Separate authorized token route for common room.
 * User identity is always derived on Supabase, never trusted from input.
 * Existing working Kanal 1 TokenClient remains untouched.
 */
class RoomTokenClient(context: Context) {
    private val app = context.applicationContext
    private val sessionStore = SessionStore(app)
    private val refresher = SessionRefresher(app)
    private val http = OkHttpClient()
    private val json = "application/json; charset=utf-8".toMediaType()

    suspend fun fetch(roomName: String, listenOnly: Boolean = false): LiveKitCredentials? =
        withContext(Dispatchers.IO) {
            if (roomName != "ortak" && !roomName.matches(Regex("kanal-[a-z0-9-]{1,64}"))) {
                return@withContext null
            }
            val endpoint = BuildConfig.SUPABASE_URL.trimEnd('/') +
                "/functions/v1/melehat-room-token"
            var current = sessionStore.load() ?: return@withContext null
            for (attempt in 0..1) {
                val request = Request.Builder()
                    .url(endpoint)
                    .addHeader("apikey", BuildConfig.SUPABASE_PUBLISHABLE_KEY)
                    .addHeader("Authorization", "Bearer " + current.accessToken)
                    .post(JSONObject().put("roomName", roomName)
                        .put("listenOnly", listenOnly).toString().toRequestBody(json))
                    .build()
                val outcome = runCatching {
                    http.newCall(request).execute().use {
                        it.code to it.body?.string().orEmpty()
                    }
                }.getOrNull() ?: return@withContext null
                if (outcome.first == 401 && attempt == 0) {
                    val refreshed = refresher.refresh() ?: return@withContext null
                    if (refreshed.userId != current.userId) return@withContext null
                    current = refreshed
                    continue
                }
                if (outcome.first !in 200..299) return@withContext null
                val data = runCatching { JSONObject(outcome.second) }.getOrNull()
                    ?: return@withContext null
                val url = data.optString("serverUrl")
                val jwt = data.optString("participantToken")
                if (url.isBlank() || jwt.isBlank()) return@withContext null
                return@withContext LiveKitCredentials(url, jwt)
            }
            null
        }
}
''', encoding="utf-8")

client = root / "voice/LiveKitPttClient.kt"
s = client.read_text(encoding="utf-8")
def substitute(old, new, n=1):
    global s
    if s.count(old) != n:
        raise SystemExit("LiveKit anchor absent/multiple: " + old[:90])
    s = s.replace(old,new,n)

substitute('    private var lastChannel: ChannelInfo? = null',
'''    private var lastChannel: ChannelInfo? = null
    @Volatile private var connectedChannelId: String? = null''')
substitute('    private val tokenClient = TokenClient(context)',
'''    private val tokenClient = TokenClient(context)
    private val roomTokenClient = RoomTokenClient(context)''')
substitute('''        lastProfile = profile
        lastChannel = channel
        if (connected && room != null) return true''',
'''        // Never report another room's connection as success.
        if (connected && room != null && connectedChannelId == channel.id) return true
        if (room != null) disconnect()
        lastProfile = profile
        lastChannel = channel''')
substitute('''        val credentials = tokenClient.fetch(
            roomName = channel.id,
            participantName = profile.fullName,
            participantIdentity = identity
        ) ?: return false''',
'''        // The common channel is new; old private-room token flow is preserved.
        val credentials = if (channel.id == "ortak") {
            roomTokenClient.fetch(roomName = channel.id)
        } else {
            tokenClient.fetch(
                roomName = channel.id,
                participantName = profile.fullName,
                participantIdentity = identity
            )
        } ?: return false''')
substitute('''            room = r
            connected = true
            LiveChannelUiState.status("LIVE")''',
'''            room = r
            connectedChannelId = channel.id
            connected = true
            LiveChannelUiState.roomName(channel.name)
            LiveChannelUiState.status("LIVE")''')
substitute('''            connected = false
            LiveChannelUiState.status("CONNECTING")
            runCatching { r.disconnect() }''',
'''            connected = false
            connectedChannelId = null
            LiveChannelUiState.status("CONNECTING")
            runCatching { r.disconnect() }''')
substitute('''        val r = room ?: return false
        return runCatching {
            // Preserve v0.27 real microphone/audio-track path.''',
'''        val r = room ?: return false
        if (!connected || connectedChannelId == null) return false
        return runCatching {
            // Preserve v0.27 real microphone/audio-track path.''')
substitute('''        room = null
        connected = false
        LiveChannelUiState.status("OFFLINE")''',
'''        room = null
        connected = false
        connectedChannelId = null
        LiveChannelUiState.status("OFFLINE")''')
substitute('''    fun isConnected(): Boolean = connected''',
'''    fun isConnected(): Boolean = connected && room != null
    fun isConnectedTo(roomId: String): Boolean =
        connected && room != null && connectedChannelId == roomId''')
client.write_text(s,encoding="utf-8")

state = root / "voice/LiveChannelUiState.kt"
s = state.read_text(encoding="utf-8")
needle='''    private val _notice = MutableStateFlow("")'''
if s.count(needle)!=1: raise SystemExit("Live status anchor missing")
s=s.replace(needle,'''    private val _roomName = MutableStateFlow("ORTAK KANAL")
    val roomName: StateFlow<String> = _roomName
    fun roomName(value: String) { _roomName.value = value }

'''+needle,1)
state.write_text(s,encoding="utf-8")

local = root / "data/LocalStore.kt"
s = local.read_text(encoding="utf-8")
if 'fun migrateDefaultRoomToCommonOnce' in s: raise SystemExit("Migration duplicate")
# Replace defaults without changing users' registered private room memberships.
s=s.replace('prefs.getString("channel_id","kanal-1")',
            'prefs.getString("channel_id","ortak")',1)
s=s.replace('prefs.getString("channel_name","KANAL 1")',
            'prefs.getString("channel_name","ORTAK KANAL")',1)
last=s.rfind('}')
if last<0: raise SystemExit("LocalStore class is incomplete")
s=s[:last]+'''
    /**
     * One-time v1.3.30 migration: move old installs to the public lobby.
     * Channel 1 membership records remain in Supabase, not in this setting.
     */
    fun migrateDefaultRoomToCommonOnce() {
        if (prefs.getBoolean("common_lobby_migrated_1330", false)) return
        prefs.edit()
            .putString("channel_id", "ortak")
            .putString("channel_name", "ORTAK KANAL")
            .putInt("channel_members", 1)
            .putBoolean("common_lobby_migrated_1330", true)
            .commit()
    }
'''+s[last:]
local.write_text(s,encoding="utf-8")
print("MELEHAT_1330_COMMON_ROOM_TOKEN_AND_LIVEKIT_READY")
