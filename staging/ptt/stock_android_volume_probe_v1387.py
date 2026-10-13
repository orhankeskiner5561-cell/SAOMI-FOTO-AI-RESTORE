#!/usr/bin/env python3
"""MELEHAT v1.3.87: isolated, non-transmitting Android Volume+ visibility test.

Reuses the existing v1.3.59 NativeVolumeProbe rather than adding a second key
listener. Android-only: no root, Shizuku, ADB, synthetic key injection, or
microphone. During the diagnostic, standard phone volume handling is preserved
by returning false from the Accessibility key filter.
"""
from pathlib import Path

base=Path("app/src/main/java/com/saomi/telsiz")
acc=base/"service/VolumePttAccessibilityService.kt"
main=base/"MainActivity.kt"
probe=base/"service/NativeVolumeProbe.kt"
ui=base/"compat/DeviceCompatibilityActivity.kt"

def change(path, old, new, label):
    original=path.read_text(encoding="utf-8")
    hits=original.count(old)
    if hits!=1:
        raise SystemExit(f"MELEHAT_1387 {label}: expected 1 matching anchor, got {hits}")
    path.write_text(original.replace(old,new,1),encoding="utf-8")

# During a diagnostic, observe stock Android key delivery but never consume the
# physical key, modify volume, open microphone or enter any PTT dispatch path.
# Returning false allows Android's ordinary volume behavior to continue.
change(acc,
'''        if (NativeVolumeProbe.observe(this,event)) return true
        if (ShizukuRawPttState.enabled) {''',
'''        if (NativeVolumeProbe.isActive(this)) {
            NativeVolumeProbe.observe(this, event)
            return false // leave the phone's normal Volume+ behavior untouched
        }
        if (ShizukuRawPttState.enabled) {''',
"accessibility standard volume pass-through")

# The Activity is a second possible key dispatcher. The diagnostic must not
# count a second copy of an Accessibility event or start a foreground PTT hold.
# The Android Accessibility listener remains the single measuring source.
change(main,
'''            if (com.saomi.telsiz.service.NativeVolumeProbe.observe(this,
                    event ?: return true)) return true''',
'''            if (com.saomi.telsiz.service.NativeVolumeProbe.isActive(this))
                return super.onKeyDown(keyCode, event)
            if (com.saomi.telsiz.service.NativeVolumeProbe.observe(this,
                    event ?: return true)) return true''',
"Activity DOWN bypass")

change(main,
'''        if (keyCode == KeyEvent.KEYCODE_VOLUME_UP &&
            event != null &&
            com.saomi.telsiz.service.NativeVolumeProbe.observe(this,event)) return true''',
'''        if (keyCode == KeyEvent.KEYCODE_VOLUME_UP &&
            com.saomi.telsiz.service.NativeVolumeProbe.isActive(this))
            return super.onKeyUp(keyCode, event)
        if (keyCode == KeyEvent.KEYCODE_VOLUME_UP &&
            event != null &&
            com.saomi.telsiz.service.NativeVolumeProbe.observe(this,event)) return true''',
"Activity UP bypass")

# KEYGUARD locked but lit is NOT the same as true dark, non-interactive screen.
# Preserve the legacy SCREEN_ON and SCREEN_OFF keys and certification behavior.
change(probe,
'''        val screen=if (context.getSystemService(PowerManager::class.java).isInteractive)
            "SCREEN_ON" else "SCREEN_OFF"''',
'''        val interactive=context.getSystemService(PowerManager::class.java).isInteractive
        val keyguard=context.getSystemService(Context.KEYGUARD_SERVICE)
            as? android.app.KeyguardManager
        val screen=if (!interactive) "SCREEN_OFF"
            else if (keyguard?.isKeyguardLocked==true) "SCREEN_LOCKED_ON"
            else "SCREEN_ON"''',
"separate locked lit screen from non-interactive dark screen")

change(probe,
'''        val onDown=p.getInt("SCREEN_ON_down",0)
        val onUp=p.getInt("SCREEN_ON_up",0)''',
'''        val onDown=p.getInt("SCREEN_ON_down",0)
        val onUp=p.getInt("SCREEN_ON_up",0)
        val lockDown=p.getInt("SCREEN_LOCKED_ON_down",0)
        val lockUp=p.getInt("SCREEN_LOCKED_ON_up",0)''',
"report three actual device states")

change(probe,
'''            "AYDINLIK basma=$onDown bırakma=$onUp | " +
            "bekleyen basış="+p.getBoolean("held",false)''',
'''            "KİLİTLİ AYDINLIK basma=$lockDown bırakma=$lockUp | " +
            "AÇIK EKRAN basma=$onDown bırakma=$onUp | " +
            "bekleyen basış="+p.getBoolean("held",false)''',
"report dark/locked-on/on independently")

# Device data is displayed locally, no telemetry upload, no recording.
# Existing test start/stop buttons remain unchanged.
change(ui,
'''        line(com.saomi.telsiz.service.NativeVolumeProbe.report(this))
        line("Android erişilebilirlik son gerçek tuş olayı: " +''',
'''        line("MELEHAT 1.3.87 • EKRAN KAPALI SES+ TANILAMA",18f,true)
        line("Cihaz: " + android.os.Build.MANUFACTURER + " " +
            android.os.Build.MODEL + " • Android " +
            android.os.Build.VERSION.RELEASE)
        line("Üç ayrı durum ölçülür: EKRAN AÇIK, KİLİTLİ AMA AYDINLIK, " +
            "TAMAMEN KARANLIK. Test ses göndermez. Test boyunca Ses+ " +
            "telefonun normal ses seviyesini değiştirmeye devam eder.")
        line(com.saomi.telsiz.service.NativeVolumeProbe.report(this))
        line("Android erişilebilirlik son gerçek tuş olayı: " +''',
"honest brand-aware on-device results")

change(ui,
'''        line("Önce SHIZUKU DIŞ MANDALI KAPAT. Sonra Android testini başlat, " +
             "ekranı karart, Ses + tuşuna 10 defa 2 saniye basıp bırak, " +
             "ekranı aç, yenile ve sonuçları gönder. " +
             "Bu test ses iletmez; normal BAS KONUŞ düğmesi korunur.")''',
'''        line("Önce SHIZUKU DIŞ MANDALI KAPAT ve Android " +
             "Erişilebilirlik iznini kontrol et. Testi başlat. " +
             "Açık ekranda 3 kez, kilitli ama aydınlık ekranda 3 kez, " +
             "tamamen karanlık ekranda 10 kez Ses+ bas-bırak yap. " +
             "Ekranı açınca uyumluluk sayfasını yeniden görüntüle. " +
             "KARANLIK basma=0 ise bu telefonda Android uygulamaya " +
             "olay ulaştırmıyor olabilir; uygulama tuşu zorla uyandıramaz.")''',
"reproducible three-state Android device test instructions")

for path, required in {
    acc: ["NativeVolumeProbe.observe(this, event)","return false // leave the phone's normal Volume+ behavior untouched",
          "ShizukuRawPttState.enabled"],
    main: ["NativeVolumeProbe.isActive(this)","super.onKeyDown(keyCode, event)",
           "super.onKeyUp(keyCode, event)"],
    probe: ["SCREEN_LOCKED_ON","SCREEN_OFF","ScreenOffPttEligibility.recordPair",
            "ExternalPttDiagnostics.record"],
    ui: ["MELEHAT 1.3.87","ANDROID YEREL TUŞ TESTİNİ BAŞLAT",
         "ANDROID YEREL TUŞ TESTİNİ BİTİR"],
}.items():
    text=path.read_text(encoding="utf-8")
    for token in required:
        if token not in text:
            raise SystemExit(f"MELEHAT_1387 missing {path.name}: {token}")

# Unmodified protected radio / video / room implementation.
fgs=(base/"service/PttForegroundService.kt").read_text(encoding="utf-8")
screen=(base/"ui/AppRoot.kt").read_text(encoding="utf-8")
assert "ACTION_PTT_DOWN" in fgs and "ACTION_PTT_UP" in fgs
assert "onPtt(true)" in screen and "onPtt(false)" in screen
assert 'applicationId = "com.melehat.telsiz"' in Path("app/build.gradle.kts").read_text(encoding="utf-8")
print("MELEHAT_1387_STOCK_ANDROID_SCREEN_OFF_VOLUME_PROBE_READY")
