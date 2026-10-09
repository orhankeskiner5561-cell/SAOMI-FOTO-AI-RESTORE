package com.saomi.telsiz.video

import android.content.Context
import com.saomi.telsiz.BuildConfig
import com.saomi.telsiz.auth.AuthSession
import com.saomi.telsiz.auth.SessionRefresher
import com.saomi.telsiz.data.SessionStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

data class MelehatVideoCall(
    val id: String, val callerId: String, val initialCalleeId: String,
    val state: String, val myState: String
)
data class MelehatVideoCredentials(val url: String, val token: String)

class VideoCallApi(context: Context) {
    private val sessions = SessionStore(context.applicationContext)
    private val refresh = SessionRefresher(context.applicationContext)
    private val client = OkHttpClient.Builder().callTimeout(8, TimeUnit.SECONDS).build()
    private val base = BuildConfig.SUPABASE_URL.trimEnd('/')
    private val jsonType = "application/json".toMediaType()

    private suspend fun post(path: String, data: JSONObject = JSONObject()): String =
        withContext(Dispatchers.IO) {
            var active: AuthSession = sessions.load() ?: error("MELEHAT oturumu bulunamadı")
            for (attempt in 0..1) {
                val request = Request.Builder()
                    .url(base + path)
                    .header("apikey", BuildConfig.SUPABASE_PUBLISHABLE_KEY)
                    .header("Authorization", "Bearer " + active.accessToken)
                    .post(data.toString().toRequestBody(jsonType))
                    .build()
                val response = client.newCall(request).execute().use {
                    it.code to it.body?.string().orEmpty()
                }
                if (response.first == 401 && attempt == 0) {
                    val updated = refresh.refresh() ?: error("Oturum süresi doldu")
                    if (updated.userId != active.userId) error("Oturum değişti")
                    active = updated
                    continue
                }
                if (response.first !in 200..299) {
                    val message = runCatching {
                        JSONObject(response.second).optString("message").ifBlank {
                            JSONObject(response.second).optString("error")
                        }
                    }.getOrDefault("")
                    error(message.ifBlank { "Arama sunucusu HTTP " + response.first })
                }
                return@withContext response.second
            }
            error("Oturum yenilenemedi")
        }

    private suspend fun rpc(name: String, data: JSONObject = JSONObject()): String =
        post("/rest/v1/rpc/" + name, data).trim().trim('"')

    suspend fun dial(userId: String): String {
        require(userId.matches(Regex("[a-f0-9-]{36}", RegexOption.IGNORE_CASE)))
        return rpc("melehat_video_start", JSONObject().put("p_target", userId))
    }
    suspend fun answer(callId: String, accept: Boolean): String =
        rpc("melehat_video_respond", JSONObject().put("p_call", callId).put("p_accept", accept))
    suspend fun end(callId: String): Boolean =
        rpc("melehat_video_end", JSONObject().put("p_call", callId)) == "true"
    suspend fun invite(callId: String, userId: String): Boolean =
        rpc("melehat_video_invite", JSONObject().put("p_call", callId).put("p_target", userId)) == "true"
    suspend fun poll(): List<MelehatVideoCall> {
        val list = JSONArray(rpc("melehat_video_poll"))
        return (0 until list.length()).map { i ->
            val c = list.getJSONObject(i)
            MelehatVideoCall(c.getString("call_id"), c.getString("caller_id"),
                c.getString("initial_callee_id"), c.getString("call_state"),
                c.getString("my_state"))
        }
    }
    suspend fun credentials(callId: String): MelehatVideoCredentials {
        val result = JSONObject(post("/functions/v1/melehat-video-token",
            JSONObject().put("callId", callId)))
        val url = result.optString("serverUrl")
        val token = result.optString("participantToken")
        if (url.isBlank() || token.isBlank()) error("Görüntülü arama yetkisi alınamadı")
        return MelehatVideoCredentials(url, token)
    }
}
