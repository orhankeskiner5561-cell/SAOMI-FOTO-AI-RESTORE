from pathlib import Path
import re

# C52: remove C51 premature service warmup, then expose UI only from real radio state.
ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=ui.read_text()

# Remove the exact C51 warm block so auth/OTP screen never starts radio notification.
s=re.sub(r'\n\s*// C51_WARM_RADIO:.*?\n\s*LaunchedEffect\(Unit\) \{.*?\n\s*\}\n', '\n', s, count=1, flags=re.S)

# Version identity visible in UI.
s=s.replace("C50","C52").replace("C51","C52")
ui.write_text(s)

b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz.c52"',t,count=1)
t=re.sub(r'versionCode\s*=\s*\d+','versionCode = 52',t,count=1)
t=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "C52"',t,count=1)
b.write_text(t)

# Add explicit radio-state broadcast hooks to existing PTT service.
p=Path("app/src/main/java/com/saomi/telsiz/service/PttForegroundService.kt")
x=p.read_text()
if "ACTION_RADIO_STATE" not in x:
    # Broadcast only on actual state transitions; UI can key animation/name/photo from these states.
    x=x.replace('updateNotification("YAYINDA • Ses karşıya gidiyor")',
'''updateNotification("YAYINDA • Ses karşıya gidiyor")
        sendBroadcast(Intent(ACTION_RADIO_STATE).setPackage(packageName)
            .putExtra(EXTRA_STATE, "TRANSMITTING"))''')
    x=x.replace('updateNotification("Kanal dinlemede • Bas-konuş hazır")',
'''updateNotification("Kanal dinlemede • Bas-konuş hazır")
        sendBroadcast(Intent(ACTION_RADIO_STATE).setPackage(packageName)
            .putExtra(EXTRA_STATE, "IDLE"))''')
    # Insert constants into companion object if present.
    x=x.replace('companion object {','''companion object {
        const val ACTION_RADIO_STATE = "com.melehat.telsiz.RADIO_STATE"
        const val EXTRA_STATE = "state"''',1)
p.write_text(x)

print("C52: C51 premature startup removed; real PTT state broadcast foundation added")
