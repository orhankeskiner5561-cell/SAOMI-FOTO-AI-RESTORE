from pathlib import Path

# MELEHAT 1.3.49: visual-only remote LiveKit speech meter.
# Keep actual LiveKit microphone, radio connection, PTT callbacks,
# existing foreground service, last-member-room and channel selection.
root=Path("app/src/main/java/com/saomi/telsiz")
state=root/"voice/LiveChannelUiState.kt"
s=state.read_text(encoding="utf-8")
anchor='    private val _notice = MutableStateFlow("")'
if s.count(anchor) != 1: raise SystemExit("1349: UI state insertion anchor changed")
s=s.replace(anchor,'''    // Remote participants only. Sampled by an SDK-driven visual meter;
    // never inferred from room membership, local microphone or floor state.
    private val _remoteAudioLevel = MutableStateFlow(0f)
    val remoteAudioLevel: StateFlow<Float> = _remoteAudioLevel
    fun remoteAudioLevel(level: Float) {
        val normalized = level.coerceIn(0f, 1f)
        if (kotlin.math.abs(_remoteAudioLevel.value - normalized) > 0.015f ||
            normalized == 0f) _remoteAudioLevel.value = normalized
    }
    @Volatile var visualizerVisible = false

'''+anchor,1)
state.write_text(s,encoding="utf-8")

live=root/"voice/LiveKitPttClient.kt"
s=live.read_text(encoding="utf-8")
import_anchor='import io.livekit.android.room.Room'
if s.count(import_anchor) != 1: raise SystemExit("1349: original LiveKit Room import changed")
s=s.replace(import_anchor,import_anchor+"\nimport io.livekit.android.room.participant.RemoteParticipant",1)
anchor='    private var eventJob: Job? = null'
if s.count(anchor) != 1: raise SystemExit("1349: LiveKit event job anchor changed")
s=s.replace(anchor,'''    private var speakerLevelJob: Job? = null

    // Sample actual LiveKit server-provided participant audio levels ONLY
    // while the Android home activity is visible. No audio recording,
    // decoding, AudioManager mode changes, or local microphone inspection.
    private fun beginRemoteSpeakerMeter(r: Room) {
        speakerLevelJob?.cancel()
        LiveChannelUiState.remoteAudioLevel(0f)
        speakerLevelJob = eventScope.launch {
            while (kotlinx.coroutines.currentCoroutineContext().isActive) {
                val newLevel =
                    if (connected && room === r && LiveChannelUiState.visualizerVisible) {
                        r.activeSpeakers.asSequence()
                            .filterIsInstance<RemoteParticipant>()
                            .filter { it.isSpeaking }
                            .map { it.audioLevel.coerceIn(0f, 1f) }
                            .maxOrNull() ?: 0f
                    } else 0f
                LiveChannelUiState.remoteAudioLevel(
                    if (newLevel >= 0.025f) newLevel else 0f
                )
                kotlinx.coroutines.delay(125)
            }
        }
    }
'''+anchor,1)
# Connect after the room assignment ensures the meter sees only the active room.
anchor='''            connected = true
            beginPresenceFor(channel.id)'''
if s.count(anchor) != 1: raise SystemExit("1349: active LiveKit room anchor changed")
s=s.replace(anchor,'''            connected = true
            beginPresenceFor(channel.id)
            beginRemoteSpeakerMeter(r)''',1)
anchor='''    suspend fun disconnect() {
'''
if s.count(anchor) != 1: raise SystemExit("1349: disconnect anchor changed")
s=s.replace(anchor,'''    suspend fun disconnect() {
        speakerLevelJob?.cancel()
        speakerLevelJob = null
        LiveChannelUiState.remoteAudioLevel(0f)
''',1)
# Clear when LiveKit drops unexpectedly as well; old room cannot color next one.
anchor='''                    is RoomEvent.Reconnecting -> {
                        connected = false'''
if s.count(anchor)!=1:raise SystemExit("1349: transport reconnect anchor changed")
s=s.replace(anchor,'''                    is RoomEvent.Reconnecting -> {
                        LiveChannelUiState.remoteAudioLevel(0f)
                        connected = false''',1)
anchor='''                    is RoomEvent.Disconnected -> {
                        connected = false'''
if s.count(anchor)!=1:raise SystemExit("1349: unexpected disconnection anchor changed")
s=s.replace(anchor,'''                    is RoomEvent.Disconnected -> {
                        LiveChannelUiState.remoteAudioLevel(0f)
                        connected = false''',1)
for protection in (
    "audioOutputType = AudioType.MediaAudioType()",
    "audioHandler = NoAudioHandler()",
    "setMicrophoneEnabled(enabled)", "RoomPresenceReporter(context)",
    "fun isConnectedTo(roomId: String)", "beginPresenceFor(channel.id)"
):
    if protection not in s: raise SystemExit("1349 protected audio feature missing: "+protection)
live.write_text(s,encoding="utf-8")

# MainActivity controls visibility (not the FGS). Locking phone or opening
# another app stops the 8 Hz sampler, even when the radio itself stays on.
main=root/"MainActivity.kt"
s=main.read_text(encoding="utf-8")
anchor='''    override fun onNewIntent(intent: Intent) {'''
if s.count(anchor)!=1:raise SystemExit("1349: MainActivity lifecycle anchor missing")
s=s.replace(anchor,'''    override fun onStart() {
        super.onStart()
        com.saomi.telsiz.voice.LiveChannelUiState.visualizerVisible = true
    }

    override fun onStop() {
        com.saomi.telsiz.voice.LiveChannelUiState.visualizerVisible = false
        com.saomi.telsiz.voice.LiveChannelUiState.remoteAudioLevel(0f)
        super.onStop()
    }

'''+anchor,1)
main.write_text(s,encoding="utf-8")

ui=root/"ui/AppRoot.kt"
s=ui.read_text(encoding="utf-8")
anchor='    val liveStatus by LiveChannelUiState.status.collectAsState()'
if s.count(anchor)!=1:raise SystemExit("1349: Compose LiveKit status collection missing")
s=s.replace(anchor,anchor+'''
    val incomingRemoteLevel by LiveChannelUiState.remoteAudioLevel.collectAsState()
    // Tween smooths out the genuinely remote LiveKit audio level, never fakes
    // a ring based on connected users or the local microphone.
    val incomingWave by androidx.compose.animation.core.animateFloatAsState(
        targetValue = if (radioOn && liveStatus == "LIVE" && !transmitting)
            incomingRemoteLevel else 0f,
        animationSpec = androidx.compose.animation.core.tween(durationMillis = 220),
        label = "MELEHAT remote voice"
    )
''',1)

# The last UI-layout change in v1.3.43 placed this 210dp PTT Box 60dp lower.
# Keep its pointerInput, size, offset and BAS KONUŞ text entirely untouched.
anchor='''                Box(Modifier.size(210.dp).offset(y = 60.dp), contentAlignment = Alignment.Center) {'''
if s.count(anchor)!=1:raise SystemExit("1349: centered PTT Box moved unexpectedly")
box=s.index(anchor)
start=s.index('                    if (radioOn && !transmitting) {',box) if '                    if (radioOn && !transmitting) {' in s[box:box+400] else s.index('                if (radioOn && !transmitting) {',box)
stop=s.index('                Surface(',start)
old_ring=s[start:stop]
if "Canvas(" not in old_ring or "drawCircle(" not in old_ring:
    raise SystemExit("1349: old idle green ring layout changed")
s=s[:start]+'''                // The idle surface is always calm: no idle animation.
                // Every radius and alpha below depends on the actual incoming
                // REMOTE participant audio level, never the local microphone.
                if (radioOn && incomingWave > 0.025f && !transmitting) {
                    Canvas(Modifier.fillMaxSize()) {
                        val intensity = incomingWave.coerceIn(0f, 1f)
                        val center = Offset(size.width / 2f, size.height / 2f)
                        val unit = size.minDimension
                        val emerald = Color(0xFF24C96B)
                        drawCircle(
                            color = emerald.copy(alpha = 0.17f + intensity * 0.23f),
                            radius = unit * (0.451f + intensity * 0.035f),
                            center = center,
                            style = androidx.compose.ui.graphics.drawscope.Stroke(
                                width = unit * (0.014f + intensity * 0.009f)
                            )
                        )
                        drawCircle(
                            color = emerald.copy(alpha = 0.12f + intensity * 0.25f),
                            radius = unit * (0.466f + intensity * 0.035f),
                            center = center,
                            style = androidx.compose.ui.graphics.drawscope.Stroke(
                                width = unit * (0.010f + intensity * 0.008f)
                            )
                        )
                        drawCircle(
                            color = emerald.copy(alpha = 0.09f + intensity * 0.22f),
                            radius = unit * (0.475f + intensity * 0.020f),
                            center = center,
                            style = androidx.compose.ui.graphics.drawscope.Stroke(
                                width = unit * (0.008f + intensity * 0.006f)
                            )
                        )
                    }
                }
'''+s[stop:]
# Mutate the actual central circle ONLY, no Audio/Video/PTT callbacks.
begin=s.index('                Surface(',box)
end=s.index('                    shadowElevation = ',begin)
portion=s[begin:end]
if portion.count('transmitting -> Color(0xFFD32F2F)')!=1 or portion.count('else -> Color(0xFF34C759)')!=1:
    raise SystemExit("1349: original green/red PTT state palette changed")
portion=portion.replace('transmitting -> Color(0xFFD32F2F)','transmitting -> Color(0xFF765747)')
portion=portion.replace('else -> Color(0xFF34C759)','else -> Color(0xFFA6806E)')
s=s[:begin]+portion+s[end:]

# Keep information true for the new color scheme.
import re
pattern=r'if \(transmitting\) "[^"\n]* = [^"\n]*" else "[^"\n]* = [^"\n]*"'
# The sublabel should not advertise green idle or red outgoing any more.
subtext=s[begin:begin+2300]
m=re.search(pattern, subtext)
if m and ('Hazır' in m.group(0) or 'Yayın' in m.group(0)):
    actual=m.group(0)
    s=s.replace(actual,'if (transmitting) "Koyu = Yayın" else "Sütlü kahve = Hazır"',1)

for original in (
    'pointerInput(radioOn)', 'onPtt(true)', 'tryAwaitRelease()',
    'onPtt(false)', 'Spacer(Modifier.height(120.dp))',
    'MelehatPendingRequestBadge', 'VideoCallMonitor.latestMissed',
    'LastRoomPreference(roomsContext)', 'roomSelection = lastRoom.id to lastRoom.name',
    'GÖRÜNTÜLÜ ARA'
):
    if original not in s:raise SystemExit("1349 protected UI feature missing: "+original)
assert 'incomingRemoteLevel' in s and 'incomingWave' in s
assert old_ring not in s
assert s.count('Color(0xFFA6806E)')==1
ui.write_text(s,encoding="utf-8")

print("MELEHAT_1349_REAL_REMOTE_AUDIO_SILENT_COFFEE_PTT_READY")
