from pathlib import Path

# v1.3.55 SAFE SCREEN-OFF KEY GATE.
# On Xiaomi Android 16 the accessibility service may receive screen-off DOWN
# but no UP or repeats. Starting a microphone with no reliable release violates
# hold-to-talk privacy. Fail closed in BOTH accessibility and radio service.
# Visible display PTT, LiveKit, video, membership and room switching stay intact.

root=Path("app/src/main/java/com/saomi/telsiz")
access=root/"service/VolumePttAccessibilityService.kt"
radio=root/"service/PttForegroundService.kt"
ui=root/"compat/DeviceCompatibilityActivity.kt"

def change(path,before,after):
    s=path.read_text(encoding="utf-8")
    matches=s.count(before)
    if matches != 1:
        raise SystemExit(f"1355 protected anchor {path.name} expected=1 found={matches}: {before[:80]}")
    path.write_text(s.replace(before,after,1),encoding="utf-8")

change(access, '''            ExternalPttDiagnostics.record(this@VolumePttAccessibilityService,
                "screen", value)
        }
    }''',
'''            ExternalPttDiagnostics.record(this@VolumePttAccessibilityService,
                "screen", value)
            // Releasing an external hold on screen-off is mandatory because
            // this OEM does not reliably deliver KEY_UP while non-interactive.
            if (value == "SCREEN_OFF" && held) {
                ExternalPttDiagnostics.record(this@VolumePttAccessibilityService,
                    "watchdog", "SCREEN_OFF_FORCED_RELEASE")
                release()
            }
        }
    }''')

change(access, '''        if (!isArmed()) {
            ExternalPttDiagnostics.record(this, "dispatch",
                "IGNORED: external switch or radio OFF")
            release()
            return false // Normal volume adjustment if not armed.
        }
        return when (event.action) {''',
'''        if (!isArmed()) {
            ExternalPttDiagnostics.record(this, "dispatch",
                "IGNORED: external switch or radio OFF")
            release()
            return false // Normal volume adjustment if not armed.
        }
        // Screen-off UP/REPEAT are missing on this tested device.
        // No microphone transmission may start on an unmatched DOWN.
        // Keep recording DOWN/UP for compatibility research.
        val power = getSystemService(android.os.PowerManager::class.java)
        if (!power.isInteractive) {
            if (held) release()
            ExternalPttDiagnostics.record(this, "dispatch",
                "SCREEN_OFF_KEY_BLOCKED_NO_RELIABLE_UP")
            return false
        }
        return when (event.action) {''')

# Independent radio-level screen-off safety: protects even if accessibility
# service is terminated while the microphone is in-flight.
change(radio, 'import android.content.Intent\n', '''import android.content.Intent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.IntentFilter
''')
change(radio, '''    private var externalLastTick = 0L
    private val externalGuard = object : Runnable {''',
'''    private var externalLastTick = 0L
    private var externalScreenReceiverRegistered = false
    private val externalScreenOffReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            if (intent.action != Intent.ACTION_SCREEN_OFF || !externalHeld) return
            ExternalPttDiagnostics.record(this@PttForegroundService, "watchdog",
                "SCREEN_OFF_SERVICE_FORCED_RELEASE")
            clearExternalGuard()
            pttHeld = false
            transmitRequestId += 1
            beginJob?.cancel()
            beginJob = null
            scope.launch {
                endTransmit()
                ExternalPttDiagnostics.record(this@PttForegroundService,
                    "audio", "PTT_STOPPED_SCREEN_OFF")
            }
        }
    }
    private val externalGuard = object : Runnable {''')
change(radio, '''        networkMonitor.start()
        val pm = getSystemService(PowerManager::class.java)''',
'''        networkMonitor.start()
        runCatching {
            registerReceiver(externalScreenOffReceiver, IntentFilter(Intent.ACTION_SCREEN_OFF))
            externalScreenReceiverRegistered = true
        }.onFailure {
            ExternalPttDiagnostics.record(this, "screen",
                "SERVICE_RECEIVER_ERROR " + it.javaClass.simpleName)
        }
        val pm = getSystemService(PowerManager::class.java)''')
change(radio, '''            ACTION_PTT_DOWN -> {
                val externalKey = intent?.getBooleanExtra("melehat.external_ptt", false) == true
                if (externalKey) {''',
'''            ACTION_PTT_DOWN -> {
                val externalKey = intent?.getBooleanExtra("melehat.external_ptt", false) == true
                if (externalKey &&
                    !getSystemService(PowerManager::class.java).isInteractive) {
                    ExternalPttDiagnostics.record(this, "service",
                        "SCREEN_OFF_PTT_BLOCKED_FOR_SAFETY")
                    return START_STICKY
                }
                if (externalKey) {''')
change(radio, '''    private suspend fun beginTransmit(requestId: Long, external: Boolean = false) {
        val session = sessions.load()''',
'''    private suspend fun beginTransmit(requestId: Long, external: Boolean = false) {
        if (external && !getSystemService(PowerManager::class.java).isInteractive) {
            ExternalPttDiagnostics.record(this, "audio",
                "SCREEN_OFF_MIC_BLOCKED_FOR_SAFETY")
            return
        }
        val session = sessions.load()''')
# Recheck before and after the microphone enable call, in addition to the
# preexisting request-ID + room state guards.
# Two protected checks: before and after setTransmitting(true).
s=radio.read_text(encoding="utf-8")
old='''if (!pttHeld || requestId != transmitRequestId || !started ||
            roomSwitching || !ptt.isConnectedTo(channel.id))'''
new='''if (!pttHeld || requestId != transmitRequestId || !started ||
            roomSwitching || !ptt.isConnectedTo(channel.id) ||
            (external && !getSystemService(PowerManager::class.java).isInteractive))'''
if s.count(old)!=2:
    raise SystemExit(f"1355 expected two mic state guards: {s.count(old)}")
radio.write_text(s.replace(old,new,2),encoding="utf-8")

change(radio, '''    override fun onDestroy() {
        clearExternalGuard()''',
'''    override fun onDestroy() {
        if (externalScreenReceiverRegistered) {
            runCatching { unregisterReceiver(externalScreenOffReceiver) }
            externalScreenReceiverRegistered = false
        }
        clearExternalGuard()''')
change(ui, '''        line("Tuş tekrarları geliyorsa uzun basış sürer; hiç tekrar olayı " +
             "gelmiyorsa güvenlik için en geç 20 saniyede yayın kapanır. " +
             "Ekran kapalı tuşunu sistem engellerse uygulama yakalayamaz.")''',
'''        line("ÖNEMLİ: Bu Xiaomi / Android 16 cihazında ekran karanlıkken " +
             "Ses + tuşunun bırakma olayı güvenilir gelmediği için fiziksel " +
             "mandaldan yayın GÜVENLİK NEDENİYLE ENGELLENDİ. " +
             "Ekran aydınlıkken Ses + kullanabilirsiniz. Ekran karanlıkken " +
             "KEY_DOWN kayıt altına alınır ama mikrofon açılmaz. " +
             "Gerçek ekran kapalı PTT için ayrı DOWN / UP gönderen, " +
             "uyumlu bir Bluetooth PTT kumandası gereklidir.")''')

# Never change any of these user-approved working paths:
service_text=radio.read_text(encoding="utf-8")
access_text=access.read_text(encoding="utf-8")
for essential in (
    "ACTION_PTT_DOWN", "ACTION_PTT_UP", "ACTION_SWITCH_ROOM",
    "roomMutex.withLock", "VideoCallMonitor.start(applicationContext)",
    "ptt.setTransmitting(true)", "return START_STICKY",
    "android.os.PowerManager", "SCREEN_OFF_PTT_BLOCKED_FOR_SAFETY",
    "SCREEN_OFF_SERVICE_FORCED_RELEASE",
):
    if essential not in service_text:
        raise SystemExit("1355 protected service capability missing: "+essential)
for essential in ("REPEAT_SILENCE_MS", "NO_REPEAT_LIMIT_MS",
                  "KEYCODE_VOLUME_UP", "SCREEN_OFF_KEY_BLOCKED_NO_RELIABLE_UP"):
    if essential not in access_text:
        raise SystemExit("1355 protected accessibility feature missing: "+essential)
print("MELEHAT_1355_FAIL_CLOSED_SCREEN_OFF_PTT_SAFE")
