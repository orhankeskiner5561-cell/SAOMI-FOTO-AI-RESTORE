from pathlib import Path
import re

# C58: repair stale LiveKit state and reconnect before PTT.
lk=Path("app/src/main/java/com/saomi/telsiz/voice/LiveKitPttClient.kt")
s=lk.read_text()
s=s.replace("        if (connected) return true","""        // Do not trust our old boolean after sleep/network changes.
        // A fresh connect request replaces a stale room so v0.27 peers remain reachable.
        if (connected && room != null) {
            runCatching { room?.disconnect() }
            room = null
            connected = false
        }""")
lk.write_text(s)

svc=Path("app/src/main/java/com/saomi/telsiz/service/PttForegroundService.kt")
u=svc.read_text()
needle="""        updateNotification("Kanal kontrol ediliyor…")
        val floor = backend.acquireFloor(session, channel.id, 15)"""
repl="""        // Android may have slept or changed network while the service survived.
        // Rebuild LiveKit before acquiring the floor, rather than trusting stale state.
        if (!ptt.connect(store.loadProfile(), channel)) {
            updateNotification("Ses sunucusuna yeniden bağlanıyor…")
            delay(350)
            if (!ptt.connect(store.loadProfile(), channel)) {
                updateNotification("Ses bağlantısı kurulamadı")
                return
            }
        }

        updateNotification("Kanal kontrol ediliyor…")
        val activeSession = sessions.load() ?: session
        val floor = backend.acquireFloor(activeSession, channel.id, 15)"""
if needle not in u: raise SystemExit("beginTransmit marker missing")
u=u.replace(needle,repl,1)
# Use refreshed session for release paths inside beginTransmit/lease where possible.
u=u.replace("backend.releaseFloor(session, channel.id)","backend.releaseFloor(activeSession, channel.id)")
u=u.replace("backend.acquireFloor(session, channel.id, 15)","backend.acquireFloor(activeSession, channel.id, 15)")
svc.write_text(u)

ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
v=ui.read_text().replace("C57 • PTT + Otomatik Yeniden Bağlanma","C58 • v0.27 Uyumlu Yeniden Bağlanma").replace("MELEHAT TELSİZ C57","MELEHAT TELSİZ C58")
ui.write_text(v)

b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz.c58"',t,count=1)
t=re.sub(r'versionCode\s*=\s*\d+','versionCode = 58',t,count=1)
t=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "C58"',t,count=1)
b.write_text(t)
print("C58 LiveKit stale-room recovery applied")
