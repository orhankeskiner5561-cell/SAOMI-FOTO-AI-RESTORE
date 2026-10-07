from pathlib import Path
import re

# C63: restore the LiveKit event collector correctly.
# LiveKit Android exposes room.events through io.livekit.android.events.collect
# (not kotlinx.coroutines.flow.collect/collectLatest).
lk=Path("app/src/main/java/com/saomi/telsiz/voice/LiveKitPttClient.kt")
s=lk.read_text()
if "import io.livekit.android.events.collect" not in s:
    s=s.replace("import io.livekit.android.events.RoomEvent\n",
                "import io.livekit.android.events.RoomEvent\nimport io.livekit.android.events.collect\n")

old='''    private fun watchRoom(r: Room) {
        // LiveKit 2.x in this project does not expose Room.events as a Kotlin Flow.
        // Keep the room persistent; presence is refreshed on connect/PTT and
        // remote audio publications are subscribed without a Flow collector.
        eventJob?.cancel()
        eventJob = null
        ensureRemoteAudioSubscribed(r)
        publishPresence(r)
    }'''
new='''    private fun watchRoom(r: Room) {
        eventJob?.cancel()
        eventJob = eventScope.launch {
            r.events.collect { event ->
                when (event) {
                    is RoomEvent.TrackPublished,
                    is RoomEvent.TrackSubscribed,
                    is RoomEvent.ParticipantConnected,
                    is RoomEvent.Reconnected -> {
                        ensureRemoteAudioSubscribed(r)
                        publishPresence(r)
                    }
                    is RoomEvent.ParticipantDisconnected,
                    is RoomEvent.TrackUnsubscribed -> publishPresence(r)
                    is RoomEvent.Disconnected -> {
                        connected = false
                        publishPresence(r)
                    }
                    else -> Unit
                }
            }
        }
        ensureRemoteAudioSubscribed(r)
        publishPresence(r)
    }'''
if old not in s:
    raise SystemExit("C62 watchRoom block not found")
s=s.replace(old,new,1)
lk.write_text(s)

ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
u=ui.read_text().replace("C62 • Sabit Dinleme + v0.27 Aktiflik",
                         "C63 • v0.27 Gelen Ses Uyumlu").replace("MELEHAT TELSİZ C62",
                         "MELEHAT TELSİZ C63")
ui.write_text(u)

b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz.c63"',t,count=1)
t=re.sub(r'versionCode\s*=\s*\d+','versionCode = 63',t,count=1)
t=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "C63"',t,count=1)
b.write_text(t)
print("C63 LiveKit room event collector + incoming audio subscription applied")
