from pathlib import Path
import re

# C61 stability repair: remove C60 crash loop; preserve C58/C59 audio path.
svc=Path("app/src/main/java/com/saomi/telsiz/service/PttForegroundService.kt")
s=svc.read_text()
# Remove C60 presence job field and startup loop.
s=s.replace("    private var presenceWatchJob: kotlinx.coroutines.Job? = null\n","")
s=re.sub(r'''\n        presenceWatchJob\?\.cancel\(\)\n        presenceWatchJob = kotlinx\.coroutines\.CoroutineScope\(kotlinx\.coroutines\.SupervisorJob\(\) \+ kotlinx\.coroutines\.Dispatchers\.Default\)\.launch \{\n            while \(isActive\) \{\n                broadcastLiveKitPresence\(\)\n                delay\(1000\)\n            \}\n        \}''',"",s)
s=s.replace("        presenceWatchJob?.cancel()\n","")
svc.write_text(s)

# C61 identity only. C59 participant broadcast remains after successful real connects,
# avoiding the C60 service-onCreate crash loop.
ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
u=ui.read_text().replace("C60 • Canlı Üye Takibi","C61 • Kararlı PTT + Üye Durumu").replace("MELEHAT TELSİZ C60","MELEHAT TELSİZ C61")
ui.write_text(u)

b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz.c61"',t,count=1)
t=re.sub(r'versionCode\s*=\s*\d+','versionCode = 61',t,count=1)
t=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "C61"',t,count=1)
b.write_text(t)
print("C61 stability repair applied")
