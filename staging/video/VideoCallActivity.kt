package com.saomi.telsiz.video

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.BackHandler
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.saomi.telsiz.data.LocalStore
import com.saomi.telsiz.service.PttForegroundService
import com.saomi.telsiz.data.BackendApi
import com.saomi.telsiz.data.SessionStore
import io.livekit.android.LiveKit
import io.livekit.android.events.RoomEvent
import io.livekit.android.events.collect
import io.livekit.android.room.Room
import io.livekit.android.room.track.VideoTrack
import io.livekit.android.room.track.Track
import io.livekit.android.renderer.SurfaceViewRenderer
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Isolated authenticated video room. The walkie-talkie microphone is never
 * published into the video call; its foreground service is suspended during
 * video and the user's previous PTT channel is restored on exit.
 */
data class VideoTileModel(val identity: String, val label: String, val track: VideoTrack?)

class VideoCallActivity : ComponentActivity() {
    companion object {
        const val EXTRA_CALL_ID = "melehat.video.call_id"
        const val EXTRA_HOST = "melehat.video.host"
    }

    private lateinit var api: VideoCallApi
    private var callId: String = ""
    private var host: Boolean = false
    private var room: Room? = null
    private var connectionJob: Job? = null
    private var pttWasOn = false
    private var videoStarted = false
    private var callEnded = false
    private var automaticCloseStarted = false
    private var status by mutableStateOf("Aranıyor…")
    private var cameraOn by mutableStateOf(true)
    private var microphoneOn by mutableStateOf(true)
    private var online by mutableStateOf(false)
    private val remoteTiles = mutableStateListOf<VideoTileModel>()
    private var localTrack by mutableStateOf<VideoTrack?>(null)
    private var memberChoices by mutableStateOf<List<Pair<String, String>>>(emptyList())
    private var inviteOpen by mutableStateOf(false)

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { granted ->
        if (granted[Manifest.permission.CAMERA] == true &&
            granted[Manifest.permission.RECORD_AUDIO] == true) connectVideo()
        else status = "Kamera ve mikrofon izni olmadan görüşmeye katılamazsınız."
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        callId = intent.getStringExtra(EXTRA_CALL_ID).orEmpty()
        host = intent.getBooleanExtra(EXTRA_HOST, false)
        if (!callId.matches(Regex("[a-fA-F0-9-]{36}"))) { finish(); return }
        api = VideoCallApi(this)

        setContent {
            MaterialTheme {
                CallView(
                    status = status,
                    videoRoom = room,
                    localVideo = localTrack,
                    remoteVideos = remoteTiles.toList(),
                    videoStarted = videoStarted,
                    cameraOn = cameraOn,
                    microphoneOn = microphoneOn,
                    canInvite = host && online,
                    inviteOpen = inviteOpen,
                    choices = memberChoices,
                    onClose = { hangUp() },
                    onCamera = { toggleCamera() },
                    onMicrophone = { toggleMicrophone() },
                    onInvite = { inviteOpen = true; loadMemberChoices() },
                    onInviteDismiss = { inviteOpen = false },
                    onInviteMember = { target ->
                        lifecycleScope.launch {
                            runCatching { api.invite(callId, target) }
                                .onSuccess { status = "Davet gönderildi. Kişinin onayı bekleniyor."; inviteOpen = false }
                                .onFailure { status = it.message ?: "Davet gönderilemedi." }
                        }
                    }
                )
                BackHandler { hangUp() }
            }
        }
        lifecycleScope.launch {
            while (!callEnded) {
                runCatching { api.poll() }.onSuccess { list ->
                    val current = list.firstOrNull { it.id == callId }
                    when {
                        current == null -> { status = "Görüşme bulunamadı."; callEnded = true }
                        current.state == "declined" -> {
                            status = "Arama reddedildi."; callEnded = true
                        }
                        current.state == "missed" -> {
                            status = "Cevap vermedi."; callEnded = true
                        }
                        current.state == "ended" || current.myState == "left" -> {
                            status = "Görüşme sona erdi."; callEnded = true
                        }
                        current.state == "active" -> {
                            online = true
                            if (!videoStarted) requestVideoPermissions()
                        }
                        else -> status = "Aranıyor… Karşı tarafın cevabı bekleniyor."
                    }
                }.onFailure { status = "Bağlantı kontrol ediliyor…" }
                if (callEnded && !automaticCloseStarted) {
                    automaticCloseStarted = true
                    val finalNotice = status
                    lifecycleScope.launch {
                        delay(2500)
                        android.widget.Toast.makeText(
                            this@VideoCallActivity, finalNotice, android.widget.Toast.LENGTH_LONG
                        ).show()
                        finish()
                    }
                }
                delay(1600)
            }
        }
    }

    private fun requestVideoPermissions() {
        if (videoStarted || callEnded) return
        val required = arrayOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO)
        val missing = required.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isEmpty()) connectVideo()
        else {
            // Mark pending connection before permission prompt to avoid repeated requests.
            videoStarted = true
            permissionLauncher.launch(required)
        }
    }

    private fun suspendRadio() {
        val local = LocalStore(this)
        if (local.isRadioEnabled()) {
            pttWasOn = true
            startService(Intent(this, PttForegroundService::class.java).apply {
                action = PttForegroundService.ACTION_STOP
            })
        }
    }

    private fun connectVideo() {
        if (room != null || callEnded) return
        videoStarted = true
        suspendRadio()
        connectionJob?.cancel()
        connectionJob = lifecycleScope.launch {
            runCatching {
                val credentials = api.credentials(callId)
                // A distinct LiveKit room, NEVER the selected walkie-talkie channel.
                delay(300) // allow PTT floor/microphone to release
                val videoRoom = LiveKit.create(applicationContext)
                room = videoRoom
                launch {
                    videoRoom.events.collect { event ->
                        when (event) {
                            is RoomEvent.TrackSubscribed -> updateRemoteTiles(videoRoom)
                            is RoomEvent.TrackUnsubscribed -> updateRemoteTiles(videoRoom)
                            is RoomEvent.ParticipantConnected -> updateRemoteTiles(videoRoom)
                            is RoomEvent.ParticipantDisconnected -> updateRemoteTiles(videoRoom)
                            is RoomEvent.Disconnected -> status = "Görüşme bağlantısı kesildi."
                            else -> Unit
                        }
                    }
                }
                videoRoom.connect(credentials.url, credentials.token)
                videoRoom.localParticipant.setMicrophoneEnabled(true)
                videoRoom.localParticipant.setCameraEnabled(true)
                localTrack = videoRoom.localParticipant.getTrackPublication(Track.Source.CAMERA)
                    ?.track as? VideoTrack
                updateRemoteTiles(videoRoom)
                status = "Görüntülü görüşme • Bağlandı"
            }.onFailure { status = "Görüntülü bağlantı kurulamadı: " + it.message.orEmpty() }
        }
    }

    private fun updateRemoteTiles(r: Room) {
        // Do not remove a participant's equal-sized tile when their camera is off.
        val latest = r.remoteParticipants.entries.map { (identity, participant) ->
            VideoTileModel(
                identity.toString(),
                participant.name?.takeIf { it.isNotBlank() } ?: "Katılımcı",
                participant.getTrackPublication(Track.Source.CAMERA)?.track as? VideoTrack
            )
        }.take(3)
        remoteTiles.clear()
        remoteTiles.addAll(latest)
    }

    private fun toggleCamera() {
        cameraOn = !cameraOn
        lifecycleScope.launch {
            room?.localParticipant?.setCameraEnabled(cameraOn)
            localTrack = room?.localParticipant?.getTrackPublication(Track.Source.CAMERA)
                ?.track as? VideoTrack
        }
    }

    private fun toggleMicrophone() {
        microphoneOn = !microphoneOn
        lifecycleScope.launch { room?.localParticipant?.setMicrophoneEnabled(microphoneOn) }
    }

    private fun loadMemberChoices() {
        lifecycleScope.launch {
            val session = SessionStore(this@VideoCallActivity).load() ?: return@launch
            val me = session.userId
            BackendApi(this@VideoCallActivity).fetchMemberDirectory(session)
                .onSuccess { members ->
                    memberChoices = members.filter { it.userId != me }
                        .map { it.userId to it.fullName }
                }.onFailure { status = "Üye listesi yüklenemedi." }
        }
    }

    private fun hangUp() {
        if (callEnded) { finish(); return }
        callEnded = true
        lifecycleScope.launch {
            runCatching { api.end(callId) }
            finish()
        }
    }

    override fun onDestroy() {
        callEnded = true
        connectionJob?.cancel()
        val oldRoom = room
        room = null
        kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.SupervisorJob() +
            kotlinx.coroutines.Dispatchers.IO).launch {
            runCatching { oldRoom?.localParticipant?.setCameraEnabled(false) }
            runCatching { oldRoom?.localParticipant?.setMicrophoneEnabled(false) }
            runCatching { oldRoom?.disconnect() }
        }
        // Restore same channel after the call, not the new private video room.
        if (pttWasOn) {
            val local = LocalStore(this)
            local.setRadioEnabled(true)
            ContextCompat.startForegroundService(this, Intent(this,
                PttForegroundService::class.java).apply {
                action = PttForegroundService.ACTION_START
            })
        }
        super.onDestroy()
    }
}

@Composable
private fun CallVideoPanel(
    room: Room, track: VideoTrack?, label: String, modifier: Modifier = Modifier
) {
    val ctx = LocalContext.current
    // Give every panel its own renderer: one tile = one equal share of the grid.
    val renderer = remember(room, ctx) {
        SurfaceViewRenderer(ctx).also { room.initVideoRenderer(it) }
    }
    DisposableEffect(renderer, track) {
        track?.addRenderer(renderer)
        onDispose { track?.removeRenderer(renderer) }
    }
    DisposableEffect(renderer) { onDispose { renderer.release() } }
    Box(modifier.background(Color.Black)) {
        AndroidView(factory = { renderer }, modifier = Modifier.fillMaxSize())
        if (track == null) {
            Text("Kamera bekleniyor", color = Color.White,
                modifier = Modifier.align(Alignment.Center))
        }
        Text(
            label, color = Color.White,
            modifier = Modifier.align(Alignment.BottomStart)
                .background(Color(0x99000000)).padding(7.dp)
        )
    }
}

@Composable
private fun VideoGrid(
    room: Room, localVideo: VideoTrack?, remoteVideos: List<VideoTileModel>,
    modifier: Modifier = Modifier
) {
    // 2 people: 1 column / 2 equal rows.
    // 3 or 4 people: a 2x2 grid, identical cell sizes (blank 4th cell for 3).
    val tiles = listOf(VideoTileModel("me", "Ben", localVideo)) + remoteVideos.take(3)
    val display = if (tiles.size == 1) tiles + VideoTileModel("waiting", "Karşı taraf", null)
        else tiles
    if (display.size <= 2) {
        Column(modifier, verticalArrangement = Arrangement.spacedBy(6.dp)) {
            display.forEach { tile ->
                key(tile.identity) {
                    CallVideoPanel(room, tile.track, tile.label,
                        Modifier.fillMaxWidth().weight(1f))
                }
            }
        }
    } else {
        Column(modifier, verticalArrangement = Arrangement.spacedBy(6.dp)) {
            for (row in 0..1) {
                Row(Modifier.weight(1f).fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    for (col in 0..1) {
                        val tile = display.getOrNull(row * 2 + col)
                        if (tile == null) {
                            Box(Modifier.weight(1f).fillMaxHeight().background(Color(0xFF26303D)),
                                contentAlignment = Alignment.Center) {
                                Text("Katılımcı bekleniyor", color = Color.LightGray)
                            }
                        } else {
                            key(tile.identity) {
                                CallVideoPanel(room, tile.track, tile.label,
                                    Modifier.weight(1f).fillMaxHeight())
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun CallView(
    status: String, videoRoom: Room?, localVideo: VideoTrack?,
    remoteVideos: List<VideoTileModel>,
    videoStarted: Boolean, cameraOn: Boolean, microphoneOn: Boolean, canInvite: Boolean,
    inviteOpen: Boolean, choices: List<Pair<String,String>>,
    onClose: () -> Unit, onCamera: () -> Unit, onMicrophone: () -> Unit,
    onInvite: () -> Unit, onInviteDismiss: () -> Unit, onInviteMember: (String) -> Unit
) {
    Column(
        modifier = Modifier.fillMaxSize().background(Color(0xFF141926))
            .systemBarsPadding().padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Text("MELEHAT • Özel Görüntülü Görüşme", color = Color.White,
            style = MaterialTheme.typography.titleMedium)
        Text(status + "  •  En fazla 4 kişi", color = Color.White)
        if (videoRoom != null && videoStarted) {
            VideoGrid(videoRoom, localVideo, remoteVideos,
                Modifier.fillMaxWidth().weight(1f))
        } else {
            Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Button(onClick = onMicrophone, enabled = videoRoom != null) {
                Text(if (microphoneOn) "Mikrofonu Kapat" else "Mikrofonu Aç")
            }
            Button(onClick = onCamera, enabled = videoRoom != null) {
                Text(if (cameraOn) "Kamerayı Kapat" else "Kamerayı Aç")
            }
        }
        if (canInvite && remoteVideos.size < 3)
            Button(onClick = onInvite) { Text("+ Kişi Ekle (En fazla 4)") }
        Button(onClick = onClose, colors = ButtonDefaults.buttonColors(
            containerColor = Color(0xFFB91C1C))) { Text("Görüşmeyi Bitir / Kapat") }
    }
    if (inviteOpen) AlertDialog(
        onDismissRequest = onInviteDismiss,
        title = { Text("Görüntülü görüşmeye davet et (en fazla 4 kişi)") },
        text = {
            Column(Modifier.heightIn(max = 350.dp).verticalScroll(rememberScrollState())) {
                choices.forEach { (id, name) ->
                    TextButton(onClick = { onInviteMember(id) }) { Text(name) }
                }
                if (choices.isEmpty()) Text("Kişiler yükleniyor…")
            }
        },
        confirmButton = { TextButton(onClick = onInviteDismiss) { Text("Kapat") } }
    )
}
