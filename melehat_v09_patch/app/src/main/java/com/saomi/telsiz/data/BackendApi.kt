package com.saomi.telsiz.data

import android.content.Context
import android.net.Uri
import com.saomi.telsiz.BuildConfig
import com.saomi.telsiz.auth.AuthSession
import com.saomi.telsiz.model.ChannelInfo
import com.saomi.telsiz.model.UserProfile
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject

class BackendApi(private val context: Context) {
    private val http = OkHttpClient()
    private val json = "application/json; charset=utf-8".toMediaTypeOrNull()

    private fun base() = BuildConfig.SUPABASE_URL.trimEnd('/')
    private fun key() = BuildConfig.SUPABASE_PUBLISHABLE_KEY

    suspend fun uploadProfilePhoto(
        session: AuthSession,
        localUri: String
    ): Result<String> = withContext(Dispatchers.IO) {
        runCatching {
            val uri = Uri.parse(localUri)
            val mime = context.contentResolver.getType(uri) ?: "image/jpeg"
            val ext = when (mime) {
                "image/png" -> "png"
                "image/webp" -> "webp"
                else -> "jpg"
            }
            val objectPath = "${session.userId}/profile.$ext"
            val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
                ?: error("Profil fotoğrafı okunamadı")

            val request = Request.Builder()
                .url("${base()}/storage/v1/object/profile-photos/$objectPath")
                .addHeader("apikey", key())
                .addHeader("Authorization", "Bearer ${session.accessToken}")
                .addHeader("x-upsert", "true")
                .post(bytes.toRequestBody(mime.toMediaTypeOrNull()))
                .build()

            http.newCall(request).execute().use { r ->
                if (!r.isSuccessful) error("Profil fotoğrafı yüklenemedi: ${r.code}")
            }

            "${base()}/storage/v1/object/public/profile-photos/$objectPath"
        }
    }

    suspend fun upsertProfile(session: AuthSession, profile: UserProfile): Result<Unit> =
        withContext(Dispatchers.IO) {
            val payload = JSONArray().put(
                JSONObject()
                    .put("user_id", session.userId)
                    .put("phone", profile.phone)
                    .put("email", profile.email)
                    .put("full_name", profile.fullName)
                    .put("photo_url", profile.photoUri)
            ).toString().toRequestBody(json)

            val request = Request.Builder()
                .url("${base()}/rest/v1/profiles?on_conflict=user_id")
                .addHeader("apikey", key())
                .addHeader("Authorization", "Bearer ${session.accessToken}")
                .addHeader("Content-Type", "application/json")
                .addHeader("Prefer", "resolution=merge-duplicates,return=minimal")
                .post(payload)
                .build()

            runCatching {
                http.newCall(request).execute().use { r ->
                    if (!r.isSuccessful) error("Profil kaydedilemedi: ${r.code}")
                }
            }
        }

    suspend fun fetchMyProfile(session: AuthSession): Result<UserProfile?> =
        withContext(Dispatchers.IO) {
            runCatching {
                val request = Request.Builder()
                    .url("${base()}/rest/v1/profiles?user_id=eq.${session.userId}&select=phone,email,full_name,photo_url")
                    .addHeader("apikey", key())
                    .addHeader("Authorization", "Bearer ${session.accessToken}")
                    .get().build()
                http.newCall(request).execute().use { r ->
                    val raw = r.body?.string().orEmpty()
                    if (!r.isSuccessful) error("Profil okunamadı: ${r.code}")
                    val arr = JSONArray(raw)
                    if (arr.length() == 0) return@use null
                    val o = arr.getJSONObject(0)
                    UserProfile(o.optString("phone"),o.optString("email"),o.optString("full_name"),o.optString("photo_url"))
                }
            }
        }

    suspend fun joinChannel(session: AuthSession, channel: ChannelInfo): Result<Unit> =
        withContext(Dispatchers.IO) {
            runCatching {
                val channelPayload = JSONArray().put(
                    JSONObject()
                        .put("id", channel.id)
                        .put("name", channel.name)
                        .put("created_by", session.userId)
                ).toString().toRequestBody(json)

                val channelRequest = Request.Builder()
                    .url("${base()}/rest/v1/channels?on_conflict=id")
                    .addHeader("apikey", key())
                    .addHeader("Authorization", "Bearer ${session.accessToken}")
                    .addHeader("Content-Type", "application/json")
                    .addHeader("Prefer", "resolution=ignore-duplicates,return=minimal")
                    .post(channelPayload)
                    .build()

                http.newCall(channelRequest).execute().use { r ->
                    if (!r.isSuccessful) error("Kanal oluşturulamadı: ${r.code}")
                }

                val memberPayload = JSONArray().put(
                    JSONObject()
                        .put("channel_id", channel.id)
                        .put("channel_name", channel.name)
                        .put("user_id", session.userId)
                ).toString().toRequestBody(json)

                val memberRequest = Request.Builder()
                    .url("${base()}/rest/v1/channel_members?on_conflict=channel_id,user_id")
                    .addHeader("apikey", key())
                    .addHeader("Authorization", "Bearer ${session.accessToken}")
                    .addHeader("Content-Type", "application/json")
                    .addHeader("Prefer", "resolution=ignore-duplicates,return=minimal")
                    .post(memberPayload)
                    .build()

                http.newCall(memberRequest).execute().use { r ->
                    if (!r.isSuccessful) error("Kanala girilemedi: ${r.code}")
                }
            }
        }

    suspend fun acquireFloor(
        session: AuthSession,
        channelId: String,
        leaseSeconds: Int = 15
    ): Boolean = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("p_channel_id", channelId)
            .put("p_lease_seconds", leaseSeconds)
            .toString()
            .toRequestBody(json)

        val request = Request.Builder()
            .url("${base()}/rest/v1/rpc/acquire_channel_floor")
            .addHeader("apikey", key())
            .addHeader("Authorization", "Bearer ${session.accessToken}")
            .addHeader("Content-Type", "application/json")
            .post(body)
            .build()

        runCatching {
            http.newCall(request).execute().use { r ->
                if (!r.isSuccessful) return@use false
                r.body?.string()?.trim()?.equals("true", ignoreCase = true) == true
            }
        }.getOrDefault(false)
    }

    suspend fun releaseFloor(session: AuthSession, channelId: String) =
        withContext(Dispatchers.IO) {
            val body = JSONObject()
                .put("p_channel_id", channelId)
                .toString()
                .toRequestBody(json)

            val request = Request.Builder()
                .url("${base()}/rest/v1/rpc/release_channel_floor")
                .addHeader("apikey", key())
                .addHeader("Authorization", "Bearer ${session.accessToken}")
                .addHeader("Content-Type", "application/json")
                .post(body)
                .build()

            runCatching { http.newCall(request).execute().close() }
        }
}