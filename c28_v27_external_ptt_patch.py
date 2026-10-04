from pathlib import Path
import re

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
    private var lastKeyEventAt = 0L

    private val releaseFailsafe = object : Runnable {
        override fun run() {
            if (!held) return
            val quietFor = SystemClock.uptimeMillis() - lastKeyEventAt
            if (quietFor >= RELEASE_QUIET_MS) {
                releasePtt()
            } else {
                handler.postDelayed(this, RELEASE_QUIET_MS - quietFor)
            }
        }
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        serviceInfo = serviceInfo.apply {
            flags = flags or AccessibilityServiceInfo.FLAG_REQUEST_FILTER_KEY_EVENTS
        }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit

    override fun onKeyEvent(event: KeyEvent): Boolean {
        if (event.keyCode != KeyEvent.KEYCODE_VOLUME_UP) return false
        lastKeyEventAt = SystemClock.uptimeMillis()
        return when (event.action) {
            KeyEvent.ACTION_DOWN -> {
                if (!held) {
                    held = true
                    sendPtt(PttForegroundService.ACTION_PTT_DOWN)
                }
                handler.removeCallbacks(releaseFailsafe)
                handler.postDelayed(releaseFailsafe, RELEASE_QUIET_MS)
                true
            }
            KeyEvent.ACTION_UP -> {
                releasePtt()
                true
            }
            else -> true
        }
    }

    override fun onInterrupt() = releasePtt()

    override fun onDestroy() {
        releasePtt()
        super.onDestroy()
    }

    private fun releasePtt() {
        handler.removeCallbacks(releaseFailsafe)
        if (held) {
            held = false
            sendPtt(PttForegroundService.ACTION_PTT_UP)
        }
    }

    private fun sendPtt(action: String) {
        val intent = Intent(this, PttForegroundService::class.java).setAction(action)
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
    }

    companion object {
        // HyperOS/other OEMs can occasionally lose ACTION_UP with screen off.
        // While a key is held Android normally sends repeat DOWN events; if those
        // events stop, release PTT so the microphone can never remain latched.
        private const val RELEASE_QUIET_MS = 1400L
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
    sp.write_text('<?xml version="1.0" encoding="utf-8"?>\\n<resources>\\n</resources>\\n')
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

ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
u=ui.read_text()
extra=[
"import android.provider.Settings",
"import android.content.ComponentName",
"import com.saomi.telsiz.service.VolumePttAccessibilityService",
"import androidx.compose.material3.Button",
]
for line in extra:
    if line not in u:
        pos=u.find("\n",u.find("package "))
        u=u[:pos+1]+line+"\n"+u[pos+1:]

u=u.replace("UpdateChecker()\n                Text(\"v0.27 • PTT + Otomatik Güncelleme\"", "AccessibilitySetupGate()\n                UpdateChecker()\n                Text(\"C28 • v0.27 TABAN • Dış Mandal\"")
u=u.replace("v0.31 TEST • Global Ses+ Mandal", "v0.28.1 • v0.27 TABAN • Dış Mandal")
u=u.replace("MELEHAT TELSİZ v0.26", "MELEHAT TELSİZ C28")
u=u.replace("MELEHAT TELSİZ v0.31 TEST", "MELEHAT TELSİZ v0.28.1")

u += r'''

private fun isMelehatAccessibilityEnabled(context: android.content.Context): Boolean {
    val expected = ComponentName(context, VolumePttAccessibilityService::class.java)
        .flattenToString()
    val enabled = Settings.Secure.getString(
        context.contentResolver,
        Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
    ).orEmpty()
    return enabled.split(':').any { it.equals(expected, ignoreCase = true) }
}

@Composable
private fun AccessibilitySetupGate() {
    val context = LocalContext.current
    var enabled by remember { mutableStateOf(isMelehatAccessibilityEnabled(context)) }
    var prompted by remember { mutableStateOf(false) }

    androidx.compose.runtime.DisposableEffect(Unit) {
        val observer = object : android.database.ContentObserver(android.os.Handler(android.os.Looper.getMainLooper())) {
            override fun onChange(selfChange: Boolean) {
                enabled = isMelehatAccessibilityEnabled(context)
            }
        }
        context.contentResolver.registerContentObserver(
            Settings.Secure.getUriFor(Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES),
            false,
            observer
        )
        onDispose { context.contentResolver.unregisterContentObserver(observer) }
    }

    LaunchedEffect(enabled) {
        if (!enabled && !prompted) {
            prompted = true
            runCatching {
                context.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                })
            }
        }
    }

    if (!enabled) {
        AlertDialog(
            onDismissRequest = { },
            title = { Text("Ses mandalı izni gerekli") },
            text = {
                Text("Arka planda ve kilitli ekranda Ses + bas-konuş için Android Erişilebilirlik ekranında MELEHAT TELSİZ özelliğini AÇIK yapın. Android güvenliği nedeniyle bu anahtarı yalnız siz açabilirsiniz.")
            },
            confirmButton = {
                Button(onClick = {
                    context.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
                }) { Text("ERİŞİLEBİLİRLİĞİ AÇ") }
            }
        )
    }
}
'''

b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"', 'applicationId = "com.melehat.telsiz.externalptt"', t)
t=re.sub(r'versionCode\s*=\s*\d+', 'versionCode = 28', t)
t=re.sub(r'versionName\s*=\s*"[^"]+"', 'versionName = "C28-v27-base-accessibility"', t)
b.write_text(t)
ui.write_text(u)
print("C28 built directly on v0.27 + accessibility service")
