from pathlib import Path
import re

# C60: continuously publish actual LiveKit room participants.
svc=Path("app/src/main/java/com/saomi/telsiz/service/PttForegroundService.kt")
s=svc.read_text()
# Start a lightweight room-presence loop with the service lifecycle.
marker='''        super.onCreate()'''
if marker not in s: raise SystemExit("onCreate marker missing")
if "presenceWatchJob" not in s:
    # add Job field beside class body
    classpos=s.find("{",s.find("class PttForegroundService"))
    s=s[:classpos+1]+'''\n    private var presenceWatchJob: kotlinx.coroutines.Job? = null\n'''+s[classpos+1:]
    s=s.replace(marker,marker+'''
        presenceWatchJob?.cancel()
        presenceWatchJob = kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.SupervisorJob() + kotlinx.coroutines.Dispatchers.Default).launch {
            while (isActive) {
                broadcastLiveKitPresence()
                delay(1000)
            }
        }''',1)
    # cancel if onDestroy exists
    if "override fun onDestroy()" in s:
        s=s.replace("override fun onDestroy() {","override fun onDestroy() {\n        presenceWatchJob?.cancel()",1)
svc.write_text(s)

ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
u=ui.read_text()
u=u.replace("C59 • v0.27 Canlı Durum Uyumlu","C60 • Canlı Üye Takibi")
u=u.replace("MELEHAT TELSİZ C59","MELEHAT TELSİZ C60")
ui.write_text(u)

b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz.c60"',t,count=1)
t=re.sub(r'versionCode\s*=\s*\d+','versionCode = 60',t,count=1)
t=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "C60"',t,count=1)
b.write_text(t)
print("C60 continuous LiveKit presence applied")
