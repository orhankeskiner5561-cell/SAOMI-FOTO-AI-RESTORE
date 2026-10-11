package com.saomi.telsiz.video

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.view.WindowManager
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.saomi.telsiz.data.LocalStore
import com.saomi.telsiz.data.SessionStore
import com.saomi.telsiz.service.PttForegroundService
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import livekit.org.webrtc.*
import livekit.org.webrtc.audio.JavaAudioDeviceModule
import org.json.JSONObject
import java.util.UUID

/**
 * Two-person DIRECT WebRTC video+audio in the actual MELEHAT Android app.
 * SDP is shared via authenticated and active-call-scoped Supabase RPC.
 * Media never enters a LiveKit room or the calling service.
 * Room-online presence is kept during the brief PTT audio suspension.
 *
 * This is NOT an SFU or 3/4-party group video service.
 */
class P2pVideoCallActivity : ComponentActivity() {
    companion object {
        const val EXTRA_CALL_ID = "melehat.video.call_id"
        const val EXTRA_HOST = "melehat.video.host"
    }

    private lateinit var api:VideoCallApi
    private lateinit var statusView:TextView
    private lateinit var localView:SurfaceViewRenderer
    private lateinit var remoteView:SurfaceViewRenderer
    private lateinit var micButton:Button
    private lateinit var cameraButton:Button
    private lateinit var reconnectButton:Button
    private var callId=""
    private var ended=false
    private var started=false
    private var connecting=false
    private var permissionWaiting=false
    private var pttWasOn=false
    private var roomId=""
    private val videoPresenceSession=UUID.randomUUID().toString()
    private var presenceJob:Job?=null
    private var mediaJob:Job?=null
    private var pollJob:Job?=null
    private var micEnabled=true
    private var cameraEnabled=true
    private var isCaller=false
    private var offerVersion=0

    private var egl:EglBase?=null
    private var pcFactory:PeerConnectionFactory?=null
    private var audioDevice:JavaAudioDeviceModule?=null
    private var capture:VideoCapturer?=null
    private var textureHelper:SurfaceTextureHelper?=null
    private var audioSource:AudioSource?=null
    private var videoSource:VideoSource?=null
    private var micTrack:AudioTrack?=null
    private var localCamera:VideoTrack?=null
    private var remoteCamera:VideoTrack?=null
    private var peer:PeerConnection?=null

    private val grantPermissions=registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ){ result ->
        permissionWaiting=false
        if(ended)return@registerForActivityResult
        if(result[Manifest.permission.CAMERA]==true &&
            result[Manifest.permission.RECORD_AUDIO]==true) startMedia()
        else notice("Kamera ve mikrofon izni gerekli. Ayarlardan izin verebilirsiniz.")
    }

    override fun onCreate(savedInstanceState:Bundle?) {
        super.onCreate(savedInstanceState)
        callId=intent.getStringExtra(EXTRA_CALL_ID).orEmpty()
        if(!callId.matches(Regex("[a-fA-F0-9-]{36}"))){finish();return}
        api=VideoCallApi(this)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        buildScreen()
        pollJob=lifecycleScope.launch {
            while(!ended) {
                try {
                    val current=api.poll().firstOrNull{it.id==callId}
                    when {
                        current==null -> { notice("Görüşme bulunamadı."); closeSoon() }
                        current.state in listOf("ended","declined","missed") ||
                            current.myState in listOf("left","missed","declined") -> {
                            notice("Görüşme sona erdi.");closeSoon()
                        }
                        current.state=="active" && !started && !permissionWaiting -> {
                            isCaller=current.callerId==SessionStore(this@P2pVideoCallActivity).load()?.userId
                            requestPermissionsIfNeeded()
                        }
                        current.state!="active" && !started ->
                            notice("Aranıyor… Karşı tarafın cevabı bekleniyor.")
                    }
                }catch(e:Exception){
                    if(!started)notice("Çağrı durumu kontrol ediliyor: "+e.javaClass.simpleName)
                }
                delay(1800)
            }
        }
    }

    private fun buildScreen(){
        val root=LinearLayout(this).apply {
            orientation=LinearLayout.VERTICAL
            setBackgroundColor(Color.rgb(20,25,38))
            setPadding(dp(12),dp(18),dp(12),dp(15))
        }
        setContentView(root)
        val title=TextView(this).apply{
            text="MELEHAT • Görüntülü Görüşme"
            setTextColor(Color.WHITE);textSize=21f
        }
        root.addView(title,LinearLayout.LayoutParams(-1,dp(45)))
        statusView=TextView(this).apply{
            text="Aranıyor… Karşı tarafın cevabı bekleniyor."
            setTextColor(Color.LTGRAY);textSize=15f;maxLines=3
        }
        root.addView(statusView,LinearLayout.LayoutParams(-1,dp(75)))
        val videoColumn=LinearLayout(this).apply{orientation=LinearLayout.VERTICAL}
        root.addView(videoColumn,LinearLayout.LayoutParams(-1,0,1f))
        fun frame(label:String):FrameLayout {
            val f=FrameLayout(this).apply{setBackgroundColor(Color.BLACK)}
            val text=TextView(this).apply{
                this.text=label
                setTextColor(Color.WHITE)
                setBackgroundColor(Color.argb(160,30,30,30))
                setPadding(dp(9),dp(7),dp(9),dp(7))
            }
            f.addView(text,FrameLayout.LayoutParams(-2,-2,Gravity.BOTTOM or Gravity.START))
            return f
        }
        val remoteFrame=frame("Karşı taraf")
        val localFrame=frame("Ben")
        videoColumn.addView(remoteFrame,LinearLayout.LayoutParams(-1,0,1f))
        videoColumn.addView(localFrame,LinearLayout.LayoutParams(-1,0,1f))
        remoteView=SurfaceViewRenderer(this).apply{setEnableHardwareScaler(true)}
        localView=SurfaceViewRenderer(this).apply{setEnableHardwareScaler(true);setMirror(true)}
        remoteFrame.addView(remoteView,0,FrameLayout.LayoutParams(-1,-1))
        localFrame.addView(localView,0,FrameLayout.LayoutParams(-1,-1))
        val controls=LinearLayout(this).apply{orientation=LinearLayout.HORIZONTAL}
        micButton=Button(this).apply{
            text="Mikrofon Kapat"
            isEnabled=false
            setOnClickListener{
                micEnabled=!micEnabled
                micTrack?.setEnabled(micEnabled)
                text=if(micEnabled)"Mikrofon Kapat" else "Mikrofon Aç"
            }
        }
        cameraButton=Button(this).apply{
            text="Kamera Kapat"
            isEnabled=false
            setOnClickListener{
                cameraEnabled=!cameraEnabled
                localCamera?.setEnabled(cameraEnabled)
                text=if(cameraEnabled)"Kamera Kapat" else "Kamera Aç"
            }
        }
        controls.addView(micButton,LinearLayout.LayoutParams(0,dp(55),1f))
        controls.addView(cameraButton,LinearLayout.LayoutParams(0,dp(55),1f))
        root.addView(controls)
        reconnectButton=Button(this).apply{
            text="Bağlantıyı Yeniden Dene"
            isEnabled=false
            setOnClickListener{
                if(!ended){notice("Görüntülü bağlantı tekrar kuruluyor…");restartMedia()}
            }
        }
        root.addView(reconnectButton,LinearLayout.LayoutParams(-1,dp(50)))
        root.addView(Button(this).apply{
            text="Görüşmeyi Bitir / Kapat"
            setBackgroundColor(Color.rgb(175,35,40))
            setTextColor(Color.WHITE)
            setOnClickListener{hangUp()}
        },LinearLayout.LayoutParams(-1,dp(55)))
    }

    private fun dp(n:Int)=(resources.displayMetrics.density*n).toInt()
    private fun notice(s:String)=runOnUiThread {if(!ended)statusView.text=s}

    private fun requestPermissionsIfNeeded(){
        if(ended||started||permissionWaiting)return
        val perms=arrayOf(Manifest.permission.CAMERA,Manifest.permission.RECORD_AUDIO)
        val missing=perms.any{ContextCompat.checkSelfPermission(this,it)!=PackageManager.PERMISSION_GRANTED}
        if(missing){permissionWaiting=true;grantPermissions.launch(perms)}
        else startMedia()
    }

    private fun startMedia(){
        if(ended||started||connecting)return
        started=true;connecting=true
        mediaJob=lifecycleScope.launch {
            try {
                // Preserve the user in the online member/room list throughout the call.
                val local=LocalStore(this@P2pVideoCallActivity)
                roomId=local.loadActiveChannel().id
                pttWasOn=local.isRadioEnabled()
                if(pttWasOn){
                    runCatching{api.videoPresence(roomId,videoPresenceSession,true)}
                    presenceJob=lifecycleScope.launch {
                        while(!ended) {
                            runCatching{api.videoPresence(roomId,videoPresenceSession,true)}
                            delay(3500L)
                        }
                    }
                    // Stop the PTT audio device only AFTER online presence is set.
                    startService(Intent(this@P2pVideoCallActivity,
                        PttForegroundService::class.java).apply{
                        action=PttForegroundService.ACTION_STOP
                    })
                }
                withContext(Dispatchers.Main){createRtc()}
                notice("Kamera hazır. Telefonlar arasında P2P bağlantısı kuruluyor…")
                if(isCaller)makeOffer() else waitAndAnswer()
            }catch(e:Exception){
                notice("P2P görüntülü bağlantı kurulamadı: "+(e.message?:e.javaClass.simpleName).take(130))
                runOnUiThread {reconnectButton.isEnabled=true}
            }finally{connecting=false}
        }
    }

    private fun createRtc(){
        PeerConnectionFactory.initialize(PeerConnectionFactory.InitializationOptions
            .builder(applicationContext).createInitializationOptions())
        egl=EglBase.create()
        val eglContext=egl?.eglBaseContext?:error("EGL görüntü motoru yok")
        remoteView.init(eglContext,null)
        localView.init(eglContext,null)
        val module=JavaAudioDeviceModule.builder(applicationContext).createAudioDeviceModule()
        audioDevice=module
        val built=PeerConnectionFactory.builder().setAudioDeviceModule(module)
            .createPeerConnectionFactory()
        pcFactory=built
        val micSourceBuilt=built.createAudioSource(MediaConstraints())
        audioSource=micSourceBuilt
        micTrack=built.createAudioTrack("MELEHAT_VIDEO_AUDIO",micSourceBuilt).apply{
            setEnabled(micEnabled)
        }
        val enumerator=Camera2Enumerator(this)
        val front=enumerator.deviceNames.firstOrNull{enumerator.isFrontFacing(it)}
        val back=enumerator.deviceNames.firstOrNull{enumerator.isBackFacing(it)}
        val name=front?:back?:error("Kamera bulunamadı")
        val capturer=enumerator.createCapturer(name,null)?:error("Kamera açılamadı")
        capture=capturer
        val helper=SurfaceTextureHelper.create("MELEHAT_P2P_CAMERA",eglContext)
        textureHelper=helper
        val source=built.createVideoSource(false)
        videoSource=source
        capturer.initialize(helper,applicationContext,source.capturerObserver)
        capturer.startCapture(640,480,20)
        val camera=built.createVideoTrack("MELEHAT_VIDEO_CAMERA",source)
        localCamera=camera
        camera.addSink(localView)
        val configuration=PeerConnection.RTCConfiguration(listOf(
            PeerConnection.IceServer.builder("stun:stun.l.google.com:19302").createIceServer(),
            PeerConnection.IceServer.builder("stun:stun.cloudflare.com:3478").createIceServer()))
        peer=built.createPeerConnection(configuration,object:PeerConnection.Observer{
            override fun onSignalingChange(state:PeerConnection.SignalingState?){}
            override fun onIceConnectionChange(state:PeerConnection.IceConnectionState?){
                when(state){
                    PeerConnection.IceConnectionState.CONNECTED,
                    PeerConnection.IceConnectionState.COMPLETED -> {
                        notice("P2P ses ve görüntü bağlantısı kuruldu")
                        runOnUiThread{reconnectButton.isEnabled=false}
                    }
                    PeerConnection.IceConnectionState.DISCONNECTED,
                    PeerConnection.IceConnectionState.FAILED -> {
                        notice("P2P bağlantısı kesildi veya kurulamadı. Tekrar deneyebilirsiniz.")
                        runOnUiThread{reconnectButton.isEnabled=true}
                    }
                    else -> Unit
                }
            }
            override fun onIceConnectionReceivingChange(value:Boolean){}
            override fun onIceGatheringChange(value:PeerConnection.IceGatheringState?){}
            override fun onIceCandidate(value:IceCandidate?){}
            override fun onIceCandidatesRemoved(value:Array<out IceCandidate>?){}
            override fun onAddStream(value:MediaStream?){}
            override fun onRemoveStream(value:MediaStream?){}
            override fun onDataChannel(value:DataChannel?){}
            override fun onRenegotiationNeeded(){}
            override fun onAddTrack(receiver:RtpReceiver?,streams:Array<out MediaStream>?){
                val incoming=receiver?.track()
                if(incoming is VideoTrack){
                    runOnUiThread{
                        remoteCamera?.removeSink(remoteView)
                        remoteCamera=incoming
                        incoming.addSink(remoteView)
                    }
                }
            }
        })?:error("P2P görüşme bağlantısı açılamadı")
        val pc=peer?:error("P2P bağlantısı yok")
        if(pc.addTrack(micTrack!!,listOf("melehat_video"))==null ||
           pc.addTrack(camera,listOf("melehat_video"))==null)
           error("Kamera veya mikrofon bağlantıya eklenemedi")
        micButton.isEnabled=true
        cameraButton.isEnabled=true
    }

    private suspend fun makeOffer(){
        val pc=peer?:error("P2P bağlantısı yok")
        applySdp(pc,true,makeSdp(pc,true))
        val offer=awaitIce(pc)
        val result=api.videoExchange(callId,"offer",offer)
        offerVersion=result.optInt("revision",0)
        notice("Görüntülü davet kabul edildi. Karşı telefonun yanıtı bekleniyor…")
        var checks=0
        while(!ended&&checks<40){
            val result=api.videoExchange(callId,"get")
            val sdp=result.optString("answer_sdp")
            if(result.optInt("answered_revision")==offerVersion&&
                sdp.startsWith("v=0") &&
                pc.signalingState()==PeerConnection.SignalingState.HAVE_LOCAL_OFFER){
                applySdp(pc,false,SessionDescription(SessionDescription.Type.ANSWER,sdp))
                notice("Telefonlar arasında görüntülü bağlantı kontrol ediliyor…")
                return
            }
            delay(1600L);checks++
        }
        if(!ended)error("Karşı telefondan görüntü yanıtı alınamadı")
    }

    private suspend fun waitAndAnswer(){
        val pc=peer?:error("P2P bağlantısı yok")
        notice("Arayan telefonun P2P görüntü teklifi bekleniyor…")
        var checks=0
        while(!ended&&checks<45){
            val result=api.videoExchange(callId,"get")
            val sdp=result.optString("offer_sdp")
            val rev=result.optInt("revision",0)
            if(rev>0&&sdp.startsWith("v=0")){
                applySdp(pc,false,SessionDescription(SessionDescription.Type.OFFER,sdp))
                applySdp(pc,true,makeSdp(pc,false))
                api.videoExchange(callId,"answer",awaitIce(pc),rev)
                notice("Yanıt gönderildi. Görüntü bağlantısı kuruluyor…")
                return
            }
            delay(1600L);checks++
        }
        if(!ended)error("Arayan telefondan P2P teklif alınamadı")
    }

    private suspend fun makeSdp(pc:PeerConnection,offer:Boolean):SessionDescription{
        val promise=CompletableDeferred<SessionDescription>()
        val callback=object:SdpObserver{
            override fun onCreateSuccess(sdp:SessionDescription?){
                if(sdp!=null)promise.complete(sdp)
                else promise.completeExceptionally(IllegalStateException("SDP boş"))
            }
            override fun onSetSuccess(){}
            override fun onCreateFailure(s:String?){
                promise.completeExceptionally(IllegalStateException(s?:"SDP hatası"))
            }
            override fun onSetFailure(s:String?){
                promise.completeExceptionally(IllegalStateException(s?:"SDP hatası"))
            }
        }
        if(offer)pc.createOffer(callback,MediaConstraints())
        else pc.createAnswer(callback,MediaConstraints())
        return withTimeout(18000L){promise.await()}
    }

    private suspend fun applySdp(pc:PeerConnection,local:Boolean,sdp:SessionDescription){
        val promise=CompletableDeferred<Unit>()
        val callback=object:SdpObserver{
            override fun onCreateSuccess(sdp:SessionDescription?){}
            override fun onSetSuccess(){promise.complete(Unit)}
            override fun onCreateFailure(s:String?){
                promise.completeExceptionally(IllegalStateException(s?:"SDP hatası"))
            }
            override fun onSetFailure(s:String?){
                promise.completeExceptionally(IllegalStateException(s?:"SDP hatası"))
            }
        }
        if(local)pc.setLocalDescription(callback,sdp)
        else pc.setRemoteDescription(callback,sdp)
        withTimeout(18000L){promise.await()}
    }

    private suspend fun awaitIce(pc:PeerConnection):String{
        var t=0L
        while(!ended&&t<27000L&&
            pc.iceGatheringState()!=PeerConnection.IceGatheringState.COMPLETE){
            delay(250L);t+=250
        }
        return pc.localDescription?.description?:error("Ağ bağlantı adayları toplanamadı")
    }

    private fun restartMedia(){
        if(ended||connecting)return
        started=false
        mediaJob?.cancel()
        disposeRtc()
        startMedia()
    }

    private fun closeSoon(){
        if(ended)return
        ended=true
        lifecycleScope.launch {delay(1200);finish()}
    }

    private fun hangUp(){
        if(ended){finish();return}
        ended=true
        lifecycleScope.launch {
            runCatching{api.end(callId)}
            finish()
        }
    }

    private fun disposeRtc(){
        runCatching{remoteCamera?.removeSink(remoteView)}
        runCatching{localCamera?.removeSink(localView)}
        remoteCamera=null
        runCatching{peer?.close()}
        runCatching{peer?.dispose()}
        peer=null
        runCatching{capture?.stopCapture()}
        runCatching{capture?.dispose()}
        capture=null
        runCatching{textureHelper?.dispose()}
        textureHelper=null
        runCatching{micTrack?.setEnabled(false)}
        runCatching{micTrack?.dispose()}
        micTrack=null
        runCatching{localCamera?.dispose()}
        localCamera=null
        runCatching{audioSource?.dispose()}
        audioSource=null
        runCatching{videoSource?.dispose()}
        videoSource=null
        runCatching{pcFactory?.dispose()}
        pcFactory=null
        runCatching{audioDevice?.release()}
        audioDevice=null
        runCatching{localView.release()}
        runCatching{remoteView.release()}
        runCatching{egl?.release()}
        egl=null
    }

    override fun onDestroy(){
        ended=true
        pollJob?.cancel()
        mediaJob?.cancel()
        presenceJob?.cancel()
        disposeRtc()
        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        if(pttWasOn){
            // Foreground radio resumes in the last selected room after video.
            ContextCompat.startForegroundService(this,Intent(this,
                PttForegroundService::class.java).apply{
                action=PttForegroundService.ACTION_START
            })
        }
        if(roomId.isNotBlank()){
            // Leave late so PTT registration has time to resume without offline blink.
            val app=applicationContext
            val lastRoom=roomId
            val session=videoPresenceSession
            kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.SupervisorJob()+
                Dispatchers.IO).launch{
                delay(if(pttWasOn)5000L else 0L)
                runCatching{VideoCallApi(app).videoPresence(lastRoom,session,false)}
            }
        }
        super.onDestroy()
    }
}
