#!/usr/bin/env python3
# MELEHAT 1.3.72 - actual remote video media codec negotiation, not UI.
# The generated build already contains v1.3.71, with successful 1:1
# hangup and native P2P audio. Do not touch those or the Android signing.
from pathlib import Path

target=Path("app/src/main/java/com/saomi/telsiz/video/P2pVideoCallActivity.kt")
content=target.read_text(encoding="utf-8")

def change(old,new,label):
    global content
    count=content.count(old)
    if count!=1:
        raise RuntimeError(label+" expected 1 occurrence, found "+str(count))
    content=content.replace(old,new,1)

# Without explicit video encoder/decoder factories the actual SDP in every
# test call offered m=video 0 and no supported video rtpmap codecs.
# ICE connected for audio while video remained inactive.
change('''        val built=PeerConnectionFactory.builder().setAudioDeviceModule(module)
            .createPeerConnectionFactory()''',
'''        // Always register BOTH hardware/software video codec factories.
        // A default audio-only PeerConnectionFactory produces m=video 0:
        // ICE can connect but no remote camera frames can ever be sent.
        val videoEncoders=DefaultVideoEncoderFactory(eglContext,true,true)
        val videoDecoders=DefaultVideoDecoderFactory(eglContext)
        val built=PeerConnectionFactory.builder()
            .setAudioDeviceModule(module)
            .setVideoEncoderFactory(videoEncoders)
            .setVideoDecoderFactory(videoDecoders)
            .createPeerConnectionFactory()''',
"WebRTC VP8/H264 hardware-software video codecs")

# Guard every SDP exchange to avoid reporting false media success with
# an inactive/rejected video section. No IPs/SDP are logged to the screen.
anchor='''    private suspend fun makeOffer(){'''
if content.count(anchor)!=1:raise RuntimeError("makeOffer boundary mismatch")
validator='''    private fun requireVideoCodec(sdp:String,phase:String) {
        val media=sdp.substringAfter("m=video","")
            .substringBefore("\\r\\nm=")
            .substringBefore("\\nm=")
        val first=media.lineSequence().firstOrNull()?.trim().orEmpty()
        if (first.startsWith("0 ") || first.isBlank() ||
            !media.contains("a=rtpmap:")) {
            throw IllegalStateException(
                phase + ": VIDEO_CODEC_EKSIK • kamera aktarımı kurulamadı"
            )
        }
    }

'''
content=content.replace(anchor,validator+anchor,1)

change('''        val offer=awaitIce(pc)
        val result=api.videoExchange(callId,"offer",offer)''',
'''        val offer=awaitIce(pc)
        requireVideoCodec(offer,"GÖNDEREN")
        val result=api.videoExchange(callId,"offer",offer)''',
"offer cannot omit video")
change('''                applySdp(pc,false,SessionDescription(SessionDescription.Type.ANSWER,sdp))
                notice("Telefonlar arasında görüntülü bağlantı kontrol ediliyor…")''',
'''                requireVideoCodec(sdp,"ALICI YANITI")
                applySdp(pc,false,SessionDescription(SessionDescription.Type.ANSWER,sdp))
                notice("Telefonlar arasında görüntülü bağlantı kontrol ediliyor…")''',
"reject inactive video answer")
change('''            if(rev>0&&sdp.startsWith("v=0")){
                applySdp(pc,false,SessionDescription(SessionDescription.Type.OFFER,sdp))''',
'''            if(rev>0&&sdp.startsWith("v=0")){
                requireVideoCodec(sdp,"ARAYAN TEKLİFİ")
                applySdp(pc,false,SessionDescription(SessionDescription.Type.OFFER,sdp))''',
"reject offer without video")
change('''                api.videoExchange(callId,"answer",awaitIce(pc),rev)
                notice("Yanıt gönderildi. Görüntü bağlantısı kuruluyor…")''',
'''                val answer=awaitIce(pc)
                requireVideoCodec(answer,"YANIT")
                api.videoExchange(callId,"answer",answer,rev)
                notice("Yanıt gönderildi. Görüntü bağlantısı kuruluyor…")''',
"reply must contain supported video")

# Retain fixed two-sided hangup from v1.3.71.
for protected in (
    'rpc("melehat_video_end_p2p"' if False else 'api.endDirect(callId)',
    "onTrack(transceiver:RtpTransceiver?)",
    "override fun onFrame(frame:VideoFrame)",
    "PttForegroundService.ACTION_START",
    "receivedRemoteFrame",
    "requireVideoCodec(answer",
    "DefaultVideoEncoderFactory",
    "DefaultVideoDecoderFactory"
):
    if protected not in content:
        raise RuntimeError("Protected video code changed: "+protected)
gradle=Path("app/build.gradle.kts").read_text(encoding="utf-8")
assert 'applicationId = "com.melehat.telsiz"' in gradle
target.write_text(content,encoding="utf-8")
print("MELEHAT_1372_VIDEO_CODECS_NEGOTIATED_AND_HANGUP_PRESERVED")
