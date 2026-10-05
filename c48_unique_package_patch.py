from pathlib import Path
import re
p=Path("app/build.gradle.kts")
if not p.exists(): p=Path("app/build.gradle")
s=p.read_text()
s,n=re.subn(r'applicationId\s*=\s*["\'][^"\']+["\']','applicationId = "com.melehat.telsiz.c48isolated"',s,count=1)
if n==0: raise SystemExit("applicationId not found")
p.write_text(s)
print("C48 unique package: com.melehat.telsiz.c48isolated")
