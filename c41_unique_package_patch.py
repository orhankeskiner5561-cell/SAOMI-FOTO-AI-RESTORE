from pathlib import Path
p=Path("app/build.gradle.kts")
if not p.exists():
    p=Path("app/build.gradle")
s=p.read_text()
old='applicationId = "com.melehat.telsiz.v27"'
if old in s:
    s=s.replace(old,'applicationId = "com.melehat.telsiz.c41test"')
else:
    import re
    s,n=re.subn(r'applicationId\s*[= ]\s*["\'].*?["\']','applicationId = "com.melehat.telsiz.c41test"',s,count=1)
    if n==0: raise SystemExit("applicationId not found")
p.write_text(s)
print("C41 independent package set")
