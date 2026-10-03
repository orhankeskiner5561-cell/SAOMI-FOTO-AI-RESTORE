from pathlib import Path
import re

# Clean automatic session refresh built directly on top of working v0.16 sources.
ref=Path('app/src/main/java/com/saomi/telsiz/auth/SessionRefresher.kt')
ref.parent.mkdir(parents=True, exist_ok=True)
ref.write_text(r'''package com.saomi.telsiz.auth

import android.content.Context
import com.saomi.telsiz.BuildConfig
import com.saomi.telsiz.data.SessionStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

class SessionRefresher(context: Context) {
    private val store = SessionStore(context.applicationContext)
    private val http = OkHttpClient()
    private val json = "application/json; charset=utf-8".toMediaTypeOrNull()

    suspend fun refresh(): AuthSession? = withContext(Dispatchers.IO) {
        val old = store.load() ?: return@withContext null
        if (old.refreshToken.isBlank()) return@withContext null

        val body = JSONObject()
            .put("refresh_token", old.refreshToken)
            .toString()
            .toRequestBody(json)

        val request = Request.Builder()
            .url(BuildConfig.SUPABASE_URL.trimEnd('/') + "/auth/v1/token?grant_type=refresh_token")
            .addHeader("apikey", BuildConfig.SUPABASE_PUBLISHABLE_KEY)
            .addHeader("Content-Type", "application/json")
            .post(body)
            .build()

        runCatching {
            http.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return@use null
                val obj = JSONObject(response.body?.string().orEmpty())
                val access = obj.optString("access_token")
                val refresh = obj.optString("refresh_token").ifBlank { old.refreshToken }
                val userId = obj.optJSONObject("user")?.optString("id").orEmpty().ifBlank { old.userId }
                if (access.isBlank() || userId.isBlank()) return@use null

                AuthSession(
                    accessToken = access,
                    refreshToken = refresh,
                    userId = userId,
                    phone = old.phone,
                    email = old.email
                ).also { store.save(it) }
            }
        }.getOrNull()
    }
}
''')

p=Path('app/src/main/java/com/saomi/telsiz/data/BackendApi.kt')
s=p.read_text()
if 'import com.saomi.telsiz.auth.SessionRefresher' not in s:
    s=s.replace('import com.saomi.telsiz.auth.AuthSession\n', 'import com.saomi.telsiz.auth.AuthSession\nimport com.saomi.telsiz.auth.SessionRefresher\n')
if 'private val refresher = SessionRefresher(context)' not in s:
    s=s.replace('private val http = OkHttpClient()\n', 'private val http = OkHttpClient()\n    private val refresher = SessionRefresher(context)\n')

start=s.index('    suspend fun acquireFloor(')
end=s.index('\n    suspend fun releaseFloor', start)
acquire=r'''    suspend fun acquireFloor(
        session: AuthSession,
        channelId: String,
        leaseSeconds: Int = 15
    ): Boolean = withContext(Dispatchers.IO) {
        fun attempt(active: AuthSession): Pair<Int, Boolean> {
            val body = JSONObject()
                .put("p_channel_id", channelId)
                .put("p_lease_seconds", leaseSeconds)
                .toString()
                .toRequestBody(json)

            val request = Request.Builder()
                .url(base() + "/rest/v1/rpc/acquire_channel_floor")
                .addHeader("apikey", key())
                .addHeader("Authorization", "Bearer " + active.accessToken)
                .addHeader("Content-Type", "application/json")
                .post(body)
                .build()

            return runCatching {
                http.newCall(request).execute().use { response ->
                    val ok = response.isSuccessful &&
                        response.body?.string()?.trim()?.equals("true", ignoreCase = true) == true
                    response.code to ok
                }
            }.getOrDefault(0 to false)
        }

        val first = attempt(session)
        if (first.first != 401) return@withContext first.second

        val fresh = refresher.refresh() ?: return@withContext false
        attempt(fresh).second
    }
'''
s=s[:start]+acquire+s[end:]

start=s.index('    suspend fun releaseFloor(')
end=s.rindex('\n}')
release=r'''    suspend fun releaseFloor(session: AuthSession, channelId: String) =
        withContext(Dispatchers.IO) {
            fun attempt(active: AuthSession): Int {
                val body = JSONObject()
                    .put("p_channel_id", channelId)
                    .toString()
                    .toRequestBody(json)

                val request = Request.Builder()
                    .url(base() + "/rest/v1/rpc/release_channel_floor")
                    .addHeader("apikey", key())
                    .addHeader("Authorization", "Bearer " + active.accessToken)
                    .addHeader("Content-Type", "application/json")
                    .post(body)
                    .build()

                return runCatching {
                    http.newCall(request).execute().use { it.code }
                }.getOrDefault(0)
            }

            if (attempt(session) == 401) {
                val fresh = refresher.refresh()
                if (fresh != null) attempt(fresh)
            }
        }
'''
s=s[:start]+release+s[end:]
p.write_text(s)

# v0.26 identity / visible text.
b=Path('app/build.gradle.kts')
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"', 'applicationId = "com.melehat.telsiz.v26"', t)
t=re.sub(r'versionCode\s*=\s*\d+', 'versionCode = 26', t)
t=re.sub(r'versionName\s*=\s*"[^"]+"', 'versionName = "0.26.0"', t)
b.write_text(t)

ui=Path('app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt')
u=ui.read_text()
u=re.sub(r'MELEHAT TELSİZ v0\.\d+(?:\.\d+)?', 'MELEHAT TELSİZ v0.26', u)
u=re.sub(r'v0\.\d+(?:\.\d+)?\s*•\s*[^"\n]*', 'v0.26 • Temiz PTT + Oturum Yenileme', u)
ui.write_text(u)

print('v0.26 clean auth refresh applied directly to v0.16')