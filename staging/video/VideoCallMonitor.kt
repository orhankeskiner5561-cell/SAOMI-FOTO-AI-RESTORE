package com.saomi.telsiz.video

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.saomi.telsiz.MainActivity
import com.saomi.telsiz.data.BackendApi
import com.saomi.telsiz.data.SessionStore
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.util.concurrent.atomic.AtomicBoolean

data class MelehatMissedCall(val id: String, val callerName: String, val time: Long)

/**
 * A single authenticated, process-wide call watcher. Also runs while the
 * existing walkie-talkie foreground service keeps the app process alive.
 * A force-stopped or OS-killed app still requires FCM for reliable delivery.
 */
object VideoCallMonitor {
    val latestMissed = MutableStateFlow<MelehatMissedCall?>(null)
    private val started = AtomicBoolean(false)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var job: Job? = null
    private const val PREF = "melehat_video_notice_v1"
    private const val INCOMING_CHANNEL = "melehat_video_incoming_v1"
    private const val MISSED_CHANNEL = "melehat_video_missed_v1"
    private const val INCOMING_ID = 50260
    private const val MISSED_ID = 50261

    private fun preferences(context: Context) =
        context.applicationContext.getSharedPreferences(PREF, Context.MODE_PRIVATE)

    fun notificationsEnabled(context: Context): Boolean =
        (Build.VERSION.SDK_INT < 33 ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS)
                == PackageManager.PERMISSION_GRANTED) &&
            (context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
                .areNotificationsEnabled()

    fun start(context: Context) {
        val app = context.applicationContext
        val p = preferences(app)
        if (p.getString("last_missed_id", "").orEmpty().isNotBlank()) {
            latestMissed.value = MelehatMissedCall(
                p.getString("last_missed_id", "").orEmpty(),
                p.getString("last_missed_name", "MELEHAT üyesi").orEmpty(),
                p.getLong("last_missed_time", System.currentTimeMillis())
            )
        }
        if (!started.compareAndSet(false, true)) return
        createChannels(app)
        job = scope.launch {
            val api = VideoCallApi(app)
            val store = SessionStore(app)
            val backend = BackendApi(app)
            while (isActive) {
                runCatching {
                    val me = store.load()
                    if (me == null) {
                        clearIncoming(app)
                    } else {
                        val p2 = preferences(app)
                        val previous = p2.getString("logged_in_user", "").orEmpty()
                        if (previous != me.userId) {
                            p2.edit().clear().putString("logged_in_user", me.userId).apply()
                            latestMissed.value = null
                            clearIncoming(app)
                        }
                        val calls = api.poll()
                        val ringing = calls.firstOrNull {
                            it.myState == "pending" &&
                                it.state in listOf("ringing", "active") &&
                                it.callerId != me.userId
                        }
                        if (ringing != null) {
                            if (p2.getString("incoming_id", "") != ringing.id) {
                                val from = runCatching {
                                    backend.fetchMemberDirectory(me).getOrNull()
                                        ?.firstOrNull { it.userId == ringing.callerId }
                                        ?.fullName
                                }.getOrNull().orEmpty().ifBlank { "MELEHAT üyesi" }
                                showIncoming(app, ringing.id, from)
                            }
                        } else {
                            clearIncoming(app)
                        }
                        val missed = calls.firstOrNull {
                            it.myState == "missed" && it.callerId != me.userId
                        }
                        if (missed != null &&
                            p2.getString("last_missed_id", "") != missed.id) {
                            val from = runCatching {
                                backend.fetchMemberDirectory(me).getOrNull()
                                    ?.firstOrNull { it.userId == missed.callerId }
                                    ?.fullName
                            }.getOrNull().orEmpty().ifBlank { "MELEHAT üyesi" }
                            recordMissed(app, missed.id, from)
                        }
                    }
                }
                delay(2500)
            }
        }
    }

    private fun createChannels(context: Context) {
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val ring = NotificationChannel(INCOMING_CHANNEL, "MELEHAT görüntülü aramalar",
            NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Kilit ekranında arayan adı ve cevap düğmeleri"
            lockscreenVisibility = Notification.VISIBILITY_PUBLIC
            enableVibration(true)
            setSound(RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE),
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build())
        }
        val missed = NotificationChannel(MISSED_CHANNEL, "MELEHAT cevapsız aramalar",
            NotificationManager.IMPORTANCE_DEFAULT).apply {
            lockscreenVisibility = Notification.VISIBILITY_PUBLIC
        }
        nm.createNotificationChannel(ring)
        nm.createNotificationChannel(missed)
    }

    private fun callIntent(context: Context, callId: String, name: String,
                           action: String): PendingIntent {
        val i = Intent(context, IncomingVideoCallActivity::class.java).apply {
            this.action = action
            data = android.net.Uri.parse("melehat://incoming/$callId/$action")
            putExtra(IncomingVideoCallActivity.EXTRA_CALL_ID, callId)
            putExtra(IncomingVideoCallActivity.EXTRA_CALLER_NAME, name)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        }
        return PendingIntent.getActivity(context, (callId + action).hashCode(),
            i, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }

    private fun showIncoming(context: Context, callId: String, callerName: String) {
        val p = preferences(context)
        p.edit().putString("incoming_id", callId).apply()
        if (!notificationsEnabled(context)) return
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val full = callIntent(context, callId, callerName, "melehat.video.SHOW")
        val open = callIntent(context, callId, callerName, IncomingVideoCallActivity.ACTION_ACCEPT)
        val decline = callIntent(context, callId, callerName, IncomingVideoCallActivity.ACTION_DECLINE)
        val notice = NotificationCompat.Builder(context, INCOMING_CHANNEL)
            .setSmallIcon(android.R.drawable.ic_menu_call)
            .setContentTitle("MELEHAT • Görüntülü arama")
            .setContentText("$callerName sizi görüntülü arıyor")
            .setCategory(NotificationCompat.CATEGORY_CALL)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setOngoing(true)
            .setAutoCancel(false)
            .setContentIntent(full)
            .setFullScreenIntent(full, true)
            .addAction(android.R.drawable.ic_menu_call, "AÇ", open)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, "REDDET", decline)
            .build()
        runCatching { nm.notify(INCOMING_ID, notice) }
    }

    fun clearIncoming(context: Context) {
        val p = preferences(context)
        if (p.getString("incoming_id", "").isNullOrBlank()) return
        p.edit().remove("incoming_id").apply()
        (context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
            .cancel(INCOMING_ID)
    }

    private fun recordMissed(context: Context, callId: String, callerName: String) {
        val stamp = System.currentTimeMillis()
        preferences(context).edit()
            .putString("last_missed_id", callId)
            .putString("last_missed_name", callerName)
            .putLong("last_missed_time", stamp).apply()
        latestMissed.value = MelehatMissedCall(callId, callerName, stamp)
        if (!notificationsEnabled(context)) return
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val content = PendingIntent.getActivity(context, 50261,
            Intent(context, MainActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            }, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val notice = NotificationCompat.Builder(context, MISSED_CHANNEL)
            .setSmallIcon(android.R.drawable.ic_menu_call)
            .setContentTitle("MELEHAT • Cevapsız görüntülü arama")
            .setContentText("$callerName sizi aradı • Cevapsız çağrı")
            .setStyle(NotificationCompat.BigTextStyle()
                .bigText("Son arayan: $callerName • Cevapsız görüntülü arama"))
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setCategory(NotificationCompat.CATEGORY_MISSED_CALL)
            .setContentIntent(content)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .build()
        runCatching { nm.notify(MISSED_ID, notice) }
    }

    fun dismissMissed(context: Context) {
        latestMissed.value = null
        preferences(context).edit()
            .remove("last_missed_id").remove("last_missed_name")
            .remove("last_missed_time").apply()
        (context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
            .cancel(MISSED_ID)
    }
}
