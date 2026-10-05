from pathlib import Path
import re
p=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=p.read_text()
s=s.replace("import com.saomi.telsiz.data.SessionStore","import com.saomi.telsiz.data.SessionStore\nimport com.saomi.telsiz.data.MemberStatusApi\nimport com.saomi.telsiz.data.MemberStatus")
s=s.replace("    val backend = remember { BackendApi(context) }","    val backend = remember { BackendApi(context) }\n    val memberApi = remember { MemberStatusApi() }\n    var members by remember { mutableStateOf<List<MemberStatus>>(emptyList()) }\n    var showMembers by remember { mutableStateOf(false) }")
anchor="    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->"
heartbeat="""    LaunchedEffect(session?.userId) {
        val current = session ?: return@LaunchedEffect
        while (true) {
            memberApi.heartbeat(current)
            members = memberApi.members(current)
            delay(30000)
        }
    }

"""
s=s.replace(anchor,heartbeat+anchor)
old='''                var showC54Members by remember { mutableStateOf(false) }
                TextButton(onClick = { showC54Members = true }) { Text("ÜYELER: 4") }
                if (showC54Members) {
                    AlertDialog(
                        onDismissRequest = { showC54Members = false },
                        title = { Text("MELEHAT ÜYELERİ • 4") },
                        text = { Text("● Yeşil: aktif   ● Gri: çevrimdışı\\nAktiflik bağlantısı hazırlanıyor.") },
                        confirmButton = { TextButton(onClick = { showC54Members = false }) { Text("KAPAT") } }
                    )
                }
                Text("C54 • PTT + Otomatik Güncelleme", style = MaterialTheme.typography.bodySmall)'''
new='''                    TextButton(onClick = { showMembers = true }) { Text("ÜYELER: " + members.size) }
                    if (showMembers) {
                        AlertDialog(
                            onDismissRequest = { showMembers = false },
                            title = { Text("MELEHAT ÜYELERİ • " + members.size) },
                            text = {
                                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                    members.forEach { m ->
                                        Row(verticalAlignment = Alignment.CenterVertically) {
                                            Text("●", color = if (m.online) Color(0xFF34C759) else Color.Gray)
                                            Spacer(Modifier.width(8.dp))
                                            Text(m.name.ifBlank { "Üye" })
                                            Spacer(Modifier.weight(1f))
                                            Text(if (m.online) "Aktif" else "Çevrimdışı", style = MaterialTheme.typography.bodySmall)
                                        }
                                    }
                                    if (members.isEmpty()) Text("Üyeler yükleniyor…")
                                }
                            },
                            confirmButton = { TextButton(onClick = { showMembers = false }) { Text("KAPAT") } }
                        )
                    }
                    Text("C55 • PTT + Otomatik Güncelleme", style = MaterialTheme.typography.bodySmall)'''
if old not in s: raise SystemExit("C54 topbar block not found")
s=s.replace(old,new)
s=s.replace("                if (radioOn && !transmitting) {\n                    Canvas(Modifier.fillMaxSize()) {","                if (false) {\n                    Canvas(Modifier.fillMaxSize()) {")
s=s.replace("MELEHAT TELSİZ C54","MELEHAT TELSİZ C55")
p.write_text(s)

m=Path("app/src/main/java/com/saomi/telsiz/data/MemberStatusApi.kt")
m.write_text('''package com.saomi.telsiz.data

import com.saomi.telsiz.BuildConfig
import com.saomi.telsiz.auth.AuthSession
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray

data class MemberStatus(val id:String,val name:String,val avatarUrl:String?,val online:Boolean)

class MemberStatusApi {
    private val http=OkHttpClient()
    private val json="application/json".toMediaType()
    private fun rpc(session:AuthSession,name:String)=Request.Builder()
        .url(BuildConfig.SUPABASE_URL.trimEnd('/')+"/rest/v1/rpc/"+name)
        .addHeader("apikey",BuildConfig.SUPABASE_PUBLISHABLE_KEY)
        .addHeader("Authorization","Bearer "+session.accessToken)
        .addHeader("Content-Type","application/json")
    suspend fun heartbeat(session:AuthSession)=withContext(Dispatchers.IO) {
        runCatching { http.newCall(rpc(session,"melehat_heartbeat").post("{}".toRequestBody(json)).build()).execute().close() }
    }
    suspend fun members(session:AuthSession):List<MemberStatus> = withContext(Dispatchers.IO) {
        runCatching {
            http.newCall(rpc(session,"get_melehat_members").post("{}".toRequestBody(json)).build()).execute().use { r ->
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
t=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz.c55"',t,count=1)
t=re.sub(r'versionCode\s*=\s*\d+','versionCode = 55',t,count=1)
t=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "C55"',t,count=1)
b.write_text(t)
print("C55 direct clean-source patch applied")
