package com.saomi.telsiz.rooms

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject

/**
 * Staged adapter. Uses the same Supabase project and logged-in MELEHAT JWT.
 * Access to preferences is limited by RLS to the current user and approved rooms.
 * No new signing key, package name, or separate communications backend.
 */
class SupabaseChannelFollowStore(
    private val client: OkHttpClient,
    private val baseUrl: String,
    private val publishableKey: String,
    private val userId: String,
    private val currentAccessToken: () -> String
) : RoomFollowStore {
    private val endpoint
        get() = baseUrl.trimEnd('/') + "/rest/v1/melehat_channel_follow_preferences"

    override suspend fun loadActiveChannels(): Set<String> = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url("$endpoint?select=channel_id,keep_active&keep_active=eq.true")
            .header("apikey", publishableKey)
            .header("Authorization", "Bearer ${currentAccessToken()}")
            .get().build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) error("Channel follow settings unavailable: HTTP ${response.code}")
            val array = JSONArray(response.body?.string().orEmpty())
            buildSet {
                for (i in 0 until array.length()) {
                    val room = array.getJSONObject(i).optString("channel_id")
                    if (room.isNotBlank() && room != "ortak") add(room)
                }
            }
        }
    }

    override suspend fun save(roomId: String, enabled: Boolean): Boolean =
        withContext(Dispatchers.IO) {
            if (roomId.isBlank() || roomId == "ortak") return@withContext false
            val payload = JSONObject()
                .put("user_id", userId)
                .put("channel_id", roomId)
                .put("keep_active", enabled)
                .toString()
            val request = Request.Builder()
                .url("$endpoint?on_conflict=user_id,channel_id")
                .header("apikey", publishableKey)
                .header("Authorization", "Bearer ${currentAccessToken()}")
                .header("Prefer", "resolution=merge-duplicates,return=minimal")
                .post(payload.toRequestBody("application/json".toMediaType()))
                .build()
            runCatching {
                client.newCall(request).execute().use { it.isSuccessful }
            }.getOrDefault(false)
        }
}
