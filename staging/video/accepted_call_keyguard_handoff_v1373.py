#!/usr/bin/env python3
# MELEHAT v1.3.73: lockscreen -> accepted native video call handoff.
# Preserve existing camera codec fixes, two-sided hangup, PTT, channels
# package ID and permanent keystore. Do not bypass a secure lock screen.
from pathlib import Path

video=Path("app/src/main/java/com/saomi/telsiz/video/P2pVideoCallActivity.kt")
incoming=Path("app/src/main/java/com/saomi/telsiz/video/IncomingVideoCallActivity.kt")
manifest=Path("app/src/main/AndroidManifest.xml")
src=video.read_text(encoding="utf-8")

def exactly(old,new,what):
    global src
    n=src.count(old)
    if n!=1:raise RuntimeError(f"{what}: expected 1 marker, got {n}")
    src=src.replace(old,new,1)

exactly('''import android.Manifest
import android.content.Intent''',
'''import android.Manifest
import android.app.KeyguardManager
import android.content.Intent
import android.content.Context
import android.os.Build
import android.view.View''',
"Android keyguard imports")

exactly('''    private lateinit var reconnectButton:Button
    private var callId=""''',
'''    private lateinit var reconnectButton:Button
    private lateinit var unlockButton:Button
    private var unlockRequestAttempted=false
    private var callId=""''',
"lock/unlock state")

exactly('''        if(result[Manifest.permission.CAMERA]==true &&
            result[Manifest.permission.RECORD_AUDIO]==true) startMedia()
        else notice("Kamera ve mikrofon izni gerekli. Ayarlardan izin verebilirsiniz.")''',
'''        if(result[Manifest.permission.CAMERA]==true &&
            result[Manifest.permission.RECORD_AUDIO]==true) {
            if (ensureScreenUnlocked()) startMedia()
        } else notice("Kamera ve mikrofon izni gerekli. Ayarlardan izin verebilirsiniz.")''',
"gate permissions by actual unlock")

exactly('''        api=VideoCallApi(this)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        buildScreen()''',
'''        api=VideoCallApi(this)
        // The incoming-call Activity is already allowed above the keyguard.
        // Carry that visibility into the ACCEPTED video Activity instead of
        // returning to the lock screen as IncomingVideoCallActivity finishes.
        // A secure PIN/biometric lock is NEVER silently bypassed.
        if(Build.VERSION.SDK_INT>=Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        buildScreen()
        if(screenIsLocked()) {
            window.decorView.post { if(!ended) ensureScreenUnlocked() }
        }''',
"accepted call above lockscreen")

exactly('''                        current.state=="active" && !started && !permissionWaiting -> {
                            isCaller=current.callerId==SessionStore(this@P2pVideoCallActivity).load()?.userId
                            requestPermissionsIfNeeded()
                        }''',
'''                        current.state=="active" && !started && !permissionWaiting -> {
                            isCaller=current.callerId==SessionStore(this@P2pVideoCallActivity).load()?.userId
                            if (ensureScreenUnlocked()) requestPermissionsIfNeeded()
                        }''',
"active call waits for device unlock")

exactly('''        root.addView(statusView,LinearLayout.LayoutParams(-1,dp(75)))
        val videoColumn''',
'''        root.addView(statusView,LinearLayout.LayoutParams(-1,dp(75)))
        unlockButton=Button(this).apply {
            text="GÖRÜŞMEYE GEÇ • EKRAN KİLİDİNİ AÇ"
            visibility=View.GONE
            setOnClickListener {
                unlockRequestAttempted=false
                ensureScreenUnlocked()
            }
        }
        root.addView(unlockButton,LinearLayout.LayoutParams(-1,dp(58)))
        val videoColumn''',
"unlock UI with manual retry")

anchor='''    private fun requestPermissionsIfNeeded(){'''
method='''    private fun screenIsLocked():Boolean {
        val keyguard=getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
        return keyguard.isKeyguardLocked || keyguard.isDeviceLocked
    }

    private fun ensureScreenUnlocked():Boolean {
        if(ended)return false
        if(!screenIsLocked()) {
            unlockRequestAttempted=false
            if(::unlockButton.isInitialized)unlockButton.visibility=View.GONE
            // Once authenticated, the video must not float over a future
            // secured lock screen; retain standard Android privacy.
            if(Build.VERSION.SDK_INT>=Build.VERSION_CODES.O_MR1)
                setShowWhenLocked(false)
            return true
        }

        if(::unlockButton.isInitialized)unlockButton.visibility=View.VISIBLE
        notice("Çağrı kabul edildi • görüntülü konuşma için ekran kilidini açın")
        if(!unlockRequestAttempted) {
            unlockRequestAttempted=true
            if(Build.VERSION.SDK_INT>=Build.VERSION_CODES.O) {
                val keyguard=getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
                keyguard.requestDismissKeyguard(this,
                    object:KeyguardManager.KeyguardDismissCallback() {
                        override fun onDismissSucceeded() {
                            runOnUiThread {
                                if(ended)return@runOnUiThread
                                // Keep the prompt guard during Android's unlock
                                // animation. Do not issue another request until the
                                // device actually becomes unlocked.
                                window.decorView.post {
                                    if(!ended && !screenIsLocked() && ensureScreenUnlocked()) {
                                        notice("Kilit açıldı • görüşmeye bağlanılıyor")
                                    }
                                }
                            }
                        }
                        override fun onDismissCancelled() {
                            notice("Ekran kilidini açıp görüşmeye devam edin")
                        }
                        override fun onDismissError() {
                            notice("Kilit açılamadı. KİLİDİ AÇ düğmesini deneyin")
                        }
                    })
            }
        }
        return false
    }

    override fun onResume() {
        super.onResume()
        if(::unlockButton.isInitialized && !ended) {
            window.decorView.post {
                if(!ended)ensureScreenUnlocked()
            }
        }
    }

'''
if src.count(anchor)!=1:raise RuntimeError("requestPermissions anchor changed")
src=src.replace(anchor,method+anchor,1)

exactly('''    private fun requestPermissionsIfNeeded(){
        if(ended||started||permissionWaiting)return
        val perms''',
'''    private fun requestPermissionsIfNeeded(){
        if(ended||started||permissionWaiting)return
        if(!ensureScreenUnlocked())return
        val perms''',
"block runtime camera permission while locked")

exactly('''    private fun startMedia(){
        if(ended||started||connecting)return
        started=true;connecting=true''',
'''    private fun startMedia(){
        if(ended||started||connecting)return
        if(!ensureScreenUnlocked())return
        started=true;connecting=true''',
"camera/microphone may only start after unlock")

# Do not regress the issues already fixed and verified by physical phone tests.
for protected in (
    "DefaultVideoEncoderFactory",
    "DefaultVideoDecoderFactory",
    "requireVideoCodec",
    "onTrack(transceiver:RtpTransceiver?)",
    "receivedRemoteFrame",
    "api.endDirect(callId)",
    "PttForegroundService.ACTION_START",
    "setShowWhenLocked(true)",
    "requestDismissKeyguard",
    "if(!ensureScreenUnlocked())return",
):
    if protected not in src:raise RuntimeError("Protected video feature missing "+protected)

txt=incoming.read_text(encoding="utf-8")
for tag in ("setShowWhenLocked(true)","setTurnScreenOn(true)",
            "P2pVideoCallActivity::class.java",
            "ACTION_ACCEPT", "VideoCallMonitor.clearIncoming"):
    if tag not in txt:raise RuntimeError("Incoming call flow changed "+tag)
assert 'P2pVideoCallActivity' in manifest.read_text(encoding="utf-8")
assert 'applicationId = "com.melehat.telsiz"' in Path("app/build.gradle.kts").read_text(encoding="utf-8")
video.write_text(src,encoding="utf-8")
print("MELEHAT_1373_ACCEPTED_CALL_LOCKSCREEN_HANDOFF_SECURE_READY")
