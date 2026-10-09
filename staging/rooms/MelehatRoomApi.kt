package com.saomi.telsiz.rooms

import android.content.Context
import com.saomi.telsiz.BuildConfig
import com.saomi.telsiz.auth.SessionRefresher
import com.saomi.telsiz.data.SessionStore
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
class MelehatRoomApi(context: Context) {
    private val sessionStore = SessionStore(context.applicationContext)
    private val sessionRefresher = SessionRefresher(context.applicationContext)
    private val http = OkHttpClient()
    private val root = BuildConfig.SUPABASE_URL.trimEnd('/')
    private val publishable = BuildConfig.SUPABASE_PUBLISHABLE_KEY
    private val jsonType = "application/json; charset=utf-8".toMediaTypeOrNull()

    private fun auth(path: String, session: AuthSession): Request.Builder =
        Request.Builder().url(root + path)
            .header("apikey", publishable)
            .header("Authorization", "Bearer " + session.accessToken)

    // Always prefer the latest stored JWT. An old Compose session snapshot must
    // not break room listings or owner approvals after an access-token refresh.
    private suspend fun executeWithRefresh(
        session: AuthSession,
        build: (AuthSession) -> Request
    ): String {
        var active = sessionStore.load()?.takeIf { it.userId == session.userId } ?: session
        for (attempt in 0..1) {
            val request = build(active)
            val (status, body) = http.newCall(request).execute().use { response ->
                response.code to response.body?.string().orEmpty()
            }
            if (status == 401 && attempt == 0) {
                active = sessionRefresher.refresh()
                    ?: error("Oturum yenilenemedi. Lütfen tekrar giriş yapın.")
                if (active.userId != session.userId) error("Oturum kimliği değişti.")
                continue
            }
            if (status !in 200..299) {
                val serverError = runCatching {
                    JSONObject(body).optString("message").ifBlank {
                        JSONObject(body).optString("msg")
                    }
                }.getOrDefault("")
                error(serverError.ifBlank { "Sunucu sorgusu: $status" })
            }
            return body
        }
        error("Oturum doğrulanamadı.")
    }

    private suspend fun array(path: String, session: AuthSession): JSONArray {
        val raw = executeWithRefresh(session) { fresh ->
            auth(path, fresh).get().build()
        }
        return JSONArray(raw)
    }

    private suspend fun rpc(name: String, session: AuthSession, data: JSONObject): String {
        val raw = executeWithRefresh(session) { fresh ->
            auth("/rest/v1/rpc/" + name, fresh)
                .header("Content-Type", "application/json")
                .post(data.toString().toRequestBody(jsonType))
                .build()
        }
        return raw.trim('"', ' ', '\n', '\r')
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

    suspend fun listRoomMemberIds(session: AuthSession, roomId: String): Result<Set<String>> =
        withContext(Dispatchers.IO) {
            runCatching {
                require(roomId.matches(Regex("kanal-[a-z0-9-]{1,64}"))) {
                    "Geçersiz oda kimliği"
                }
                val arr = array(
                    "/rest/v1/channel_members?select=user_id&channel_id=eq." + roomId,
                    session
                )
                buildSet {
                    for (i in 0 until arr.length()) {
                        add(arr.getJSONObject(i).getString("user_id"))
                    }
                }
            }
        }

    suspend fun deleteRoom(session: AuthSession, roomId: String): Result<String> =
        withContext(Dispatchers.IO) {
            runCatching {
                require(roomId != "ortak" && roomId.matches(Regex("kanal-[a-z0-9-]{1,64}")))
                val answer = rpc("melehat_delete_channel", session,
                    JSONObject().put("p_channel_id", roomId))
                if (answer != "true") error("Kanal silme onaylanmadı.")
                answer
            }
        }

    suspend fun importLegacyMembers(session: AuthSession, targetRoomId: String): Result<String> =
        withContext(Dispatchers.IO) {
            runCatching {
                require(targetRoomId != "kanal-1" &&
                    targetRoomId.matches(Regex("kanal-[a-z0-9-]{1,64}")))
                val total = rpc("melehat_import_legacy_members", session,
                    JSONObject().put("p_target_channel_id", targetRoomId))
                "Özel kanalda " + total.toInt() + " onaylı üye var."
            }
        }
}
