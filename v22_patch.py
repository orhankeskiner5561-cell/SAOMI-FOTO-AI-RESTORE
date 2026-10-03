from pathlib import Path
import re

# Remove accessibility service registration added by v17.
manifest=Path("app/src/main/AndroidManifest.xml")
m=manifest.read_text()
m=re.sub(r'\s*<service\s+android:name="\.service\.VolumePttAccessibilityService"[\s\S]*?</service>\s*', '\n', m)
manifest.write_text(m)

# Remove generated accessibility service source and XML if present.
svc=Path("app/src/main/java/com/saomi/telsiz/service/VolumePttAccessibilityService.kt")
if svc.exists(): svc.unlink()
xml=Path("app/src/main/res/xml/volume_ptt_accessibility_service.xml")
if xml.exists(): xml.unlink()

p=Path("app/src/main/java/com/saomi/telsiz/service/PttForegroundService.kt")
s=p.read_text()

# Remove direct references to removed accessibility service actions.
s=re.sub(r'''\s*VolumePttAccessibilityService\.ACTION_VOLUME_PTT_DOWN -> \{[\s\S]*?\n\s*\}\n\n\s*VolumePttAccessibilityService\.ACTION_VOLUME_PTT_UP -> \{[\s\S]*?\n\s*\}\n''','\n',s, count=1)

# Imports for MediaSession / VolumeProvider / delayed release timer.
if 'import android.media.session.MediaSession' not in s:
    s=s.replace('import android.os.Build\n', 'import android.os.Build\nimport android.media.VolumeProvider\nimport android.media.session.MediaSession\nimport android.os.Handler\nimport android.os.Looper\n')

# Fields.
field_anchor='''    private var leaseJob: Job? = null
'''
if field_anchor in s and 'private var mediaSession:' not in s:
    s=s.replace(field_anchor, field_anchor + '''    private var mediaSession: MediaSession? = null
    private val volumePttHandler = Handler(Looper.getMainLooper())
    private var volumePttRelease: Runnable? = null
''')

# Helper methods before onDestroy.
if 'private fun startVolumeKeyPttSession()' not in s:
    marker='''    override fun onDestroy() {
'''
    helper=r'''    private fun startVolumeKeyPttSession() {
        if (mediaSession != null) return
        val session = MediaSession(this, "MELEHAT_PTT")
        val provider = object : VolumeProvider(
            VolumeProvider.VOLUME_CONTROL_RELATIVE,
            100,
            50
        ) {
            override fun onAdjustVolume(direction: Int) {
                if (!started) return
                // Ses açma tuşu: ilk olayda konuşmayı başlat.
                // Tuş basılı tutulurken Android tekrar olayları yollar; her olay
                // bırakma zamanlayıcısını yeniler. Olaylar kesilince ~450 ms sonra bırakır.
                if (direction > 0) {
                    val down = Intent(this@PttForegroundService, PttForegroundService::class.java).apply {
                        action = ACTION_PTT_DOWN
                    }
                    startService(down)

                    volumePttRelease?.let { volumePttHandler.removeCallbacks(it) }
                    val release = Runnable {
                        val up = Intent(this@PttForegroundService, PttForegroundService::class.java).apply {
                            action = ACTION_PTT_UP
                        }
                        startService(up)
                    }
                    volumePttRelease = release
                    volumePttHandler.postDelayed(release, 450L)
                } else if (direction < 0) {
                    // Ses kısma tuşu acil bırakma / konuşmayı kes.
                    volumePttRelease?.let { volumePttHandler.removeCallbacks(it) }
                    val up = Intent(this@PttForegroundService, PttForegroundService::class.java).apply {
                        action = ACTION_PTT_UP
                    }
                    startService(up)
                }
            }
        }
        session.setPlaybackToRemote(provider)
        session.isActive = true
        mediaSession = session
    }

    private fun stopVolumeKeyPttSession() {
        volumePttRelease?.let { volumePttHandler.removeCallbacks(it) }
        volumePttRelease = null
        mediaSession?.isActive = false
        mediaSession?.release()
        mediaSession = null
    }

'''
    s=s.replace(marker, helper+marker)

# Activate session when radio starts.
if 'startVolumeKeyPttSession()' in s:
    # add only in radio start path after radio_enabled true if not already
    target='''        getSharedPreferences("melehat_ptt", MODE_PRIVATE).edit()
            .putBoolean("radio_enabled", true).apply()
'''
    if target in s and target+'        startVolumeKeyPttSession()\n' not in s:
        s=s.replace(target, target+'        startVolumeKeyPttSession()\n',1)

# Stop session when radio stops and service destroyed.
stop_target='''        getSharedPreferences("melehat_ptt", MODE_PRIVATE).edit()
            .putBoolean("radio_enabled", false).apply()
'''
if stop_target in s and 'stopVolumeKeyPttSession()' not in s[s.find(stop_target):s.find(stop_target)+400]:
    s=s.replace(stop_target, stop_target+'        stopVolumeKeyPttSession()\n',1)

destroy_anchor='''    override fun onDestroy() {
'''
if destroy_anchor in s and 'override fun onDestroy() {\n        stopVolumeKeyPttSession()' not in s:
    s=s.replace(destroy_anchor, '''    override fun onDestroy() {
        stopVolumeKeyPttSession()
''',1)

p.write_text(s)

# Version text / gradle.
ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
u=ui.read_text()
for old in ["v0.21 • Ses Açma Tuşu PTT","v0.18 • Ses Açma Tuşu PTT","v0.17 • Ses Açma Tuşu PTT"]:
    u=u.replace(old,"v0.22 • Güvenli Ses Tuşu PTT")
for old in ["MELEHAT TELSİZ v0.21","MELEHAT TELSİZ v0.18","MELEHAT TELSİZ v0.17"]:
    u=u.replace(old,"MELEHAT TELSİZ v0.22")
ui.write_text(u)

b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'versionCode\s*=\s*\d+', 'versionCode = 22', t)
t=re.sub(r'versionName\s*=\s*"[^"]+"', 'versionName = "0.22.0"', t)
# Fresh package id to avoid all previous install residues.
t=re.sub(r'applicationId\s*=\s*"[^"]+"', 'applicationId = "com.melehat.telsiz.v22"', t)
b.write_text(t)

print("v0.22 removes AccessibilityService and uses MediaSession VolumeProvider PTT")
