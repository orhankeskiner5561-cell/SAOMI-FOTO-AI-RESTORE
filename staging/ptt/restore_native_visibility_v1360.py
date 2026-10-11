from pathlib import Path

# MELEHAT v1.3.60: restore independent Android Accessibility event visibility.
# PTT dispatch + Shizuku ownership stay exactly as v1.3.59.
# This patch is instrumentation-only: log native events BEFORE the Shizuku
# early-return. Never mistake "no native events delivered" for proof of
# hardware failure. Avoid resetting a running 180s native test on extra taps.

root=Path("app/src/main/java/com/saomi/telsiz")
access=root/"service/VolumePttAccessibilityService.kt"
diagnostics=root/"service/ExternalPttDiagnostics.kt"
native=root/"service/NativeVolumeProbe.kt"
ui=root/"compat/DeviceCompatibilityActivity.kt"

def replace(path,old,new,n=1):
    s=path.read_text(encoding="utf-8")
    if s.count(old)!=n:
        raise SystemExit(f"1360 protected anchor {path.name}: {s.count(old)} != {n}, {old[:95]}")
    path.write_text(s.replace(old,new,n),encoding="utf-8")

# A separate lane prevents the native key telemetry from being overwritten by
# 3-minute test start/stop markers stored in the "key" stage.
replace(diagnostics,
'"key", "dispatch", "service", "audio", "watchdog", "access", "screen", "shizuku" -> stage',
'"key", "dispatch", "service", "audio", "watchdog", "access", "screen", "shizuku", "native" -> stage')

# Original v1.3.58 consumed Accessibility keys when Shizuku raw was active,
# BEFORE the older key logger. This observer preserves visibility without
# dispatching any PTT or changing how either source owns the microphone.
replace(access,
'''        if (event.keyCode != KeyEvent.KEYCODE_VOLUME_UP) return false
        if (NativeVolumeProbe.observe(this,event)) return true''',
'''        if (event.keyCode != KeyEvent.KEYCODE_VOLUME_UP) return false
        // ALWAYS observe Android's delivered key, regardless of active PTT
        // owner. Logging is side-effect-free; Shizuku still exclusively owns
        // actual talking when enabled.
        if ((event.action == KeyEvent.ACTION_DOWN && event.repeatCount == 0) ||
            event.action == KeyEvent.ACTION_UP) {
            ExternalPttDiagnostics.record(this, "native",
                "ACCESSIBILITY_" +
                (if (event.action == KeyEvent.ACTION_UP) "KEY_UP" else "KEY_DOWN") +
                " " + ExternalPttDiagnostics.screenState(this) +
                " SHIZUKU_OWNER=" + ShizukuRawPttState.enabled)
        }
        if (NativeVolumeProbe.observe(this,event)) return true''')

# Prevent accidental repeated taps from erasing in-progress observations.
replace(native,
'''    @Synchronized fun start(context: Context) {
        val now=System.currentTimeMillis()''',
'''    @Synchronized fun start(context: Context) {
        if (isActive(context)) {
            ExternalPttDiagnostics.record(context,"native",
                "ANDROID_ONLY_TEST_ALREADY_RUNNING_NO_RESET")
            return
        }
        val now=System.currentTimeMillis()''')

replace(ui,
'''        line(com.saomi.telsiz.service.NativeVolumeProbe.report(this))
        action("ANDROID YEREL TUŞ TESTİNİ BAŞLAT") {''',
'''        line(com.saomi.telsiz.service.NativeVolumeProbe.report(this))
        line("Android erişilebilirlik son gerçek tuş olayı: " +
            com.saomi.telsiz.service.ExternalPttDiagnostics.describe(this,"native"))
        line("Bu satır, Shizuku mandalı açık olsa bile Android'in teslim " +
             "ettiği tuş olaylarını ayrı kaydeder. Olay gelmiyorsa yeni " +
             "bir olay varmış gibi gösterilmez.")
        action("ANDROID YEREL TUŞ TESTİNİ BAŞLAT") {''')

for file,required in [
    (access, "SHIZUKU_OWNER="),
    (access, "NativeVolumeProbe.observe(this,event)"),
    (access, "ShizukuRawPttState.enabled"),
    (native, "ANDROID_ONLY_TEST_ALREADY_RUNNING_NO_RESET"),
    (diagnostics, '"native" -> stage'),
    (ui, 'ExternalPttDiagnostics.describe(this,"native")'),
    (ui, "SHIZUKU DIŞ MANDALI AÇ"),
]:
    if required not in file.read_text(encoding="utf-8"):
        raise SystemExit("1360 safety/check missing "+required)
print("MELEHAT_1360_SEPARATE_NATIVE_AND_SHIZUKU_DIAGNOSTICS_OK")
