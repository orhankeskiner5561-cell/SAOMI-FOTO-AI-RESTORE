from pathlib import Path
import re

# C53 foundation: member count/presence endpoint client + clean version identity.
p=Path("app/src/main/java/com/saomi/telsiz/data/MemberStatusApi.kt")
p.parent.mkdir(parents=True,exist_ok=True)
p.write_text(r'''package com.saomi.telsiz.data

import com.saomi.telsiz.BuildConfig
import com.saomi.telsiz.auth.AuthSession
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray

data class MemberStatus(val id:String,val name:String,val avatarUrl:String?,val online:Boolean)

class MemberStatusApi {
    private val http=OkHttpClient()
    suspend fun members(session:AuthSession):List<MemberStatus> = withContext(Dispatchers.IO) {
        val req=Request.Builder()
            .url(BuildConfig.SUPABASE_URL.trimEnd('/')+"/rest/v1/melehat_member_status?select=user_id,display_name,avatar_url,online&order=display_name.asc")
            .addHeader("apikey",BuildConfig.SUPABASE_PUBLISHABLE_KEY)
            .addHeader("Authorization","Bearer "+session.accessToken).build()
        runCatching {
            http.newCall(req).execute().use { r ->
                if(!r.isSuccessful) return@use emptyList()
                val a=JSONArray(r.body?.string().orEmpty())
                (0 until a.length()).map { i -> a.getJSONObject(i).let { o ->
                    MemberStatus(o.optString("user_id"),o.optString("display_name"),o.optString("avatar_url").takeIf{it.isNotBlank()},o.optBoolean("online"))
                }}
            }
        }.getOrDefault(emptyList())
    }
}
''')

b=Path("app/build.gradle.kts"); t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz.c53"',t,count=1)
t=re.sub(r'versionCode\s*=\s*\d+','versionCode = 53',t,count=1)
t=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "C53"',t,count=1)
b.write_text(t)

ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=ui.read_text().replace("C50","C53").replace("C51","C53").replace("C52","C53")
ui.write_text(s)
print("C53 member/presence client foundation + version identity")
