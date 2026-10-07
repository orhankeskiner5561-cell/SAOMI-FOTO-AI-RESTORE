from pathlib import Path
import re

# V28: v0.27 is the transport baseline. Do NOT apply C58-C63 transport rewrites.
# Add only live member presence on top of v0.27-compatible audio/PTT.

api=Path("app/src/main/java/com/saomi/telsiz/net/MemberStatusApi.kt")
api.parent.mkdir(parents=True, exist_ok=True)
api.write_text(r'''package com.saomi.telsiz.net

import com.saomi.telsiz.auth.AuthSession
import com.saomi.telsiz.auth.SessionRefresher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

data class MelehatMember(
    val id: String,
    val name: String,
    val avatarUrl: String?,
    val online: Boolean
)

class MemberStatusApi(private val refresher: SessionRefresher) {
    private val base = "https://ecbzcexhpzntgrfpizxc.supabase.co/rest/v1/rpc/"

    suspend fun heartbeat(session: AuthSession): Boolean = withContext(Dispatchers.IO) {
        val active = refresher.refresh(session) ?: session
        rpc("melehat_heartbeat", active.accessToken, "{}") != null
    }

    suspend fun members(session: AuthSession): List<MelehatMember> = withContext(Dispatchers.IO) {
        val active = refresher.refresh(session) ?: session
        val raw = rpc("get_melehat_members", active.accessToken, "{}") ?: return@withContext emptyList()
        val a = JSONArray(raw)
        buildList {
            for (i in 0 until a.length()) {
                val o = a.getJSONObject(i)
                add(MelehatMember(
                    o.optString("user_id"),
                    o.optString("display_name", "Üye"),
                    o.optString("avatar_url").takeIf { it.isNotBlank() && it != "null" },
                    o.optBoolean("online", false)
                ))
            }
        }
    }

    private fun rpc(fn: String, token: String, body: String): String? {
        val c = (URL(base + fn).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 7000
            readTimeout = 7000
            doOutput = true
            setRequestProperty("apikey", BuildConfig.SUPABASE_ANON_KEY)
            setRequestProperty("Authorization", "Bearer $token")
            setRequestProperty("Content-Type", "application/json")
        }
        c.outputStream.use { it.write(body.toByteArray()) }
        return if (c.responseCode in 200..299) c.inputStream.bufferedReader().use { it.readText() } else null
    }
}
''')

# Presence/UI: reuse the proven C53+C54 UI only, but remove C53's incompatible net client.
for patch_name in ["../c53_members_presence_patch.py","../c54_visible_members_patch.py"]:
    q=Path(patch_name)
    if q.exists():
        exec(q.read_text(), {"__name__":"__main__"})

# C53 net client is not compatible with the v0.27 SessionRefresher API.
# It is not needed for preserving v0.27 audio/PTT; remove it for this clean baseline build.
bad=Path("app/src/main/java/com/saomi/telsiz/net/MemberStatusApi.kt")
if bad.exists():
    bad.unlink()

ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
u=ui.read_text().replace("C54 • PTT + Otomatik Güncelleme","V28 • v0.27 Ses Altyapısı").replace("MELEHAT TELSİZ C54","MELEHAT TELSİZ V28")
ui.write_text(u)

b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz.v28"',t,count=1)
t=re.sub(r'versionCode\s*=\s*\d+','versionCode = 28',t,count=1)
t=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "0.28"',t,count=1)
b.write_text(t)
print("V28 pure v0.27 audio/PTT baseline prepared")
