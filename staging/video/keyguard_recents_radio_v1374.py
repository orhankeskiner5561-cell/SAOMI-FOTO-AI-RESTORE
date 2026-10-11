#!/usr/bin/env python3
# MELEHAT v1.3.74: accepted locked-screen call handoff and foreground
# radio survival on recent-task swipe. No PTT codec/signal/SDP changes,
# no forced unlock, no package or keystore changes.
from pathlib import Path
root=Path("app/src/main")
base=root/"java/com/saomi/telsiz"
incoming=base/"video/IncomingVideoCallActivity.kt"
video=base/"video/P2pVideoCallActivity.kt"
service=base/"service/PttForegroundService.kt"
manifest=root/"AndroidManifest.xml"
def change(path,old,new,label):
    current=path.read_text(encoding="utf-8")
    n=current.count(old)
    if n!=1: raise RuntimeError(f"{label}: expected 1 anchor; got {n}")
    path.write_text(current.replace(old,new,1),encoding="utf-8")

# Android 12-16 treats CALL acceptance as a user-initiated action, but may
# return to the keyguard when the accepted Activity is in the same excluded
# recents task as the incoming-call screen. Give the accepted call a separate
# foreground task and lockscreen-visible Android window.
change(manifest,
'''        <activity
            android:name="com.saomi.telsiz.video.P2pVideoCallActivity"
            android:exported="false"
            android:screenOrientation="portrait" />''',
'''        <activity
            android:name="com.saomi.telsiz.video.P2pVideoCallActivity"
            android:exported="false"
            android:screenOrientation="portrait"
            android:showWhenLocked="true"
            android:turnScreenOn="true"
            android:launchMode="singleTop"
            android:taskAffinity="com.melehat.telsiz.acceptedcall"
            android:excludeFromRecents="false" />''',
"accepted video manifest/task above keyguard")
change(incoming,
'''                            putExtra(P2pVideoCallActivity.EXTRA_CALL_ID, callId)
                            putExtra(P2pVideoCallActivity.EXTRA_HOST, false)
                        })
                    }
                    finish()''',
'''                            putExtra(P2pVideoCallActivity.EXTRA_CALL_ID, callId)
                            putExtra(P2pVideoCallActivity.EXTRA_HOST, false)
                            // Separate the active video task from the full-screen
                            // incoming-call task (excluded from Recents).
                            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or
                                Intent.FLAG_ACTIVITY_CLEAR_TOP or
                                Intent.FLAG_ACTIVITY_SINGLE_TOP)
                        })
                    }
                    finish()''',
"accepted call foreground task handoff")
# Add a persistent user-visible "return to call" notification if the OS
# backgrounds the accepted Activity. Never silently unlock secured phones.
videoSource=video.read_text(encoding="utf-8")
if "onResume()" not in videoSource or "ensureScreenUnlocked()" not in videoSource:
    raise RuntimeError("Prior secure keyguard handoff missing")

change(video,
'''import android.app.KeyguardManager
import android.content.Intent''',
'''import android.app.KeyguardManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import androidx.core.app.NotificationCompat
import android.content.Intent''',
"call return notification imports")

change(video,
'''    private var unlockRequestAttempted=false
    private var callId=""''',
'''    private var unlockRequestAttempted=false
    private val returnNotificationId=50874
    private val returnChannelId="melehat_video_return_v1"
    private var callId=""''',
"return notification state")

entry='''    override fun onResume() {
        super.onResume()'''
if video.read_text(encoding="utf-8").count(entry)!=1:
    raise RuntimeError("onResume handoff changed")

extra='''    private fun notifyReturnToCall() {
        if(ended)return
        if(Build.VERSION.SDK_INT>=33 &&
            androidx.core.content.ContextCompat.checkSelfPermission(this,
                Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED) {
            return
        }
        val notifications=getSystemService(Context.NOTIFICATION_SERVICE)
            as NotificationManager
        notifications.createNotificationChannel(
            NotificationChannel(returnChannelId,"MELEHAT aktif görüntülü görüşme",
                NotificationManager.IMPORTANCE_HIGH).apply {
                lockscreenVisibility=android.app.Notification.VISIBILITY_PUBLIC
            })
        val resume=Intent(this,P2pVideoCallActivity::class.java).apply {
            putExtra(EXTRA_CALL_ID,callId)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or
                Intent.FLAG_ACTIVITY_SINGLE_TOP)
        }
        val pending=PendingIntent.getActivity(this,returnNotificationId,
            resume,PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val item=NotificationCompat.Builder(this,returnChannelId)
            .setSmallIcon(android.R.drawable.ic_menu_call)
            .setContentTitle("MELEHAT görüntülü görüşme sürüyor")
            .setContentText("Görüşme ekranına dönmek için dokunun")
            .setContentIntent(pending)
            .setCategory(NotificationCompat.CATEGORY_CALL)
            .setOngoing(true)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()
        runCatching{notifications.notify(returnNotificationId,item)}
    }

    private fun hideReturnNotification(){
        runCatching{
            (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
                .cancel(returnNotificationId)
        }
    }

    override fun onStop(){
        super.onStop()
        // Android may temporarily show the lock screen after call accept.
        // Do not lose the in-progress call; let the user reopen it.
        if(!ended)notifyReturnToCall()
    }

'''
change(video,entry,extra+entry,"foreground reopen notification and onStop")
change(video,
'''    override fun onResume() {
        super.onResume()
        if(::unlockButton.isInitialized''',
'''    override fun onResume() {
        super.onResume()
        hideReturnNotification()
        if(::unlockButton.isInitialized''',
"cancel reopen notice while visible")
change(video,
'''    override fun onDestroy(){
        ended=true''',
'''    override fun onDestroy(){
        hideReturnNotification()
        ended=true''',
"clear return-notification on hangup")

# The radio FGS already has START_STICKY, stopWithTask=false and holds a
# user-enabled radio session, but onTaskRemoved only changed notification.
# Reaffirm foreground state and active presence immediately on swiping,
# without launching activities or a new microphone service in background.
change(service,
'''        if (started && store.isRadioEnabled()) {
            runCatching {
                updateNotification("MELEHAT arka planda • Telsiz dinlemede")
            }
        }
        super.onTaskRemoved(rootIntent)''',
'''        if (started && store.isRadioEnabled()) {
            ExternalPttDiagnostics.record(this,"service",
                "RECENTS_TASK_REMOVED_KEEP_RADIO_ACTIVE")
            runCatching {
                // Existing foreground service stays alive independently of UI.
                startAsForeground("MELEHAT arka planda • Telsiz açık")
            }
            com.saomi.telsiz.video.VideoCallMonitor.start(applicationContext)
            scope.launch {
                if (!started || !store.isRadioEnabled()) return@launch
                runCatching {
                    roomMutex.withLock {
                        if (started && !roomSwitching && !ptt.isConnected()) {
                            ptt.ensureConnected()
                        }
                    }
                }.onFailure {
                    ExternalPttDiagnostics.record(this@PttForegroundService,
                        "service", "RECENTS_CONNECTION_CHECK_FAILED " +
                            it.javaClass.simpleName)
                }
            }
        }
        super.onTaskRemoved(rootIntent)''',
"task swipe keeps current foreground radio registration")

# Confirm permanent service / startup identity and locked media privacy.
m=manifest.read_text(encoding="utf-8")
sv=service.read_text(encoding="utf-8")
vi=video.read_text(encoding="utf-8")
inc=incoming.read_text(encoding="utf-8")
assert 'android:stopWithTask="false"' in m
assert 'android:showWhenLocked="true"' in m
assert 'android.permission.USE_FULL_SCREEN_INTENT' in m
assert 'return START_STICKY' in sv
assert 'VideoCallMonitor.start(applicationContext)' in sv
assert 'forceMute()' in sv and 'ACTION_PTT_UP' in sv
assert 'PttForegroundService.ACTION_START' in vi
assert 'ensureScreenUnlocked()' in vi and 'requestDismissKeyguard' in vi
assert 'api.endDirect(callId)' in vi
assert 'addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or' in inc
assert 'applicationId = "com.melehat.telsiz"' in Path("app/build.gradle.kts").read_text()
print("MELEHAT_1374_LOCKED_ACCEPT_HANDOFF_AND_RECENTS_RADIO_GUARD_READY")
