from pathlib import Path
p=Path("app/build.gradle.kts")
s=p.read_text()
s=s.replace('applicationId = "com.saomi.telsiz"', 'applicationId = "com.saomi.telsiz.ptt19"')
s=s.replace("versionCode = 18","versionCode = 19")
s=s.replace('versionName = "0.18.0"','versionName = "0.19.0"')
p.write_text(s)
print("v19 package id applied")
