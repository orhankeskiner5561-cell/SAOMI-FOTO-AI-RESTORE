from pathlib import Path

# v1.3.28 fixes JWT expiry for the member list only.
# The v0.27 PTT/LiveKit client and signing setup are untouched.
api = Path("app/src/main/java/com/saomi/telsiz/data/BackendApi.kt")
s = api.read_text()
start = s.find("    suspend fun fetchMemberDirectory(")
end = s.find("\n    suspend fun acquireFloor(", start)
if start < 0 or end < 0:
    raise SystemExit("Member API anchor missing; refusing incomplete build")
replacement = r'''    suspend fun fetchMemberDirectory(session: AuthSession): Result<List<MemberDirectoryProfile>> =
        withContext(Dispatchers.IO) {
            runCatching {
                fun fetch(active: AuthSession): Pair<Int, String> {
                    val request = Request.Builder()
                        .url("${base()}/rest/v1/profiles?select=user_id,full_name,photo_url&order=full_name.asc")
                        .addHeader("apikey", key())
                        .addHeader("Authorization", "Bearer ${active.accessToken}")
                        .get().build()
                    return http.newCall(request).execute().use { response ->
                        response.code to response.body?.string().orEmpty()
                    }
                }
                // BackendApi's Context constructor argument need not be a
                // stored class property; refresh only when the JWT expires.
                var result = fetch(session)
                if (result.first == 401) {
                    val renewed = refresher.refresh()
                        ?: error("Üye listesi oturumu yenilenemedi.")
                    if (renewed.userId != session.userId)
                        error("Oturum kimliği uyuşmuyor.")
                    result = fetch(renewed)
                }
                if (result.first !in 200..299)
                    error("Üyeler okunamadı: ${result.first}")
                val arr = JSONArray(result.second)
                buildList {
                    for (i in 0 until arr.length()) {
                        val o = arr.getJSONObject(i)
                        add(MemberDirectoryProfile(
                            o.optString("user_id"),
                            o.optString("full_name").ifBlank { "Üye" },
                            o.optString("photo_url")
                        ))
                    }
                }
            }
        }

'''
s = s[:start] + replacement + s[end:]
api.write_text(s)
print("MELEHAT_MEMBER_DIRECTORY_REFRESH_OK")
