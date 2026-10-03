from pathlib import Path
import re

ref=Path("app/src/main/java/com/saomi/telsiz/auth/SessionRefresher.kt")
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
    private val appContext = context.applicationContext
    private val store = SessionStore(appContext)
    private val http = OkHttpClient()
    private val json = "application/json; charset=utf-8".toMediaTypeOrNull()

    suspend fun refresh(): AuthSession? = withContext(Dispatchers.IO) {
        val old = store.load() ?: return@withContext null
        if (old.refreshToken.isBlank()) return@withContext null

        val payload = JSONObject()
            .put("refresh_token", old.refreshToken)
            .toString()
            .toRequestBody(json)

        val req = Request.Builder()
            .url(BuildConfig.SUPABASE_URL.trimEnd('/') + "/auth/v1/token?grant_type=refresh_token")
            .addHeader("apikey", BuildConfig.SUPABASE_PUBLISHABLE_KEY)
            .addHeader("Content-Type", "application/json")
            .post(payload)
            .build()

        runCatching {
            http.newCall(req).execute().use { r ->
                if (!r.isSuccessful) return@use null
                val o = JSONObject(r.body?.string().orEmpty())
                val access = o.optString("access_token")
                val refresh = o.optString("refresh_token", old.refreshToken)
                val user = o.optJSONObject("user")
                val userId = user?.optString("id").orEmpty().ifBlank { old.userId }
                if (access.isBlank() || userId.isBlank()) return@use null

                val fresh = AuthSession(
                    accessToken = access,
                    refreshToken = refresh,
                    userId = userId,
                    phone = old.phone,
                    email = old.email
                )
                store.save(fresh)
                fresh
            }
        }.getOrNull()
    }
}
''')

p=Path("app/src/main/java/com/saomi/telsiz/data/BackendApi.kt")
s=p.read_text()
if 'import com.saomi.telsiz.auth.SessionRefresher' not in s:
    s=s.replace('import com.saomi.telsiz.auth.AuthSession\n',
                'import com.saomi.telsiz.auth.AuthSession\nimport com.saomi.telsiz.auth.SessionRefresher\n')
if 'private val refresher = SessionRefresher(context)' not in s:
    s=s.replace('private val http = OkHttpClient()\n',
                'private val http = OkHttpClient()\n    private val refresher = SessionRefresher(context)\n')

start=s.index('    suspend fun acquireFloor(')
end=s.index('\n    suspend fun releaseFloor', start)
new_acquire=r'''    suspend fun acquireFloor(
        session: AuthSession,
        channelId: String,
        leaseSeconds: Int = 15
    ): Boolean = withContext(Dispatchers.IO) {
        suspend fun attempt(active: AuthSession): Pair<Int, Boolean> {
            val body = JSONObject()
                .put("p_channel_id", channelId)
                .put("p_lease_seconds", leaseSeconds)
                .toString()
                .toRequestBody(json)

            val request = Request.Builder()
                .url("\${base()}/rest/v1/rpc/acquire_channel_floor")
                .addHeader("apikey", key())
                .addHeader("Authorization", "Bearer \${active.accessToken}")
                .addHeader("Content-Type", "application/json")
                .post(body)
                .build()

            return runCatching {
                http.newCall(request).execute().use { r ->
                    val ok = r.isSuccessful &&
                        r.body?.string()?.trim()?.equals("true", ignoreCase = true) == true
                    r.code to ok
                }
            }.getOrDefault(0 to false)
        }

        val first = attempt(session)
        if (first.first != 401) return@withContext first.second

        val fresh = refresher.refresh() ?: return@withContext false
        attempt(fresh).second
    }
'''
s=s[:start]+new_acquire+s[end:]

start=s.index('    suspend fun releaseFloor(')
end=s.rindex('\n}')
new_release=r'''    suspend fun releaseFloor(session: AuthSession, channelId: String) =
        withContext(Dispatchers.IO) {
            suspend fun attempt(active: AuthSession): Int {
                val body = JSONObject()
                    .put("p_channel_id", channelId)
                    .toString()
                    .toRequestBody(json)

                val request = Request.Builder()
                    .url("\${base()}/rest/v1/rpc/release_channel_floor")
                    .addHeader("apikey", key())
                    .addHeader("Authorization", "Bearer \${active.accessToken}")
                    .addHeader("Content-Type", "application/json")
                    .post(body)
                    .build()

                return runCatching {
                    http.newCall(request).execute().use { it.code }
                }.getOrDefault(0)
            }

            val first = attempt(session)
            if (first == 401) {
                val fresh = refresher.refresh()
                if (fresh != null) attempt(fresh)
            }
        }
'''
s=s[:start]+new_release+s[end:]
p.write_text(s)

print("v0.23 automatic Supabase session refresh and 401 retry applied")
