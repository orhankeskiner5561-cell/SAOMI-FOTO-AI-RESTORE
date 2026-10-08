from pathlib import Path
import re

# Redmi Note 12 Pro / MIUI-HyperOS compatibility layer.
# Do not alter v0.27 LiveKit/PTT/audio code; only Android lifecycle/manifest compatibility.
manifest=Path("app/src/main/AndroidManifest.xml")
s=manifest.read_text()

def add_perm(name):
    global s
    line=f'<uses-permission android:name="{name}" />'
    if line not in s:
        pos=s.find("<application")
        s=s[:pos]+line+"\n    "+s[pos:]

add_perm("android.permission.POST_NOTIFICATIONS")
add_perm("android.permission.FOREGROUND_SERVICE")
add_perm("android.permission.FOREGROUND_SERVICE_MICROPHONE")
add_perm("android.permission.WAKE_LOCK")

# Keep foreground microphone service legal on Android 13/14+ / MIUI.
s=re.sub(
    r'(<service[^>]*android:name="[^"]*PttForegroundService"[^>]*)(/?>)',
    lambda m: m.group(1) + ('' if 'foregroundServiceType=' in m.group(1) else ' android:foregroundServiceType="microphone"') + m.group(2),
    s, count=1, flags=re.S
)
manifest.write_text(s)

# Version bump only. Stable package/signing chain remains unchanged.
g=Path("app/build.gradle.kts")
w=g.read_text()
w=re.sub(r'versionCode\s*=\s*\d+','versionCode = 121',w,count=1)
w=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "1.2.1"',w,count=1)
if 'applicationId = "com.melehat.telsiz"' not in w:
    raise SystemExit("Permanent package changed")
g.write_text(w)

print("REDMI_NOTE12PRO_COMPAT_OK")
