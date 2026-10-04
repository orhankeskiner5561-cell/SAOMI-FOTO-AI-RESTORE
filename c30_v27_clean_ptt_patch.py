from pathlib import Path
import re

# C30 is applied directly after the clean v0.27 build chain.
pkg=Path("app/src/main/java/com/saomi/telsiz")
svc=pkg/"service"/"VolumePttAccessibilityService.kt"
svc.parent.mkdir(parents=True, exist_ok=True)
svc.write_text(r'''package com.saomi.telsiz.service

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.KeyEvent
import android.view.accessibility.AccessibilityEvent

class VolumePttAccessibilityService : AccessibilityService() {
    private val handler = Handler(Looper.getMainLooper())
    private var held = false
    private var lastEvent = 0L
    private val releaseGuard = object : Runnable {
        override fun run() {
            if (!held) return
            val quiet = SystemClock.uptimeMillis() - lastEvent
            if (quiet >= 800L) release() else handler.postDelayed(this, 800L - quiet)
        }
    }
    override fun onServiceConnected() {
        serviceInfo = serviceInfo.apply {
            flags = flags or AccessibilityServiceInfo.FLAG_REQUEST_FILTER_KEY_EVENTS
        }
    }
    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit
    override fun onInterrupt() = release()
    override fun onDestroy() { release(); super.onDestroy() }
    override fun onKeyEvent(event: KeyEvent): Boolean {
        if (event.keyCode != KeyEvent.KEYCODE_VOLUME_UP) return false
        lastEvent = SystemClock.uptimeMillis()
        if (event.action == KeyEvent.ACTION_DOWN) {
            if (!held) { held = true; send(PttForegroundService.ACTION_PTT_DOWN) }
            handler.removeCallbacks(releaseGuard)
            handler.postDelayed(releaseGuard, 800L)
            return true
        }
        if (event.action == KeyEvent.ACTION_UP) { release(); return true }
        return true
    }
    private fun release() {
        handler.removeCallbacks(releaseGuard)
        if (held) { held = false; send(PttForegroundService.ACTION_PTT_UP) }
    }
    private fun send(action: String) {
        val i=Intent(this,PttForegroundService::class.java).setAction(action)
        if (android.os.Build.VERSION.SDK_INT >= 26) startForegroundService(i) else startService(i)
    }
}
''')

xml=Path("app/src/main/res/xml"); xml.mkdir(parents=True,exist_ok=True)
(xml/"volume_ptt_accessibility.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<accessibility-service xmlns:android="http://schemas.android.com/apk/res/android"
 android:accessibilityEventTypes="typeWindowStateChanged"
 android:accessibilityFeedbackType="feedbackGeneric"
 android:notificationTimeout="0"
 android:accessibilityFlags="flagRequestFilterKeyEvents"
 android:canRequestFilterKeyEvents="true"
 android:canRetrieveWindowContent="false" />
""")

mp=Path("app/src/main/AndroidManifest.xml")
m=mp.read_text()
if "VolumePttAccessibilityService" not in m:
    m=m.replace("</application>", """<service
 android:name=".service.VolumePttAccessibilityService"
 android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE"
 android:exported="true">
 <intent-filter><action android:name="android.accessibilityservice.AccessibilityService" /></intent-filter>
 <meta-data android:name="android.accessibilityservice" android:resource="@xml/volume_ptt_accessibility" />
</service>
</application>""")
mp.write_text(m)

ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
u=ui.read_text()
for line in ["import android.provider.Settings","import androidx.compose.material3.Button"]:
    if line not in u:
        pos=u.find("\n",u.find("package ")); u=u[:pos+1]+line+"\n"+u[pos+1:]
u=u.replace('UpdateChecker()\n                Text("v0.27 • PTT + Otomatik Güncelleme"',
'''C30AccessibilityButton()
                UpdateChecker()
                Text("C30 • v0.27 temiz taban • Kilit ekranı PTT"''',1)
u += r'''

@Composable
private fun C30AccessibilityButton() {
    val context = LocalContext.current
    Button(onClick = { context.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }) {
        Text("SES MANDALI ERİŞİLEBİLİRLİK İZNİ")
    }
}
'''
ui.write_text(u)

# IMPORTANT: retain the exact v0.27 applicationId so C30 is install-compatible
# with the user's installed v0.27 package. Only increase version metadata.
b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz.v27"',t)
t=re.sub(r'versionCode\s*=\s*\d+','versionCode = 30',t)
t=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "C30-v27-clean-base"',t)
b.write_text(t)
print("C30 applied directly to clean v0.27 base; package id retained")
