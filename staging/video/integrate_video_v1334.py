from pathlib import Path

root=Path("app/src/main")
src=Path("../staging/video")
target=root/"java/com/saomi/telsiz/video"
target.mkdir(parents=True,exist_ok=True)
for file in ("VideoCallApi.kt","VideoCallActivity.kt"):
    text=(src/file).read_text(encoding="utf-8")
    if not text.strip(): raise SystemExit(file+" empty")
    (target/file).write_text(text,encoding="utf-8")

# Only append private activity/camera permission; never replace the working
# microphone/LiveKit/PTT service or existing Android package identity.
manifest=root/"AndroidManifest.xml"
s=manifest.read_text(encoding="utf-8")
if '<uses-permission android:name="android.permission.CAMERA"' not in s:
    s=s.replace("<application", '<uses-permission android:name="android.permission.CAMERA" />\n    <application',1)
if 'com.saomi.telsiz.video.VideoCallActivity' not in s:
    s=s.replace("</application>",'''
        <activity
            android:name="com.saomi.telsiz.video.VideoCallActivity"
            android:exported="false"
            android:screenOrientation="portrait" />
    </application>''',1)
manifest.write_text(s,encoding="utf-8")
print("MELEHAT_VIDEO_ACTIVITY_MANIFEST_OK")
