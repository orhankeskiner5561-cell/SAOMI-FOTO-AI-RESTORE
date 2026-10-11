#!/usr/bin/env python3
# MELEHAT v1.3.71: track remote video frames and close both ends of a
# direct P2P call. No changes to walkie-talkie, authorization or APK signing.
from pathlib import Path
src=Path("app/src/main/java/com/saomi/telsiz")
video=src/"video/P2pVideoCallActivity.kt"
api=src/"video/VideoCallApi.kt"
assert video.exists() and api.exists()
text=video.read_text(encoding="utf-8")
def fix(old,new,label):
 global text
 n=text.count(old)
 if n!=1:raise RuntimeError(f"{label}: expected one occurrence, got {n}")
 text=text.replace(old,new,1)

fix('''    private var remoteCamera:VideoTrack?=null
    private var peer:PeerConnection?=null''',
'''    private var remoteCamera:VideoTrack?=null
    private var frameWatch:VideoSink?=null
    @Volatile private var receivedRemoteFrame=false
    private var peer:PeerConnection?=null''',
"remote video state")

fix('''        buildScreen()
        pollJob=lifecycleScope.launch {''',
'''        buildScreen()
        // Android Back, navigation gesture and the red button all hang up
        // the SAME server-side direct call for BOTH devices.
        onBackPressedDispatcher.addCallback(this,
            object: androidx.activity.OnBackPressedCallback(true) {
                override fun handleOnBackPressed() { hangUp() }
            })
        pollJob=lifecycleScope.launch {''',
"system back ends call")

# Avoid labeling ICE as successful video when no remote frames have arrived.
fix('''                        notice("P2P ses ve görüntü bağlantısı kuruldu")
                        runOnUiThread{reconnectButton.isEnabled=false}''',
'''                        notice(if(receivedRemoteFrame)
                            "P2P ses ve karşı görüntü aktif"
                            else "P2P ağ bağlantısı var • karşı kamera görüntüsü bekleniyor")
                        runOnUiThread{reconnectButton.isEnabled=false}''',
"honest ICE status")

# Fix the lost video event: modern unified-plan WebRTC emits onTrack,
# while Android builds may still emit onAddTrack or onAddStream.
fix('''            override fun onAddStream(value:MediaStream?){}
            override fun onRemoveStream(value:MediaStream?){}''',
'''            override fun onAddStream(value:MediaStream?){
                value?.videoTracks?.forEach { attachRemoteVideo(it) }
            }
            override fun onRemoveStream(value:MediaStream?){}''',
"legacy stream fallback")

fix('''            override fun onAddTrack(receiver:RtpReceiver?,streams:Array<out MediaStream>?){
                val incoming=receiver?.track()
                if(incoming is VideoTrack){
                    runOnUiThread{
                        remoteCamera?.removeSink(remoteView)
                        remoteCamera=incoming
                        incoming.addSink(remoteView)
                    }
                }
            }''',
'''            override fun onAddTrack(receiver:RtpReceiver?,streams:Array<out MediaStream>?){
                when(val media=receiver?.track()) {
                    is VideoTrack -> attachRemoteVideo(media)
                    is AudioTrack -> media.setEnabled(true)
                }
            }
            override fun onTrack(transceiver:RtpTransceiver?){
                when(val media=transceiver?.receiver?.track()) {
                    is VideoTrack -> attachRemoteVideo(media)
                    is AudioTrack -> media.setEnabled(true)
                }
            }''',
"unified-plan onTrack and audio handling")

fix('''        remoteView=SurfaceViewRenderer(this).apply{setEnableHardwareScaler(true)}''',
'''        remoteView=SurfaceViewRenderer(this).apply{
            setEnableHardwareScaler(true)
            setZOrderOnTop(false)
        }''',
"remote video surface stacking")
fix('''        localView=SurfaceViewRenderer(this).apply{setEnableHardwareScaler(true);setMirror(true)}''',
'''        localView=SurfaceViewRenderer(this).apply{
            setEnableHardwareScaler(true)
            setMirror(true)
            setZOrderMediaOverlay(true)
        }''',
"local video surface stacking")

# Install sink only when actual Android media tracks reach the receiver.
# This also distinguishes ICE connection from REAL remote video frames.
point='''    private suspend fun makeOffer(){'''
if text.count(point)!=1:raise RuntimeError("makeOffer anchor changed")
helper='''    private fun attachRemoteVideo(track:VideoTrack) {
        runOnUiThread {
            if(ended || peer==null || !::remoteView.isInitialized)return@runOnUiThread
            if(remoteCamera===track)return@runOnUiThread
            runCatching { remoteCamera?.removeSink(remoteView) }
            val previousWatch=frameWatch
            if(previousWatch!=null)runCatching{remoteCamera?.removeSink(previousWatch)}
            receivedRemoteFrame=false
            remoteCamera=track
            track.setEnabled(true)
            track.addSink(remoteView)
            val monitor=object:VideoSink {
                private var first=true
                override fun onFrame(frame:VideoFrame) {
                    if(first) {
                        first=false
                        receivedRemoteFrame=true
                        notice("P2P ses ve karşı görüntü aktif")
                    }
                }
            }
            frameWatch=monitor
            track.addSink(monitor)
        }
    }

'''
text=text.replace(point,helper+point,1)

fix('''    private fun closeSoon(){
        if(ended)return
        ended=true
        lifecycleScope.launch {delay(1200);finish()}
    }''',
'''    private fun closeSoon(){
        if(ended)return
        ended=true
        // Turn the microphone/camera OFF on the receiving phone immediately.
        micTrack?.setEnabled(false)
        localCamera?.setEnabled(false)
        lifecycleScope.launch {delay(400);finish()}
    }''',
"remote party shutdown")

fix('''    private fun hangUp(){
        if(ended){finish();return}
        ended=true
        lifecycleScope.launch {
            runCatching{api.end(callId)}
            finish()
        }
    }''',
'''    private fun hangUp(){
        if(ended){finish();return}
        ended=true
        // No video/audio may continue broadcasting while the server is told.
        micTrack?.setEnabled(false)
        localCamera?.setEnabled(false)
        lifecycleScope.launch {
            runCatching { api.endDirect(callId) }
            finish()
        }
    }''',
"end full P2P call for both participants")

fix('''        runCatching{remoteCamera?.removeSink(remoteView)}
        runCatching{localCamera?.removeSink(localView)}
        remoteCamera=null''',
'''        runCatching{remoteCamera?.removeSink(remoteView)}
        frameWatch?.let{ watcher ->
            runCatching{remoteCamera?.removeSink(watcher)}
        }
        frameWatch=null
        receivedRemoteFrame=false
        runCatching{localCamera?.removeSink(localView)}
        remoteCamera=null''',
"dispose receiver monitoring")

# Do not keep a false "connected" status when no remote video is flowing.
apiText=api.read_text(encoding="utf-8")
old='''    suspend fun end(callId: String): Boolean =
        rpc("melehat_video_end", JSONObject().put("p_call", callId)) == "true"'''
new='''    suspend fun end(callId: String): Boolean =
        rpc("melehat_video_end", JSONObject().put("p_call", callId)) == "true"
    // For private two-person P2P, either party ending the call closes
    // the SAME video call on both phones; unlike multi-party leave.
    suspend fun endDirect(callId:String):Boolean =
        rpc("melehat_video_end_p2p",JSONObject().put("p_call",callId))=="true"'''
if apiText.count(old)!=1:raise RuntimeError("VideoCallApi end method changed")
apiText=apiText.replace(old,new,1)

for marker in (
  "onTrack(transceiver:RtpTransceiver?)",
  "onAddTrack(receiver:RtpReceiver?",
  "onAddStream(value:MediaStream?)",
  "override fun onFrame(frame:VideoFrame)",
  "api.endDirect(callId)",
  "incoming.addSink" if False else "track.addSink(remoteView)",
  "receivedRemoteFrame",
  "setZOrderMediaOverlay(true)"
):
 assert marker in text, "Video source protection missing "+marker
assert "melehat_video_end_p2p" in apiText
assert "PttForegroundService.ACTION_START" in text
assert 'applicationId = "com.melehat.telsiz"' in Path("app/build.gradle.kts").read_text()
video.write_text(text,encoding="utf-8")
api.write_text(apiText,encoding="utf-8")
print("MELEHAT_1371_REMOTE_VIDEO_AND_BOTH_SIDES_END_READY")
