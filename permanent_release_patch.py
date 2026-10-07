from pathlib import Path
import re
p=Path("app/build.gradle.kts")
s=p.read_text()
s=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz"',s,count=1)
s=re.sub(r'versionCode\s*=\s*\d+','versionCode = 101',s,count=1)
s=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "1.0.1"',s,count=1)
p.write_text(s)
u=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
t=u.read_text().replace("v0.27 • PTT + Otomatik Güncelleme","1.0 • v0.27 SES/PTT TEMELİ")
u.write_text(t)
print("PERMANENT_RELEASE_ID_READY")
