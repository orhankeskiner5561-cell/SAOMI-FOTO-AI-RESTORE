from pathlib import Path

ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
u=ui.read_text().replace("v0.17 • Ses Açma Tuşu PTT","v0.18 • Ses Açma Tuşu PTT").replace("MELEHAT TELSİZ v0.17","MELEHAT TELSİZ v0.18")
ui.write_text(u)

b=Path("app/build.gradle.kts")
t=b.read_text().replace("versionCode = 17","versionCode = 18").replace('versionName = "0.17.0"','versionName = "0.18.0"')
b.write_text(t)

print("v0.18 PTT release bump applied")
