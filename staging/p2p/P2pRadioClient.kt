package com.saomi.telsiz.p2p

import android.content.Context
import android.content.pm.PackageManager
import android.Manifest
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
import kotlinx.coroutines.withTimeout
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import livekit.org.webrtc.*
import livekit.org.webrtc.audio.JavaAudioDeviceModule
import java.util.UUID
import java.util.concurrent.TimeUnit

/**
 * Native, authenticated, direct peer-to-peer audio for TWO registered
 * MELEHAT users listening to the same room. No browser and no LiveKit room.
 * SDP is exchanged by a private Supabase RPC; audio only by WebRTC.
 * The PTT microphone audio track defaults to disabled and every release
 * synchronously disables it before network work.
 */
class P2pRadioClient(private val context: Context) {
    private val sessions = SessionStore(context)
    private val refresh = SessionRefresher(context)
    private val http = OkHttpClient.Builder().callTimeout(15, TimeUnit.SECONDS).build()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val jsonType = "application/json".toMediaType()
    private val base = BuildConfig.SUPABASE_URL.trimEnd('/') + "/rest/v1/rpc/"
    private var loop: Job? = null
    private var factory: PeerConnectionFactory? = null
    private var adm: JavaAudioDeviceModule? = null
    private var source: AudioSource? = null
    @Volatile private var track: AudioTrack? = null
    @Volatile private var peer: PeerConnection? = null
    @Volatile private var running = false
    @Volatile private var online = false
    private var channel: ChannelInfo? = null
    private var profile: UserProfile? = null
    private var selfId = ""
    private var peerId = ""
    private var peerSession = ""
    private var sessionId = ""
    private var seenRevision = 0
    private var offeredRevision = 0
    private var answeredRevision = 0
    private var lastAttempt = 0L
    private var peerName = ""
    private var generation = 0

    private suspend fun rpc(name: String, body: JSONObject): JSONObject {
        var auth = sessions.load() ?: error("P2P_OTURUM_YOK")
        for (attempt in 0..1) {
            val req = Request.Builder().url(base + name)
                .header("apikey", BuildConfig.SUPABASE_PUBLISHABLE_KEY)
                .header("Authorization", "Bearer " + auth.accessToken)
                .post(body.toString().toRequestBody(jsonType)).build()
            val (code, response) = http.newCall(req).execute().use {
                it.code to it.body?.string().orEmpty()
            }
            if (code == 401 && attempt == 0) {
                auth = refresh.refresh()?.takeIf { it.userId == selfId }
                    ?: error("P2P_OTURUM_YENILENEMEDI")
                continue
            }
            if (code !in 200..299) {
                val message = runCatching {
                    JSONObject(response).optString("message")
                }.getOrDefault("")
                error("P2P_RPC_$code " + message.take(100))
            }
            return JSONObject(response)
        }
        error("P2P_IZIN_HATASI")
    }

    private suspend fun presence(action: String): JSONObject =
        rpc("melehat_p2p_native_presence_rpc",
            JSONObject().put("p_action",action).put("p_room",channel?.id)
                .put("p_session",sessionId))

    private suspend fun signaling(
        action: String, sdp: String? = null, revision: Int = 0
    ): JSONObject {
        val o = JSONObject().put("p_action", action)
            .put("p_room",channel?.id)
            .put("p_session",sessionId)
            .put("p_peer",peerId)
            .put("p_peer_session",peerSession)
            .put("p_revision",revision)
        if (sdp != null) o.put("p_sdp",sdp)
        return rpc("melehat_p2p_native_signal_rpc",o)
    }

    @Synchronized fun forceMute() {
        track?.setEnabled(false)
    }

    fun isConnected(): Boolean = running
    fun isConnectedTo(id: String): Boolean =
        running && online && channel?.id == id

    suspend fun connect(p: UserProfile, target: ChannelInfo): Boolean {
        if (running && channel?.id == target.id) return true
        disconnect()
        if (!p.isComplete || sessions.load() == null) {
            LiveChannelUiState.connectionProblem("P2P_OTURUM_GEREKLI")
            return false
        }
        if (context.checkSelfPermission(Manifest.permission.RECORD_AUDIO) !=
            PackageManager.PERMISSION_GRANTED) {
            LiveChannelUiState.connectionProblem("P2P_MIKROFON_IZNI_GEREKLI")
            return false
        }
        profile=p;channel=target
        selfId = sessions.load()?.userId.orEmpty()
        sessionId = UUID.randomUUID().toString()
        peerId="";peerSession="";generation++
        LiveChannelUiState.status("CONNECTING")
        LiveChannelUiState.roomId(target.id)
        LiveChannelUiState.roomName(target.name)
        LiveChannelUiState.connectionProblem("P2P_ESLESIYOR")
        return try {
            // Validate login/room membership before keeping a WebRTC device alive.
            presence("beat")
            initializeWebRtc()
            running=true
            loop=scope.launch { watchPeers(generation) }
            true
        } catch (e: Exception) {
            LiveChannelUiState.connectionProblem(
                "P2P_BASLATILAMADI_" + e.javaClass.simpleName.take(25))
            stopPeer()
            false
        }
    }

    suspend fun ensureConnected(): Boolean {
        if (running) return true
        val p = profile ?: return false
        val c = channel ?: return false
        return connect(p,c)
    }

    private fun initializeWebRtc() {
        if (factory != null) return
        PeerConnectionFactory.initialize(
            PeerConnectionFactory.InitializationOptions.builder(context.applicationContext)
                .createInitializationOptions())
        val module = JavaAudioDeviceModule.builder(context.applicationContext)
            .createAudioDeviceModule()
        val built = PeerConnectionFactory.builder()
            .setAudioDeviceModule(module)
            .createPeerConnectionFactory()
        adm = module
        factory = built
    }

    private fun stopPeer() {
        forceMute()
        online=false
        peer?.close()
        peer?.dispose()
        peer=null
        track?.dispose()
        track=null
        source?.dispose()
        source=null
        seenRevision=0;offeredRevision=0;answeredRevision=0
        LiveChannelUiState.remoteAudioLevel(0f)
        if (running) {
            LiveChannelUiState.members(emptyList())
            LiveChannelUiState.status("CONNECTING")
        }
    }

    private fun beginPeer() {
        stopPeer()
        val localFactory=factory ?: error("P2P_FACTORY_MISSING")
        val configuration=PeerConnection.RTCConfiguration(listOf(
            PeerConnection.IceServer.builder("stun:stun.l.google.com:19302")
                .createIceServer(),
            PeerConnection.IceServer.builder("stun:stun.cloudflare.com:3478")
                .createIceServer()))
        val connection=localFactory.createPeerConnection(configuration,
            object : PeerConnection.Observer {
                override fun onSignalingChange(p0: PeerConnection.SignalingState?) {}
                override fun onIceConnectionChange(state: PeerConnection.IceConnectionState?) {
                    when(state) {
                        PeerConnection.IceConnectionState.CONNECTED,
                        PeerConnection.IceConnectionState.COMPLETED -> {
                            online=true
                            LiveChannelUiState.status("LIVE")
                            LiveChannelUiState.connectionProblem("")
                            LiveChannelUiState.members(listOf(
                                LiveMember(selfId,profile?.fullName.orEmpty().ifBlank { "Ben" }),
                                LiveMember(peerId,peerName.ifBlank { "P2P üye" })))
                        }
                        PeerConnection.IceConnectionState.DISCONNECTED,
                        PeerConnection.IceConnectionState.FAILED,
                        PeerConnection.IceConnectionState.CLOSED -> {
                            online=false
                            forceMute()
                            if(running) {
                                LiveChannelUiState.status("CONNECTING")
                                LiveChannelUiState.connectionProblem("P2P_BAGLANTI_KOPTU")
                            }
                        }
                        else -> Unit
                    }
                }
                override fun onIceConnectionReceivingChange(p0: Boolean) {}
                override fun onIceGatheringChange(p0: PeerConnection.IceGatheringState?) {}
                override fun onIceCandidate(candidate: IceCandidate?) {}
                override fun onIceCandidatesRemoved(candidates: Array<out IceCandidate>?) {}
                override fun onAddStream(stream: MediaStream?) {}
                override fun onRemoveStream(stream: MediaStream?) {}
                override fun onDataChannel(channel: DataChannel?) {}
                override fun onRenegotiationNeeded() {}
                override fun onAddTrack(receiver: RtpReceiver?, mediaStreams: Array<out MediaStream>?) {
                    receiver?.track()?.setEnabled(true)
                }
            }) ?: error("P2P_PEER_CREATE_FAILED")
        val localSource=localFactory.createAudioSource(MediaConstraints())
        val localTrack=localFactory.createAudioTrack("MELEHAT_NATIVE_MIC", localSource)
        localTrack.setEnabled(false)
        source=localSource
        track=localTrack
        peer=connection
        val sender=connection.addTrack(localTrack,listOf("melehat_native_voice"))
        if(sender==null) error("P2P_AUDIO_TRACK_ATTACH_FAILED")
    }

    private suspend fun makeOffer(): SessionDescription =
        suspendSdp { obs -> peer?.createOffer(obs,MediaConstraints()) }

    private suspend fun makeAnswer(): SessionDescription =
        suspendSdp { obs -> peer?.createAnswer(obs,MediaConstraints()) }

    private suspend fun suspendSdp(start: (SdpObserver)->Unit): SessionDescription {
        val promise=CompletableDeferred<SessionDescription>()
        start(object:SdpObserver {
            override fun onCreateSuccess(desc:SessionDescription?) {
                if(desc==null) promise.completeExceptionally(
                    IllegalStateException("SDP_EMPTY"))
                else promise.complete(desc)
            }
            override fun onSetSuccess() {}
            override fun onCreateFailure(reason:String?) {
                promise.completeExceptionally(IllegalStateException(reason?: "SDP_CREATE_FAILED"))
            }
            override fun onSetFailure(reason:String?) {
                promise.completeExceptionally(IllegalStateException(reason?: "SDP_SET_FAILED"))
            }
        })
        return withTimeout(14000L){promise.await()}
    }

    private suspend fun applySdp(local: Boolean, desc: SessionDescription) {
        val promise=CompletableDeferred<Unit>()
        val callback=object:SdpObserver {
            override fun onCreateSuccess(value:SessionDescription?) {}
            override fun onSetSuccess() {promise.complete(Unit)}
            override fun onCreateFailure(reason:String?) {
                promise.completeExceptionally(IllegalStateException(reason?:"CREATE_FAILED"))
            }
            override fun onSetFailure(reason:String?) {
                promise.completeExceptionally(IllegalStateException(reason?:"SET_FAILED"))
            }
        }
        val conn=peer ?: error("P2P_PEER_GONE")
        if(local)conn.setLocalDescription(callback,desc)
        else conn.setRemoteDescription(callback,desc)
        withTimeout(14000L){promise.await()}
    }

    private suspend fun waitCandidates(): String {
        val conn=peer ?: error("P2P_PEER_GONE")
        var elapsed=0L
        while(running && elapsed<25000L &&
             conn.iceGatheringState()!=PeerConnection.IceGatheringState.COMPLETE) {
            delay(200L)
            elapsed+=200L
        }
        return conn.localDescription?.description ?: error("P2P_NO_LOCAL_SDP")
    }

    private suspend fun offer() {
        beginPeer()
        applySdp(true,makeOffer())
        val sdp=waitCandidates()
        val result=signaling("offer",sdp)
        offeredRevision=result.optInt("revision",0)
        lastAttempt=System.currentTimeMillis()
        LiveChannelUiState.connectionProblem("P2P_KARSI_TARAF_BEKLENIYOR")
    }

    private suspend fun answer(revision: Int, sdp: String) {
        beginPeer()
        applySdp(false,SessionDescription(SessionDescription.Type.OFFER,sdp))
        applySdp(true,makeAnswer())
        val localSdp=waitCandidates()
        signaling("answer",localSdp,revision)
        seenRevision=revision
        LiveChannelUiState.connectionProblem("P2P_DOGRULANIYOR")
    }

    private suspend fun watchPeers(epoch: Int) {
        while(scope.isActive && running && generation==epoch) {
            try {
                val heartbeat=presence("beat")
                val other=heartbeat.optString("peer_id").takeUnless {
                    it.isBlank() || it=="null"
                }.orEmpty()
                val otherSession=heartbeat.optString("peer_session").takeUnless {
                    it.isBlank() || it=="null"
                }.orEmpty()
                val overLimit=heartbeat.optBoolean("too_many")
                if(overLimit) {
                    if(peer!=null)stopPeer()
                    peerId="";peerSession=""
                    LiveChannelUiState.connectionProblem("P2P_IKI_KISI_SINIRI")
                } else if(other.isBlank()||otherSession.isBlank()) {
                    if(peer!=null)stopPeer()
                    peerId="";peerSession=""
                    LiveChannelUiState.connectionProblem("P2P_KARSI_UYE_BEKLENIYOR")
                } else {
                    if(peerId!=other || peerSession!=otherSession) {
                        if(peer!=null)stopPeer()
                        peerId=other;peerSession=otherSession
                        lastAttempt=0L
                    }
                    if (selfId < other) {
                        if(peer==null || (!online &&
                            System.currentTimeMillis()-lastAttempt>35000L)) offer()
                        else if(offeredRevision>0 && !online) {
                            val result=signaling("get")
                            if(result.optInt("answered_revision")==offeredRevision) {
                                val sdp=result.optString("answer_sdp")
                                if(sdp.startsWith("v=0") &&
                                    peer?.signalingState()==PeerConnection.SignalingState.HAVE_LOCAL_OFFER) {
                                    applySdp(false,SessionDescription(SessionDescription.Type.ANSWER,sdp))
                                    LiveChannelUiState.connectionProblem("P2P_AG_TESTI")
                                }
                            }
                        }
                    } else {
                        val result=signaling("get")
                        val revision=result.optInt("revision",0)
                        val sdp=result.optString("offer_sdp")
                        if(revision>0 && sdp.startsWith("v=0") &&
                            revision!=seenRevision) answer(revision,sdp)
                    }
                }
            } catch(e:Exception) {
                if(running)LiveChannelUiState.connectionProblem(
                    "P2P_AG_HATASI_" + e.javaClass.simpleName.take(22))
                delay(2500L)
            }
            delay(2500L)
        }
    }

    suspend fun setTransmitting(enabled:Boolean):Boolean {
        if(!enabled) {forceMute();return true}
        if(!online || !running || peer==null) {
            forceMute()
            return false
        }
        track?.setEnabled(true)
        return track?.enabled()==true
    }

    suspend fun disconnect() {
        running=false;generation++
        forceMute()
        val old=loop
        loop=null
        old?.cancelAndJoin()
        if(sessionId.isNotBlank() && channel!=null) {
            runCatching {presence("leave")}
        }
        stopPeer()
        channel=null
        peerId="";peerSession="";sessionId=""
        LiveChannelUiState.status("OFFLINE")
        LiveChannelUiState.members(emptyList())
        LiveChannelUiState.connectionProblem("")
    }
}
