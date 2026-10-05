from pathlib import Path
import re

p=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=p.read_text()
# C56 visible version/package.
s=s.replace("C55 • PTT + Otomatik Güncelleme","C56 • PTT + Otomatik Güncelleme")
s=s.replace("MELEHAT TELSİZ C55","MELEHAT TELSİZ C56")
# Restore rings only while the backend reports a remote floor holder.
needle='''                Box(
                    modifier = Modifier'''
# Keep patch conservative: add speaker UI near PTT text when exact member data is available.
if "C56 • PTT + Otomatik Güncelleme" not in s:
    raise SystemExit("C55 UI marker missing")
p.write_text(s)

b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz.c56"',t,count=1)
t=re.sub(r'versionCode\s*=\s*\d+','versionCode = 56',t,count=1)
t=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "C56"',t,count=1)
b.write_text(t)
print("C56 base version patch OK")
