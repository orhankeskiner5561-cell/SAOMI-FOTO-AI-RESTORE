from pathlib import Path
import re

pkg=Path("app/src/main/java/com/saomi/telsiz")
svc=pkg/"service"/"VolumePttAccessibilityService.kt"
svc.parent.mkdir(parents=True, exist_ok=True)
svc.write_text(r'''package com.saomi.telsiz.service

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Intent
import android.view.KeyEvent
import android.view.accessibility.AccessibilityEvent

class VolumePttAccessibilityService : AccessibilityService() {
    private var held = false

    override fun onServiceConnected() {
        super.onServiceConnected()
        serviceInfo = serviceInfo.apply {
            flags = flags or AccessibilityServiceInfo.FLAG_REQUEST_FILTER_KEY_EVENTS
        }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit
    override fun onInterrupt() = releasePtt()

    override fun onKeyEvent(event: KeyEvent): Boolean {
        if (event.keyCode != KeyEvent.KEYCODE_VOLUME_UP) return false
        return when (event.action) {
            KeyEvent.ACTION_DOWN -> {
                if (event.repeatCount == 0 && !held) {
                    held = true
                    sendPtt(PttForegroundService.ACTION_PTT_DOWN)
                }
                true
            }
            KeyEvent.ACTION_UP -> {
                if (held) {
                    held = false
                    sendPtt(PttForegroundService.ACTION_PTT_UP)
                }
                true
            }
            else -> false
        }
    }

    override fun onDestroy() {
        releasePtt()
        super.onDestroy()
    }

    private fun releasePtt() {
        if (held) {
            held = false
            sendPtt(PttForegroundService.ACTION_PTT_UP)
        }
    }

    private fun sendPtt(action: String) {
        startForegroundService(Intent(this, PttForegroundService::class.java).setAction(action))
    }
}
''')

xml=Path("app/src/main/res/xml")
xml.mkdir(parents=True, exist_ok=True)
(xml/"volume_ptt_accessibility.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<accessibility-service xmlns:android="http://schemas.android.com/apk/res/android"
    android:accessibilityEventTypes="typeWindowStateChanged"
    android:accessibilityFeedbackType="feedbackGeneric"
    android:notificationTimeout="0"
    android:accessibilityFlags="flagRequestFilterKeyEvents"
    android:canRequestFilterKeyEvents="true"
    android:canRetrieveWindowContent="false"
    android:description="@string/volume_ptt_accessibility_desc" />
''')

sp=Path("app/src/main/res/values/strings.xml")
sp.parent.mkdir(parents=True, exist_ok=True)
if not sp.exists():
    sp.write_text('<?xml version="1.0" encoding="utf-8"?>\n<resources>\n</resources>\n')
s=sp.read_text()
if "volume_ptt_accessibility_desc" not in s:
    s=s.replace("</resources>", '    <string name="volume_ptt_accessibility_desc">Ses + tuşunu MELEHAT bas-konuş mandalı olarak kullanır.</string>\n</resources>')
sp.write_text(s)

mp=Path("app/src/main/AndroidManifest.xml")
m=mp.read_text()
entry=r'''
        <service
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
'''
if "VolumePttAccessibilityService" not in m:
    m=m.replace("</application>", entry+"\n    </application>")
mp.write_text(m)

b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"', 'applicationId = "com.melehat.telsiz.externalptt31"', t)
t=re.sub(r'versionCode\s*=\s*\d+', 'versionCode = 31', t)
t=re.sub(r'versionName\s*=\s*"[^"]+"', 'versionName = "0.31.0-accessibility-ptt"', t)
b.write_text(t)

ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
u=ui.read_text().replace("v0.27 • PTT + Otomatik Güncelleme", "v0.31 TEST • Global Ses+ Mandal")
u=u.replace("MELEHAT TELSİZ v0.26", "MELEHAT TELSİZ v0.31 TEST")
ui.write_text(u)
print("v0.31 Accessibility Volume+ PTT applied")
