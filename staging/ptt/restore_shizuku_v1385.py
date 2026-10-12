#!/usr/bin/env python3
"""MELEHAT v1.3.85: restore user-verified v1.3.58 Shizuku raw Volume+ PTT.

Restores explicit user-enabled Shizuku preference across room switches,
Android START_STICKY radio service recreation, and temporary reader exit.
Exclusively owns hardware PTT while running: disables smart-silence fallback
and retains the proven RAW_DOWN->PTT_DOWN / RAW_UP->PTT_UP fail-closed flow.
No change to microphone track, existing radio floor, channel, video or UI core.
Shizuku is optional and requires separately running authorized Shizuku.
"""
from pathlib import Path
root=Path("app/src/main/java/com/saomi/telsiz")
svc=root/"service/PttForegroundService.kt"
ui=root/"compat/DeviceCompatibilityActivity.kt"
acc=root/"service/VolumePttAccessibilityService.kt"
probe=root/"service/ShizukuRawKeyProbe.kt"
smart=root/"service/SmartExternalVoiceGate.kt"

def patch(p,a,b,name):
    s=p.read_text("utf-8")
    n=s.count(a)
    assert n==1, f"{name}: expected exactly 1, found {n}"
    p.write_text(s.replace(a,b,1),"utf-8")

# User explicitly opts in with the existing SHIZUKU DIŞ MANDALI AÇ action.
# This preference records preference, NOT device permission. Each restoration
# must pass Shizuku.pingBinder(), authorization, source file and radio tests.
patch(svc,
'''    private var rawPttEnabled = false
    private var rawPttHeld = false''',
'''    private var rawPttEnabled = false
    private var rawPttHeld = false
    private var rawRestoreJob: Job? = null
    private fun rawPref() =
        getSharedPreferences("melehat_shizuku_raw_ptt", MODE_PRIVATE)
    private fun rawDesired() = rawPref().getBoolean("user_enabled",false)

    private fun startRawRestore() {
        if(rawRestoreJob?.isActive==true)return
        rawRestoreJob=scope.launch {
            // Auto-restore only after user has opted into Shizuku on this phone.
            while (isActive && started && store.isRadioEnabled()) {
                if(rawDesired() && !NativeVolumeProbe.isActive(
                        this@PttForegroundService)) {
                    rawPttHandler.post {
                        if(rawDesired() && started && store.isRadioEnabled() &&
                            !roomSwitching && !rawPttEnabled && !rawPttHeld &&
                            !pttHeld && !transmitting &&
                            shizukuRawProbe?.isRunning() != true) {
                            rawPttEnable()
                        }
                    }
                }
                delay(15000L)
            }
        }
    }
    private fun stopRawRestore() {
        rawRestoreJob?.cancel()
        rawRestoreJob=null
    }''',"persisted Shizuku restore controller")

patch(svc,
'''    private fun rawPttDisable(reason: String) {
        rawPttRelease(reason)''',
'''    private fun rawPttDisable(reason: String) {
        // Only an explicit user disable or starting diagnostic testing
        // clears preference. Room switch, process exit and temporary Shizuku
        // reader stop are safe to recover after the channel is stable.
        if(reason=="USER_DISABLED" || reason=="SWITCH_TO_DIAGNOSTIC") {
            rawPref().edit().putBoolean("user_enabled",false).apply()
        }
        rawPttRelease(reason)''',"keep preference through channel lifecycle")

patch(svc,
'''        rawPttEnabled=true
        ShizukuRawPttState.enabled=true
        ExternalPttDiagnostics.record(this,"shizuku","RAW_MODE_ARMED")''',
'''        rawPttEnabled=true
        ShizukuRawPttState.enabled=true
        rawPref().edit().putBoolean("user_enabled",true).apply()
        // A user-selected raw hardware key has exclusive ownership.
        // The 2 second voice-silence fallback is not used in Shizuku mode.
        SmartExternalPttMode.setEnabled(this,false)
        SmartExternalVoiceGate.stop()
        smartMonitorJob?.cancel()
        smartMonitorJob=null
        smartExternal=false
        ExternalPttDiagnostics.record(this,"shizuku",
            "RAW_MODE_ARMED_V1358_RESTORED " +
                ExternalPttDiagnostics.screenState(this))''',"exclusive Shizuku without smart voice fallback")

patch(svc,
'''            ACTION_SHIZUKU_PTT_ENABLE -> rawPttEnable()
            ACTION_SHIZUKU_PTT_DISABLE -> rawPttDisable("USER_DISABLED")''',
'''            ACTION_SHIZUKU_PTT_ENABLE -> {
                rawPttEnable()
                if(rawPttEnabled) startRawRestore()
            }
            ACTION_SHIZUKU_PTT_DISABLE -> {
                rawPttDisable("USER_DISABLED")
                stopRawRestore()
            }''',"existing user actions with future restore")

patch(svc,
'''                started = true
                store.setRadioEnabled(true)
                if (wakeLock?.isHeld != true) wakeLock?.acquire()''',
'''                started = true
                store.setRadioEnabled(true)
                // START_STICKY radio resume after app task exit or process kill
                // should not silently lose the user's enabled Shizuku mandal.
                startRawRestore()
                if (wakeLock?.isHeld != true) wakeLock?.acquire()''',"autostart restore on sticky radio")

patch(svc,
'''            ACTION_STOP -> {
                ptt.forceMute()
                if (rawPttEnabled) rawPttDisable("RADIO_STOP")''',
'''            ACTION_STOP -> {
                ptt.forceMute()
                stopRawRestore()
                if (rawPttEnabled) rawPttDisable("RADIO_STOP")''',"no hidden audio on radio stop")

patch(svc,
'''    private suspend fun stopRadio() {
        SmartExternalVoiceGate.stop()''',
'''    private suspend fun stopRadio() {
        stopRawRestore()
        SmartExternalVoiceGate.stop()''',"cancel rearm on shutdown")

patch(svc,
'''    override fun onDestroy() {
        if (rawPttEnabled) rawPttDisable("SERVICE_DESTROY")''',
'''    override fun onDestroy() {
        stopRawRestore()
        if (rawPttEnabled) rawPttDisable("SERVICE_DESTROY")''',"no active reader after service destruction")

# If Shizuku mode is running, user cannot simultaneously arm smart fallback.
# The independent smart switch remains for Android-only non-Shizuku users.
patch(ui,
'''        line("Gerçek Shizuku mandalı: " +
            if (com.saomi.telsiz.service.ShizukuRawPttState.enabled)
                "AKTİF" else "KAPALI")''',
'''        line("Gerçek Shizuku mandalı: " +
            if (com.saomi.telsiz.service.ShizukuRawPttState.enabled)
                "AKTİF" else "KAPALI")
        line("Shizuku yeniden bağlanma tercihi: " +
            if(getSharedPreferences("melehat_shizuku_raw_ptt",MODE_PRIVATE)
                .getBoolean("user_enabled",false)) "AÇIK" else "KAPALI")
        line("v1.3.58 mandalı geri getirildi: Ses+ gerçek DOWN ile yayına " +
             "başlar, gerçek UP ile derhal susar. Başka kaynak tuşa ortak " +
             "olmaz. Kanal değişiminde ve telsiz servisi yeniden açıldığında " +
             "Shizuku izinli ve çalışıyorsa otomatik yeniden bağlanır. " +
             "Shizuku durursa yayın emniyetle kapanır; bir tuş basışı " +
             "30 saniyeyi aşamaz.")
''',"show correct Shizuku status and restore preference")

# Disallow arming smart mode when user has selected Shizuku's raw key mode.
patch(ui,
'''                    if (!com.saomi.telsiz.service.ScreenOffPttEligibility.consent(
                        this@DeviceCompatibilityActivity) ||
                        !externalPrefs.getBoolean("enabled",false)) {''',
'''                    if (com.saomi.telsiz.service.ShizukuRawPttState.enabled ||
                        getSharedPreferences("melehat_shizuku_raw_ptt",MODE_PRIVATE)
                            .getBoolean("user_enabled",false)) {
                        android.widget.Toast.makeText(this@DeviceCompatibilityActivity,
                            "Önce Shizuku dış mandalını kapatın.",
                            android.widget.Toast.LENGTH_LONG).show()
                    } else if (!com.saomi.telsiz.service.ScreenOffPttEligibility.consent(
                        this@DeviceCompatibilityActivity) ||
                        !externalPrefs.getBoolean("enabled",false)) {''',
"prevent accidental dual mode")

for needed,file in (
    ("RAW_MAX_HOLD_MS = 30000L",svc),
    ('"UP" -> rawPttRelease("RAW_PTT_UP")',svc),
    ('onUnexpectedExit=',svc),
    ('"RAW_MODE_ARMED_V1358_RESTORED "',svc),
    ('if (ShizukuRawPttState.enabled)',acc),
    ('onRawKey(event)',probe),
    ('"AKILLI MANDALI AÇ"',ui),
):
    assert needed in file.read_text("utf-8"), "Protected invariant missing: "+needed
assert 'applicationId = "com.melehat.telsiz"' in Path("app/build.gradle.kts").read_text()
assert (root/"ui/AppRoot.kt").read_text().count("onPtt(true)")>=1
print("MELEHAT_1385_SHIZUKU_V1358_RESTORED_EXCLUSIVE_REARM_READY")
