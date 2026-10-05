from pathlib import Path
import re
p=Path("app/build.gradle.kts")
if not p.exists(): p=Path("app/build.gradle")
s=p.read_text()
s,n=re.subn(r'applicationId\s*=\s*["\'][^"\']+["\']','applicationId = "com.melehat.telsiz.c50"',s,count=1)
if n==0: raise SystemExit("applicationId not found")
p.write_text(s)

# UI-visible version labels: replace stale v0.26/v0.27 text in source/resources only.
for base in [Path("app/src/main/java"), Path("app/src/main/res")]:
    if not base.exists(): continue
    for f in base.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in {".kt",".java",".xml",".txt"}: continue
        try: t=f.read_text()
        except: continue
        nt=t.replace("v0.26","C50").replace("v0.27","C50")
        if nt!=t: f.write_text(nt)
print("C50: fresh package + visible version labels updated; no accessibility changes")
