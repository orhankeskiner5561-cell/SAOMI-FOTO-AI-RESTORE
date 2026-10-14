#!/usr/bin/env python3
"""MELEHAT v1.3.89: keep an explicitly enabled foreground radio session
independent of Activity visibility and offer an opt-in Android Doze exemption.
Never fake 'online' state when the authenticated presence server is unreachable.
Do not change PTT, WebRTC, video calls, credentials, package ID or signing.
"""
from pathlib import Path

base = Path("app/src/main")
service = base / "java/com/saomi/telsiz/service/PttForegroundService.kt"
activity = base / "java/com/saomi/telsiz/MainActivity.kt"
manifest = base / "AndroidManifest.xml"

def replace_once(path: Path, before: str, after: str, label: str) -> None:
    contents = path.read_text(encoding="utf-8")
    found = contents.count(before)
    if found != 1:
        raise RuntimeError(f"v1389 {label}: expected 1 anchor, got {found}")
    path.write_text(contents.replace(before, after, 1), encoding="utf-8")

# ACTION_START is also issued when the Activity is recreated. This previously
# set CONNECTING and began a new P2P/LiveKit connect even if the foreground
# service and its active heartbeat were already running. A second connect
# must not interrupt an existing PTT floor or room presence.
replace_once(service,
'''            ACTION_START -> {
                sessions.load()?.userId?.let { currentUser ->''',
'''            ACTION_START -> {
                if (started && store.isRadioEnabled()) {
                    // Activity reopen is not a fresh session. No WebRTC reset,
                    // no new presence sessionId, no extra heartbeat coroutine.
                    startAsForeground("MELEHAT açık • Kanal dinlemede")
                    return START_STICKY
                }
                sessions.load()?.userId?.let { currentUser ->''',
"idempotent running-radio START")

# Save an intentional OFF command immediately, before asynchronous shutdown.
# If Android evicts the process during cleanup, START_STICKY must not restart
# a radio which the user has explicitly disabled.
replace_once(service,
'''            ACTION_STOP -> {
                ptt.forceMute()''',
'''            ACTION_STOP -> {
                store.setRadioEnabled(false)
                ptt.forceMute()''',
"persist OFF before cleanup")

# The service already has a PARTIAL_WAKE_LOCK while user-enabled, a persistent
# FGS notification, START_STICKY and stopWithTask=false. Do not duplicate or
# abuse extra wake locks / background microphone starts here. Even a wake lock
# cannot override Android's Doze networking limits; the *user* can explicitly
# permit uninterrupted connected-device communication.
replace_once(manifest,
'''    <uses-permission android:name="android.permission.WAKE_LOCK"/>''',
'''    <uses-permission android:name="android.permission.WAKE_LOCK"/>
    <uses-permission android:name="android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS"/>''',
"Android opt-in optimization declaration")

# Only the visible Activity may ask the user for battery background access.
# Permission is never silently granted; fallback goes to MELEHAT app settings.
replace_once(activity,
'''    private var authCallbackNonce = 0
''',
'''    private var authCallbackNonce = 0

    private fun offerAlwaysOnlineBatteryAccessOnce() {
        if (!LocalStore(this).isRadioEnabled()) return
        val power = getSystemService(android.os.PowerManager::class.java)
        if (power.isIgnoringBatteryOptimizations(packageName)) return
        val pref = getSharedPreferences("melehat_background_help", MODE_PRIVATE)
        if (pref.getBoolean("v1389_optin_shown", false)) return
        pref.edit().putBoolean("v1389_optin_shown", true).apply()
        window.decorView.post {
            if (isFinishing || isDestroyed) return@post
            android.app.AlertDialog.Builder(this)
                .setTitle("MELEHAT • Uyku modunda çevrimiçi kal")
                .setMessage(
                    "Telsiz AÇIK olduğunda, ekran kapalıyken ve uygulama arka " +
                    "plandayken bağlantıyı korumak için Android pil kısıtlamasını " +
                    "MELEHAT için kaldırmanız önerilir. Telefonun onayı gerekir. " +
                    "Bu, pil kullanımını artırabilir. Bağlantı kesildiğinde " +
                    "sistem yeniden bağlanmayı deneyecektir; internet yokken " +
                    "çevrimiçi gösterilmeyeceksiniz."
                )
                .setPositiveButton("İZİN AYARINI AÇ") { _, _ ->
                    val direct = android.content.Intent(
                        android.provider.Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                        android.net.Uri.parse("package:" + packageName)
                    )
                    runCatching { startActivity(direct) }.onFailure {
                        runCatching {
                            startActivity(android.content.Intent(
                                android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                android.net.Uri.parse("package:" + packageName)))
                        }
                    }
                }
                .setNegativeButton("ŞİMDİ DEĞİL", null)
                .show()
        }
    }
''', "one-time opt-in battery permission UI")

# Current-enabled radio users get the choice when installing this update.
# New radio users get the choice when they explicitly turn radio ON.
replace_once(activity,
'''        if (!offerExternalPttSetupOnce()) offerBrandCompatibilityCheckOnce()
''',
'''        if (!offerExternalPttSetupOnce()) offerBrandCompatibilityCheckOnce()
        if (localStore.isRadioEnabled()) offerAlwaysOnlineBatteryAccessOnce()
''', "offer settings on existing enabled radio")
replace_once(activity,
'''                    onRadioToggle = { enabled ->
                        sendServiceAction(
                            if (enabled) PttForegroundService.ACTION_START
                            else PttForegroundService.ACTION_STOP
                        )
                    },''',
'''                    onRadioToggle = { enabled ->
                        sendServiceAction(
                            if (enabled) PttForegroundService.ACTION_START
                            else PttForegroundService.ACTION_STOP
                        )
                        if (enabled) offerAlwaysOnlineBatteryAccessOnce()
                    },''', "offer settings on user-enabled radio")

sv = service.read_text(encoding="utf-8")
act = activity.read_text(encoding="utf-8")
xml = manifest.read_text(encoding="utf-8")
for invariant in (
    'if (started && store.isRadioEnabled()) {',
    'return START_STICKY', 'wakeLock?.acquire()',
    'override fun onTaskRemoved(rootIntent: Intent?)',
    'private suspend fun stopRadio()', 'store.setRadioEnabled(false)',
    'ACTION_PTT_DOWN', 'ACTION_PTT_UP', 'VideoCallMonitor.start(applicationContext)',
):
    if invariant not in sv: raise RuntimeError("v1389 FGS invariant: " + invariant)
for invariant in (
    'offerAlwaysOnlineBatteryAccessOnce()',
    'ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS',
    'override fun onStop()', 'sendPhysicalPttAction(',
):
    if invariant not in act: raise RuntimeError("v1389 activity invariant: " + invariant)
for invariant in (
    'android:stopWithTask="false"',
    'android:foregroundServiceType="microphone"',
    'android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS',
):
    if invariant not in xml: raise RuntimeError("v1389 manifest invariant: " + invariant)
if 'applicationId = "com.melehat.telsiz"' not in Path("app/build.gradle.kts").read_text():
    raise RuntimeError("v1389 permanent package changed")
print("MELEHAT_1389_SCREEN_SLEEP_FOREGROUND_CONTINUITY_AND_BATTERY_OPTIN_READY")
