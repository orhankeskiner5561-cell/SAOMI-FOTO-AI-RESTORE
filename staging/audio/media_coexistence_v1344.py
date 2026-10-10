from pathlib import Path

# MELEHAT 1.3.44 – use media audio only for always-on PTT/listening rooms.
# The default LiveKit AudioSwitchHandler reserves global Android audio focus
# and puts the phone into voice-call mode even while PTT is idle, which
# reduces the volume of YouTube/social video apps and Bluetooth A2DP audio.
#
# LiveKit 2.29.0 officially supports MediaAudioType + NoAudioHandler:
# no automatic voice-call routing or competing AUDIOFOCUS_GAIN request.
# The existing room token, microphone publication, PTT gestures,
# server-side floor lock, live presence, and private video-call room are
# preserved unchanged.
p = Path("app/src/main/java/com/saomi/telsiz/voice/LiveKitPttClient.kt")
s = p.read_text(encoding="utf-8")
old = "        val r = LiveKit.create(context)"
new = '''        // Audio coexistence: do not own the phone/headset audio route or
        // audio focus for a continuously connected receive-only PTT room.
        // A mic track is created only when BAS KONUŞ actually starts.
        val r = LiveKit.create(
            appContext = context.applicationContext,
            overrides = LiveKitOverrides(
                audioOptions = AudioOptions(
                    audioOutputType = AudioType.MediaAudioType(),
                    audioHandler = NoAudioHandler(),
                    disableAudioPrewarming = true
                )
            )
        )'''
if s.count(old) != 1:
    raise SystemExit("MELEHAT 1344: cannot locate exactly one radio LiveKit.create")
s = s.replace(old, new, 1)

for imp in ("import io.livekit.android.LiveKitOverrides",
            "import io.livekit.android.AudioOptions",
            "import io.livekit.android.AudioType",
            "import io.livekit.android.audio.NoAudioHandler"):
    if imp not in s:
        anchor = "import io.livekit.android.LiveKit\n"
        if anchor not in s:
            raise SystemExit("MELEHAT 1344: LiveKit import missing")
        s = s.replace(anchor, anchor + imp + "\n", 1)

assert 'setMicrophoneEnabled(false)' in s
assert 'setMicrophoneEnabled(enabled)' in s
assert 'roomTokenClient.fetch' in s
assert 'fun isConnectedTo(roomId: String)' in s
assert 'beginPresenceFor(channel.id)' in s
assert 'private fun beginPresenceFor(roomId: String)' in s
assert 'AudioType.MediaAudioType()' in s
assert 'audioHandler = NoAudioHandler()' in s
assert 'disableAudioPrewarming = true' in s
assert s.count('LiveKit.create(') == 1
p.write_text(s, encoding="utf-8")
print("MELEHAT_1344_MEDIA_COEXISTENCE_RADIO_ONLY_OK")
