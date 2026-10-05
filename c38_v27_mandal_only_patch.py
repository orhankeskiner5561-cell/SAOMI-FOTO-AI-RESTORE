from pathlib import Path

# C38: clean v0.27 + ONLY external Volume+ PTT accessibility.
svc=Path("app/src/main/java/com/saomi/telsiz/service/VolumePttAccessibilityService.kt")
svc.parent.mkdir(parents=True, exist_ok=True)
svc.write_text(r'''package com.saomi.telsiz.service
import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Intent
import android.view.KeyEvent
import android.view.accessibility.AccessibilityEvent
class VolumePttAccessibilityService : AccessibilityService() {
 private var held=false
 override fun onServiceConnected(){ super.onServiceConnected(); serviceInfo=serviceInfo.apply{ flags=flags or AccessibilityServiceInfo.FLAG_REQUEST_FILTER_KEY_EVENTS } }
 override fun onAccessibilityEvent(event: AccessibilityEvent?)=Unit
 override fun onKeyEvent(event: KeyEvent):Boolean {
  if(event.keyCode!=KeyEvent.KEYCODE_VOLUME_UP) return false
  if(event.action==KeyEvent.ACTION_DOWN && !held){ held=true; send(PttForegroundService.ACTION_PTT_DOWN) }
  else if(event.action==KeyEvent.ACTION_UP && held){ held=false; send(PttForegroundService.ACTION_PTT_UP) }
  return true
 }
 override fun onInterrupt(){ if(held){held=false;send(PttForegroundService.ACTION_PTT_UP)} }
 private fun send(a:String){ val i=Intent(this,PttForegroundService::class.java).setAction(a); if(android.os.Build.VERSION.SDK_INT>=26) startForegroundService(i) else startService(i) }
}
''')
xml=Path("app/src/main/res/xml"); xml.mkdir(parents=True,exist_ok=True)
(xml/"volume_ptt_accessibility.xml").write_text('''<?xml version="1.0" encoding="utf-8"?>
<accessibility-service xmlns:android="http://schemas.android.com/apk/res/android" android:accessibilityEventTypes="typeWindowStateChanged" android:accessibilityFeedbackType="feedbackGeneric" android:notificationTimeout="0" android:accessibilityFlags="flagRequestFilterKeyEvents" android:canRequestFilterKeyEvents="true" android:canRetrieveWindowContent="false" />''')
mp=Path("app/src/main/AndroidManifest.xml"); m=mp.read_text()
entry='''        <service android:name=".service.VolumePttAccessibilityService" android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE" android:exported="true"><intent-filter><action android:name="android.accessibilityservice.AccessibilityService" /></intent-filter><meta-data android:name="android.accessibilityservice" android:resource="@xml/volume_ptt_accessibility" /></service>\n'''
m=m.replace("</application>",entry+"    </application>"); mp.write_text(m)
print("C38 minimal external Volume+ PTT applied to clean v0.27")
