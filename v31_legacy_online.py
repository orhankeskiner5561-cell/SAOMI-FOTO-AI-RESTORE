from pathlib import Path
import re

p=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=p.read_text()

# V31 keeps V30 voice/PTT untouched. Extend presence RPC to include legacy v0.27 channel activity.
s=s.replace("V30 • v0.27 SES/PTT • CANLI ÜYELER","V31 • v0.27 SES/PTT • CANLI ÜYELER")
s=s.replace("MELEHAT TELSİZ V30","MELEHAT TELSİZ V31")
s=s.replace('req("get_melehat_members")','req("get_melehat_members_v31")')

p.write_text(s)
b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz.v31"',t,count=1)
t=re.sub(r'versionCode\s*=\s*\d+','versionCode = 3101',t,count=1)
t=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "31.1"',t,count=1)
b.write_text(t)
assert "get_melehat_members_v31" in p.read_text()
print("V31_LEGACY_ONLINE_READY")
