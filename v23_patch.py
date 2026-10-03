from pathlib import Path
import re

service = r'''package com.saomi.telsiz.service

import android.app.*
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.VolumeProvider
import android.media.session.MediaSession
import android.media.session.PlaybackState
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import com.saomi.telsiz.audio.AudioRouteManager
import com.saomi.telsiz.audio.MediaPttController
import com.saomi.telsiz.data.BackendApi
import com.saomi.telsiz.data.LocalStore
import com.saomi.telsiz.data.SessionStore
import com.saomi.telsiz.net.NetworkMonitor
import com.saomi.telsiz.voice.LiveKitPttClient
import kotlinx.coroutines.*

class PttForegroundService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private lateinit var ptt: LiveKitPttClient
    private lateinit var store: LocalStore
    private lateinit var sessions: SessionStore
    private lateinit var backend: BackendApi
    private lateinit var audioRoute: AudioRouteManager
    private lateinit var mediaPtt: MediaPttController
    private lateinit var networkMonitor: NetworkMonitor
    private var wakeLock: PowerManager.WakeLock? = null

    private var started = false
    private var transmitting = false
    @Volatile private var pttHeld = false
    private var transmitRequestId = 0L
    private var beginJob: Job? = null
    private var leaseJob: Job? = null

    private var volumeSession: MediaSession? = null
    private val volumeHandler = Handler(Looper.getMainLooper())
    private var volumeReleaseRunnable: Runnable? = null
    private var volumePttActive = false

    override fun onCreate() {
        super.onCreate()
        ptt = LiveKitPttClient(applicationContext)
        store = LocalStore(applicationContext)
        sessions = SessionStore(applicationContext)
        backend = BackendApi(applicationContext)
        audioRoute = AudioRouteManager(applicationContext)
        mediaPtt = MediaPttController(applicationContext) {
            val i = Intent(applicationContext, PttForegroundService::class.java).apply {
                action = ACTION_TOGGLE_PTT
            }
            startService(i)
        }
        networkMonitor = NetworkMonitor(
            applicationContext,
            onAvailable = {
                if (started) {
                    scope.launch {
                        val ok = ptt.connect(store.loadProfile(), store.loadActiveChannel())
                        updateNotification(
                            if (ok) "Bağlantı geri geldi • Bas-konuş hazır"
                            else "İnternet var • Ses sunucusu bekleniyor"
                        )
                    }
                }
            },
            onLost = {
                if (started) updateNotification("İNTERNET YOK • Yeniden bağlanacak")
            }
        )
        networkMonitor.start()

        val pm = getSystemService(PowerManager::class.java)
        wakeLock = pm.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "saomi:telsiz"
        ).apply { setReferenceCounted(false) }

        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                startAsForeground("Bağlanıyor…")
                started = true
                store.setRadioEnabled(true)
                if (wakeLock?.isHeld != true) wakeLock?.acquire()
                val route = audioRoute.activateBestRoute()
                startVolumePttSession()
                updateNotification("Ses çıkışı: $route • Bağlanıyor…")
                scope.launch {
                    val ok = ptt.connect(store.loadProfile(), store.loadActiveChannel())
                    updateNotification(
                        if (ok) "Kanal dinlemede • Bas-konuş hazır • Ses açma=P.T.T."
                        else "Ses sunucusu bağlantısı bekleniyor"
                    )
                }
            }

            ACTION_STOP -> {
                scope.launch { stopRadio() }
            }

            ACTION_PTT_DOWN -> {
                if (started) {
                    pttHeld = true
                    transmitRequestId += 1
                    val requestId = transmitRequestId
                    if (!transmitting) {
                        beginJob?.cancel()
                        beginJob = scope.launch { beginTransmit(requestId) }
                    }
                }
            }

            ACTION_PTT_UP -> {
                if (started) {
                    pttHeld = false
                    transmitRequestId += 1
                    beginJob?.cancel()
                    beginJob = null
                    scope.launch { endTransmit() }
                }
            }

            ACTION_TOGGLE_PTT -> {
                if (started) {
                    if (transmitting || pttHeld) {
                        pttHeld = false
                        transmitRequestId += 1
                        beginJob?.cancel()
                        beginJob = null
                        scope.launch { endTransmit() }
                    } else {
                        pttHeld = true
                        transmitRequestId += 1
                        val requestId = transmitRequestId
                        beginJob?.cancel()
                        beginJob = scope.launch { beginTransmit(requestId) }
                    }
                }
            }
        }
        return START_STICKY
    }

    private fun startVolumePttSession() {
        if (volumeSession != null) return

        val session = MediaSession(this, "MELEHAT_VOLUME_PTT")
        session.setPlaybackState(
            PlaybackState.Builder()
                .setState(PlaybackState.STATE_PLAYING, 0L, 1f)
                .setActions(PlaybackState.ACTION_PLAY_PAUSE)
                .build()
        )

        val provider = object : VolumeProvider(
            VolumeProvider.VOLUME_CONTROL_RELATIVE,
            100,
            50
        ) {
            override fun onAdjustVolume(direction: Int) {
                if (!started) return

                if (direction > 0) {
                    if (!volumePttActive) {
                        volumePttActive = true
                        onVolumePttDown()
                    }

                    volumeReleaseRunnable?.let { volumeHandler.removeCallbacks(it) }
                    val release = Runnable {
                        if (volumePttActive) {
                            volumePttActive = false
                            onVolumePttUp()
                        }
                    }
                    volumeReleaseRunnable = release
                    volumeHandler.postDelayed(release, 550L)
                } else if (direction < 0) {
                    volumeReleaseRunnable?.let { volumeHandler.removeCallbacks(it) }
                    volumeReleaseRunnable = null
                    if (volumePttActive || transmitting || pttHeld) {
                        volumePttActive = false
                        onVolumePttUp()
                    }
                }
            }
        }

        session.setPlaybackToRemote(provider)
        session.isActive = true
        volumeSession = session
    }

    private fun stopVolumePttSession() {
        volumeReleaseRunnable?.let { volumeHandler.removeCallbacks(it) }
        volumeReleaseRunnable = null
        volumePttActive = false
        volumeSession?.isActive = false
        volumeSession?.release()
        volumeSession = null
    }

    private fun onVolumePttDown() {
        val i = Intent(this, PttForegroundService::class.java).apply {
            action = ACTION_PTT_DOWN
        }
        startService(i)
    }

    private fun onVolumePttUp() {
        val i = Intent(this, PttForegroundService::class.java).apply {
            action = ACTION_PTT_UP
        }
        startService(i)
    }

    private suspend fun beginTransmit(requestId: Long) {
        val session = sessions.load()
        val channel = store.loadActiveChannel()

        if (session == null) {
            updateNotification("Telefon doğrulaması gerekli")
            return
        }

        updateNotification("Kanal kontrol ediliyor…")
        val floor = backend.acquireFloor(session, channel.id, 15)
        if (!floor) {
            if (pttHeld && requestId == transmitRequestId) {
                updateNotification("KANAL MEŞGUL • Başka biri konuşuyor")
            }
            return
        }

        if (!pttHeld || requestId != transmitRequestId || !started) {
            backend.releaseFloor(session, channel.id)
            ptt.setTransmitting(false)
            updateNotification("Kanal dinlemede • Bas-konuş hazır")
            return
        }

        val enabled = ptt.setTransmitting(true)
        if (!enabled) {
            backend.releaseFloor(session, channel.id)
            updateNotification("Ses bağlantısı hazır değil")
            return
        }

        if (!pttHeld || requestId != transmitRequestId || !started) {
            ptt.setTransmitting(false)
            backend.releaseFloor(session, channel.id)
            transmitting = false
            updateNotification("Kanal dinlemede • Bas-konuş hazır")
            return
        }

        transmitting = true
        updateNotification("YAYINDA • Ses karşıya gidiyor")

        leaseJob?.cancel()
        leaseJob = scope.launch {
            while (isActive && transmitting) {
                delay(8_000)
                val renewed = backend.acquireFloor(session, channel.id, 15)
                if (!renewed) {
                    ptt.setTransmitting(false)
                    transmitting = false
                    updateNotification("Yayın kesildi • Kanal kilidi yenilenemedi")
                    break
                }
            }
        }
    }

    private suspend fun endTransmit() {
        pttHeld = false
        transmitting = false
        leaseJob?.cancel()
        leaseJob = null

        ptt.setTransmitting(false)

        val session = sessions.load()
        if (session != null) {
            backend.releaseFloor(session, store.loadActiveChannel().id)
        }

        updateNotification("Kanal dinlemede • Bas-konuş hazır • Ses açma=P.T.T.")
    }

    private suspend fun stopRadio() {
        pttHeld = false
        transmitRequestId += 1
        beginJob?.cancel()
        beginJob = null
        if (transmitting) endTransmit() else ptt.setTransmitting(false)
        started = false
        store.setRadioEnabled(false)
        stopVolumePttSession()
        ptt.disconnect()
        audioRoute.deactivate()
        if (wakeLock?.isHeld == true) wakeLock?.release()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun buildNotification(text: String): Notification {
        val toggleIntent = Intent(this, PttForegroundService::class.java).apply {
            action = ACTION_TOGGLE_PTT
        }
        val stopIntent = Intent(this, PttForegroundService::class.java).apply {
            action = ACTION_STOP
        }

        val flags = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("MELEHAT TELSİZ açık")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .addAction(
                android.R.drawable.ic_btn_speak_now,
                if (transmitting) "Yayını Kes" else "Bas-Konuş",
                PendingIntent.getService(this, 201, toggleIntent, flags)
            )
            .addAction(
                android.R.drawable.ic_delete,
                "Telsizi Kapat",
                PendingIntent.getService(this, 202, stopIntent, flags)
            )
            .build()
    }

    private fun startAsForeground(text: String) {
        val notification = buildNotification(text)
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
            )
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    private fun updateNotification(text: String) {
        getSystemService(NotificationManager::class.java).notify(
            NOTIFICATION_ID,
            buildNotification(text)
        )
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            getSystemService(NotificationManager::class.java).createNotificationChannel(
                NotificationChannel(
                    CHANNEL_ID,
                    "MELEHAT TELSİZ",
                    NotificationManager.IMPORTANCE_HIGH
                ).apply {
                    description = "Telsiz arka plan servisi ve PTT kontrolleri"
                    lockscreenVisibility = Notification.VISIBILITY_PUBLIC
                }
            )
        }
    }

    override fun onDestroy() {
        stopVolumePttSession()
        pttHeld = false
        transmitRequestId += 1
        beginJob?.cancel()
        leaseJob?.cancel()
        networkMonitor.stop()
        mediaPtt.release()
        audioRoute.deactivate()
        if (wakeLock?.isHeld == true) wakeLock?.release()
        scope.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        const val ACTION_START = "com.saomi.telsiz.START"
        const val ACTION_STOP = "com.saomi.telsiz.STOP"
        const val ACTION_PTT_DOWN = "com.saomi.telsiz.PTT_DOWN"
        const val ACTION_PTT_UP = "com.saomi.telsiz.PTT_UP"
        const val ACTION_TOGGLE_PTT = "com.saomi.telsiz.TOGGLE_PTT"
        private const val CHANNEL_ID = "saomi_ptt"
        private const val NOTIFICATION_ID = 101
    }
}
'''

p=Path("app/src/main/java/com/saomi/telsiz/service/PttForegroundService.kt")
p.write_text(service)

# Fresh app identity + version.
b=Path("app/build.gradle.kts")
s=b.read_text()
s=re.sub(r'applicationId\s*=\s*"[^"]+"', 'applicationId = "com.melehat.telsiz.v23"', s)
s=re.sub(r'versionCode\s*=\s*\d+', 'versionCode = 23', s)
s=re.sub(r'versionName\s*=\s*"[^"]+"', 'versionName = "0.23.0"', s)
b.write_text(s)

ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
u=ui.read_text()
u=re.sub(r'v0\.\d+\s*•\s*[^"]*', 'v0.23 • Güvenli Ses Tuşu PTT', u, count=1)
ui.write_text(u)

print("v0.23 clean v0.16 + MediaSession volume PTT applied")
