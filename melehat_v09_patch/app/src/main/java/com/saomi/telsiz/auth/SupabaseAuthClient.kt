package com.saomi.telsiz.auth

import com.saomi.telsiz.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

class SupabaseAuthClient {
    private val http = OkHttpClient()
    private val json = "application/json; charset=utf-8".toMediaType()

    private fun base() = BuildConfig.SUPABASE_URL.trimEnd('/')
    private fun key() = BuildConfig.SUPABASE_PUBLISHABLE_KEY

    fun isConfigured(): Boolean = base().isNotBlank() && key().isNotBlank()

    suspend fun sendEmailOtp(email: String): Result<Unit> = withContext(Dispatchers.IO) {
        if (!isConfigured()) return@withContext Result.failure(IllegalStateException("Supabase bağlantısı henüz yapılandırılmadı."))
        val body = JSONObject().put("email", email.trim().lowercase()).put("create_user", true).toString().toRequestBody(json)
        val request = Request.Builder().url("${base()}/auth/v1/otp").addHeader("apikey", key()).addHeader("Authorization", "Bearer ${key()}").post(body).build()
        runCatching {
            http.newCall(request).execute().use { response ->
                val raw = response.body?.string().orEmpty()
                if (!response.isSuccessful) error("E-posta kodu gönderilemedi: ${response.code} ${raw.take(120)}")
            }
        }
    }

    suspend fun verifyEmailOtp(phone: String, email: String, code: String): Result<AuthSession> = withContext(Dispatchers.IO) {
        if (!isConfigured()) return@withContext Result.failure(IllegalStateException("Supabase bağlantısı henüz yapılandırılmadı."))
        val normalizedEmail = email.trim().lowercase()
        val body = JSONObject().put("email", normalizedEmail).put("token", code).put("type", "email").toString().toRequestBody(json)
        val request = Request.Builder().url("${base()}/auth/v1/verify").addHeader("apikey", key()).addHeader("Authorization", "Bearer ${key()}").post(body).build()
        runCatching {
            http.newCall(request).execute().use { response ->
                val raw = response.body?.string().orEmpty()
                if (!response.isSuccessful) error("Kod doğrulanamadı: ${response.code} ${raw.take(120)}")
                val o = JSONObject(raw); val user = o.optJSONObject("user")
                AuthSession(o.getString("access_token"), o.optString("refresh_token"), user?.optString("id").orEmpty(), phone.trim(), user?.optString("email").orEmpty().ifBlank { normalizedEmail })
            }
        }
    }
}