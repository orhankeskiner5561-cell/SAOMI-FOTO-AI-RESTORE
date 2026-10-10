from pathlib import Path

# MELEHAT 1.3.46 – permission diagnostics and OEM-specific guidance only.
# Never modify LiveKit, channel selection, PTT, microphone floor,
# Bluetooth audio route, service lifecycle, signing or versioning.
base = Path("app/src/main")
java = base / "java/com/saomi/telsiz"
compat = java / "compat"
compat.mkdir(parents=True, exist_ok=True)
src = Path("../staging/compat/DeviceCompatibilityActivity.kt")
assert src.is_file(), "MELEHAT v1346 compatibility source missing"
(compat / src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

manifest = base / "AndroidManifest.xml"
m = manifest.read_text(encoding="utf-8")
if 'com.saomi.telsiz.compat.DeviceCompatibilityActivity' in m:
    raise SystemExit("MELEHAT 1346 duplicate compatibility activity")
if m.count("</application>") != 1:
    raise SystemExit("MELEHAT 1346 manifest root mismatch")
m = m.replace("</application>", '''
        <activity
            android:name="com.saomi.telsiz.compat.DeviceCompatibilityActivity"
            android:exported="false"
            android:screenOrientation="unspecified"/>
    </application>''', 1)
manifest.write_text(m, encoding="utf-8")

# Replace the old one-time Xiaomi-only battery dialog with an all-brand guide.
main = java / "MainActivity.kt"
s = main.read_text(encoding="utf-8")
if s.count("        explainBackgroundBatteryOnce()") != 1:
    raise SystemExit("MELEHAT 1346 v1345 battery dialog call missing")
s = s.replace("        explainBackgroundBatteryOnce()",
              "        offerBrandCompatibilityCheckOnce()", 1)
start = s.index("    private fun explainBackgroundBatteryOnce() {")
end = s.index("    override fun onNewIntent(intent: Intent) {", start)
s = s[:start] + '''    private fun offerBrandCompatibilityCheckOnce() {
        val prefs = getSharedPreferences("melehat_device_compat", MODE_PRIVATE)
        if (prefs.getBoolean("v1346_offered", false)) return
        // Present this ONLY from a foreground Activity; the user chooses
        // which permissions/settings to grant. Never open OEM panels from FGS.
        window.decorView.post {
            if (isFinishing || isDestroyed) return@post
            android.app.AlertDialog.Builder(this)
                .setTitle("MELEHAT • Telefon uyumluluğu")
                .setMessage(
                    "Telefon markası ve Android sürümüne göre pil, " +
                    "otomatik başlatma, mikrofon, bildirim ve Bluetooth " +
                    "izinlerini kontrol edebilirsiniz. Ayarlar izniniz olmadan " +
                    "değiştirilmeyecek. Şimdi kontrol etmek ister misiniz?"
                )
                .setPositiveButton("UYUMLULUĞU KONTROL ET") { _, _ ->
                    startActivity(android.content.Intent(
                        this, com.saomi.telsiz.compat.DeviceCompatibilityActivity::class.java))
                }
                .setNegativeButton("SONRA", null)
                .show()
            prefs.edit().putBoolean("v1346_offered", true).apply()
        }
    }

''' + s[end:]
if "sendServiceAction" not in s or "PttForegroundService.ACTION_START" not in s:
    raise SystemExit("MELEHAT 1346 base Activity changed")
main.write_text(s, encoding="utf-8")

# Keep the user-configurable compatibility screen accessible afterwards.
# Add a non-invasive action to the existing foreground radio notification,
# without moving any of the meticulously positioned main-screen buttons.
service = java / "service/PttForegroundService.kt"
s = service.read_text(encoding="utf-8")
start = s.index("    private fun buildNotification(text: String): Notification {")
end = s.index("    private fun startAsForeground(", start)
section = s[start:end]
if section.count("            .build()") != 1:
    raise SystemExit("MELEHAT 1346 notification builder unexpectedly changed")
section = section.replace("            .build()", '''            .addAction(
                android.R.drawable.ic_menu_preferences,
                "Telefon Uyumluluğu",
                PendingIntent.getActivity(
                    this, 206,
                    Intent(this, com.saomi.telsiz.compat.DeviceCompatibilityActivity::class.java),
                    flags
                )
            )
            .build()''', 1)
s = s[:start] + section + s[end:]
for protected in (
    "ACTION_PTT_DOWN", "ACTION_PTT_UP", "ACTION_STOP", "ACTION_SWITCH_ROOM",
    "onTaskRemoved(rootIntent: Intent?)", "return START_STICKY",
    "val resolvedAction = intent?.action ?: if (store.isRadioEnabled()) ACTION_START else null",
    "AudioRouteManager", "VideoCallMonitor.start(applicationContext)"
):
    assert protected in s, "MELEHAT 1346 protected service code missing: " + protected
service.write_text(s, encoding="utf-8")

assert 'android:stopWithTask="false"' in m
assert "android.permission.POST_NOTIFICATIONS" in m
assert "android.permission.RECORD_AUDIO" in m
assert "android.permission.BLUETOOTH_CONNECT" in m
assert "android.permission.USE_FULL_SCREEN_INTENT" in m
print("MELEHAT_1346_DEVICE_COMPATIBILITY_CENTER_OK")
