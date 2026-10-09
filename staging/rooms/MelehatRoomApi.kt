package com.saomi.telsiz.rooms

import com.saomi.telsiz.BuildConfig
import com.saomi.telsiz.auth.AuthSession
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject

data class RoomListing(val roomId: String, val title: String,
    val ownerId: String, val member: Boolean)
data class RoomRequest(val id: String, val roomId: String,
    val requesterId: String, val status: String)

/** Staged: authenticated Supabase room operations; PTT remains unchanged. */
class MelehatRoomApi {
    private val http = OkHttpClient()
    private val root = BuildConfig.SUPABASE_URL.trimEnd('/')
    private val publishable = BuildConfig.SUPABASE_PUBLISHABLE_KEY
    private val jsonType = "application/json; charset=utf-8".toMediaTypeOrNull()

    private fun auth(path: String, session: AuthSession): Request.Builder =
        Request.Builder().url(root + path)
            .header("apikey", publishable)
            .header("Authorization", "Bearer " + session.accessToken)

    private fun array(path: String, session: AuthSession): JSONArray {
        http.newCall(auth(path, session).get().build()).execute().use { response ->
            if (!response.isSuccessful) error("Sunucu sorgusu: " + response.code)
            return JSONArray(response.body?.string().orEmpty())
        }
    }

    private fun rpc(name: String, session: AuthSession, data: JSONObject): String {
        val request = auth("/rest/v1/rpc/" + name, session)
            .header("Content-Type", "application/json")
            .post(data.toString().toRequestBody(jsonType)).build()
        http.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val message = runCatching { JSONObject(body).optString("message") }.getOrDefault("")
                error(message.ifBlank { "Sunucu işlemi: " + response.code })
            }
            return body.trim('"', ' ', '\n', '\r')
        }
    }

    suspend fun listRooms(session: AuthSession): Result<List<RoomListing>> =
        withContext(Dispatchers.IO) {
            runCatching {
                val settings = array(
                    "/rest/v1/melehat_channel_settings?select=channel_id,owner_id,listed&listed=eq.true",
                    session
                )
                val channels = array("/rest/v1/channels?select=id,name", session)
                val myMembers = array(
                    "/rest/v1/channel_members?select=channel_id&user_id=eq." + session.userId,
                    session
                )
                val names = buildMap<String, String> {
                    for (i in 0 until channels.length()) {
                        val o = channels.getJSONObject(i)
                        put(o.optString("id"), o.optString("name"))
                    }
                }
                val membership = buildSet<String> {
                    for (i in 0 until myMembers.length()) {
                        add(myMembers.getJSONObject(i).optString("channel_id"))
                    }
                }
                buildList {
                    for (i in 0 until settings.length()) {
                        val o = settings.getJSONObject(i)
                        val room = o.optString("channel_id")
                        add(RoomListing(room, names[room] ?: room,
                            o.optString("owner_id"), room in membership))
                    }
                }
            }
        }

    suspend fun listRequests(session: AuthSession): Result<List<RoomRequest>> =
        withContext(Dispatchers.IO) {
            runCatching {
                val arr = array(
                    "/rest/v1/melehat_channel_join_requests?select=id,channel_id,requester_id,status&order=created_at.desc",
                    session
                )
                buildList {
                    for (i in 0 until arr.length()) {
                        val o = arr.getJSONObject(i)
                        add(RoomRequest(o.optString("id"), o.optString("channel_id"),
                            o.optString("requester_id"), o.optString("status")))
                    }
                }
            }
        }

    suspend fun createRoom(session: AuthSession, name: String): Result<String> =
        withContext(Dispatchers.IO) {
            runCatching {
                rpc("melehat_create_channel", session,
                    JSONObject().put("p_name", name).put("p_listed", true))
            }
        }

    suspend fun requestJoin(session: AuthSession, room: String): Result<String> =
        withContext(Dispatchers.IO) {
            runCatching {
                rpc("melehat_request_join", session, JSONObject().put("p_channel_id", room))
            }
        }

    suspend fun reviewRequest(
        session: AuthSession, requestId: String, approve: Boolean
    ): Result<String> = withContext(Dispatchers.IO) {
        runCatching {
            rpc("melehat_review_join", session, JSONObject()
                .put("p_request_id", requestId).put("p_approve", approve))
        }
    }
}
