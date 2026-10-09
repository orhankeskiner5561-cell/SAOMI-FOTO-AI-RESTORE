package com.saomi.telsiz.video

import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.lifecycle.lifecycleScope
import android.content.Intent
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** Only shows for a server-verified pending MELEHAT video-call invitation. */
class IncomingVideoCallActivity : ComponentActivity() {
    companion object {
        const val EXTRA_CALL_ID = "melehat.incoming.id"
        const val EXTRA_CALLER_NAME = "melehat.incoming.name"
        const val ACTION_ACCEPT = "melehat.video.ACCEPT"
        const val ACTION_DECLINE = "melehat.video.DECLINE"
    }

    private var callId: String = ""
    private var callerName by mutableStateOf("MELEHAT üyesi")
    private var active by mutableStateOf(true)
    private var busy by mutableStateOf(false)
    private var message by mutableStateOf("Görüntülü arama")
    private lateinit var api: VideoCallApi

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // OS-approved full-screen incoming CALL notification opens this Activity
        // above the keyguard. No prohibited direct background Activity start.
        if (Build.VERSION.SDK_INT >= 27) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        callId = intent.getStringExtra(EXTRA_CALL_ID).orEmpty()
        callerName = intent.getStringExtra(EXTRA_CALLER_NAME)
            ?.takeIf { it.isNotBlank() } ?: "MELEHAT üyesi"
        if (!callId.matches(Regex("[a-fA-F0-9-]{36}"))) { finish(); return }
        api = VideoCallApi(this)
        setContent {
            MaterialTheme {
                Column(
                    Modifier.fillMaxSize().background(Color(0xFF161C2E))
                        .systemBarsPadding().padding(horizontal = 24.dp, vertical = 36.dp),
                    verticalArrangement = Arrangement.SpaceEvenly,
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text("MELEHAT TELSİZ", color = Color(0xFFFFA760),
                        style = MaterialTheme.typography.headlineSmall)
                    Text("Gelen görüntülü arama", color = Color.White,
                        style = MaterialTheme.typography.titleLarge)
                    Text(callerName, color = Color.White,
                        style = MaterialTheme.typography.headlineMedium)
                    Text(message, color = Color.LightGray)
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                        Button(onClick = { respond(false) }, enabled = !busy,
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFC83244))) {
                            Text("REDDET")
                        }
                        Button(onClick = { respond(true) }, enabled = !busy,
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF26864C))) {
                            Text("AÇ • KABUL ET")
                        }
                    }
                    Text("Arama yanıtlanmazsa yaklaşık 35 saniyede sona erer.",
                        color = Color.LightGray,
                        style = MaterialTheme.typography.bodySmall)
                }
                BackHandler { respond(false) }
            }
        }

        // The screen itself also validates that the invitation is still
        // ringing: expired calls never remain stuck on top of the lockscreen.
        lifecycleScope.launch {
            while (active) {
                val valid = runCatching {
                    api.poll().any {
                        it.id == callId && it.myState == "pending" &&
                            it.state in listOf("ringing", "active")
                    }
                }.getOrNull()
                if (valid == false) {
                    active = false
                    VideoCallMonitor.clearIncoming(applicationContext)
                    message = "Arama sona erdi • Cevapsız"
                    delay(1300)
                    finish()
                    break
                }
                delay(1600)
            }
        }
        when (intent.action) {
            ACTION_ACCEPT -> respond(true)
            ACTION_DECLINE -> respond(false)
        }
    }

    private fun respond(accept: Boolean) {
        if (!active || busy) return
        busy = true
        message = if (accept) "Bağlanılıyor…" else "Arama reddediliyor…"
        lifecycleScope.launch {
            runCatching { api.answer(callId, accept) }
                .onSuccess {
                    active = false
                    VideoCallMonitor.clearIncoming(applicationContext)
                    if (accept) {
                        startActivity(Intent(this@IncomingVideoCallActivity,
                            VideoCallActivity::class.java).apply {
                            putExtra(VideoCallActivity.EXTRA_CALL_ID, callId)
                            putExtra(VideoCallActivity.EXTRA_HOST, false)
                        })
                    }
                    finish()
                }
                .onFailure {
                    active = false
                    VideoCallMonitor.clearIncoming(applicationContext)
                    message = "Arama sona erdi: " + it.message.orEmpty()
                    delay(1600)
                    finish()
                }
            busy = false
        }
    }

    override fun onDestroy() {
        active = false
        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        super.onDestroy()
    }
}
