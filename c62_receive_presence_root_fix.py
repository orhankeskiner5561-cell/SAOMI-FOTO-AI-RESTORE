from pathlib import Path
import re

# C62: fix the two root causes:
# 1) C58 disconnected/recreated the LiveKit room on every PTT press.
# 2) v0.27 LiveKit identity is phone digits, while member list key is Supabase UUID.
# Keep one listening room alive, explicitly subscribe remote audio, and publish presence by display name.

lk=Path("app/src/main/java/com/saomi/telsiz/voice/LiveKitPttClient.kt")
lk.write_text(r'''package com.saomi.telsiz.voice

import android.content.Context
import com.saomi.telsiz.model.ChannelInfo
import com.saomi.telsiz.model.UserProfile
import io.livekit.android.LiveKit
import io.livekit.android.events.RoomEvent
import io.livekit.android.room.Room
import io.livekit.android.room.track.RemoteTrackPublication
import kotlinx.coroutines.*

class LiveKitPttClient(
    private val context: Context,
    private val onPresenceChanged: (Set<String>, Set<String>) -> Unit = { _, _ -> }
) {
    private var room: Room? = null
    @Volatile private var connected = false
    private val tokenClient = TokenClient(context)
    private val eventScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var eventJob: Job? = null

    suspend fun connect(profile: UserProfile, channel: ChannelInfo): Boolean {
        // IMPORTANT: do not tear down a healthy listening room on every PTT press.
        if (connected && room != null) {
            ensureRemoteAudioSubscribed(room!!)
            publishPresence(room!!)
            return true
        }
        if (!profile.isComplete) return false

        val identity = profile.phone.filter { it.isDigit() }.ifBlank { profile.fullName }
        val credentials = tokenClient.fetch(
            roomName = channel.id,
            participantName = profile.fullName,
            participantIdentity = identity
        ) ?: return false

        runCatching { room?.disconnect() }
        eventJob?.cancel()

        val r = LiveKit.create(context)
        return runCatching {
            r.connect(credentials.serverUrl, credentials.participantToken)
            r.localParticipant.setMicrophoneEnabled(false)
            room = r
            connected = true
            ensureRemoteAudioSubscribed(r)
            publishPresence(r)
            watchRoom(r)
            true
        }.getOrElse {
            connected = false
            runCatching { r.disconnect() }
            false
        }
    }

    private fun watchRoom(r: Room) {
        eventJob?.cancel()
        eventJob = eventScope.launch {
            r.events.collect { event ->
                when (event) {
                    is RoomEvent.ParticipantConnected,
                    is RoomEvent.ParticipantDisconnected,
                    is RoomEvent.ParticipantNameChanged -> publishPresence(r)

                    is RoomEvent.TrackPublished -> {
                        (event.publication as? RemoteTrackPublication)?.setSubscribed(true)
                        publishPresence(r)
                    }

                    is RoomEvent.TrackUnmuted -> {
                        (event.publication as? RemoteTrackPublication)?.setSubscribed(true)
                        publishPresence(r)
                    }

                    is RoomEvent.TrackSubscriptionPermissionChanged -> {
                        event.trackPublication.setSubscribed(true)
                    }

                    is RoomEvent.Reconnected -> {
                        connected = true
                        ensureRemoteAudioSubscribed(r)
                        publishPresence(r)
                    }

                    is RoomEvent.Disconnected -> {
                        if (room === r) {
                            connected = false
                            onPresenceChanged(emptySet(), emptySet())
                        }
                    }

                    else -> Unit
                }
            }
        }
    }

    private fun ensureRemoteAudioSubscribed(r: Room) {
        r.remoteParticipants.values.forEach { participant ->
            participant.trackPublications.values.forEach { publication ->
                (publication as? RemoteTrackPublication)?.let {
                    if (!it.subscribed) it.setSubscribed(true)
                    it.setEnabled(true)
                }
            }
        }
    }

    private fun publishPresence(r: Room) {
        val remotes = r.remoteParticipants.values
        val ids = remotes.mapNotNull { it.identity?.value?.takeIf(String::isNotBlank) }.toSet()
        val names = remotes.mapNotNull { it.name?.trim()?.takeIf(String::isNotBlank) }.toSet()
        onPresenceChanged(ids, names)
    }

    suspend fun setTransmitting(enabled: Boolean): Boolean {
        val r = room ?: return false
        return runCatching {
            r.localParticipant.setMicrophoneEnabled(enabled)
            true
        }.getOrDefault(false)
    }

    suspend fun disconnect() {
        eventJob?.cancel()
        runCatching { room?.localParticipant?.setMicrophoneEnabled(false) }
        runCatching { room?.disconnect() }
        room = null
        connected = false
        onPresenceChanged(emptySet(), emptySet())
    }

    fun isConnected(): Boolean = connected

    fun connectedRemoteIdentities(): Set<String> =
        room?.remoteParticipants?.values
            ?.mapNotNull { it.identity?.value }
            ?.toSet()
            ?: emptySet()

    fun connectedRemoteNames(): Set<String> =
        room?.remoteParticipants?.values
            ?.mapNotNull { it.name?.trim() }
            ?.filter { it.isNotBlank() }
            ?.toSet()
            ?: emptySet()
}
''')

svc=Path("app/src/main/java/com/saomi/telsiz/service/PttForegroundService.kt")
s=svc.read_text()
s=s.replace("ptt = LiveKitPttClient(applicationContext)",'''ptt = LiveKitPttClient(applicationContext) { ids, names ->
            broadcastLiveKitPresence(ids, names)
        }''')
# replace old helper with overload carrying both identity and display name
s=re.sub(r'''    private fun broadcastLiveKitPresence\(\) \{.*?\n    \}\n''',lambda _m: '''    private fun broadcastLiveKitPresence(
        ids: Set<String> = ptt.connectedRemoteIdentities(),
        names: Set<String> = ptt.connectedRemoteNames()
    ) {
        sendBroadcast(Intent("com.saomi.telsiz.LIVEKIT_PRESENCE").apply {
            setPackage(packageName)
            putExtra("remote_ids", ids.joinToString(","))
            putExtra("remote_names", names.joinToString("\u001F"))
        })
    }
''',s,flags=re.S)
svc.write_text(s)

ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
u=ui.read_text()
if "legacyLiveNames" not in u:
    u=u.replace("var legacyLiveIds by remember { mutableStateOf<Set<String>>(emptySet()) }",
                "var legacyLiveIds by remember { mutableStateOf<Set<String>>(emptySet()) }\n    var legacyLiveNames by remember { mutableStateOf<Set<String>>(emptySet()) }")
    u=u.replace('legacyLiveIds = raw.split(",").filter { it.isNotBlank() }.toSet()',
                'legacyLiveIds = raw.split(",").filter { it.isNotBlank() }.toSet()\n                val rawNames = intent?.getStringExtra("remote_names").orEmpty()\n                legacyLiveNames = rawNames.split("\\u001F").map { it.trim() }.filter { it.isNotBlank() }.toSet()')
u=u.replace("m.online || legacyLiveIds.contains(m.id)",
            "m.online || legacyLiveIds.contains(m.id) || legacyLiveNames.any { it.equals(m.name, ignoreCase = true) }")
u=u.replace("C61 • Kararlı PTT + Üye Durumu","C62 • Sabit Dinleme + v0.27 Aktiflik")
u=u.replace("MELEHAT TELSİZ C61","MELEHAT TELSİZ C62")
ui.write_text(u)

b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz.c62"',t,count=1)
t=re.sub(r'versionCode\s*=\s*\d+','versionCode = 62',t,count=1)
t=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "C62"',t,count=1)
b.write_text(t)
print("C62 persistent receive + legacy presence fix applied")
