from pathlib import Path
import re

pkg=Path("app/src/main/java/com/saomi/telsiz")
svc=pkg/"service"/"VolumeMediaPttService.kt"
svc.parent.mkdir(parents=True, exist_ok=True)
svc.write_text(r'''package com.saomi.telsiz.service

import android.app.Service
import android.content.Intent
import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.media.VolumeProvider
import android.media.session.MediaSession
import android.media.session.PlaybackState
import android.os.IBinder

class VolumeMediaPttService : Service() {
    private lateinit var session: MediaSession
    private var silentTrack: AudioTrack? = null
    private var held = false

    private val provider = object : VolumeProvider(VOLUME_CONTROL_RELATIVE, 100, 50) {
        override fun onAdjustVolume(direction: Int) {
            when {
                direction > 0 && !held -> {
                    held = true
                    sendPtt(PttForegroundService.ACTION_PTT_DOWN)
                }
                direction == 0 && held -> {
                    held = false
                    sendPtt(PttForegroundService.ACTION_PTT_UP)
                }
            }
            setCurrentVolume(50)
        }
    }

    override fun onCreate() {
        super.onCreate()
        startSilentPlayback()
        session = MediaSession(this, "MELEHAT_SCREEN_OFF_VOLUME_PTT").apply {
            setFlags(MediaSession.FLAG_HANDLES_MEDIA_BUTTONS or MediaSession.FLAG_HANDLES_TRANSPORT_CONTROLS)
            setPlaybackState(PlaybackState.Builder()
                .setActions(PlaybackState.ACTION_PLAY or PlaybackState.ACTION_PAUSE)
                .setState(PlaybackState.STATE_PLAYING, 0L, 1f).build())
            setPlaybackToRemote(provider)
            isActive = true
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (::session.isInitialized && !session.isActive) session.isActive = true
        if (silentTrack?.playState != AudioTrack.PLAYSTATE_PLAYING) startSilentPlayback()
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        releaseHeld()
        runCatching { silentTrack?.stop() }
        silentTrack?.release()
        silentTrack = null
        if (::session.isInitialized) {
            session.isActive = false
            session.release()
        }
        super.onDestroy()
    }

    private fun startSilentPlayback() {
        if (silentTrack?.playState == AudioTrack.PLAYSTATE_PLAYING) return
        runCatching {
            silentTrack?.release()
            val rate = 8000
            val min = AudioTrack.getMinBufferSize(rate, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
            val size = maxOf(min, 2048)
            val track = AudioTrack.Builder()
                .setAudioAttributes(AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build())
                .setAudioFormat(AudioFormat.Builder()
                    .setSampleRate(rate)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .build())
                .setBufferSizeInBytes(size)
                .setTransferMode(AudioTrack.MODE_STATIC)
                .build()
            track.write(ByteArray(size), 0, size)
            track.setLoopPoints(0, size / 2, -1)
            track.setVolume(0f)
            track.play()
            silentTrack = track
        }
    }

    private fun releaseHeld() {
        if (held) sendPtt(PttForegroundService.ACTION_PTT_UP)
        held = false
    }

    private fun sendPtt(action: String) {
        startForegroundService(Intent(this, PttForegroundService::class.java).setAction(action))
    }
}
''')

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
t=re.sub(r'applicationId\s*=\s*"[^"]+"', 'applicationId = "com.melehat.telsiz.volumetest30"', t)
t=re.sub(r'versionCode\s*=\s*\d+', 'versionCode = 30', t)
t=re.sub(r'versionName\s*=\s*"[^"]+"', 'versionName = "0.30.0-screenoff-volume"', t)
b.write_text(t)

ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
u=ui.read_text()
u=u.replace("v0.27 • PTT + Otomatik Güncelleme", "v0.30 TEST • Ekran Kapalı Ses+")
u=u.replace("MELEHAT TELSİZ v0.26", "MELEHAT TELSİZ v0.30 TEST")
ui.write_text(u)
print("v0.30 silent AudioTrack + MediaSession screen-off Volume+ test applied")
