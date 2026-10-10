from pathlib import Path

# MELEHAT v1.3.58: opt-in raw Shizuku Volume+ source drives existing PTT
# through the same LiveKit/floor channel path. Safety requirements:
# • No raw event may start an unrequested foreground radio.
# • Release on UP, reader exit, Shizuku disable, room switch, radio stop,
#   service destruction, or bounded maximum physical hold.
# • Keep existing Accessibility screen-off block for the legacy key source.
# • Never create an independent microphone or bypass floor authorization.

root=Path("app/src/main/java/com/saomi/telsiz")
svc=root/"service/PttForegroundService.kt"
acc=root/"service/VolumePttAccessibilityService.kt"
probe=root/"service/ShizukuRawKeyProbe.kt"
ui=root/"compat/DeviceCompatibilityActivity.kt"

def patch(path, old, new, count=1):
    s=path.read_text(encoding="utf-8")
    n=s.count(old)
    if n != count:
        raise SystemExit(f"v1358 anchor error {path.name} want={count} got={n}: {old[:100]}")
    path.write_text(s.replace(old,new,count),encoding="utf-8")

# Active solely while the foreground service owns the selected raw input.
state=root/"service/ShizukuRawPttState.kt"
if state.exists():
    raise SystemExit("v1358 raw state already present")
state.write_text('''package com.saomi.telsiz.service

/** Process-local single hardware input owner. Never a persisted authorization. */
object ShizukuRawPttState {
    @Volatile var enabled: Boolean = false
}
''',encoding="utf-8")

# Existing proven diagnostic reader gains optional callbacks; diagnostics remains
# the default with no microphone control.
patch(probe,
'class ShizukuRawKeyProbe(private val context: Context) {',
'''class ShizukuRawKeyProbe(
    private val context: Context,
    private val onRawKey: (String) -> Unit = {},
    private val onUnexpectedExit: () -> Unit = {}
) {''')
patch(probe,'    fun start() {','    fun start(): Boolean {')
patch(probe,'''            record("DOSYALAR_EKSIK: rish ve rish_shizuku.dex seçin")
            return''',
'''            record("DOSYALAR_EKSIK: rish ve rish_shizuku.dex seçin")
            return false''')
patch(probe,'''            record("SHIZUKU_YETKISI_GEREKLI")
            return''',
'''            record("SHIZUKU_YETKISI_GEREKLI")
            return false''')
patch(probe,'''            record("DEX_CHMOD_HATASI")
            return''',
'''            record("DEX_CHMOD_HATASI")
            return false''')
patch(probe,'''        if (running) return''','''        if (running) return true''')
patch(probe,'''            } finally {
                running = false
                process?.destroy()
                process = null
                synchronized(lock) { keyDown = false }
            }
        }, "melehat-shizuku-raw-diag").apply { isDaemon=true; start() }
    }''',
'''            } finally {
                val unexpected = running
                running = false
                process?.destroy()
                process = null
                synchronized(lock) { keyDown = false }
                if (unexpected) onUnexpectedExit()
            }
        }, "melehat-shizuku-raw-diag").apply { isDaemon=true; start() }
        return true
    }

    fun isRunning(): Boolean = running''')
patch(probe,'''            if (event!="REPEAT")
                record("RAW_KEY_" + event + " " + ExternalPttDiagnostics.screenState(context))''',
'''            if (event!="REPEAT") {
                record("RAW_KEY_" + event + " " + ExternalPttDiagnostics.screenState(context))
                onRawKey(event)
            }''')

# The existing Accessibility handler MUST NOT dispatch a second hardware
# command when the proven raw reader is enabled. It can keep system key capture.
patch(acc,'''        if (event.keyCode != KeyEvent.KEYCODE_VOLUME_UP) return false
        if (event.repeatCount == 0''',
'''        if (event.keyCode != KeyEvent.KEYCODE_VOLUME_UP) return false
        if (ShizukuRawPttState.enabled) {
            // Raw input has exclusive ownership; no competing KEY_UP, timeout,
            // or screen-off release from accessibility is allowed.
            return true
        }
        if (event.repeatCount == 0''')

# Handler serializes raw key callbacks with Android onStartCommand and guards
# against UP/DOWN ordering races while the display turns off.
patch(svc,'    private var shizukuRawProbe: ShizukuRawKeyProbe? = null',
'''    private var shizukuRawProbe: ShizukuRawKeyProbe? = null
    private val rawPttHandler = Handler(Looper.getMainLooper())
    private var rawPttEnabled = false
    private var rawPttHeld = false
    private var rawPttStartedAt = 0L
    private var rawPttSessionId = 0L
    private val rawPttSafety = object: Runnable {
        override fun run() {
            if (!rawPttHeld) return
            val elapsed = SystemClock.uptimeMillis() - rawPttStartedAt
            if (elapsed >= RAW_MAX_HOLD_MS ||
                !rawPttAuthorized() || !store.isRadioEnabled() || roomSwitching) {
                ExternalPttDiagnostics.record(this@PttForegroundService, "watchdog",
                    "RAW_MAX_OR_LOST_SOURCE_RELEASE")
                rawPttRelease("RAW_SAFETY_RELEASE")
                return
            }
            // Feed the existing short PTT guard while the raw device is
            // connected; the independent 30s cap always terminates a lost UP.
            refreshExternalGuard(true)
            rawPttHandler.postDelayed(this, 1000L)
        }
    }
    private fun rawPttAuthorized(): Boolean =
        rawPttEnabled && rawPttHeld && ShizukuRawPttState.enabled &&
            shizukuRawProbe?.isRunning() == true

    private fun rawPttInput(event: String) {
        if (!rawPttEnabled || !ShizukuRawPttState.enabled) return
        when (event) {
            "DOWN" -> {
                if (rawPttHeld || !started || !store.isRadioEnabled() ||
                    roomSwitching || transmitting || pttHeld ||
                    shizukuRawProbe?.isRunning() != true) {
                    ExternalPttDiagnostics.record(this,"shizuku","RAW_DOWN_NOT_ARMED")
                    return
                }
                rawPttHeld = true
                rawPttStartedAt = SystemClock.uptimeMillis()
                rawPttSessionId += 1L
                ExternalPttDiagnostics.record(this,"shizuku",
                    "RAW_PTT_DOWN " + ExternalPttDiagnostics.screenState(this))
                val intent=Intent(this,PttForegroundService::class.java)
                    .setAction(ACTION_PTT_DOWN)
                    .putExtra("melehat.external_ptt",true)
                    .putExtra("melehat.shizuku_raw",true)
                onStartCommand(intent,0,0)
                rawPttHandler.removeCallbacks(rawPttSafety)
                rawPttHandler.postDelayed(rawPttSafety,1000L)
            }
            "UP" -> rawPttRelease("RAW_PTT_UP")
        }
    }

    private fun rawPttRelease(reason: String) {
        if (!rawPttHeld) return
        rawPttHeld=false
        rawPttSessionId+=1L
        rawPttHandler.removeCallbacks(rawPttSafety)
        ExternalPttDiagnostics.record(this,"shizuku",reason)
        val intent=Intent(this,PttForegroundService::class.java)
            .setAction(ACTION_PTT_UP)
            .putExtra("melehat.external_ptt",true)
            .putExtra("melehat.shizuku_raw",true)
        onStartCommand(intent,0,0)
    }

    private fun rawPttDisable(reason: String) {
        rawPttRelease(reason)
        rawPttEnabled=false
        ShizukuRawPttState.enabled=false
        rawPttHandler.removeCallbacks(rawPttSafety)
        shizukuRawProbe?.stop()
        shizukuRawProbe=null
        ExternalPttDiagnostics.record(this,"shizuku","RAW_MODE_OFF "+reason)
    }

    private fun rawPttEnable() {
        if (!started || !store.isRadioEnabled() || roomSwitching ||
            pttHeld || transmitting || rawPttHeld) {
            ExternalPttDiagnostics.record(this,"shizuku","RAW_MODE_REQUIRES_IDLE_RADIO")
            return
        }
        if (rawPttEnabled && shizukuRawProbe?.isRunning()==true) return
        shizukuRawProbe?.stop()
        rawPttEnabled=false
        ShizukuRawPttState.enabled=false
        val bridge=ShizukuRawKeyProbe(
            this,
            onRawKey={ key -> rawPttHandler.post { rawPttInput(key) } },
            onUnexpectedExit={
                rawPttHandler.post {
                    if (rawPttEnabled) rawPttDisable("RAW_READER_EXIT")
                }
            }
        )
        shizukuRawProbe=bridge
        if (!bridge.start()) {
            shizukuRawProbe=null
            ExternalPttDiagnostics.record(this,"shizuku","RAW_MODE_START_FAILED")
            return
        }
        rawPttEnabled=true
        ShizukuRawPttState.enabled=true
        ExternalPttDiagnostics.record(this,"shizuku","RAW_MODE_ARMED")
    }

    private val RAW_MAX_HOLD_MS = 30000L''')

# Do not let the v1.3.55 forced-release receiver kill raw-mode PTT when the
# display transitions to off. Its protection still works for legacy inputs.
patch(svc,'''            if (intent.action != Intent.ACTION_SCREEN_OFF || !externalHeld) return''',
'''            if (intent.action != Intent.ACTION_SCREEN_OFF || !externalHeld ||
                rawPttAuthorized()) return''')
patch(svc,'''            ACTION_SHIZUKU_DIAG_START -> {''',
'''            ACTION_SHIZUKU_PTT_ENABLE -> rawPttEnable()
            ACTION_SHIZUKU_PTT_DISABLE -> rawPttDisable("USER_DISABLED")
            ACTION_SHIZUKU_DIAG_START -> {''')
patch(svc,'''            ACTION_SHIZUKU_DIAG_START -> {
                if (!started || !store.isRadioEnabled()) {''',
'''            ACTION_SHIZUKU_DIAG_START -> {
                if (rawPttEnabled) rawPttDisable("SWITCH_TO_DIAGNOSTIC")
                if (!started || !store.isRadioEnabled()) {''')
patch(svc,'''            ACTION_SHIZUKU_DIAG_STOP -> {
                shizukuRawProbe?.stop()''',
'''            ACTION_SHIZUKU_DIAG_STOP -> {
                if (rawPttEnabled) rawPttDisable("DIAG_STOP")
                shizukuRawProbe?.stop()''')

# Since only internal raw callback marks held, legacy sources still obey the
# screen-off block. The PTT source is gated on each suspend-path check too.
patch(svc,'''                if (externalKey &&
                    !getSystemService(PowerManager::class.java).isInteractive) {''',
'''                if (externalKey &&
                    !getSystemService(PowerManager::class.java).isInteractive &&
                    !(intent?.getBooleanExtra("melehat.shizuku_raw",false)==true
                      && rawPttAuthorized())) {''')
patch(svc,'''        if (external && !getSystemService(PowerManager::class.java).isInteractive) {''',
'''        if (external && !getSystemService(PowerManager::class.java).isInteractive &&
            !rawPttAuthorized()) {''')
patch(svc,'''(external && !getSystemService(PowerManager::class.java).isInteractive))''',
'''(external && !getSystemService(PowerManager::class.java).isInteractive &&
             !rawPttAuthorized()))''',count=2)

# Every stop, channel switch and service termination forcibly closes raw
# transmission before other asynchronous room/floor cleanup.
patch(svc,'''            ACTION_SWITCH_ROOM -> {
                val roomId = intent?.getStringExtra(EXTRA_ROOM_ID).orEmpty()''',
'''            ACTION_SWITCH_ROOM -> {
                if (rawPttEnabled) rawPttDisable("ROOM_SWITCH")
                val roomId = intent?.getStringExtra(EXTRA_ROOM_ID).orEmpty()''')
patch(svc,'''            ACTION_STOP -> {
                clearExternalGuard()''',
'''            ACTION_STOP -> {
                if (rawPttEnabled) rawPttDisable("RADIO_STOP")
                clearExternalGuard()''')
patch(svc,'''    override fun onDestroy() {
        shizukuRawProbe?.stop()''',
'''    override fun onDestroy() {
        if (rawPttEnabled) rawPttDisable("SERVICE_DESTROY")
        shizukuRawProbe?.stop()''')
patch(svc,'''        const val ACTION_SHIZUKU_DIAG_START = "com.saomi.telsiz.SHIZUKU_DIAG_START"''',
'''        const val ACTION_SHIZUKU_PTT_ENABLE = "com.saomi.telsiz.SHIZUKU_PTT_ENABLE"
        const val ACTION_SHIZUKU_PTT_DISABLE = "com.saomi.telsiz.SHIZUKU_PTT_DISABLE"
        const val ACTION_SHIZUKU_DIAG_START = "com.saomi.telsiz.SHIZUKU_DIAG_START"''')

patch(ui,'''        line("SHIZUKU HAM TUŞ TESTİ • mikrofonu kontrol etmez", 18f, true)''',
'''        line("SHIZUKU SES + MANDAL • BASILI KONUŞ", 18f, true)
        line("Ham DOWN/UP olayları üç kez karanlık ekranda doğrulandı. " +
             "Bu özellik isteğe bağlıdır. Tuş basılıyken seçili kanala konuşur, " +
             "bırakınca susar; Shizuku durursa veya tuş bırakma olayı kaybolursa " +
             "güvenlik sınırı en fazla 30 saniyedir.")
        line("Gerçek Shizuku mandalı: " +
            if (com.saomi.telsiz.service.ShizukuRawPttState.enabled)
                "AKTİF" else "KAPALI")
        action("SHIZUKU DIŞ MANDALI AÇ") {
            val i=Intent(this,com.saomi.telsiz.service.PttForegroundService::class.java)
                .setAction(com.saomi.telsiz.service.PttForegroundService.ACTION_SHIZUKU_PTT_ENABLE)
            runCatching { startService(i) }
            render()
        }
        action("SHIZUKU DIŞ MANDALI KAPAT") {
            val i=Intent(this,com.saomi.telsiz.service.PttForegroundService::class.java)
                .setAction(com.saomi.telsiz.service.PttForegroundService.ACTION_SHIZUKU_PTT_DISABLE)
            runCatching { startService(i) }
            render()
        }
        line("SHIZUKU HAM TUŞ TESTİ • mikrofonu kontrol etmez", 18f, true)''')

# The legacy informative text is no longer universally true when the
# verified Shizuku source is active; explain that distinction clearly.
patch(ui,'''        line("ÖNEMLİ: Bu Xiaomi / Android 16 cihazında ekran karanlıkken " +''',
'''        line("NOT: Klasik erişilebilirlik mandalı karanlık ekranda " +
             "güvenlik nedeniyle engellidir. Gerçek basma-bırakma sinyali " +
             "olan Shizuku mandalını ayrıca etkinleştirebilirsiniz.")
        line("ÖNEMLİ: Bu Xiaomi / Android 16 cihazında ekran karanlıkken " +''')
# Guard old hard-coded warning, retained as historical legacy-only guidance:
patch(ui,'''             "mandaldan yayın GÜVENLİK NEDENİYLE ENGELLENDİ. " +''',
'''             "ERİŞİLEBİLİRLİK mandalından yayın engellendi. " +''')

for needle,file in [
    ("rawPttAuthorized()",svc),
    ("RAW_MAX_HOLD_MS = 30000L",svc),
    ("ACTION_SHIZUKU_PTT_ENABLE",svc),
    ("SHIZUKU DIŞ MANDALI AÇ",ui),
    ("SCREEN_OFF_PTT_BLOCKED_FOR_SAFETY",svc),
    ("setTransmitting(true)",svc),
    ("endTransmit()",svc),
    ("roomMutex.withLock",svc),
    ("VideoCallMonitor.start(applicationContext)",svc),
    ("onUnexpectedExit",probe),
    ("RAW_KEY_UP",probe),
    ("ShizukuRawPttState.enabled",acc)
]:
    if needle not in file.read_text(encoding="utf-8"):
        raise SystemExit("v1358 required invariant absent: "+needle)
print("MELEHAT_1358_SHIZUKU_RAW_PTT_BRIDGE_READY")
