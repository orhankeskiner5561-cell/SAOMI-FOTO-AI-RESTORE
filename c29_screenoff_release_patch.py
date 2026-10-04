from pathlib import Path
import re

svc=Path("app/src/main/java/com/saomi/telsiz/service/VolumePttAccessibilityService.kt")
s=svc.read_text()
s=s.replace("private const val RELEASE_QUIET_MS = 1400L", "private const val RELEASE_QUIET_MS = 800L")
svc.write_text(s)

ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
u=ui.read_text()
u=u.replace("C28 • v0.27 TABAN • Dış Mandal", "C29 • v0.27 TABAN • Kilit Ekranı PTT")
u=u.replace("MELEHAT TELSİZ C28", "MELEHAT TELSİZ C29")
ui.write_text(u)

b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'versionCode\s*=\s*\d+', 'versionCode = 29', t)
t=re.sub(r'versionName\s*=\s*"[^"]+"', 'versionName = "C29-screenoff-release-failsafe"', t)
b.write_text(t)
# Repair malformed literal \\n sequences produced when strings.xml is created from scratch.
strings=Path("app/src/main/res/values/strings.xml")
if strings.exists():
    x=strings.read_text()
    x=x.replace("\\\\n", "\\n")
    strings.write_text(x)
print("C29 applied: 800ms screen-off release failsafe + strings.xml repair")
