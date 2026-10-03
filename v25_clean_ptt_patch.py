from pathlib import Path
import re

service = r'''package com.saomi.telsiz.service

import android.app.*
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.PowerManager
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.saomi.telsiz.audio.AudioRouteManager
import com.saomi.telsiz.audio.MediaPttController
import com.saomi.telsiz.net.NetworkMonitor
import com.saomi.telsiz.data.BackendApi
import com.saomi.telsiz.data.LocalStore
import com.saomi.telsiz.data.SessionStore
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
                updateNotification("Ses çıkışı: $route • Bağlanıyor…")
                scope.launch {
                    val ok = ptt.connect(store.loadProfile(), store.loadActiveChannel())
                    updateNotification(
                        if (ok) "Kanal dinlemede • Bas-konuş hazır"
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

        updateNotification("Kanal dinlemede • Bas-konuş hazır")
    }

    private suspend fun stopRadio() {
        pttHeld = false
        transmitRequestId += 1
        beginJob?.cancel()
        beginJob = null
        if (transmitting) endTransmit() else ptt.setTransmitting(false)
        started = false
        store.setRadioEnabled(false)
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

Path('app/src/main/java/com/saomi/telsiz/service/PttForegroundService.kt').write_text(service)

# Remove every accessibility-service trace if an old file happens to exist.
svc=Path('app/src/main/java/com/saomi/telsiz/service/VolumePttAccessibilityService.kt')
if svc.exists(): svc.unlink()
xml=Path('app/src/main/res/xml/volume_ptt_accessibility_service.xml')
if xml.exists(): xml.unlink()

manifest=Path('app/src/main/AndroidManifest.xml')
m=manifest.read_text()
m=re.sub(r'\s*<service\s+android:name="\.service\.VolumePttAccessibilityService"[\s\S]*?</service>\s*', '\n', m)
manifest.write_text(m)

# Clean all visible version text and make it consistent.
ui=Path('app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt')
u=ui.read_text()
u=re.sub(r'MELEHAT TELSİZ v0\.\d+(?:\.\d+)?', 'MELEHAT TELSİZ v0.25', u)
u=re.sub(r'v0\.\d+(?:\.\d+)?\s*•\s*[^"\n]*', 'v0.25 • Temiz Bas-Konuş', u)
ui.write_text(u)

b=Path('app/build.gradle.kts')
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"', 'applicationId = "com.melehat.telsiz.v25"', t)
t=re.sub(r'versionCode\s*=\s*\d+', 'versionCode = 25', t)
t=re.sub(r'versionName\s*=\s*"[^"]+"', 'versionName = "0.25.0"', t)
b.write_text(t)

print('v0.25 clean v0.16 PTT service restored; volume-key layers removed')