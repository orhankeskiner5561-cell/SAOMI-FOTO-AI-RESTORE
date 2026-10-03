from pathlib import Path

# 1) Accessibility service that captures hardware VOLUME UP globally while radio is enabled.
svc=Path("app/src/main/java/com/saomi/telsiz/service/VolumePttAccessibilityService.kt")
svc.parent.mkdir(parents=True, exist_ok=True)
svc.write_text(r'''package com.saomi.telsiz.service

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.os.Build
import android.view.KeyEvent
import android.view.accessibility.AccessibilityEvent

class VolumePttAccessibilityService : AccessibilityService() {

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit

    override fun onInterrupt() = Unit

    override fun onKeyEvent(event: KeyEvent): Boolean {
        if (event.keyCode != KeyEvent.KEYCODE_VOLUME_UP) {
            return super.onKeyEvent(event)
        }

        // Only steal the volume-up key while MELEHAT radio/listening is explicitly ON.
        val enabled = getSharedPreferences("melehat_ptt", MODE_PRIVATE)
            .getBoolean("radio_enabled", false)
        if (!enabled) return super.onKeyEvent(event)

        val action = when (event.action) {
            KeyEvent.ACTION_DOWN -> {
                // Ignore key-repeat events; one DOWN is enough and avoids duplicate floor requests.
                if (event.repeatCount > 0) return true
                ACTION_VOLUME_PTT_DOWN
            }
            KeyEvent.ACTION_UP -> ACTION_VOLUME_PTT_UP
            else -> return true
        }

        val intent = Intent(this, PttForegroundService::class.java).apply {
            this.action = action
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
        // Consume the key so Android volume does not change while PTT is enabled.
        return true
    }

    companion object {
        const val ACTION_VOLUME_PTT_DOWN = "com.saomi.telsiz.action.VOLUME_PTT_DOWN"
        const val ACTION_VOLUME_PTT_UP = "com.saomi.telsiz.action.VOLUME_PTT_UP"
    }
}
''')

# 2) Accessibility metadata.
xml=Path("app/src/main/res/xml/volume_ptt_accessibility_service.xml")
xml.parent.mkdir(parents=True, exist_ok=True)
xml.write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<accessibility-service xmlns:android="http://schemas.android.com/apk/res/android"
    android:accessibilityEventTypes="typeAllMask"
    android:accessibilityFeedbackType="feedbackGeneric"
    android:notificationTimeout="0"
    android:canRequestFilterKeyEvents="true"
    android:accessibilityFlags="flagRequestFilterKeyEvents" />
''')

# 3) Register accessibility service in AndroidManifest.
manifest=Path("app/src/main/AndroidManifest.xml")
m=manifest.read_text()
entry=r'''
        <service
            android:name=".service.VolumePttAccessibilityService"
            android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE"
            android:exported="true"
            android:label="MELEHAT TELSİZ Ses Tuşu">
            <intent-filter>
                <action android:name="android.accessibilityservice.AccessibilityService" />
            </intent-filter>
            <meta-data
                android:name="android.accessibilityservice"
                android:resource="@xml/volume_ptt_accessibility_service" />
        </service>
'''
if ".service.VolumePttAccessibilityService" not in m:
    m=m.replace("</application>", entry + "\n    </application>")
manifest.write_text(m)

# 4) Wire global Volume-Up DOWN/UP into the same strict hold-to-talk state machine.
p=Path("app/src/main/java/com/saomi/telsiz/service/PttForegroundService.kt")
s=p.read_text()

needle='''        when (intent?.action) {
'''
insert='''        when (intent?.action) {
            VolumePttAccessibilityService.ACTION_VOLUME_PTT_DOWN -> {
                if (started) {
                    pttHeld = true
                    transmitRequestId += 1
                    val requestId = transmitRequestId
                    if (!transmitting) {
                        beginJob?.cancel()
                        beginJob = scope.launch { beginTransmit(requestId) }
                    }
                }
            }

            VolumePttAccessibilityService.ACTION_VOLUME_PTT_UP -> {
                if (started) {
                    pttHeld = false
                    transmitRequestId += 1
                    beginJob?.cancel()
                    beginJob = null
                    scope.launch { endTransmit() }
                }
            }
'''
if "ACTION_VOLUME_PTT_DOWN ->" not in s:
    if needle not in s:
        raise SystemExit("Could not find onStartCommand action switch")
    s=s.replace(needle, insert, 1)

# Persist whether the radio/listening mode is actually ON. Accessibility service
# only consumes Volume-Up while this flag is true.
if 'getSharedPreferences("melehat_ptt", MODE_PRIVATE).edit().putBoolean("radio_enabled", true).apply()' not in s:
    s=s.replace(
        '''        started = true
''',
        '''        started = true
        getSharedPreferences("melehat_ptt", MODE_PRIVATE).edit()
            .putBoolean("radio_enabled", true).apply()
''',
        1
    )

if 'putBoolean("radio_enabled", false)' not in s:
    marker='''        started = false
'''
    # choose the stopRadio occurrence, not the field initializer (which has 4 spaces)
    s=s.replace(
        marker,
        '''        started = false
        getSharedPreferences("melehat_ptt", MODE_PRIVATE).edit()
            .putBoolean("radio_enabled", false).apply()
''',
        1
    )

# Ensure a destroyed service never leaves the hardware key hijacked.
destroy='''    override fun onDestroy() {
'''
if destroy in s and 'radio_enabled", false' in s and 'onDestroy() {' in s:
    # Add an explicit clear directly in onDestroy if not already there.
    tag='''    override fun onDestroy() {
        pttHeld = false
'''
    if tag in s and 'override fun onDestroy() {\n        getSharedPreferences("melehat_ptt"' not in s:
        s=s.replace(tag, '''    override fun onDestroy() {
        getSharedPreferences("melehat_ptt", MODE_PRIVATE).edit()
            .putBoolean("radio_enabled", false).apply()
        pttHeld = false
''', 1)

p.write_text(s)

# 5) Version.
ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
u=ui.read_text().replace("v0.16 • PTT Güvenli Bas-Konuş","v0.17 • Ses Açma Tuşu PTT").replace("MELEHAT TELSİZ v0.16","MELEHAT TELSİZ v0.17")
ui.write_text(u)

b=Path("app/build.gradle.kts")
t=b.read_text().replace("versionCode = 16","versionCode = 17").replace('versionName = "0.16.0"','versionName = "0.17.0"')
b.write_text(t)

print("v0.17 global Volume-Up hold-to-talk accessibility patch applied")
