package com.saomi.telsiz.p2p

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import com.saomi.telsiz.BuildConfig
import com.saomi.telsiz.auth.SessionRefresher
import com.saomi.telsiz.data.SessionStore
import com.saomi.telsiz.model.ChannelInfo
import com.saomi.telsiz.model.UserProfile
import com.saomi.telsiz.voice.LiveChannelUiState
import com.saomi.telsiz.voice.LiveMember
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeout
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import livekit.org.webrtc.*
import livekit.org.webrtc.audio.JavaAudioDeviceModule
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit

/**
 * Up to 4 authenticated MELEHAT users in one channel, direct P2P mesh.
 * One local audio track fans out to 1-3 peer connections. Supabase exchanges
 * protected SDP only; no TURN or LiveKit media service. Must be tested
 * with all members using this build; operator NAT may still block peers.
 */
class P2pMeshRadioClient(private val context:Context) {
    private val sessions=SessionStore(context)
    private val refresh=SessionRefresher(context)
    private val http=OkHttpClient.Builder().callTimeout(15,TimeUnit.SECONDS).build()
    private val scope=CoroutineScope(SupervisorJob()+Dispatchers.IO)
    private val jsonType="application/json".toMediaType()
    private val base=BuildConfig.SUPABASE_URL.trimEnd('/')+"/rest/v1/rpc/"
    private val connections=ConcurrentHashMap<String, Link>()
    private val speechMutex=Mutex()
    private var watchJob:Job?=null
    private var factory:PeerConnectionFactory?=null
    private var audioDevice:JavaAudioDeviceModule?=null
    private var micSource:AudioSource?=null
    @Volatile private var mic:AudioTrack?=null
    @Volatile private var running=false
    @Volatile private var admitted=true
    private var userId=""
    private var sessionId=""
    private var profile:UserProfile?=null
    private var room:ChannelInfo?=null
    private var epoch=0

    private class Link(
      val userId:String,val session:String,val pc:PeerConnection
    ) {
        @Volatile var connected=false
        @Volatile var offerRev=0
        @Volatile var answerRev=0
        var worker:Job?=null
    }

    private suspend fun rpc(name:String,json:JSONObject):JSONObject {
        var session=sessions.load()?:error("P2P_OTURUM_YOK")
        for(i in 0..1){
            val rq=Request.Builder().url(base+name)
                .header("apikey",BuildConfig.SUPABASE_PUBLISHABLE_KEY)
                .header("Authorization","Bearer "+session.accessToken)
                .post(json.toString().toRequestBody(jsonType)).build()
            val result=http.newCall(rq).execute().use{
                it.code to it.body?.string().orEmpty()
            }
            if(result.first==401 && i==0){
                session=refresh.refresh()?.takeIf{it.userId==userId}
                    ?:error("P2P_OTURUM_YENILENEMEDI")
                continue
            }
            if(result.first !in 200..299){
                val msg=runCatching{
                    JSONObject(result.second).optString("message")
                }.getOrDefault("")
                error("P2P_RPC_"+result.first+"_"+msg.take(70))
            }
            return JSONObject(result.second)
        }
        error("P2P_KIMLIK_HATASI")
    }

    private suspend fun presence(action:String):JSONObject =
        rpc("melehat_p2p_native_presence_rpc",
            JSONObject().put("p_action",action).put("p_room",room?.id)
                .put("p_session",sessionId))

    private suspend fun exchange(
      l:Link,act:String,sdp:String?=null,revision:Int=0
    ):JSONObject {
        val payload=JSONObject().put("p_action",act).put("p_room",room?.id)
            .put("p_session",sessionId).put("p_peer",l.userId)
            .put("p_peer_session",l.session).put("p_revision",revision)
        if(sdp!=null)payload.put("p_sdp",sdp)
        return rpc("melehat_p2p_native_signal_rpc",payload)
    }

    @Synchronized fun forceMute() {mic?.setEnabled(false)}
    fun isConnected():Boolean=running
    fun isConnectedTo(channelId:String):Boolean=
        running&&admitted&&room?.id==channelId&&connections.values.any{it.connected}

    suspend fun connect(p:UserProfile,c:ChannelInfo):Boolean {
        if(running&&room?.id==c.id)return true
        disconnect()
        if(!p.isComplete||sessions.load()==null){
            LiveChannelUiState.connectionProblem("P2P_OTURUM_GEREKLI")
            return false
        }
        if(context.checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=
            PackageManager.PERMISSION_GRANTED) {
            LiveChannelUiState.connectionProblem("P2P_MIKROFON_IZNI_GEREKLI")
            return false
        }
        profile=p;room=c
        userId=sessions.load()?.userId.orEmpty()
        sessionId=UUID.randomUUID().toString()
        val thisEpoch=++epoch
        LiveChannelUiState.roomId(c.id)
        LiveChannelUiState.roomName(c.name)
        LiveChannelUiState.status("CONNECTING")
        LiveChannelUiState.connectionProblem("P2P_ESLESIYOR")
        return try{
            presence("beat")
            createAudio()
            running=true
            watchJob=scope.launch{watch(thisEpoch)}
            true
        }catch(e:Exception){
            LiveChannelUiState.connectionProblem(
                "P2P_BASLATMA_"+e.javaClass.simpleName.take(20))
            destroyAllLinks()
            cleanupAudio()
            false
        }
    }

    suspend fun ensureConnected():Boolean {
        if(running)return true
        return connect(profile?:return false,room?:return false)
    }

    private fun createAudio(){
        if(factory!=null)return
        PeerConnectionFactory.initialize(
            PeerConnectionFactory.InitializationOptions
                .builder(context.applicationContext).createInitializationOptions())
        val audio=JavaAudioDeviceModule.builder(context.applicationContext)
            .createAudioDeviceModule()
        val fac=PeerConnectionFactory.builder()
            .setAudioDeviceModule(audio).createPeerConnectionFactory()
        val source=fac.createAudioSource(MediaConstraints())
        val track=fac.createAudioTrack("MELEHAT_GROUP_MIC",source)
        track.setEnabled(false)
        audioDevice=audio;factory=fac;micSource=source;mic=track
    }

    private fun cleanupAudio(){
        forceMute()
        mic?.dispose();mic=null
        micSource?.dispose();micSource=null
        factory?.dispose();factory=null
        audioDevice?.release();audioDevice=null
    }

    private fun linkTo(id:String,session:String):Link {
        val fac=factory?:error("P2P_FACTORY_YOK")
        val config=PeerConnection.RTCConfiguration(listOf(
            PeerConnection.IceServer.builder("stun:stun.l.google.com:19302")
                .createIceServer(),
            PeerConnection.IceServer.builder("stun:stun.cloudflare.com:3478")
                .createIceServer()))
        val pc=fac.createPeerConnection(config,object:PeerConnection.Observer{
            override fun onSignalingChange(value:PeerConnection.SignalingState?){}
            override fun onIceConnectionChange(value:PeerConnection.IceConnectionState?){
                val l=connections[id]?:return
                if(l.session!=session)return
                when(value){
                    PeerConnection.IceConnectionState.CONNECTED,
                    PeerConnection.IceConnectionState.COMPLETED -> l.connected=true
                    PeerConnection.IceConnectionState.DISCONNECTED,
                    PeerConnection.IceConnectionState.FAILED,
                    PeerConnection.IceConnectionState.CLOSED -> l.connected=false
                    else -> Unit
                }
                displayStatus()
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
                receiver?.track()?.setEnabled(true)
            }
        })?:error("P2P_AG_BAGLANTISI_OLUSTURULAMADI")
        if(pc.addTrack(mic?:error("P2P_MIKROFON_YOK"),
                listOf("melehat_group_audio"))==null){
            pc.dispose()
            error("P2P_AUDIO_TRACK_FAILED")
        }
        return Link(id,session,pc)
    }

    private fun displayStatus(){
        if(!running)return
        val live=connections.values.filter{it.connected}
        if(live.isNotEmpty()&&admitted) {
            LiveChannelUiState.status("LIVE")
            LiveChannelUiState.connectionProblem("")
            LiveChannelUiState.members(
                listOf(LiveMember(userId,profile?.fullName.orEmpty().ifBlank{"Ben"}))+
                    live.map{LiveMember(it.userId,"P2P üye")})
        } else {
            forceMute()
            LiveChannelUiState.status("CONNECTING")
            LiveChannelUiState.members(emptyList())
            LiveChannelUiState.connectionProblem(
                if(!admitted) "P2P_ILK_4_UYE_SINIRI"
                else if(connections.isEmpty()) "P2P_KARSI_UYE_BEKLENIYOR"
                else "P2P_AG_KURULUYOR")
        }
    }

    private fun remove(id:String){
        val l=connections.remove(id)?:return
        l.worker?.cancel()
        l.pc.close();l.pc.dispose()
        displayStatus()
    }

    private fun destroyAllLinks(){
        for(id in connections.keys.toList())remove(id)
    }

    private suspend fun createDescription(
        pc:PeerConnection,offer:Boolean
    ):SessionDescription {
        val result=CompletableDeferred<SessionDescription>()
        val cb=object:SdpObserver {
            override fun onCreateSuccess(value:SessionDescription?){
                if(value!=null)result.complete(value)
                else result.completeExceptionally(IllegalStateException("SDP_BOS"))
            }
            override fun onSetSuccess(){}
            override fun onCreateFailure(message:String?){
                result.completeExceptionally(IllegalStateException(message?:"SDP_CREATE_FAIL"))
            }
            override fun onSetFailure(message:String?){
                result.completeExceptionally(IllegalStateException(message?:"SDP_SET_FAIL"))
            }
        }
        if(offer)pc.createOffer(cb,MediaConstraints())
        else pc.createAnswer(cb,MediaConstraints())
        return withTimeout(15000L){result.await()}
    }

    private suspend fun applyDescription(
      pc:PeerConnection,local:Boolean,description:SessionDescription
    ){
        val done=CompletableDeferred<Unit>()
        val cb=object:SdpObserver {
            override fun onCreateSuccess(value:SessionDescription?){}
            override fun onSetSuccess(){done.complete(Unit)}
            override fun onCreateFailure(message:String?){
                done.completeExceptionally(IllegalStateException(message?:"SDP_CREATE_FAIL"))
            }
            override fun onSetFailure(message:String?){
                done.completeExceptionally(IllegalStateException(message?:"SDP_SET_FAIL"))
            }
        }
        if(local)pc.setLocalDescription(cb,description)
        else pc.setRemoteDescription(cb,description)
        withTimeout(15000L){done.await()}
    }

    private suspend fun awaitIce(pc:PeerConnection):String {
        var t=0L
        while(running && t<25000L &&
              pc.iceGatheringState()!=PeerConnection.IceGatheringState.COMPLETE) {
            delay(250L);t+=250L
        }
        return pc.localDescription?.description?:error("P2P_SDP_ICE_BOS")
    }

    private suspend fun negotiate(link:Link) {
        val leader=userId<link.userId
        while(scope.isActive && running && admitted && connections[link.userId]===link) {
            try {
                if(link.connected){delay(3000L);continue}
                if(leader){
                    if(link.offerRev==0) {
                        applyDescription(link.pc,true,createDescription(link.pc,true))
                        link.offerRev=exchange(link,"offer",awaitIce(link.pc))
                            .optInt("revision",0)
                    }
                    var checks=0
                    while(running && connections[link.userId]===link && !link.connected &&
                           link.answerRev==0 && checks<22){
                        val reply=exchange(link,"get")
                        val sdp=reply.optString("answer_sdp")
                        if(reply.optInt("answered_revision")==link.offerRev &&
                           sdp.startsWith("v=0") &&
                           link.pc.signalingState()==PeerConnection.SignalingState.HAVE_LOCAL_OFFER){
                            applyDescription(link.pc,false,
                                SessionDescription(SessionDescription.Type.ANSWER,sdp))
                            link.answerRev=link.offerRev
                            break
                        }
                        checks++
                        delay(1900L)
                    }
                    var waited=0L
                    while(running && connections[link.userId]===link &&
                          !link.connected && waited<12000L){
                        delay(1000L);waited+=1000L
                    }
                    if(!link.connected && connections[link.userId]===link){
                        remove(link.userId)
                        delay(1600L)
                    }
                    return
                } else {
                    val offer=exchange(link,"get")
                    val revision=offer.optInt("revision",0)
                    val sdp=offer.optString("offer_sdp")
                    if(revision>0 && sdp.startsWith("v=0") && revision!=link.answerRev){
                        if(link.answerRev>0){
                            remove(link.userId)
                            return
                        }
                        applyDescription(link.pc,false,
                            SessionDescription(SessionDescription.Type.OFFER,sdp))
                        applyDescription(link.pc,true,createDescription(link.pc,false))
                        exchange(link,"answer",awaitIce(link.pc),revision)
                        link.answerRev=revision
                    }
                }
            } catch(e:Exception) {
                if(running && connections[link.userId]===link)
                    LiveChannelUiState.connectionProblem(
                        "P2P_ICE_"+e.javaClass.simpleName.take(20))
                delay(2400L)
            }
            delay(2300L)
        }
    }

    private suspend fun watch(generation:Int) {
        while(running && scope.isActive && epoch==generation) {
            try {
                val res=presence("beat")
                admitted=res.optBoolean("selected",false)
                val arr=res.optJSONArray("peers")
                val allowed=mutableMapOf<String,String>()
                if(admitted&&arr!=null)
                    for(i in 0 until arr.length()){
                        val p=arr.getJSONObject(i)
                        val id=p.optString("user_id")
                        val sid=p.optString("session_id")
                        if(id.isNotBlank()&&sid.isNotBlank()&&id!=userId)
                            allowed[id]=sid
                    }
                for(id in connections.keys.toList())
                    if(allowed[id]!=connections[id]?.session)remove(id)
                for((id,sid) in allowed){
                    if(!connections.containsKey(id)){
                        val link=linkTo(id,sid)
                        connections[id]=link
                        link.worker=scope.launch{negotiate(link)}
                    }
                }
                displayStatus()
            } catch(e:Exception){
                LiveChannelUiState.connectionProblem(
                    "P2P_ESLESME_"+e.javaClass.simpleName.take(20))
            }
            delay(2500L)
        }
    }

    suspend fun setTransmitting(enabled:Boolean):Boolean {
        if(!enabled){
            forceMute()
            if(running)speechMutex.withLock{runCatching{presence("talk_off")}}
            return true
        }
        if(!isConnectedTo(room?.id.orEmpty())){
            forceMute()
            return false
        }
        mic?.setEnabled(true)
        val ok=mic?.enabled()==true
        if(ok)scope.launch{
            speechMutex.withLock{
                if(mic?.enabled()==true)runCatching{presence("talk_on")}
            }
        }
        return ok
    }

    suspend fun disconnect(){
        running=false;admitted=false;epoch++
        forceMute()
        val old=watchJob;watchJob=null
        old?.cancelAndJoin()
        destroyAllLinks()
        if(sessionId.isNotBlank()&&room!=null)runCatching{presence("leave")}
        cleanupAudio()
        userId="";sessionId="";room=null
        LiveChannelUiState.members(emptyList())
        LiveChannelUiState.status("OFFLINE")
        LiveChannelUiState.connectionProblem("")
    }
}
