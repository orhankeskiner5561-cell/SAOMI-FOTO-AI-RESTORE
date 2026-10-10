from pathlib import Path

# v1.3.54: bounded long-hold PTT, repeat heartbeats, service-side fallback
# release, and persistent on-device diagnostic history. Other radio/video
# layers untouched. No screen-off key capture is claimed if OEM filters events.
root = Path("app/src/main/java/com/saomi/telsiz")
acc = root / "service/VolumePttAccessibilityService.kt"
svc = root / "service/PttForegroundService.kt"
diag = root / "service/ExternalPttDiagnostics.kt"
ui = root / "compat/DeviceCompatibilityActivity.kt"

def replace(path, old, new, count=1):
    s=path.read_text(encoding="utf-8")
    if s.count(old)!=count:
        raise SystemExit(f"v1354 unexpected {path.name} anchor {s.count(old)}: {old[:85]}")
    path.write_text(s.replace(old,new,count),encoding="utf-8")

# Do not discard earlier records after each test. Retain 240 latest events,
# bounded for storage/privacy. No sound, addresses or credentials logged.
replace(diag, '"key", "dispatch", "service", "audio", "watchdog", "access" -> stage',
        '"key", "dispatch", "service", "audio", "watchdog", "access", "screen" -> stage')
replace(diag, '    fun record(context: Context, stage: String, detail: String) {',
        '    @Synchronized fun record(context: Context, stage: String, detail: String) {')
replace(diag, '''        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putLong(key + "_at", System.currentTimeMillis())
            .putString(key + "_result", detail.take(160))
            .apply()''',
'''        val prefs=context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val now=System.currentTimeMillis()
        val whenText=java.text.SimpleDateFormat(
            "MM-dd HH:mm:ss.SSS", java.util.Locale.getDefault()
        ).format(java.util.Date(now))
        val entry="$whenText | " + stage.uppercase(java.util.Locale.ROOT) +
            " | " + detail.replace("\\n", " ").take(150)
        val recent=prefs.getString("history", "").orEmpty()
            .lineSequence().filter { it.isNotBlank() }.takeLastSafely(239).toList()
        prefs.edit().putLong(key + "_at",now)
            .putString(key + "_result",detail.take(160))
            .putString("history", (recent + entry).joinToString("\\n"))
            .apply()''')
# Preserve only 240 records; app has Kotlin's lineSequence().toList().takeLast
# but no built-in takeLast on Sequence, so use a local helper below.
replace(diag, '''    fun screenState(context: Context): String {''',
'''    private fun Sequence<String>.takeLastSafely(max: Int): Sequence<String> =
        toList().takeLast(max).asSequence()

    fun history(context: Context): String {
        val lines=context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString("history", "").orEmpty()
            .lineSequence().filter { it.isNotBlank() }.toList()
        return if (lines.isEmpty()) "Henüz olay kaydı yok."
            else lines.takeLast(35).joinToString("\\n")
    }

    fun screenState(context: Context): String {''')
# Correct literal Kotlin line separators in generated output: raw python
# string above contains "\\n"; Kotlin should receive "\n".
s=diag.read_text(encoding="utf-8").replace('replace("\\\\n", " ")','replace("\\n", " ")').replace('joinToString("\\\\n")','joinToString("\\n")')
diag.write_text(s,encoding="utf-8")

# Screen transition events independently of key callbacks.
replace(acc, 'import android.content.Intent',
'''import android.content.Intent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.IntentFilter''')
replace(acc, '''    private var lastDownAt = 0L''',
'''    private var lastDownAt = 0L
    private var repeatEvents = false
    private var lastHeartbeatAt = 0L
    private var screenReceiverRegistered = false

    private val screenReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            val value = when(intent.action) {
                Intent.ACTION_SCREEN_OFF -> "SCREEN_OFF"
                Intent.ACTION_SCREEN_ON -> "SCREEN_ON"
                else -> return
            }
            ExternalPttDiagnostics.record(this@VolumePttAccessibilityService,
                "screen", value)
        }
    }

    private fun holdTimeoutMs() =
        if (repeatEvents) REPEAT_SILENCE_MS else NO_REPEAT_LIMIT_MS''')
replace(acc, '''            if (elapsed >= RELEASE_TIMEOUT_MS || !isArmed()) {''',
'''            val limit = holdTimeoutMs()
            if (elapsed >= limit || !isArmed()) {''')
replace(acc, '''                handler.postDelayed(this, RELEASE_TIMEOUT_MS - elapsed)''',
            '''                handler.postDelayed(this, limit - elapsed)''')
replace(acc, '''        ExternalPttDiagnostics.record(this, "access", "SERVICE_CONNECTED " +
            ExternalPttDiagnostics.screenState(this))
    }''',
'''        ExternalPttDiagnostics.record(this, "access", "SERVICE_CONNECTED " +
            ExternalPttDiagnostics.screenState(this))
        if (!screenReceiverRegistered) {
            runCatching {
                registerReceiver(screenReceiver, IntentFilter().apply {
                    addAction(Intent.ACTION_SCREEN_OFF)
                    addAction(Intent.ACTION_SCREEN_ON)
                })
                screenReceiverRegistered = true
            }.onFailure {
                ExternalPttDiagnostics.record(this, "screen",
                    "RECEIVER_ERROR " + it.javaClass.simpleName)
            }
        }
    }''')
replace(acc, '''        ExternalPttDiagnostics.record(this, "key",
            (if (event.action == KeyEvent.ACTION_DOWN) "DOWN"
             else if (event.action == KeyEvent.ACTION_UP) "UP" else "OTHER") +
            " repeat=" + event.repeatCount + " " +
            ExternalPttDiagnostics.screenState(this))''',
'''        if (event.repeatCount == 0 || event.action != KeyEvent.ACTION_DOWN ||
            SystemClock.uptimeMillis() - lastHeartbeatAt >= 700L) {
            ExternalPttDiagnostics.record(this, "key",
                (if (event.action == KeyEvent.ACTION_UP) "KEY_UP"
                 else if (event.repeatCount > 0) "KEY_REPEAT" else "KEY_DOWN") +
                " repeat=" + event.repeatCount + " " +
                ExternalPttDiagnostics.screenState(this))
        }''')
replace(acc, '''            KeyEvent.ACTION_DOWN -> {
                lastDownAt = SystemClock.uptimeMillis()
                // A repeated DOWN must never start a new transmission after a
                // failsafe timeout: wait for the next *fresh* physical press.
                if (!held && event.repeatCount == 0) {
                    held = true
                    if (!dispatch(PttForegroundService.ACTION_PTT_DOWN)) {
                        held = false
                        return true
                    }
                }
                if (held) {
                    handler.removeCallbacks(timeout)
                    handler.postDelayed(timeout, RELEASE_TIMEOUT_MS)
                }
                true
            }''',
'''            KeyEvent.ACTION_DOWN -> {
                val now = SystemClock.uptimeMillis()
                // Fresh physical DOWN only; a late repeated event cannot
                // accidentally restart after an automatic release.
                if (!held && event.repeatCount == 0) {
                    held = true
                    repeatEvents = false
                    lastDownAt = now
                    lastHeartbeatAt = now
                    if (!dispatch(PttForegroundService.ACTION_PTT_DOWN)) {
                        held = false
                        handler.removeCallbacks(timeout)
                        return true
                    }
                } else if (held && event.repeatCount > 0) {
                    repeatEvents = true
                    lastDownAt = now
                    if (now - lastHeartbeatAt >= 700L) {
                        lastHeartbeatAt = now
                        dispatch(PttForegroundService.ACTION_EXTERNAL_PTT_HEARTBEAT)
                    }
                }
                if (held) {
                    handler.removeCallbacks(timeout)
                    handler.postDelayed(timeout, holdTimeoutMs())
                }
                true
            }''')
replace(acc, '''    override fun onDestroy() {
        ExternalPttDiagnostics.record(this, "access", "SERVICE_DESTROYED")
        release()
        super.onDestroy()
    }''',
'''    override fun onDestroy() {
        ExternalPttDiagnostics.record(this, "access", "SERVICE_DESTROYED")
        release()
        if (screenReceiverRegistered) {
            runCatching { unregisterReceiver(screenReceiver) }
            screenReceiverRegistered = false
        }
        super.onDestroy()
    }''')
replace(acc, '''        held = false
        dispatch(PttForegroundService.ACTION_PTT_UP)''',
'''        held = false
        repeatEvents = false
        dispatch(PttForegroundService.ACTION_PTT_UP)''')
replace(acc, '''        private const val RELEASE_TIMEOUT_MS = 1800L''',
'''        // Some OEM lock screens emit one DOWN but no repeats.
        // Without a reliable UP we cannot allow endless microphone capture:
        // first press is bounded to 20s; repeat heartbeat gaps to 3.5s.
        private const val NO_REPEAT_LIMIT_MS = 20000L
        private const val REPEAT_SILENCE_MS = 3500L''')

# A second, service-owned guard protects against accessibility service death.
replace(svc, 'import android.os.PowerManager',
'''import android.os.PowerManager
import android.os.Handler
import android.os.Looper
import android.os.SystemClock''')
replace(svc, '''    private var roomSwitchJob: Job? = null''',
'''    private var roomSwitchJob: Job? = null
    private val externalGuardHandler = Handler(Looper.getMainLooper())
    private var externalHeld = false
    private var externalRepeating = false
    private var externalLastTick = 0L
    private val externalGuard = object : Runnable {
        override fun run() {
            if (!externalHeld) return
            val maxWait = if (externalRepeating) 4500L else 21000L
            val quiet = SystemClock.uptimeMillis() - externalLastTick
            if (quiet >= maxWait) {
                externalHeld = false
                pttHeld = false
                transmitRequestId += 1
                beginJob?.cancel()
                beginJob = null
                ExternalPttDiagnostics.record(this@PttForegroundService,
                    "watchdog", "SERVICE_AUTO_RELEASE " +
                    ExternalPttDiagnostics.screenState(this@PttForegroundService))
                scope.launch {
                    endTransmit()
                    ExternalPttDiagnostics.record(this@PttForegroundService,
                        "audio", "PTT_STOPPED SERVICE_FAILSAFE")
                }
            } else externalGuardHandler.postDelayed(this, maxWait - quiet)
        }
    }
    private fun refreshExternalGuard(repeat: Boolean) {
        if (repeat && !externalHeld) return
        if (!repeat) {
            externalHeld = true
            externalRepeating = false
        } else externalRepeating = true
        externalLastTick = SystemClock.uptimeMillis()
        externalGuardHandler.removeCallbacks(externalGuard)
        externalGuardHandler.postDelayed(externalGuard,
            if (externalRepeating) 4500L else 21000L)
    }
    private fun clearExternalGuard() {
        externalGuardHandler.removeCallbacks(externalGuard)
        externalHeld = false
        externalRepeating = false
    }''')
replace(svc, '''            ACTION_SWITCH_ROOM -> {
                val roomId = intent?.getStringExtra(EXTRA_ROOM_ID).orEmpty()''',
'''            ACTION_SWITCH_ROOM -> {
                // Never keep a physical-key hold during a channel change.
                if (externalHeld) {
                    ExternalPttDiagnostics.record(this,"service","ROOM_SWITCH_RELEASE")
                    clearExternalGuard()
                }
                val roomId = intent?.getStringExtra(EXTRA_ROOM_ID).orEmpty()''')
replace(svc, '''            ACTION_STOP -> {
                started = false''',
'''            ACTION_STOP -> {
                clearExternalGuard()
                started = false''')
replace(svc, '''                if (started && !roomSwitching) {
                    pttHeld = true
                    transmitRequestId += 1''',
'''                if (started && !roomSwitching) {
                    if (externalKey) refreshExternalGuard(false)
                    pttHeld = true
                    transmitRequestId += 1''',count=1)
replace(svc, '''            ACTION_PTT_UP -> {
                if (intent?.getBooleanExtra("melehat.external_ptt", false) == true) {''',
'''            ACTION_EXTERNAL_PTT_HEARTBEAT -> {
                if (started && !roomSwitching && externalHeld &&
                    intent?.getBooleanExtra("melehat.external_ptt",false) == true) {
                    refreshExternalGuard(true)
                    ExternalPttDiagnostics.record(this,"service",
                        "KEY_REPEAT_HEARTBEAT " + ExternalPttDiagnostics.screenState(this))
                }
            }

            ACTION_PTT_UP -> {
                val wasExternal = externalHeld ||
                    intent?.getBooleanExtra("melehat.external_ptt",false) == true
                if (wasExternal) clearExternalGuard()
                if (intent?.getBooleanExtra("melehat.external_ptt", false) == true) {''')
replace(svc, '''                    scope.launch { endTransmit() }
                }
            }

            ACTION_TOGGLE_PTT -> {''',
'''                    scope.launch {
                        endTransmit()
                        if (wasExternal) ExternalPttDiagnostics.record(
                            this@PttForegroundService, "audio",
                            "PTT_STOPPED " + ExternalPttDiagnostics.screenState(this@PttForegroundService))
                    }
                }
            }

            ACTION_TOGGLE_PTT -> {''')
replace(svc, '''    override fun onDestroy() {
        roomSwitchJob?.cancel()''',
'''    override fun onDestroy() {
        clearExternalGuard()
        roomSwitchJob?.cancel()''')
replace(svc, '''        const val ACTION_SWITCH_ROOM = "com.saomi.telsiz.SWITCH_ROOM"''',
'''        const val ACTION_EXTERNAL_PTT_HEARTBEAT = "com.saomi.telsiz.EXTERNAL_PTT_HEARTBEAT"
        const val ACTION_SWITCH_ROOM = "com.saomi.telsiz.SWITCH_ROOM"''')
# Leave all UI PTT pointer handlers and LiveKit core unchanged.
for protected in (
    'roomSwitching || !ptt.isConnectedTo(channel.id)',
    'backend.releaseFloor(session, channel.id)',
    'onTaskRemoved(rootIntent: Intent?)',
    'ptt.setTransmitting(true)',
    'VideoCallMonitor.start(applicationContext)',
    'const val ACTION_SWITCH_ROOM', 'return START_STICKY'
):
    if protected not in svc.read_text(encoding="utf-8"):
        raise SystemExit("v1354 protected radio feature missing: "+protected)

replace(ui, '''        action("Dış mandal test kaydını yenile") { render() }''',
'''        line("Son olayların geçmişi (en yeni altta)", 18f, true)
        line(com.saomi.telsiz.service.ExternalPttDiagnostics.history(this), 12f)
        action("Dış mandal test kaydını yenile") { render() }''')
replace(ui, '''        for (stage in listOf("access", "key", "dispatch", "service", "audio", "watchdog"))''',
'''        for (stage in listOf("access", "screen", "key", "dispatch", "service", "audio", "watchdog"))''')
replace(ui, '''                "key" -> "Tuş algılandı"''',
'''                "screen" -> "Ekranın gerçek durumu"
                "key" -> "Tuş algılandı"''')
replace(ui, '''        line("Gerçek ekran kapalı testi yapılana kadar kilitli ekranda " +
             "kesintisiz uzun konuşma garanti edilemez.")''',
'''        line("Tuş tekrarları geliyorsa uzun basış sürer; hiç tekrar olayı " +
             "gelmiyorsa güvenlik için en geç 20 saniyede yayın kapanır. " +
             "Ekran kapalı tuşunu sistem engellerse uygulama yakalayamaz.")''')
print("MELEHAT_1354_BOUNDED_KEY_HOLD_AND_PERSISTENT_HISTORY_OK")
