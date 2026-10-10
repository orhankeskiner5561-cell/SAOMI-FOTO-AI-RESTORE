from pathlib import Path

# MELEHAT v1.3.51 – optional physical Volume+ PTT for an already-running radio.
# Keep v1.3.50 Android identity, LiveKit, voice floor, channel selection,
# microphone, video, Compose PTT button, update system and signing untouched.
base = Path("app/src/main")
src = base / "java/com/saomi/telsiz"
svc = src / "service/VolumePttAccessibilityService.kt"
svc.parent.mkdir(parents=True, exist_ok=True)
if svc.exists():
    raise SystemExit("v1351: External Volume PTT exists; refusing to overwrite")
svc.write_text(r'''package com.saomi.telsiz.service

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Intent
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import android.view.KeyEvent
import android.view.accessibility.AccessibilityEvent
import com.saomi.telsiz.data.LocalStore

/**
 * An opt-in volume-up key listener, active only while the user's radio is ON.
 * No media sessions, synthetic playback, screen scraping or microphone access.
 * Android/OEM must deliver key events to AccessibilityService. Some lock screens
 * may block ACTION_UP: the repeat-time watchdog releases PTT to avoid latching.
 */
class VolumePttAccessibilityService : AccessibilityService() {
    private val handler = Handler(Looper.getMainLooper())
    private var held = false
    private var lastDownAt = 0L

    private val timeout = object : Runnable {
        override fun run() {
            if (!held) return
            val elapsed = SystemClock.uptimeMillis() - lastDownAt
            if (elapsed >= RELEASE_TIMEOUT_MS || !isArmed()) {
                release()
            } else {
                handler.postDelayed(this, RELEASE_TIMEOUT_MS - elapsed)
            }
        }
    }

    private fun isArmed(): Boolean =
        getSharedPreferences(PREFS, MODE_PRIVATE).getBoolean(KEY_ENABLED, false) &&
            LocalStore(this).isRadioEnabled()

    override fun onServiceConnected() {
        super.onServiceConnected()
        serviceInfo = serviceInfo.apply {
            flags = flags or AccessibilityServiceInfo.FLAG_REQUEST_FILTER_KEY_EVENTS
        }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit

    override fun onKeyEvent(event: KeyEvent): Boolean {
        if (event.keyCode != KeyEvent.KEYCODE_VOLUME_UP) return false
        if (!isArmed()) {
            release()
            return false // Volume+ remains a normal volume key when disarmed.
        }
        return when (event.action) {
            KeyEvent.ACTION_DOWN -> {
                lastDownAt = SystemClock.uptimeMillis()
                // A repeated DOWN must never start a new transmission after a
                // failsafe timeout: wait for the next *fresh* physical press.
                if (!held && event.repeatCount == 0) {
                    held = true
                    if (!dispatch(PttForegroundService.ACTION_PTT_DOWN)) {
                        held = false
                        return true
                    }
                }
                if (held) {
                    handler.removeCallbacks(timeout)
                    handler.postDelayed(timeout, RELEASE_TIMEOUT_MS)
                }
                true
            }
            KeyEvent.ACTION_UP -> {
                release()
                true
            }
            else -> false
        }
    }

    override fun onInterrupt() = release()

    override fun onDestroy() {
        release()
        super.onDestroy()
    }

    private fun release() {
        handler.removeCallbacks(timeout)
        if (!held) return
        held = false
        dispatch(PttForegroundService.ACTION_PTT_UP)
    }

    private fun dispatch(action: String): Boolean {
        return runCatching {
            // Never turn the radio on from a key press; only signal the
            // existing authorized foreground radio service.
            val intent = Intent(this, PttForegroundService::class.java).setAction(action)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent)
            } else {
                startService(intent)
            }
            true
        }.getOrElse {
            Log.w(TAG, "External PTT action unavailable: " + action, it)
            false
        }
    }

    companion object {
        private const val PREFS = "melehat_external_ptt"
        private const val KEY_ENABLED = "enabled"
        private const val RELEASE_TIMEOUT_MS = 1800L
        private const val TAG = "MelehatExternalPtt"
    }
}
''', encoding="utf-8")

xml = base / "res/xml"
xml.mkdir(parents=True, exist_ok=True)
(xml / "volume_ptt_accessibility.xml").write_text('''<?xml version="1.0" encoding="utf-8"?>
<accessibility-service xmlns:android="http://schemas.android.com/apk/res/android"
    android:description="@string/melehat_volume_ptt_description"
    android:accessibilityEventTypes="typeWindowStateChanged"
    android:accessibilityFeedbackType="feedbackGeneric"
    android:notificationTimeout="0"
    android:canRequestFilterKeyEvents="true"
    android:canRetrieveWindowContent="false"
    android:accessibilityFlags="flagRequestFilterKeyEvents" />
''', encoding="utf-8")

values = base / "res/values"
values.mkdir(parents=True, exist_ok=True)
(values / "external_ptt_strings.xml").write_text('''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="melehat_volume_ptt_description">MELEHAT, yalnızca izin verdiğinizde ve telsiziniz açıkken telefonun ses açma tuşunu basılı konuşma mandalı olarak kullanır.</string>
</resources>
''', encoding="utf-8")

manifest = base / "AndroidManifest.xml"
m = manifest.read_text(encoding="utf-8")
if m.count("</application>") != 1 or "VolumePttAccessibilityService" in m:
    raise SystemExit("v1351: Manifest service anchor changed")
m = m.replace("</application>", '''        <service
            android:name=".service.VolumePttAccessibilityService"
            android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE"
            android:exported="true">
            <intent-filter>
                <action android:name="android.accessibilityservice.AccessibilityService" />
            </intent-filter>
            <meta-data
                android:name="android.accessibilityservice"
                android:resource="@xml/volume_ptt_accessibility" />
        </service>
    </application>''', 1)
manifest.write_text(m, encoding="utf-8")

# Present the opt-in switch in the existing phone compatibility screen.
# Do not move any tiles or the carefully-positioned on-screen PTT button.
compat = src / "compat/DeviceCompatibilityActivity.kt"
s = compat.read_text(encoding="utf-8")
anchor = '        line("İzinler ve pil ayarları", 18f, true)'
if s.count(anchor) != 1:
    raise SystemExit("v1351: Compatibility settings anchor changed")
panel = '''        line("DIŞ MANDAL • Ses +", 18f, true)
        val externalPrefs = getSharedPreferences("melehat_external_ptt", MODE_PRIVATE)
        val externalSwitch = android.widget.Switch(this).apply {
            text = "Ses + ile basılı konuş"
            isChecked = externalPrefs.getBoolean("enabled", false)
            setPadding(4, 6, 4, 12)
            setOnCheckedChangeListener { _, checked ->
                externalPrefs.edit().putBoolean("enabled", checked).apply()
                if (!checked) {
                    // Force a release if the switch is disabled during a hold.
                    val stop = Intent(this@DeviceCompatibilityActivity,
                        com.saomi.telsiz.service.PttForegroundService::class.java)
                        .setAction(com.saomi.telsiz.service.PttForegroundService.ACTION_PTT_UP)
                    runCatching { startService(stop) }
                }
            }
        }
        panel.addView(externalSwitch)
        val expected = android.content.ComponentName(
            this, com.saomi.telsiz.service.VolumePttAccessibilityService::class.java
        ).flattenToString()
        val services = Settings.Secure.getString(
            contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        ).orEmpty()
        val accessOn = services.split(':').any { it.equals(expected, ignoreCase = true) }
        line("Erişilebilirlik / İndirilen uygulamalar: " +
            if (accessOn) "✓ Etkin" else "⚠ Kapalı")
        action("Dış mandal erişilebilirlik iznini aç") {
            openSettings(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }
        line("MELEHAT telsizi AÇIK olmalı. Ses + basılıyken yayın, bırakınca " +
             "durma isteği gönderilir. Android ekran kilitliyken tuş bırakma " +
             "olayını engellerse emniyet zaman aşımı yayını kapatır. " +
             "Bu durumda uzun konuşma kesilebilir. Android 13+ yandan " +
             "yüklenen APK için önce Uygulama bilgisi > sağ üst menü > " +
             "Kısıtlı ayarlara izin ver gerekebilir.")
        line("Gerçek ekran kapalı testi yapılana kadar kilitli ekranda " +
             "kesintisiz uzun konuşma garanti edilemez.")

'''
s=s.replace(anchor,panel+anchor,1)
for preserved in (
    'WindowCompat.setDecorFitsSystemWindows(window, false)',
    'WindowInsetsCompat.Type.displayCutout()',
    'Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT',
    'line("MELEHAT • Uyumluluk Kontrolü", 19f, true)',
    'Settings.ACTION_ACCESSIBILITY_SETTINGS',
):
    if preserved not in s: raise SystemExit("v1351: Missing compatibility feature: "+preserved)
compat.write_text(s, encoding="utf-8")

# Add discoverable entry to the radio's existing compatibility notification,
# without modifying the actual service's PTT state machine.
service = src / "service/PttForegroundService.kt"
core = service.read_text(encoding="utf-8")
for protect in (
    "ACTION_PTT_DOWN", "ACTION_PTT_UP", "ACTION_SWITCH_ROOM",
    "roomSwitching || !ptt.isConnectedTo(channel.id)",
    'val resolvedAction = intent?.action ?: if (store.isRadioEnabled()) ACTION_START else null',
    "VideoCallMonitor.start(applicationContext)"
):
    if protect not in core: raise SystemExit("v1351: Protected service missing: "+protect)
assert "VolumePttAccessibilityService" not in core
assert 'android:foregroundServiceType="microphone"' in m
assert 'android:stopWithTask="false"' in m
assert "com.melehat.telsiz" in (base.parent.parent / "build.gradle.kts").read_text()
print("MELEHAT_1351_EXTERNAL_VOLUME_PTT_READY")
