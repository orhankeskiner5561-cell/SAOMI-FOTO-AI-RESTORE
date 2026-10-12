#!/usr/bin/env python3
"""MELEHAT v1.3.80 — genuine remote-speech triple dark-brown rings, red TX.
Visual-only PTT state palette. Passive inbound WebRTC stats for native P2P.
No changes to sender track, microphone, channel transport, signaling or PTT callbacks.
"""
from pathlib import Path
root=Path("app/src/main/java/com/saomi/telsiz")
ui=root/"ui/AppRoot.kt"
duo=root/"p2p/P2pRadioClient.kt"
mesh=root/"p2p/P2pMeshRadioClient.kt"
helper=root/"p2p/RemoteVoiceStatsMeter.kt"

def single(text,old,new,label):
    n=text.count(old)
    if n!=1: raise RuntimeError(label+": expected 1, got "+str(n))
    return text.replace(old,new,1)

s=ui.read_text(encoding="utf-8")
anchor="                Box(Modifier.size(210.dp).offset(y = 60.dp), contentAlignment = Alignment.Center) {"
assert s.count(anchor)==1, "PTT dimensions/position changed, refuse unsafe patch"
begin=s.index("                // The idle surface is always calm:",s.index(anchor))
end=s.index("                Surface(",begin)
old_visual=s[begin:end]
assert "val emerald = Color(0xFF24C96B)" in old_visual
assert old_visual.count("drawCircle(")==3
new_visual='''                // Three genuine remote-voice rings. The oversized Canvas is
                // drawn outside the 210dp layout box WITHOUT changing layout
                // size/positions, PTT touch target, cards or scroll coordinates.
                // Zero remote audio => no ring, no idle pulsing.
                if (radioOn && liveStatus == "LIVE" &&
                    incomingWave > 0.025f && !transmitting) {
                    Canvas(
                        Modifier.requiredSize(250.dp).align(Alignment.Center)
                    ) {
                        val intensity = incomingWave.coerceIn(0f, 1f)
                        val center = Offset(size.width / 2f, size.height / 2f)
                        val scale = size.minDimension / 250f
                        val darkBrown = Color(0xFF654333)
                        for (ring in 0..2) {
                            val radius = (101f + ring * 8f +
                                intensity * (2.5f + ring * 1.5f)) * scale
                            val opacity = (0.44f - ring * 0.07f +
                                intensity * 0.42f).coerceIn(0f, 0.95f)
                            drawCircle(
                                color = darkBrown.copy(alpha = opacity),
                                radius = radius,
                                center = center,
                                style = androidx.compose.ui.graphics.drawscope.Stroke(
                                    width = (2.4f + intensity * 1.8f) * scale
                                )
                            )
                        }
                    }
                }
'''
s=s[:begin]+new_visual+s[end:]
s=single(s,'transmitting -> Color(0xFF765747)','transmitting -> Color(0xFFD32F2F)',"red outgoing transmission")
s=single(s,'transmitting -> "Koyu = Yayın"','transmitting -> "Kırmızı = Yayın"',"true outgoing color legend")
assert 'else -> Color(0xFFA6806E)' in s, "Idle milk-coffee appearance must remain"
assert s.count("onPtt(true)")==1 and s.count("onPtt(false)")==1
assert "pointerInput(radioOn, liveStatus)" in s
assert 'Modifier.requiredSize(250.dp)' in s
assert 'Color(0xFF24C96B)' not in s, "Old green ring color must be replaced"
for protected in ("YENİ ABONELER", "GÜNCELLE", "KURULUMU TAMAMLA", "RecentSubscriberApi", "roomApi.listRequests", "LastRoomPreference"):
    assert protected in s, "Protected home-screen feature missing: "+protected
ui.write_text(s,encoding="utf-8")

# Passive stats of RECEIVED WebRTC inbound-rtp tracks, not outgoing audio.
# Fallback to energy/time delta when the audioLevel member is unavailable.
assert not helper.exists(), "Remote meter already present: refuse overwrite"
helper.write_text(r'''package com.saomi.telsiz.p2p

import kotlin.math.sqrt
import livekit.org.webrtc.PeerConnection
import java.util.concurrent.ConcurrentHashMap

/**
 * A read-only visual meter. Never touches microphone, audio track, SDP,
 * signaling, media capture, audio-routing, or PTT arbitration.
 */
internal class RemoteVoiceStatsMeter {
    private val previous = ConcurrentHashMap<String, Pair<Double, Double>>()

    fun clear() { previous.clear() }

    fun sample(pc: PeerConnection, key: String, onLevel: (Float) -> Unit) {
        pc.getStats { report ->
            var highest = 0f
            for (item in report.statsMap.values) {
                if (item.type != "inbound-rtp") continue
                val kind = item.members["kind"]?.toString()
                    ?: item.members["mediaType"]?.toString()
                if (kind != "audio") continue
                val level = (item.members["audioLevel"] as? Number)?.toDouble()
                val energy = (item.members["totalAudioEnergy"] as? Number)?.toDouble()
                val seconds = (item.members["totalSamplesDuration"] as? Number)?.toDouble()
                val sampleKey = key + ":" + item.id
                var raw = level ?: 0.0
                if (energy != null && seconds != null) {
                    val old = previous.put(sampleKey, energy to seconds)
                    if (level == null && old != null) {
                        val deltaTime = seconds - old.second
                        val deltaEnergy = energy - old.first
                        if (deltaTime > 0.0 && deltaEnergy >= 0.0) {
                            raw = sqrt(deltaEnergy / deltaTime)
                        }
                    }
                }
                if (raw.isFinite()) {
                    // Compress the typically quiet RTC audio-level scale;
                    // suppress low background hiss to keep the idle button calm.
                    val visual = ((raw - 0.012) * 4.2).coerceIn(0.0, 1.0).toFloat()
                    if (visual > highest) highest = visual
                }
            }
            onLevel(highest)
        }
    }
}
''', encoding="utf-8")

d=duo.read_text(encoding="utf-8")
d=single(d,'    private var loop: Job? = null','''    private var loop: Job? = null
    private var remoteMeterJob: Job? = null
    private val remoteMeter = RemoteVoiceStatsMeter()

    private fun startRemoteVoiceMeter(connection: PeerConnection) {
        remoteMeterJob?.cancel()
        remoteMeter.clear()
        remoteMeterJob = scope.launch {
            while (isActive && running && online && peer === connection) {
                if (LiveChannelUiState.visualizerVisible) {
                    remoteMeter.sample(connection, "duo") { level ->
                        if (running && online && peer === connection &&
                            LiveChannelUiState.visualizerVisible) {
                            LiveChannelUiState.remoteAudioLevel(level)
                        }
                    }
                } else {
                    LiveChannelUiState.remoteAudioLevel(0f)
                }
                delay(240L)
            }
            LiveChannelUiState.remoteAudioLevel(0f)
        }
    }
''',"duo passive stats")
d=single(d,'''                            LiveChannelUiState.connectionProblem("")
                            LiveChannelUiState.members(listOf(''',
'''                            LiveChannelUiState.connectionProblem("")
                            if (remoteMeterJob?.isActive != true) {
                                peer?.let { startRemoteVoiceMeter(it) }
                            }
                            LiveChannelUiState.members(listOf(''', "duo ICE online hook")
d=single(d,'''                            online=false
                            forceMute()
                            if(running)''',
'''                            online=false
                            remoteMeterJob?.cancel()
                            remoteMeterJob = null
                            LiveChannelUiState.remoteAudioLevel(0f)
                            forceMute()
                            if(running)''',"duo disconnect hook")
d=single(d,'''    private fun stopPeer() {
        forceMute()''',
'''    private fun stopPeer() {
        remoteMeterJob?.cancel()
        remoteMeterJob = null
        remoteMeter.clear()
        forceMute()''',"duo close")
for word in ("track?.setEnabled(true)", "track?.setEnabled(false)", "suspend fun disconnect()", 'presence("beat")'):
    assert word in d, "Duo transport unexpectedly changed: "+word
duo.write_text(d,encoding="utf-8")

m=mesh.read_text(encoding="utf-8")
m=single(m,'''    private var watchJob:Job?=null''',
'''    private var watchJob:Job?=null
    private var remoteMeterJob:Job?=null
    private val remoteMeter=RemoteVoiceStatsMeter()
    private val voiceLevels=ConcurrentHashMap<String,Pair<Float,Long>>()

    private fun startRemoteVoiceMeter() {
        remoteMeterJob?.cancel()
        remoteMeter.clear()
        voiceLevels.clear()
        remoteMeterJob=scope.launch {
            while (isActive && running) {
                val activeLinks=connections.values.filter { it.connected }
                if (LiveChannelUiState.visualizerVisible && activeLinks.isNotEmpty()) {
                    for (link in activeLinks) {
                        remoteMeter.sample(link.pc, link.userId) { level ->
                            if (running && LiveChannelUiState.visualizerVisible &&
                                connections[link.userId] === link && link.connected) {
                                val now=android.os.SystemClock.elapsedRealtime()
                                voiceLevels[link.userId]=level to now
                                val strongest=voiceLevels.values
                                    .filter { now - it.second < 700L }
                                    .maxOfOrNull { it.first } ?: 0f
                                LiveChannelUiState.remoteAudioLevel(strongest)
                            }
                        }
                    }
                } else {
                    voiceLevels.clear()
                    LiveChannelUiState.remoteAudioLevel(0f)
                }
                delay(240L)
            }
            LiveChannelUiState.remoteAudioLevel(0f)
        }
    }
''',"mesh passive stats")
m=single(m,
'''            running=true
            runCatching{registerNetworkRecovery()}
            watchJob=scope.launch{watch(thisEpoch)}''',
'''            running=true
            startRemoteVoiceMeter()
            watchJob=scope.launch{watch(thisEpoch)}''',"mesh start")
m=single(m,'''    private fun remove(id:String){
        val l=connections.remove(id)?:return''',
'''    private fun remove(id:String){
        voiceLevels.remove(id)
        val l=connections.remove(id)?:return''',"mesh remove link")
m=single(m,'''    suspend fun disconnect(){
        running=false;admitted=false;epoch++''',
'''    suspend fun disconnect(){
        running=false;admitted=false;epoch++
        remoteMeterJob?.cancel()
        remoteMeterJob=null
        remoteMeter.clear()
        voiceLevels.clear()
        LiveChannelUiState.remoteAudioLevel(0f)''',"mesh disconnect")
for word in ("mic?.setEnabled(true)","mic?.setEnabled(false)","suspend fun disconnect()", 'presence("beat")'):
    assert word in m, "Mesh transport unexpectedly changed: "+word
mesh.write_text(m,encoding="utf-8")

assert 'applicationId = "com.melehat.telsiz"' in Path("app/build.gradle.kts").read_text()
print("MELEHAT_1380_REAL_REMOTE_P2P_THREE_BROWN_RINGS_RED_PTT_READY")
