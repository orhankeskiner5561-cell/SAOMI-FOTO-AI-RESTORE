#!/usr/bin/env python3
"""MELEHAT v1.3.82: consent-gated, test-certified Android screen-off Volume+ PTT.
No privileged key capture or hidden permission, and no changes to core voice/video.
"""
from pathlib import Path
root=Path("app/src/main/java/com/saomi/telsiz")
acc=root/"service/VolumePttAccessibilityService.kt"
fgs=root/"service/PttForegroundService.kt"
probe=root/"service/NativeVolumeProbe.kt"
compat=root/"compat/DeviceCompatibilityActivity.kt"
gate=root/"service/ScreenOffPttEligibility.kt"

def replace(path, before, after, note):
    s=path.read_text("utf-8")
    n=s.count(before)
    if n!=1: raise RuntimeError(note+" matched "+str(n))
    path.write_text(s.replace(before,after,1),"utf-8")

if gate.exists(): raise RuntimeError("ScreenOffPttEligibility already installed")
gate.write_text('''package com.saomi.telsiz.service

import android.content.Context
import android.os.Build

/**
 * Only stock Android Accessibility KEY_DOWN and KEY_UP, tested with microphone
 * disabled. No root, Shizuku, media hijacking or bypass of platform filtering.
 * Qualification never guarantees future OEM delivery; fast fail-closed timers
 * independently stop a missing KEY_UP.
 */
object ScreenOffPttEligibility {
    private const val PREF="melehat_screen_off_key_qualification"
    private const val VALID_FOR_MS=7L*24L*60L*60L*1000L

    private fun prefs(context:Context)=context.getSharedPreferences(PREF,Context.MODE_PRIVATE)

    fun consent(context:Context):Boolean=prefs(context).getBoolean("consent",false)

    fun grantConsent(context:Context) {
        prefs(context).edit().putBoolean("consent",true).apply()
    }

    fun revokeConsent(context:Context) {
        prefs(context).edit().putBoolean("consent",false).apply()
    }

    fun resetTest(context:Context) {
        prefs(context).edit()
            .remove("qualified_until").remove("fingerprint")
            .putInt("consecutive_pairs",0).putInt("unmatched",0).apply()
    }

    fun recordPair(context:Context,screenOffBoth:Boolean,elapsedMs:Long,orphan:Boolean) {
        val p=prefs(context)
        if(orphan || !screenOffBoth || elapsedMs !in 120L..8000L) {
            // Only mismatches while running this diagnostic reset the test.
            p.edit().putInt("consecutive_pairs",0)
                .putInt("unmatched",p.getInt("unmatched",0)+1)
                .remove("qualified_until").apply()
            return
        }
        val next=p.getInt("consecutive_pairs",0)+1
        val e=p.edit().putInt("consecutive_pairs",next)
        if(next>=3 && p.getInt("unmatched",0)==0) {
            e.putString("fingerprint",Build.FINGERPRINT)
             .putLong("qualified_until",System.currentTimeMillis()+VALID_FOR_MS)
        }
        e.apply()
    }

    fun isQualified(context:Context):Boolean {
        val p=prefs(context)
        return p.getString("fingerprint",null)==Build.FINGERPRINT &&
            System.currentTimeMillis()<p.getLong("qualified_until",0L)
    }

    fun allowed(context:Context):Boolean =
        consent(context) && isQualified(context) &&
        context.getSharedPreferences("melehat_external_ptt",Context.MODE_PRIVATE)
            .getBoolean("enabled",false) &&
        !NativeVolumeProbe.isActive(context)

    fun report(context:Context):String {
        val p=prefs(context)
        return if(isQualified(context))
            "TEST GEÇTİ • 7 günlük güvenli deneme etkin" +
                if(consent(context)) "" else " • kullanıcı onayı gerekli"
        else "TEST GEREKLİ • karanlık ekranda üç ayrı Ses+ bas-bırak " +
            "(eşleşen: "+p.getInt("consecutive_pairs",0)+
            ", eksik/yanlış: "+p.getInt("unmatched",0)+")"
    }
}
''',"utf-8")

# Diagnostic is a no-mic key event qualifier, never a transmitting path.
replace(probe,
'''        context.getSharedPreferences(PREF,Context.MODE_PRIVATE).edit()
            .clear().putBoolean("active",true)''',
'''        ScreenOffPttEligibility.resetTest(context)
        context.getSharedPreferences(PREF,Context.MODE_PRIVATE).edit()
            .clear().putBoolean("active",true)''',"reset test")
replace(probe,
'''        if (event.action==KeyEvent.ACTION_DOWN) {
            if (held) {''',
'''        if (event.action==KeyEvent.ACTION_DOWN) {
            if (held) {''',"diagnostic retained marker")  # assert exact shape
replace(probe,
'''            edit.putInt(key,prefs.getInt(key,0)+1)
                .putBoolean("held",false)
            val elapsed=if (held) SystemClock.uptimeMillis()-
                prefs.getLong("press_at",SystemClock.uptimeMillis()) else -1L
            ExternalPttDiagnostics.record(context,"key",''',
'''            edit.putInt(key,prefs.getInt(key,0)+1)
                .putBoolean("held",false)
            val elapsed=if (held) SystemClock.uptimeMillis()-
                prefs.getLong("press_at",SystemClock.uptimeMillis()) else -1L
            ScreenOffPttEligibility.recordPair(
                context,
                screenOffBoth = held && screen=="SCREEN_OFF" &&
                    prefs.getString("press_screen","")=="SCREEN_OFF",
                elapsedMs=elapsed,
                orphan=!held
            )
            ExternalPttDiagnostics.record(context,"key",''',"only matched DOWN/UP qualify")

replace(probe,
'''        edit.apply()
        // Return true: an experiment must not invoke any PTT path.''',
'''        edit.apply()
        // After three real DOWN/UP pairs, stop the no-audio qualification test.
        if (event.action == KeyEvent.ACTION_UP &&
            ScreenOffPttEligibility.isQualified(context)) stop(context)
        // Return true: an experiment must not invoke any PTT path.''',"automatically finish certified no-audio test")

# Unarmed accessibility events remain normal volume controls.
replace(acc,
'''    private fun isArmed(): Boolean =
        getSharedPreferences(PREFS, MODE_PRIVATE).getBoolean(KEY_ENABLED, false) &&
            LocalStore(this).isRadioEnabled()''',
'''    private fun isArmed(): Boolean =
        ScreenOffPttEligibility.consent(this) &&
            getSharedPreferences(PREFS, MODE_PRIVATE).getBoolean(KEY_ENABLED, false) &&
            LocalStore(this).isRadioEnabled()''',"in-app explicit consent gate")
replace(acc,
'''        if (!power.isInteractive) {
            if (held) release()
            ExternalPttDiagnostics.record(this, "dispatch",
                "SCREEN_OFF_KEY_BLOCKED_NO_RELIABLE_UP")
            return false
        }
        return when (event.action) {''',
'''        if (!power.isInteractive && !ScreenOffPttEligibility.allowed(this)) {
            if (held) release()
            ExternalPttDiagnostics.record(this, "dispatch",
                "SCREEN_OFF_KEY_BLOCKED_NO_RELIABLE_UP")
            return false
        }
        return when (event.action) {''',"conditional screen-off after 3 real matched pairs")
replace(acc,
'''                if (!held && event.repeatCount == 0) {
                    held = true''',
'''                if (!held && event.repeatCount == 0) {
                    held = true''',"preserve fresh down only")
replace(acc,
'''        private const val NO_REPEAT_LIMIT_MS = 20000L''',
'''        private const val NO_REPEAT_LIMIT_MS = 8000L''',"short fail-closed timer")
# no-repeat limit now eight seconds for both screen states; no fake long hold.
# Suppressed KEY_UP cannot cause indefinite listening.

# The microphone service separately rejects uncertified screen-off events.
replace(fgs,
'''                    !(intent?.getBooleanExtra("melehat.shizuku_raw",false)==true
                      && rawPttAuthorized())) {''',
'''                    !((intent?.getBooleanExtra("melehat.shizuku_raw",false)==true
                      && rawPttAuthorized()) ||
                      ScreenOffPttEligibility.allowed(this))) {''',"server-screen-off ACTION_DOWN guard")
replace(fgs,
'''        if (external && !getSystemService(PowerManager::class.java).isInteractive &&
            !rawPttAuthorized()) {''',
'''        if (external && !getSystemService(PowerManager::class.java).isInteractive &&
            !rawPttAuthorized() && !ScreenOffPttEligibility.allowed(this)) {''',"pre-floor microphone gate")
old='''(external && !getSystemService(PowerManager::class.java).isInteractive &&
             !rawPttAuthorized())'''
s=fgs.read_text("utf-8")
if s.count(old)!=2: raise RuntimeError("expected 2 additional recheck guards, got "+str(s.count(old)))
s=s.replace(old,'''(external && !getSystemService(PowerManager::class.java).isInteractive &&
             !rawPttAuthorized() && !ScreenOffPttEligibility.allowed(this))''')
fgs.write_text(s,"utf-8")
replace(fgs,
'''            val maxWait = if (externalRepeating) 4500L else 21000L''',
'''            val maxWait = if (externalRepeating) 4500L else 9000L''',"service-side independent cutoff")
replace(fgs,
'''            if (externalRepeating) 4500L else 21000L)''',
'''            if (externalRepeating) 4500L else 9000L)''',"guard initial timeout")
# No retroactive screen-off permission: any held external key on screen-off
# transitions is forcibly released. Only fresh DOWN while off is eligible.

# Play disclosure occurs before requesting user opt-in; never claim the app is
# an 'isAccessibilityTool' or grant Accessibility permissions automatically.
s=compat.read_text("utf-8")
old='''            setOnCheckedChangeListener { _, checked ->
                externalPrefs.edit().putBoolean("enabled", checked).apply()
                if (!checked) {
                    // Force a release if the switch is disabled during a hold.
                    val stop = Intent(this@DeviceCompatibilityActivity,
                        com.saomi.telsiz.service.PttForegroundService::class.java)
                        .setAction(com.saomi.telsiz.service.PttForegroundService.ACTION_PTT_UP)
                    runCatching { startService(stop) }
                }
            }'''
new='''            setOnCheckedChangeListener { button, checked ->
                if (checked &&
                    !com.saomi.telsiz.service.ScreenOffPttEligibility.consent(
                        this@DeviceCompatibilityActivity)) {
                    button.isChecked=false
                    android.app.AlertDialog.Builder(this@DeviceCompatibilityActivity)
                        .setTitle("MELEHAT • Ses+ dış mandal izni")
                        .setMessage(
                            "MELEHAT, Android Erişilebilirlik hizmetini yalnızca Ses+ " +
                            "tuşunun basma/bırakma olaylarını dinleyip telsiz " +
                            "mikrofonunu sizin komutunuzla açmak ve kapatmak için " +
                            "kullanır. Ekran içeriği okunmaz, başka uygulamalardaki " +
                            "bilgiler toplanmaz; tuş olayları sunucuya gönderilmez. " +
                            "Basılı konuştuğunuz ses seçili kanaldaki üyelere iletilir. " +
                            "İzni Android Ayarları'ndan istediğiniz zaman kapatabilirsiniz. " +
                            "Kilitli ekranda çalışma cihazınızın izin verdiği tuş " +
                            "olaylarına bağlıdır; uyumluluk testi gerektirir."
                        )
                        .setNegativeButton("ONAYLAMIYORUM",null)
                        .setPositiveButton("KABUL EDİYORUM") { _,_ ->
                            com.saomi.telsiz.service.ScreenOffPttEligibility.grantConsent(
                                this@DeviceCompatibilityActivity)
                            externalPrefs.edit().putBoolean("enabled",true).apply()
                            render()
                        }
                        .show()
                } else {
                    externalPrefs.edit().putBoolean("enabled",checked).apply()
                    if (!checked) {
                        val stop = Intent(this@DeviceCompatibilityActivity,
                            com.saomi.telsiz.service.PttForegroundService::class.java)
                            .setAction(com.saomi.telsiz.service.PttForegroundService.ACTION_PTT_UP)
                        runCatching { startService(stop) }
                    }
                }
            }'''
if s.count(old)!=1:raise RuntimeError("on-off switch consent anchor changed")
s=s.replace(old,new,1)
old_line='''        line("Dış Mandal anahtarı: " + if (externalEnabled) "✓ AÇIK" else "⚠ KAPALI")'''
extra='''        line("Karanlık ekran Ses+ güvenlik testi: " +
            com.saomi.telsiz.service.ScreenOffPttEligibility.report(this))
        line("Karanlık ekranda yayın yalnızca üç başarılı bas-bırak " +
             "testinden sonra, açık kullanıcı onayıyla denenebilir. " +
             "Tuş bırakma gelmezse kısa güvenlik süresiyle yayın kesilir. " +
             "Her marka/modelde çalışması garanti edilmez.")
'''
if s.count(old_line)!=1:raise RuntimeError("compat status anchor changed")
s=s.replace(old_line,old_line+"\n"+extra,1)
compat.write_text(s,"utf-8")
replace(compat,
'''            isChecked = externalPrefs.getBoolean("enabled", false)''',
'''            isChecked = externalPrefs.getBoolean("enabled", false) &&
                com.saomi.telsiz.service.ScreenOffPttEligibility.consent(
                    this@DeviceCompatibilityActivity)''',"switch reflects explicit consent")
replace(compat,
'''        val externalEnabled = externalPrefs.getBoolean("enabled", false)''',
'''        val externalEnabled = externalPrefs.getBoolean("enabled", false) &&
            com.saomi.telsiz.service.ScreenOffPttEligibility.consent(this)''',"status reflects consent")

assert "applicationId = \"com.melehat.telsiz\"" in Path("app/build.gradle.kts").read_text()
for token in (
    "SCREEN_OFF_KEY_BLOCKED_NO_RELIABLE_UP",
    "SCREEN_OFF_FORCED_RELEASE",
    "ACTION_PTT_UP", "KEYCODE_VOLUME_UP",
    "NativeVolumeProbe.observe(this,event)",
    "ShizukuRawPttState.enabled"
): assert token in acc.read_text("utf-8")
for token in (
    "SCREEN_OFF_PTT_BLOCKED_FOR_SAFETY",
    "SCREEN_OFF_SERVICE_FORCED_RELEASE",
    "SCREEN_OFF_MIC_BLOCKED_FOR_SAFETY",
    "RAW_MAX_HOLD_MS = 30000L",
    "ptt.forceMute()", "transmitRequestId",
    "PttForegroundService"
): assert token in fgs.read_text("utf-8")
print("MELEHAT_1382_SCREEN_OFF_CERTIFIED_NATIVE_VOLUME_PTT_WITH_USER_CONSENT_READY")
