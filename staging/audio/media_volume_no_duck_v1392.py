#!/usr/bin/env python3
"""MELEHAT v1.3.92: Media-volume audio without global voice-call ducking.

The 1.3.91 foreground service held MODE_IN_COMMUNICATION and
AUDIOFOCUS_GAIN for the ENTIRE online session, not only PTT. That
reduces YouTube/media volume and redirects speaker/Bluetooth routing.
Keep the authenticated PTT, foreground service and persistent connection;
change only Android's global audio ownership and P2P playback attributes.
"""
from pathlib import Path

root=Path("app/src/main/java/com/saomi/telsiz")
service=root/"service/PttForegroundService.kt"
duo=root/"p2p/P2pRadioClient.kt"
mesh=root/"p2p/P2pMeshRadioClient.kt"

def one(path, old, new, label):
    src=path.read_text(encoding="utf-8")
    matches=src.count(old)
    if matches!=1:raise RuntimeError(
        f"v1392 {label} expected once, found {matches}")
    path.write_text(src.replace(old,new,1),encoding="utf-8")

# Never take AUDIOFOCUS_GAIN, MODE_IN_COMMUNICATION, or speaker/SCO
# ownership merely because the user switched on background listening.
# Voice call handling is independent and remains untouched.
one(service,
    "import com.saomi.telsiz.audio.AudioRouteManager\n", "",
    "remove global audio router import")
one(service,
    "    private lateinit var audioRoute: AudioRouteManager\n", "",
    "remove router state")
one(service,
    "        audioRoute = AudioRouteManager(applicationContext)\n", "",
    "remove router instance")
one(service,
'''                val route = audioRoute.activateBestRoute()
                updateNotification("Ses çıkışı: $route • Bağlanıyor…")''',
'''                // Online radio receives through the media audio stream.
                // Do not duck YouTube/music or switch the whole phone
                // into narrow-band call mode merely for passive listening.
                updateNotification("Telsiz dinlemede • Ses normal medya çıkışında")''',
    "stop permanent voice-call focus")
src=service.read_text(encoding="utf-8")
if src.count("        audioRoute.deactivate()\n")!=2:
    raise RuntimeError("v1392 route shutdown anchors changed")
service.write_text(src.replace("        audioRoute.deactivate()\n",""),encoding="utf-8")

# Native two-person and mesh WebRTC default to VOICE_COMMUNICATION usage
# even with a muted microphone, so Android may select low-volume voice
# hardware path. MediaAudioAttributes makes RECEIVE volume use STREAM_MUSIC;
# microphone callbacks, echo/noise cancellation, PTT and network are intact.
for path in (duo,mesh):
    original=path.read_text(encoding="utf-8")
    if "import android.media.AudioAttributes" not in original:
        one(path, "import android.Manifest\n",
            "import android.Manifest\nimport android.media.AudioAttributes\n",
            path.name+" import")
    one(path,
'''JavaAudioDeviceModule.builder(context.applicationContext)
            .setSamplesReadyCallback''',
'''JavaAudioDeviceModule.builder(context.applicationContext)
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            .setSamplesReadyCallback''',
       path.name+" media output while keeping PCM callbacks")

s=service.read_text(encoding="utf-8")
for old in ("audioRoute.activateBestRoute()", "audioRoute.deactivate()",
            "AudioRouteManager", "AudioManager.MODE_IN_COMMUNICATION"):
    if old in s:raise RuntimeError("v1392 leaked global audio route: "+old)
for required in (
 "ACTION_START", "ACTION_STOP", "return START_STICKY",
 "startAsForeground(", "wakeLock?.acquire()",
 "ptt.connect(store.loadProfile(), store.loadActiveChannel())",
 "ACTION_PTT_DOWN", "ACTION_PTT_UP", "ptt.forceMute()",
 "VideoCallMonitor.start(applicationContext)",
 "RoomPresenceReporter" if False else "roomMutex.withLock",
):
 if required not in s:raise RuntimeError("v1392 PTT invariant absent "+required)
for path in (duo,mesh):
 text=path.read_text(encoding="utf-8")
 for t in ("setAudioAttributes(", "AudioAttributes.USAGE_MEDIA",
           "AudioAttributes.CONTENT_TYPE_SPEECH",
           "setSamplesReadyCallback", "SmartExternalVoiceGate.onPcm",
           ("localTrack.setEnabled(false)" if path==duo else "track.setEnabled(false)")):
  if t not in text: raise RuntimeError(
      "v1392 protected "+path.name+": "+t)
build=Path("app/build.gradle.kts").read_text(encoding="utf-8")
if 'applicationId = "com.melehat.telsiz"' not in build:
 raise RuntimeError("v1392 package identity changed")
print("MELEHAT_1392_MEDIA_VOLUME_NO_ALWAYS_ON_CALL_AUDIO_FOCUS_OK")
