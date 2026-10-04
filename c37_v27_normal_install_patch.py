from pathlib import Path
import re

# C37: rebuild the PTT path as one source of truth on top of clean v0.27.
# UI press and Accessibility Volume+ both feed the same foreground service.
service = Path("app/src/main/java/com/saomi/telsiz/service/PttForegroundService.kt")
s = service.read_text()

# Keep the LiveKit connection warm when radio is on; serialize PTT transitions.
if "private val pttMutex = Mutex()" not in s:
    s=s.replace("import kotlinx.coroutines.*", "import kotlinx.coroutines.*\nimport kotlinx.coroutines.sync.Mutex\nimport kotlinx.coroutines.sync.withLock")
    s=s.replace("private var leaseJob: Job? = null", "private var leaseJob: Job? = null\n    private val pttMutex = Mutex()")

# Do not ignore a PTT-down while an earlier transition is still settling.
s=s.replace(
"""                    if (!transmitting) {
                        beginJob?.cancel()
                        beginJob = scope.launch { beginTransmit(requestId) }
                    }""",
"""                    beginJob?.cancel()
                    beginJob = scope.launch { beginTransmit(requestId) }"""
)

# Replace begin/end with serialized, stale-request-safe versions.
start=s.index("    private suspend fun beginTransmit(")
end=s.index("    private suspend fun stopRadio()", start)
new=r'''    private suspend fun beginTransmit(requestId: Long) = pttMutex.withLock {
        if (!started || !pttHeld || requestId != transmitRequestId) return@withLock

        val session = sessions.load()
        val channel = store.loadActiveChannel()
        if (session == null) {
            updateNotification("Oturum doğrulaması gerekli")
            return@withLock
        }

        // The LiveKit room is connected while the radio is ON. Floor ownership
        // is the only network operation that must happen on a press.
        val floor = backend.acquireFloor(session, channel.id, 15)
        if (!floor) {
            if (pttHeld && requestId == transmitRequestId)
                updateNotification("KANAL MEŞGUL • Başka biri konuşuyor")
            return@withLock
        }

        if (!started || !pttHeld || requestId != transmitRequestId) {
            backend.releaseFloor(session, channel.id)
            return@withLock
        }

        if (!ptt.setTransmitting(true)) {
            backend.releaseFloor(session, channel.id)
            updateNotification("Ses bağlantısı hazırlanıyor • tekrar basın")
            return@withLock
        }

        if (!started || !pttHeld || requestId != transmitRequestId) {
            ptt.setTransmitting(false)
            backend.releaseFloor(session, channel.id)
            return@withLock
        }

        transmitting = true
        updateNotification("YAYINDA • Ses karşıya gidiyor")
        leaseJob?.cancel()
        leaseJob = scope.launch {
            while (isActive && transmitting && pttHeld) {
                delay(8_000)
                if (!backend.acquireFloor(session, channel.id, 15)) {
                    ptt.setTransmitting(false)
                    transmitting = false
                    updateNotification("Yayın kesildi • Kanal kilidi yenilenemedi")
                    break
                }
            }
        }
    }

    private suspend fun endTransmit() = pttMutex.withLock {
        pttHeld = false
        transmitting = false
        leaseJob?.cancel()
        leaseJob = null
        ptt.setTransmitting(false)
        val session = sessions.load()
        if (session != null) backend.releaseFloor(session, store.loadActiveChannel().id)
        if (started) updateNotification("Kanal dinlemede • Bas-konuş hazır")
    }

'''
s=s[:start]+new+s[end:]
service.write_text(s)

# Global Volume+ accessibility capture. Do not use a short watchdog: that was
# cutting long holds into tiny audio bursts. ACTION_UP is authoritative.
svc=Path("app/src/main/java/com/saomi/telsiz/service/VolumePttAccessibilityService.kt")
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

    override fun onKeyEvent(event: KeyEvent): Boolean {
        if (event.keyCode != KeyEvent.KEYCODE_VOLUME_UP) return false
        when (event.action) {
            KeyEvent.ACTION_DOWN -> {
                if (!held) {
                    held = true
                    send(PttForegroundService.ACTION_PTT_DOWN)
                }
            }
            KeyEvent.ACTION_UP -> release()
        }
        return true
    }

    override fun onInterrupt() = release()
    override fun onDestroy() { release(); super.onDestroy() }

    private fun release() {
        if (!held) return
        held = false
        send(PttForegroundService.ACTION_PTT_UP)
    }

    private fun send(action: String) {
        val i=Intent(this,PttForegroundService::class.java).setAction(action)
        if (android.os.Build.VERSION.SDK_INT >= 26) startForegroundService(i) else startService(i)
    }
}
''')

xml=Path("app/src/main/res/xml"); xml.mkdir(parents=True, exist_ok=True)
(xml/"volume_ptt_accessibility.xml").write_text('''<?xml version="1.0" encoding="utf-8"?>
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
if not sp.exists(): sp.write_text('<?xml version="1.0" encoding="utf-8"?>\n<resources>\n</resources>\n')
st=sp.read_text()
if "volume_ptt_accessibility_desc" not in st:
    st=st.replace("</resources>", '    <string name="volume_ptt_accessibility_desc">Ses açma tuşunu MELEHAT bas-konuş mandalı olarak kullanır.</string>\n</resources>')
sp.write_text(st)

mp=Path("app/src/main/AndroidManifest.xml")
m=mp.read_text()
m=re.sub(r'\s*<service\s+android:name="\.service\.VolumePttAccessibilityService"[\s\S]*?</service>\s*', '\n', m)
entry='''        <service
            android:name=".service.VolumePttAccessibilityService"
            android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE"
            android:exported="true">
            <intent-filter>
                <action android:name="android.accessibilityservice.AccessibilityService" />
            </intent-filter>
            <meta-data android:name="android.accessibilityservice" android:resource="@xml/volume_ptt_accessibility" />
        </service>
'''
m=m.replace("</application>", entry+"    </application>")
mp.write_text(m)

# Keep visible version text consistent and provide the permission shortcut.
ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
u=ui.read_text()
for line in ["import android.provider.Settings","import android.content.Intent","import androidx.compose.material3.Button"]:
    if line not in u:
        pos=u.find("\n",u.find("package ")); u=u[:pos+1]+line+"\n"+u[pos+1:]
u=u.replace('UpdateChecker()\n                Text("v0.27 • PTT + Otomatik Güncelleme"', 'C37AccessibilityButton()\n                UpdateChecker()\n                Text("C37 • v0.27 temiz taban • Kilit ekranı PTT"')
u=re.sub(r'MELEHAT TELSİZ v0\.26', 'MELEHAT TELSİZ C37', u)
u += r'''

@Composable
private fun C37AccessibilityButton() {
    val context = LocalContext.current
    Button(onClick = { context.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }) {
        Text("SES MANDALI ERİŞİLEBİLİRLİK İZNİ")
    }
}
'''
ui.write_text(u)

b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"', 'applicationId = "com.melehat.telsiz.c37"', t)
t=re.sub(r'versionCode\s*=\s*\d+', 'versionCode = 37', t)
t=re.sub(r'versionName\s*=\s*"[^"]+"', 'versionName = "C37-v27-normal-install"', t)
b.write_text(t)
print("C37 root PTT rebuild applied")
