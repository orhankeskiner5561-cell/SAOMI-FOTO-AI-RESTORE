from pathlib import Path
import re

pkg=Path("app/src/main/java/com/saomi/telsiz")
svc=pkg/"service"/"VolumeMediaPttService.kt"
svc.parent.mkdir(parents=True, exist_ok=True)
svc.write_text("""package com.saomi.telsiz.service

import android.app.Service
import android.content.Intent
import android.media.VolumeProvider
import android.media.session.MediaSession
import android.media.session.PlaybackState
import android.os.IBinder

class VolumeMediaPttService : Service() {
    private lateinit var session: MediaSession
    private var held = false

    private val provider = object : VolumeProvider(VOLUME_CONTROL_RELATIVE, 100, 50) {
        override fun onAdjustVolume(direction: Int) {
            if (direction > 0 && !held) {
                held = true
                sendPtt(PttForegroundService.ACTION_PTT_DOWN)
            } else if (direction == 0 && held) {
                held = false
                sendPtt(PttForegroundService.ACTION_PTT_UP)
            }
            setCurrentVolume(50)
        }
    }

    override fun onCreate() {
        super.onCreate()
        session = MediaSession(this, "MELEHAT_VOLUME_PTT").apply {
            setPlaybackState(PlaybackState.Builder()
                .setState(PlaybackState.STATE_PLAYING, 0L, 1f).build())
            setPlaybackToRemote(provider)
            isActive = true
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int) = START_STICKY
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        if (held) sendPtt(PttForegroundService.ACTION_PTT_UP)
        held = false
        if (::session.isInitialized) { session.isActive = false; session.release() }
        super.onDestroy()
    }

    private fun sendPtt(action: String) {
        startForegroundService(Intent(this, PttForegroundService::class.java).setAction(action))
    }
}
""")

mp=Path("app/src/main/AndroidManifest.xml")
m=mp.read_text()
entry='''        <service
            android:name=".service.VolumeMediaPttService"
            android:exported="false" />
'''
if "VolumeMediaPttService" not in m:
    m=m.replace("</application>", entry+"\n    </application>")
mp.write_text(m)

pp=pkg/"service"/"PttForegroundService.kt"
s=pp.read_text()
needle="""            ACTION_START -> {
"""
replacement="""            ACTION_START -> {
                runCatching { startService(Intent(this, VolumeMediaPttService::class.java)) }
"""
if needle in s and "VolumeMediaPttService::class.java" not in s:
    s=s.replace(needle,replacement,1)
pp.write_text(s)

b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"', 'applicationId = "com.melehat.telsiz.volumetest"', t)
t=re.sub(r'versionCode\s*=\s*\d+', 'versionCode = 29', t)
t=re.sub(r'versionName\s*=\s*"[^"]+"', 'versionName = "0.29.0-volume-test"', t)
b.write_text(t)

ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
u=ui.read_text().replace("v0.27 • PTT + Otomatik Güncelleme", "v0.29 TEST • Ses+ Dış Mandal")
ui.write_text(u)
print("v0.29 media volume PTT test applied")
