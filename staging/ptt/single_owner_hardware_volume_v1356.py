from pathlib import Path

# v1.3.56: Physical-volume PTT must have one owner. Previously MainActivity
# sent untagged ACTION_PTT_DOWN independently of accessibility. A physical
# press begun just before screen-off could keep the microphone active because
# v1.3.55 screen-off safety only releases explicitly tagged external holds.
# Keep the safety block on dark screen until low-level KEY_UP can be verified.
root=Path("app/src/main/java/com/saomi/telsiz")
activity=root/"MainActivity.kt"
service=root/"service/PttForegroundService.kt"
acc=root/"service/VolumePttAccessibilityService.kt"
compat=root/"compat/DeviceCompatibilityActivity.kt"

def patch(path,old,new):
    s=path.read_text(encoding="utf-8")
    if s.count(old)!=1:
        raise SystemExit(f"v1356 protected anchor failed {path.name}: {s.count(old)} occurrences {old[:85]}")
    path.write_text(s.replace(old,new,1),encoding="utf-8")

patch(activity,'''    override fun onStop() {
        com.saomi.telsiz.voice.LiveChannelUiState.visualizerVisible = false''',
'''    override fun onStop() {
        // A foreground Activity never owns PTT after the display goes dark.
        // Android may omit ACTION_UP when locking; release before onStop.
        if (volumePttDown) {
            volumePttDown = false
            sendPhysicalPttAction(PttForegroundService.ACTION_PTT_UP)
            com.saomi.telsiz.service.ExternalPttDiagnostics.record(
                this,"key","ACTIVITY_STOP_FORCED_RELEASE")
        }
        com.saomi.telsiz.voice.LiveChannelUiState.visualizerVisible = false''')

patch(activity,'''    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_VOLUME_UP && !volumePttDown) {
            volumePttDown = true
            sendServiceAction(PttForegroundService.ACTION_PTT_DOWN)
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    override fun onKeyUp(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_VOLUME_UP && volumePttDown) {
            volumePttDown = false
            sendServiceAction(PttForegroundService.ACTION_PTT_UP)
            return true
        }
        return super.onKeyUp(keyCode, event)
    }''',
'''    private fun isPhysicalPttEnabled(): Boolean =
        getSharedPreferences("melehat_external_ptt", MODE_PRIVATE)
            .getBoolean("enabled", false) && LocalStore(this).isRadioEnabled()

    private fun accessibilityOwnsVolume(): Boolean {
        val serviceId = android.content.ComponentName(
            this, com.saomi.telsiz.service.VolumePttAccessibilityService::class.java
        ).flattenToString()
        return android.provider.Settings.Secure.getString(
            contentResolver, android.provider.Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        ).orEmpty().split(':').any { it.equals(serviceId, ignoreCase=true) }
    }

    private fun sendPhysicalPttAction(action: String) {
        // Tag every physical button as external. The existing foreground
        // radio then applies its screen-off guard and bounded release logic.
        val intent = Intent(this, PttForegroundService::class.java)
            .setAction(action).putExtra("melehat.external_ptt", true)
        runCatching { startService(intent) }.onFailure {
            com.saomi.telsiz.service.ExternalPttDiagnostics.record(
                this, "dispatch", "ACTIVITY_PTT_ERROR " + it.javaClass.simpleName)
        }
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_VOLUME_UP) {
            if (!isPhysicalPttEnabled() || accessibilityOwnsVolume()) {
                return super.onKeyDown(keyCode, event)
            }
            if (!volumePttDown && (event?.repeatCount ?: 0) == 0) {
                volumePttDown = true
                com.saomi.telsiz.service.ExternalPttDiagnostics.record(
                    this, "key", "ACTIVITY_KEY_DOWN_SCREEN_ON")
                sendPhysicalPttAction(PttForegroundService.ACTION_PTT_DOWN)
            }
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    override fun onKeyUp(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_VOLUME_UP && volumePttDown) {
            volumePttDown = false
            sendPhysicalPttAction(PttForegroundService.ACTION_PTT_UP)
            com.saomi.telsiz.service.ExternalPttDiagnostics.record(
                this, "key", "ACTIVITY_KEY_UP_SCREEN_ON")
            return true
        }
        return super.onKeyUp(keyCode, event)
    }''')

patch(service,'''            ACTION_PTT_DOWN -> {
                val externalKey = intent?.getBooleanExtra("melehat.external_ptt", false) == true
                if (externalKey &&
                    !getSystemService(PowerManager::class.java).isInteractive) {''',
'''            ACTION_PTT_DOWN -> {
                val externalKey = intent?.getBooleanExtra("melehat.external_ptt", false) == true
                // Duplicate hardware DOWN must not reset the request ID or
                // extend an already held transmission. One physical press = one PTT.
                if (externalKey && externalHeld) {
                    ExternalPttDiagnostics.record(this, "service",
                        "DUPLICATE_PHYSICAL_DOWN_IGNORED")
                    return START_STICKY
                }
                if (externalKey &&
                    !getSystemService(PowerManager::class.java).isInteractive) {''')

patch(service,'''        ptt.setTransmitting(false)

        val session = sessions.load()
        if (session != null) {''',
'''        val muted = ptt.setTransmitting(false)
        ExternalPttDiagnostics.record(this, "audio",
            (if (muted) "MIC_MUTED" else "MIC_MUTE_NOT_CONFIRMED") +
            " " + ExternalPttDiagnostics.screenState(this))

        val session = sessions.load()
        if (session != null) {''')

patch(compat,'''        line("ÖNEMLİ: Bu Xiaomi / Android 16 cihazında ekran karanlıkken " +''',
'''        line("v1.3.56: Telefon Ses + tuşu artık hem Activity hem Erişilebilirlik " +
             "üzerinden iki ayrı PTT başlatamaz. Ekran kapanırken Activity'nin " +
             "bekleyen fiziksel tuş basışı zorunlu olarak kapatılır.")
        line("ÖNEMLİ: Bu Xiaomi / Android 16 cihazında ekran karanlıkken " +''')

for text, file in [
("ACTIVITY_STOP_FORCED_RELEASE",activity),
("accessibilityOwnsVolume()",activity),
('putExtra("melehat.external_ptt", true)',activity),
("DUPLICATE_PHYSICAL_DOWN_IGNORED",service),
("SCREEN_OFF_PTT_BLOCKED_FOR_SAFETY",service),
("SCREEN_OFF_SERVICE_FORCED_RELEASE",service),
("MIC_MUTED",service),
("NO_REPEAT_LIMIT_MS",acc)
]:
    if text not in file.read_text(encoding="utf-8"):
        raise SystemExit("v1356 protected safety invariant missing "+text)
print("MELEHAT_1356_SINGLE_HARDWARE_SOURCE_AND_MIC_MUTE_LOGS_OK")