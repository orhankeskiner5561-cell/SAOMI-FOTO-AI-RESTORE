from pathlib import Path

# v1.3.59 Android-only accessibility key diagnostic.
# Non-transmitting, no Shizuku access or ADB required for this diagnostic.
# Only an explicit test window records native DOWN/UP events. Existing secure
# radio, on-screen PTT, Shizuku raw bridge and LiveKit are preserved unchanged.
root=Path("app/src/main/java/com/saomi/telsiz")
access=root/"service/VolumePttAccessibilityService.kt"
main=root/"MainActivity.kt"
ui=root/"compat/DeviceCompatibilityActivity.kt"
diag=root/"service/NativeVolumeProbe.kt"
svc=root/"service/PttForegroundService.kt"
if diag.exists(): raise SystemExit("NativeVolumeProbe already exists")

def modify(path,old,new,count=1):
    s=path.read_text(encoding="utf-8")
    if s.count(old)!=count: raise SystemExit(f"v1359 {path.name} missing or repeated anchor({s.count(old)}): {old[:110]}")
    path.write_text(s.replace(old,new,count),encoding="utf-8")

diag.write_text(r'''package com.saomi.telsiz.service

import android.content.Context
import android.os.PowerManager
import android.os.SystemClock
import android.view.KeyEvent
import java.util.Locale

/**
 * Standard Android-only KEY_UP reliability test.
 * It NEVER opens the microphone, grants privileges or starts a PTT session.
 *
 * Event counts use a held state, so a missing UP is not silently accepted as
 * a new test. Records distinguish lit-screen vs non-interactive SCREEN_OFF.
 */
object NativeVolumeProbe {
    private const val PREF = "melehat_native_volume_probe"
    private const val WINDOW_MS = 180_000L

    @Synchronized fun start(context: Context) {
        val now=System.currentTimeMillis()
        context.getSharedPreferences(PREF,Context.MODE_PRIVATE).edit()
            .clear().putBoolean("active",true)
            .putLong("until",now + WINDOW_MS)
            .apply()
        ExternalPttDiagnostics.record(context,"key","ANDROID_ONLY_TEST_START_180S_NO_MIC")
    }

    @Synchronized fun stop(context: Context) {
        context.getSharedPreferences(PREF,Context.MODE_PRIVATE).edit()
            .putBoolean("active",false).apply()
        ExternalPttDiagnostics.record(context,"key","ANDROID_ONLY_TEST_STOP")
    }

    fun isActive(context: Context): Boolean {
        val p=context.getSharedPreferences(PREF,Context.MODE_PRIVATE)
        return p.getBoolean("active",false) &&
            System.currentTimeMillis() < p.getLong("until",0L)
    }

    @Synchronized fun observe(context: Context,event:KeyEvent): Boolean {
        if (!isActive(context) || event.keyCode!=KeyEvent.KEYCODE_VOLUME_UP)
            return false
        if (event.action != KeyEvent.ACTION_DOWN && event.action != KeyEvent.ACTION_UP)
            return true
        if (event.action==KeyEvent.ACTION_DOWN && event.repeatCount>0) return true
        val prefs=context.getSharedPreferences(PREF,Context.MODE_PRIVATE)
        val screen=if (context.getSystemService(PowerManager::class.java).isInteractive)
            "SCREEN_ON" else "SCREEN_OFF"
        val held=prefs.getBoolean("held",false)
        val edit=prefs.edit()
        if (event.action==KeyEvent.ACTION_DOWN) {
            if (held) {
                edit.putInt(screen+"_duplicates",prefs.getInt(screen+"_duplicates",0)+1)
                ExternalPttDiagnostics.record(context,"key",
                    "ANDROID_ONLY_DOWN_DUPLICATE_"+screen)
            } else {
                edit.putBoolean("held",true)
                    .putLong("press_at",SystemClock.uptimeMillis())
                    .putString("press_screen",screen)
                    .putInt(screen+"_down",prefs.getInt(screen+"_down",0)+1)
                ExternalPttDiagnostics.record(context,"key","ANDROID_ONLY_DOWN_"+screen)
            }
        } else {
            val key=if (held) screen+"_up" else screen+"_orphan_up"
            edit.putInt(key,prefs.getInt(key,0)+1)
                .putBoolean("held",false)
            val elapsed=if (held) SystemClock.uptimeMillis()-
                prefs.getLong("press_at",SystemClock.uptimeMillis()) else -1L
            ExternalPttDiagnostics.record(context,"key",
                "ANDROID_ONLY_"+(if (held) "UP_" else "ORPHAN_UP_")+
                screen+" elapsed="+elapsed+"ms")
        }
        edit.apply()
        // Return true: an experiment must not invoke any PTT path.
        return true
    }

    fun report(context:Context):String {
        val p=context.getSharedPreferences(PREF,Context.MODE_PRIVATE)
        val offDown=p.getInt("SCREEN_OFF_down",0)
        val offUp=p.getInt("SCREEN_OFF_up",0)
        val onDown=p.getInt("SCREEN_ON_down",0)
        val onUp=p.getInt("SCREEN_ON_up",0)
        val orphan=p.getInt("SCREEN_OFF_orphan_up",0)
        val dup=p.getInt("SCREEN_OFF_duplicates",0)
        val remaining=((p.getLong("until",0L)-System.currentTimeMillis())/1000L)
            .coerceAtLeast(0L)
        val mode=if (isActive(context)) "TEST DEVAM EDİYOR ("+remaining+" sn)"
            else "TEST KAPALI"
        return "$mode | KARANLIK basma=$offDown bırakma=$offUp " +
            "eşleşmeyen bırakma=$orphan çift basma=$dup | " +
            "AYDINLIK basma=$onDown bırakma=$onUp | " +
            "bekleyen basış="+p.getBoolean("held",false)
    }
}
''',encoding="utf-8")

# Diagnostic interception goes BEFORE the Shizuku owner branch, so the
# test is a no-transmit path even if the user forgets to disable raw mode.
modify(access,
'''        if (event.keyCode != KeyEvent.KEYCODE_VOLUME_UP) return false
        if (ShizukuRawPttState.enabled) {''',
'''        if (event.keyCode != KeyEvent.KEYCODE_VOLUME_UP) return false
        if (NativeVolumeProbe.observe(this,event)) return true
        if (ShizukuRawPttState.enabled) {''')

# Foreground Activity has a second hardware fallback. It must never publish
# while Android-only diagnostic is active.
modify(main,
'''        if (keyCode == KeyEvent.KEYCODE_VOLUME_UP) {
            if (!isPhysicalPttEnabled() || accessibilityOwnsVolume()) {''',
'''        if (keyCode == KeyEvent.KEYCODE_VOLUME_UP) {
            if (com.saomi.telsiz.service.NativeVolumeProbe.observe(this,
                    event ?: return true)) return true
            if (!isPhysicalPttEnabled() || accessibilityOwnsVolume()) {''')
modify(main,
'''        if (keyCode == KeyEvent.KEYCODE_VOLUME_UP && volumePttDown) {''',
'''        if (keyCode == KeyEvent.KEYCODE_VOLUME_UP &&
            event != null &&
            com.saomi.telsiz.service.NativeVolumeProbe.observe(this,event)) return true
        if (keyCode == KeyEvent.KEYCODE_VOLUME_UP && volumePttDown) {''')

# Never let a parallel Shizuku raw listener start transmission while a
# no-audio Android-native key experiment is running.
modify(svc,
'''    private fun rawPttInput(event: String) {
        if (!rawPttEnabled || !ShizukuRawPttState.enabled) return''',
'''    private fun rawPttInput(event: String) {
        if (NativeVolumeProbe.isActive(this)) {
            rawPttRelease("ANDROID_NATIVE_DIAG_NO_AUDIO")
            return
        }
        if (!rawPttEnabled || !ShizukuRawPttState.enabled) return''')
modify(svc,
'''    private fun rawPttEnable() {
        if (!started || !store.isRadioEnabled() || roomSwitching ||''',
'''    private fun rawPttEnable() {
        if (NativeVolumeProbe.isActive(this)) {
            ExternalPttDiagnostics.record(this,"key","NATIVE_DIAG_BLOCKS_SHIZUKU_PTT")
            return
        }
        if (!started || !store.isRadioEnabled() || roomSwitching ||''')

# Keep the experiment clearly separated from the Shizuku PTT and the normal
# Android accessibility mandal. Do not enable it while Shizuku PTT is active.
modify(ui,
'''        line("SHIZUKU SES + MANDAL • BASILI KONUŞ", 18f, true)''',
'''        line("ANDROID YEREL DIŞ MANDAL TESTİ • SHIZUKU GEREKTİRMEZ",18f,true)
        line("Bu testte mikrofondan ses GÖNDERİLMEZ. " +
             "Erişilebilirlik izni açık olmalıdır. Test 3 dakika sonra biter. " +
             "Ekran kapalıyken Android'in gönderdiği Ses + basma ve bırakma " +
             "olayları ölçülür. Başarısızlık diğer üyelerde otomatik dış " +
             "mandal garantisi verilemeyeceğini gösterir.")
        line(com.saomi.telsiz.service.NativeVolumeProbe.report(this))
        action("ANDROID YEREL TUŞ TESTİNİ BAŞLAT") {
            if (com.saomi.telsiz.service.ShizukuRawPttState.enabled) {
                com.saomi.telsiz.service.ExternalPttDiagnostics.record(
                    this,"key","ANDROID_TEST_ICIN_ONCE_SHIZUKU_MANDAL_KAPAT")
            } else {
                com.saomi.telsiz.service.NativeVolumeProbe.start(this)
            }
            render()
        }
        action("ANDROID YEREL TUŞ TESTİNİ BİTİR") {
            com.saomi.telsiz.service.NativeVolumeProbe.stop(this)
            render()
        }
        line("Önce SHIZUKU DIŞ MANDALI KAPAT. Sonra Android testini başlat, " +
             "ekranı karart, Ses + tuşuna 10 defa 2 saniye basıp bırak, " +
             "ekranı aç, yenile ve sonuçları gönder. " +
             "Bu test ses iletmez; normal BAS KONUŞ düğmesi korunur.")
        line("SHIZUKU SES + MANDAL • BASILI KONUŞ", 18f, true)''')

for needle,path in (
    ("NativeVolumeProbe.observe(this,event)",access),
    ("NativeVolumeProbe.observe(this",main),
    ("ANDROID YEREL TUŞ TESTİNİ BAŞLAT",ui),
    ("ANDROID_ONLY_DOWN_",diag),
    ("ANDROID_ONLY_UP_",diag),
    ("SCREEN_OFF",diag),
):
    if needle not in path.read_text(encoding="utf-8"):
        raise SystemExit("v1359 invariant missing "+needle)

print("MELEHAT_1359_ANDROID_ONLY_KEY_DIAGNOSTIC_READY")
