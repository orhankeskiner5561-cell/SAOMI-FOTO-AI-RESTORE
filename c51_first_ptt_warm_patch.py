from pathlib import Path
import re

# C51: make radio/voice path warm as soon as the authenticated UI opens.
p=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=p.read_text()

# Find the existing service START action used by the UI and add a one-shot warm start
# when the authenticated radio screen is composed. Reuses existing service; no new audio stack.
if "C51_WARM_RADIO" not in s:
    marker = 'val context = LocalContext.current'
    idx = s.find(marker)
    if idx < 0: raise SystemExit("LocalContext marker not found")
    insert = marker + '''
    // C51_WARM_RADIO: prepare the existing radio service immediately on screen entry.
    LaunchedEffect(Unit) {
        runCatching {
            context.startForegroundService(
                Intent(context, com.saomi.telsiz.service.PttForegroundService::class.java).apply {
                    action = com.saomi.telsiz.service.PttForegroundService.ACTION_START
                }
            )
        }
    }
'''
    s=s[:idx]+s[idx:].replace(marker,insert,1)

s=s.replace("C50 • PTT + Otomatik Güncelleme","C51 • PTT + Otomatik Güncelleme")
s=s.replace("MELEHAT TELSİZ C50","MELEHAT TELSİZ C51")
p.write_text(s)

b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz.c51"',t,count=1)
t=re.sub(r'versionCode\s*=\s*\d+','versionCode = 51',t,count=1)
t=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "C51"',t,count=1)
b.write_text(t)
print("C51 warm radio/PTT startup applied")
