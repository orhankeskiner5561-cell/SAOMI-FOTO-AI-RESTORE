from pathlib import Path

# MELEHAT 1.3.45: real Android service recovery after the process is evicted.
# Do not touch LiveKit, PTT-mandali, room transfer, floor leases, audio route,
# video calling, app signing, or user's radioOn preference.
base = Path("app/src/main")
service = base / "java/com/saomi/telsiz/service/PttForegroundService.kt"
s = service.read_text(encoding="utf-8")

original = "        when (intent?.action) {"
restored = """        // Android may recreate a START_STICKY foreground service with
        // intent == null after process death. Previous versions ignored
        // this restart, leaving radioOn=true but nobody in the LiveKit room.
        val resolvedAction = intent?.action ?: if (store.isRadioEnabled()) ACTION_START else null
        when (resolvedAction) {"""
if s.count(original) != 1:
    raise SystemExit("MELEHAT 1345: expected service onStartCommand action dispatch once")
if "return START_STICKY" not in s:
    raise SystemExit("MELEHAT 1345: START_STICKY foreground-service contract absent")
s=s.replace(original, restored, 1)

# Kotlin used to smart-cast intent in when(intent?.action). Now that null
# service restarts have their own resolved action, room switch extras must
# access the optional Intent safely as well.
for before, after in (
    ('val roomId = intent.getStringExtra(EXTRA_ROOM_ID).orEmpty()',
     'val roomId = intent?.getStringExtra(EXTRA_ROOM_ID).orEmpty()'),
    ('val roomName = intent.getStringExtra(EXTRA_ROOM_NAME).orEmpty()',
     'val roomName = intent?.getStringExtra(EXTRA_ROOM_NAME).orEmpty()'),
):
    if s.count(before) != 1:
        raise SystemExit("MELEHAT 1345 channel switch Intent anchor missing")
    s=s.replace(before,after,1)


# The task can be swiped from Android Recent Apps while the foreground
# service remains active. Don't call stopSelf, and don't flip radioOff.
anchor = '    override fun onBind(intent: Intent?): IBinder? = null'
if s.count(anchor) != 1:
    raise SystemExit("MELEHAT 1345: service tail anchor changed")
s=s.replace(anchor, '''    override fun onTaskRemoved(rootIntent: Intent?) {
        // A foreground radio is NOT tied to the activity/task.
        // Android is responsible for START_STICKY recreation if it kills us.
        // Deliberately do NOT start a microphone FGS from the background:
        // Android 14+ restricts such starts and may throw SecurityException.
        if (started && store.isRadioEnabled()) {
            runCatching {
                updateNotification("MELEHAT arka planda • Telsiz dinlemede")
            }
        }
        super.onTaskRemoved(rootIntent)
    }

'''+anchor,1)
for required in (
    'roomMutex.withLock', 'if (started && !roomSwitching)',
    'ptt.ensureConnected()', 'roomSwitching || !ptt.isConnectedTo(channel.id)',
    'VideoCallMonitor.start(applicationContext)',
    'return START_STICKY',
    'private var keepAliveJob: Job? = null',
    'ACTION_SWITCH_ROOM',
    'private suspend fun stopRadio()', 'store.setRadioEnabled(false)'
):
    if required not in s:
        raise SystemExit("MELEHAT 1345 protected working code missing: "+required)
service.write_text(s, encoding="utf-8")

manifest = base / "AndroidManifest.xml"
m=manifest.read_text(encoding="utf-8")
import re
pattern = r'(<service\s+android:name="\.service\.PttForegroundService"[^>]*?)(/>)'
matches = list(re.finditer(pattern,m,re.DOTALL))
if len(matches) != 1:
    raise SystemExit("MELEHAT 1345 foreground-service manifest declaration unexpected")
original_service = matches[0].group(0)
if "android:stopWithTask" not in original_service:
    patched = original_service[:-2] + ' android:stopWithTask="false" />'
    m=m.replace(original_service,patched,1)
if 'android:foregroundServiceType="microphone"' not in m:
    raise SystemExit("MELEHAT 1345 protected microphone FGS type missing")
manifest.write_text(m,encoding="utf-8")


# Device makers (especially Xiaomi/MIUI/HyperOS) may terminate even an active
# foreground service. Show a one-time, optional Android battery-settings guide
# while the Activity is actually in the foreground. Do not silently request
# exemptions or modify system settings without user consent.
activity = base / "java/com/saomi/telsiz/MainActivity.kt"
a = activity.read_text(encoding="utf-8")
existing = '''        render()
    }

    override fun onNewIntent(intent: Intent) {'''
updated = '''        render()
        explainBackgroundBatteryOnce()
    }

    private fun explainBackgroundBatteryOnce() {
        if (!LocalStore(this).isRadioEnabled()) return
        val power = getSystemService(android.os.PowerManager::class.java)
        if (power.isIgnoringBatteryOptimizations(packageName)) return
        val prefs = getSharedPreferences("melehat_background_help", MODE_PRIVATE)
        if (prefs.getBoolean("v1345_shown_once", false)) return
        prefs.edit().putBoolean("v1345_shown_once", true).apply()
        android.app.AlertDialog.Builder(this)
            .setTitle("MELEHAT arka planda çevrimiçi kalsın")
            .setMessage(
                "Telsiz anahtarı açıkken Android'in uygulamayı uykuya almasını " +
                "önlemek için MELEHAT > Pil bölümünde Kısıtlama yok / Sınırsız " +
                "seçin. Xiaomi telefonlarda ayrıca Otomatik başlatmaya izin " +
                "verin. Bu izinleri telefonun ayarlarından siz açabilirsiniz."
            )
            .setPositiveButton("Uygulama ayarlarını aç") { _, _ ->
                runCatching {
                    startActivity(android.content.Intent(
                        android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                        android.net.Uri.parse("package:" + packageName)
                    ))
                }
            }
            .setNegativeButton("Sonra", null)
            .show()
    }

    override fun onNewIntent(intent: Intent) {'''
if a.count(existing) != 1:
    raise SystemExit("MELEHAT 1345 Activity onCreate anchor missing")
a=a.replace(existing,updated,1)
assert "PttForegroundService.ACTION_START" in a
assert "sendServiceAction" in a
activity.write_text(a,encoding="utf-8")

# Force-stop and some OEM battery termination cannot be bypassed by apps.
# We keep all background permissions unchanged; no abusive alarms, phantom
# Activities, or recurring background microphone FGS launches.
print("MELEHAT_1345_STICKY_SERVICE_AND_TASK_REMOVAL_RECOVERY_OK")
