from pathlib import Path

p=Path("app/build.gradle.kts")
s=p.read_text()
# v0.18 sonrasında ayrı temiz paket kimliği
if 'applicationId = "com.saomi.telsiz"' in s:
    s=s.replace('applicationId = "com.saomi.telsiz"', 'applicationId = "com.melehat.telsiz.v21"')
elif 'applicationId = "com.saomi.telsiz.ptt19"' in s:
    s=s.replace('applicationId = "com.saomi.telsiz.ptt19"', 'applicationId = "com.melehat.telsiz.v21"')
s=s.replace("versionCode = 18","versionCode = 21")
s=s.replace("versionCode = 19","versionCode = 21")
s=s.replace('versionName = "0.18.0"','versionName = "0.21.0"')
s=s.replace('versionName = "0.19.0"','versionName = "0.21.0"')
p.write_text(s)

ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
u=ui.read_text()
u=u.replace("v0.18 • Ses Açma Tuşu PTT","v0.21 • Ses Açma Tuşu PTT")
u=u.replace("v0.17 • Ses Açma Tuşu PTT","v0.21 • Ses Açma Tuşu PTT")
u=u.replace("MELEHAT TELSİZ v0.18","MELEHAT TELSİZ v0.21")
u=u.replace("MELEHAT TELSİZ v0.17","MELEHAT TELSİZ v0.21")
ui.write_text(u)

print("v0.21 clean package applied")
