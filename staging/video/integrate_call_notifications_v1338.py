from pathlib import Path

# v1.3.38. No changes to LiveKit media, PTT floor, signing or radio channels.
root = Path("app/src/main")
java = root / "java/com/saomi/telsiz"
video = java / "video"
video.mkdir(parents=True, exist_ok=True)
for filename in ("VideoCallMonitor.kt", "IncomingVideoCallActivity.kt"):
    src = Path("../staging/video") / filename
    if not src.is_file():
        raise SystemExit("Missing MELEHAT incoming call source "+filename)
    (video / filename).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

manifest = root / "AndroidManifest.xml"
s = manifest.read_text(encoding="utf-8")
for permission in ("android.permission.POST_NOTIFICATIONS",
                   "android.permission.USE_FULL_SCREEN_INTENT"):
    tag = '<uses-permission android:name="' + permission + '" />'
    if permission not in s:
        s = s.replace("<application", tag + "\n    <application", 1)

name = 'android:name="com.saomi.telsiz.video.IncomingVideoCallActivity"'
if name not in s:
    entry = '''
        <activity
            android:name="com.saomi.telsiz.video.IncomingVideoCallActivity"
            android:exported="false"
            android:showWhenLocked="true"
            android:turnScreenOn="true"
            android:excludeFromRecents="true" />
'''
    if s.count("</application>") != 1:
        raise SystemExit("MELEHAT AndroidManifest missing application closure")
    s = s.replace("</application>", entry + "    </application>", 1)
manifest.write_text(s, encoding="utf-8")

service = java / "service/PttForegroundService.kt"
s = service.read_text(encoding="utf-8")
if "VideoCallMonitor.start(applicationContext)" in s:
    raise SystemExit("Duplicate PTT call-monitor setup")
if "    override fun onCreate() {" in s:
    s = s.replace("    override fun onCreate() {",
                  """    override fun onCreate() {
        // Poll video invitation status through the already-running radio FGS.
        // Does not create or modify any PTT microphone/audio connections.
        com.saomi.telsiz.video.VideoCallMonitor.start(applicationContext)""", 1)
else:
    pos = s.find("    override fun onStartCommand(")
    if pos < 0:
        raise SystemExit("No safe PTT foreground-service lifecycle anchor")
    s = s[:pos] + """    override fun onCreate() {
        super.onCreate()
        com.saomi.telsiz.video.VideoCallMonitor.start(applicationContext)
    }

""" + s[pos:]
service.write_text(s, encoding="utf-8")

main = java / "MainActivity.kt"
s = main.read_text(encoding="utf-8")
anchor = "        super.onCreate(savedInstanceState)"
if s.count(anchor) != 1:
    raise SystemExit("MainActivity onCreate anchor incorrect: " + str(s.count(anchor)))
s = s.replace(anchor, anchor + '''
        // Start caller-ID/missed-call monitor from the user-visible Activity;
        // the same process-wide monitor is shared with the radio service.
        com.saomi.telsiz.video.VideoCallMonitor.start(applicationContext)
        if (android.os.Build.VERSION.SDK_INT >= 33 &&
            androidx.core.content.ContextCompat.checkSelfPermission(
                this, android.Manifest.permission.POST_NOTIFICATIONS
            ) != android.content.pm.PackageManager.PERMISSION_GRANTED
        ) {
            // Runtime prompt is shown in foreground only, never from a service.
            requestPermissions(
                arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 50263
            )
        }
''', 1)
main.write_text(s, encoding="utf-8")

ui = java / "ui/AppRoot.kt"
s = ui.read_text(encoding="utf-8")
anchor = "    val videoApi = remember(callContext) { VideoCallApi(callContext) }"
if s.count(anchor) != 1:
    raise SystemExit("MELEHAT video API UI anchor not found")
s = s.replace(anchor, anchor + '''
    val lastMissedVideo by com.saomi.telsiz.video.VideoCallMonitor.latestMissed.collectAsState()
''', 1)

# Existing modal still handles calls while the app is in the foreground.
# Avoid playing two simultaneous ringtones when Android call notification
# is permitted and already providing the system phone ring.
start = s.find('    DisposableEffect(incomingVideoCall?.id) {')
end_marker = '        onDispose { sound?.stop() }\n    }'
end = s.find(end_marker,start)
if start < 0 or end < 0:
    raise SystemExit("Existing incoming-call ringtone effect anchor changed")
end += len(end_marker)
block = s[start:end]
if 'val sound = if (ringing != null)' not in block:
    raise SystemExit("Ringtone effect changed")
block = block.replace(
    'val sound = if (ringing != null) {',
    '''val sound = if (ringing != null &&
            !com.saomi.telsiz.video.VideoCallMonitor.notificationsEnabled(callContext)) {'''
)
s=s[:start]+block+s[end:]

# Display last incoming unanswered video call in MELEHAT home, even after
# restarting the app; clearing it doesn't clear prior call permissions.
status = 'Text("Telsiz durumu"'
if s.count(status) != 1:
    raise SystemExit("Telsiz status visual location changed: "+str(s.count(status)))
pos=s.find(status)
# Only inject before the containing status Text, preserving existing PTT layout.
line=s.rfind("\n",0,pos)+1
prefix=s[line:pos]
if not prefix.isspace():
    raise SystemExit("Unexpected status indentation")
banner = '''
            if (lastMissedVideo != null) {
                val missed = lastMissedVideo!!
                androidx.compose.material3.Card(
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(Modifier.fillMaxWidth().padding(10.dp)) {
                        Text("📵 Son cevapsız görüntülü arama",
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFFC12842))
                        Text("Arayan: " + missed.callerName)
                        TextButton(onClick = {
                            com.saomi.telsiz.video.VideoCallMonitor.dismissMissed(callContext)
                        }) { Text("GÖRDÜM") }
                    }
                }
            }
            if (android.os.Build.VERSION.SDK_INT >= 34) {
                val callNotices = callContext.getSystemService(
                    android.app.NotificationManager::class.java
                )
                if (!callNotices.canUseFullScreenIntent()) {
                    TextButton(onClick = {
                        runCatching {
                            callContext.startActivity(android.content.Intent(
                                android.provider.Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT,
                                android.net.Uri.parse("package:" + callContext.packageName)
                            ))
                        }
                    }) {
                        Text("🔔 Kilit ekranında gelen aramayı göster • İZİN VER")
                    }
                }
            }
'''
s=s[:line]+banner+s[line:]
for keep in ("AÇ / KABUL ET", "REDDET / KAPAT", "MelehatPendingRequestBadge",
             "KANAL AÇ  +", "incomingVideoCall", "roomSelection = createdId to cmd.second"):
    if keep not in s:
        raise SystemExit("Prior working UI component missing: "+keep)
ui.write_text(s, encoding="utf-8")
print("MELEHAT_1338_FULL_SCREEN_CALLER_AND_MISSED_NOTICE_OK")
