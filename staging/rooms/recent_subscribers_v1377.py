#!/usr/bin/env python3
"""MELEHAT 1.3.77: isolated recent subscribers UI + authenticated directory.
No existing button positions, radio/audio/video logic, package ID or signature change.
"""
from pathlib import Path

root=Path("app/src/main/java/com/saomi/telsiz")
ui=root/"ui/AppRoot.kt"
s=ui.read_text("utf-8")

api=root/"data/RecentSubscriberApi.kt"
assert not api.exists(), "RecentSubscriberApi already exists; avoid duplicate source"
api.write_text(r'''package com.saomi.telsiz.data

import android.content.Context
import com.saomi.telsiz.BuildConfig
import com.saomi.telsiz.auth.SessionRefresher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import java.util.concurrent.TimeUnit

data class RecentSubscriber(
    val userId: String,
    val fullName: String,
    val registeredAtMs: Long,
    val online: Boolean
)

/** A read-only directory; presence is calculated by the server, not guessed locally. */
class RecentSubscriberApi(context: Context) {
    private val sessions = SessionStore(context.applicationContext)
    private val refresher = SessionRefresher(context.applicationContext)
    private val http = OkHttpClient.Builder().callTimeout(8, TimeUnit.SECONDS).build()
    private val endpoint = BuildConfig.SUPABASE_URL.trimEnd('/') +
        "/rest/v1/rpc/melehat_recent_subscribers"

    suspend fun list(): Result<List<RecentSubscriber>> = withContext(Dispatchers.IO) {
        runCatching {
            var active = sessions.load() ?: error("Oturum bulunamadı.")
            for (attempt in 0..1) {
                val request = Request.Builder().url(endpoint)
                    .header("apikey", BuildConfig.SUPABASE_PUBLISHABLE_KEY)
                    .header("Authorization", "Bearer " + active.accessToken)
                    .post("{}".toRequestBody("application/json".toMediaType()))
                    .build()
                val result = http.newCall(request).execute().use {
                    it.code to it.body?.string().orEmpty()
                }
                if (result.first == 401 && attempt == 0) {
                    val refreshed = refresher.refresh()
                        ?: error("Üye listesi oturumu yenilenemedi.")
                    if (refreshed.userId != active.userId)
                        error("Oturum kimliği değişti.")
                    active = refreshed
                    continue
                }
                if (result.first !in 200..299)
                    error("Yeni aboneler alınamadı: " + result.first)
                val array = JSONArray(result.second)
                return@runCatching buildList {
                    for (i in 0 until array.length()) {
                        val row = array.getJSONObject(i)
                        add(RecentSubscriber(
                            userId = row.optString("user_id"),
                            fullName = row.optString("full_name").ifBlank { "Üye" },
                            registeredAtMs = row.optLong("created_at_ms", 0L),
                            online = row.optBoolean("online", false)
                        ))
                    }
                }
            }
            error("Üye oturumu doğrulanamadı.")
        }
    }
}
''',encoding="utf-8")

def one(old,new,name):
    global s
    n=s.count(old)
    assert n==1, "MELEHAT 1377 missing/ambiguous " + name + ": " + str(n)
    s=s.replace(old,new,1)

# Only imports and a new self-contained composable state + dialog.
for imp in (
    "import com.saomi.telsiz.data.RecentSubscriberApi",
    "import com.saomi.telsiz.data.RecentSubscriber",
    "import androidx.compose.foundation.layout.offset",
    "import androidx.compose.foundation.clickable",
    "import androidx.compose.foundation.shape.CircleShape",
    "import androidx.compose.foundation.background",
):
    if "\n" + imp + "\n" not in "\n" + s:
        pos=s.find("\n",s.find("package "))
        s=s[:pos+1]+imp+"\n"+s[pos+1:]

anchor='    var activeRoomByUser by remember { mutableStateOf<Map<String, String>>(emptyMap()) }'
one(anchor,anchor+'''
    // The subscriber badge uses its own persisted read cursor. It cannot
    // mutate channel membership, PTT or the pre-existing Members dialog.
    val subscriberApi = remember(roomsContext) { RecentSubscriberApi(roomsContext) }
    val subscriberPrefs = remember(roomsContext) {
        roomsContext.getSharedPreferences(
            "melehat_recent_subscriber_views", android.content.Context.MODE_PRIVATE
        )
    }
    val subscriberUserKey = session?.userId.orEmpty()
    var subscriberSeenAt by remember(subscriberUserKey) {
        mutableStateOf(subscriberPrefs.getLong("seen_" + subscriberUserKey, 0L))
    }
    var subscribers by remember(subscriberUserKey) {
        mutableStateOf<List<RecentSubscriber>>(emptyList())
    }
    var subscribersLoaded by remember(subscriberUserKey) { mutableStateOf(false) }
    var subscribersError by remember(subscriberUserKey) { mutableStateOf("") }
    var showRecentSubscribers by remember { mutableStateOf(false) }
    val hasNewSubscribers = !showRecentSubscribers && subscriberSeenAt > 0L &&
        subscribers.any { it.userId != subscriberUserKey &&
            it.registeredAtMs > subscriberSeenAt }

    LaunchedEffect(subscriberUserKey) {
        if (subscriberUserKey.isBlank()) return@LaunchedEffect
        while (true) {
            subscriberApi.list()
                .onSuccess { fresh ->
                    subscribers = fresh
                    subscribersLoaded = true
                    subscribersError = ""
                    // First install establishes the baseline; old members are
                    // not falsely marked as new.
                    if (subscriberSeenAt == 0L) {
                        val now = System.currentTimeMillis()
                        subscriberSeenAt = now
                        subscriberPrefs.edit()
                            .putLong("seen_" + subscriberUserKey, now).apply()
                    }
                }
                .onFailure {
                    subscribersError = "Yeni abone bilgileri güncellenemiyor."
                }
            kotlinx.coroutines.delay(12000L)
        }
    }
''',"subscriber-only state")

# Insert content in the existing title BoxWithConstraints. A visual offset
# DOES NOT participate in Compose layout measurement; the old header keeps
# the same measured width/height, and all home controls retain their places.
title_end='''                            modifier = Modifier.fillMaxWidth()
                        )
                    }'''
button='''                            modifier = Modifier.fillMaxWidth()
                        )
                        Box(
                            modifier = Modifier.align(Alignment.Center)
                                .offset(y = 54.dp)
                                .width(180.dp).height(30.dp)
                                .background(Color(0xFF6A4CAF), RoundedCornerShape(10.dp))
                                .clickable {
                                    showRecentSubscribers = true
                                    val now = System.currentTimeMillis()
                                    subscriberSeenAt = now
                                    if (subscriberUserKey.isNotBlank()) {
                                        subscriberPrefs.edit()
                                            .putLong("seen_" + subscriberUserKey, now).apply()
                                    }
                                },
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                "YENİ ABONELER",
                                color = Color.White,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                maxLines = 1
                            )
                            if (hasNewSubscribers) {
                                Box(
                                    Modifier.align(Alignment.TopEnd)
                                        .offset(x = 2.dp, y = (-2).dp)
                                        .size(11.dp)
                                        .background(Color(0xFF64C443), CircleShape)
                                )
                            }
                        }
                    }'''
one(title_end,button,"overlaid title button")

dialog_anchor='            if (showMembers) {'
dialog='''            if (showRecentSubscribers) {
                AlertDialog(
                    onDismissRequest = { showRecentSubscribers = false },
                    title = { Text("YENİ ABONELER") },
                    text = {
                        Column {
                            if (subscribersError.isNotBlank()) {
                                Text(subscribersError, color = Color(0xFFB00020),
                                    fontSize = 12.sp)
                            }
                            when {
                                !subscribersLoaded -> Text("Aboneler yükleniyor…")
                                subscribers.isEmpty() -> Text("Kayıtlı abone bulunamadı.")
                                else -> {
                                    Column(
                                        Modifier.heightIn(max = 410.dp)
                                            .verticalScroll(rememberScrollState())
                                    ) {
                                        subscribers.forEach { subscriber ->
                                            val online = subscriber.online &&
                                                subscribersError.isBlank()
                                            Row(
                                                modifier = Modifier.fillMaxWidth()
                                                    .padding(vertical = 7.dp),
                                                verticalAlignment = Alignment.CenterVertically
                                            ) {
                                                Box(
                                                    Modifier.size(11.dp)
                                                        .background(
                                                            if (online) Color(0xFF64B746)
                                                            else Color(0xFF9E9E9E),
                                                            CircleShape
                                                        )
                                                )
                                                Spacer(Modifier.width(10.dp))
                                                Column(modifier = Modifier.weight(1f)) {
                                                    Text(
                                                        subscriber.fullName,
                                                        fontWeight = FontWeight.SemiBold,
                                                        maxLines = 1,
                                                        overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                                                    )
                                                    val registered = if (subscriber.registeredAtMs > 0L)
                                                        java.text.SimpleDateFormat(
                                                            "dd.MM.yyyy HH:mm",
                                                            java.util.Locale("tr", "TR")
                                                        ).format(
                                                            java.util.Date(subscriber.registeredAtMs)
                                                        ) else ""
                                                    Text(
                                                        (if (online) "Çevrimiçi"
                                                        else "Çevrimdışı") +
                                                            (if (registered.isNotBlank())
                                                                " • Kayıt: " + registered
                                                             else ""),
                                                        fontSize = 12.sp,
                                                        color = Color.Gray,
                                                        maxLines = 1
                                                    )
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    confirmButton = {
                        TextButton(onClick = { showRecentSubscribers = false }) {
                            Text("KAPAT")
                        }
                    }
                )
            }
'''
one(dialog_anchor,dialog+dialog_anchor,"isolated subscriber dialog")

for marker in (
    'Text("KANALA GİR")','Text("KANALI SİL", color = Color(0xFFB00020))',
    'onPtt(true)', 'onPtt(false)','activeP2pRoomActivity',
    'P2pVideoCallActivity','MELEHAT_UPDATE_MANIFEST',
    'LastRoomPreference','roomApi.listRequests',
    'application/vnd.android.package-archive',
    'val radioOnline = radioOn &&',
):
    assert marker in s, "Protected system missing: "+marker
assert 'applicationId = "com.melehat.telsiz"' in Path("app/build.gradle.kts").read_text()
ui.write_text(s,encoding="utf-8")
print("MELEHAT_1377_RECENT_SUBSCRIBERS_OVERLAY_ONLINE_UNREAD_READY")
