from pathlib import Path
import re

p=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=p.read_text()

# Make the built UI unmistakably V29.
s=s.replace("v0.27 • PTT + Otomatik Güncelleme","V29 • v0.27 SES/PTT • CANLI ÜYELER")
s=s.replace("MELEHAT TELSİZ v0.26","MELEHAT TELSİZ V29")

# Add a visible member entry without touching any voice/PTT/LiveKit source.
marker='Text("V29 • v0.27 SES/PTT • CANLI ÜYELER"'
if marker in s and 'Text("ÜYELER")' not in s:
    pos=s.find(marker)
    end=s.find("\n",pos)
    indent=s[s.rfind("\n",0,pos)+1:pos]
    s=s[:end+1]+indent+'Text("ÜYELER", fontWeight = FontWeight.Bold, color = Color(0xFF6B4FB3))\n'+s[end+1:]

p.write_text(s)

b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz.v29final"',t,count=1)
t=re.sub(r'versionCode\s*=\s*\d+','versionCode = 2901',t,count=1)
t=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "29.1"',t,count=1)
b.write_text(t)

# Hard verification: fail build if final UI markers were not really inserted.
check=p.read_text()
assert "V29 • v0.27 SES/PTT • CANLI ÜYELER" in check
assert "MELEHAT TELSİZ V29" in check
assert 'Text("ÜYELER"' in check
print("FINAL_V29_UI_VERIFIED")
