from pathlib import Path
import re

p=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=p.read_text()

for imp in ["import okhttp3.MediaType.Companion.toMediaType","import okhttp3.RequestBody.Companion.toRequestBody","import org.json.JSONArray","import com.saomi.telsiz.auth.AuthSession","import com.saomi.telsiz.BuildConfig"]:
    if imp not in s:
        pos=s.find("\n",s.find("package "))
        s=s[:pos+1]+imp+"\n"+s[pos+1:]

s=s.replace('Text("ÜYELER", fontWeight = FontWeight.Bold, color = Color(0xFF6B4FB3))','RealMembersPanel(session)')
s=s.replace("V29 • v0.27 SES/PTT • CANLI ÜYELER","V30 • v0.27 SES/PTT • CANLI ÜYELER")
s=s.replace("MELEHAT TELSİZ V29","MELEHAT TELSİZ V30")

s += r"""
private data class UiMember(val name:String,val online:Boolean)

@Composable
private fun RealMembersPanel(session: AuthSession?) {
    var open by remember { mutableStateOf(false) }
    var members by remember { mutableStateOf<List<UiMember>>(emptyList()) }
    val client = remember { OkHttpClient() }

    LaunchedEffect(session?.userId) {
        val active = session ?: return@LaunchedEffect
        while (true) {
            withContext(Dispatchers.IO) {
                runCatching {
                    val base = BuildConfig.SUPABASE_URL.trimEnd('/') + "/rest/v1/rpc/"
                    val body = "{}".toRequestBody("application/json".toMediaType())
                    fun req(name:String)=Request.Builder().url(base+name)
                        .addHeader("apikey",BuildConfig.SUPABASE_PUBLISHABLE_KEY)
                        .addHeader("Authorization","Bearer "+active.accessToken)
                        .addHeader("Content-Type","application/json").post(body).build()
                    client.newCall(req("melehat_heartbeat")).execute().close()
                    client.newCall(req("get_melehat_members")).execute().use { r ->
                        if(r.isSuccessful) {
                            val a=JSONArray(r.body?.string().orEmpty())
                            members=(0 until a.length()).map { i ->
                                val o=a.getJSONObject(i)
                                UiMember(o.optString("display_name","Üye"),o.optBoolean("online",false))
                            }
                        }
                    }
                }
            }
            delay(15000)
        }
    }

    TextButton(onClick={open=true}) { Text("ÜYELER: ${members.size}",fontWeight=FontWeight.Bold) }
    if(open) AlertDialog(
        onDismissRequest={open=false},
        title={Text("MELEHAT ÜYELERİ • ${members.size}")},
        text={Column(verticalArrangement=Arrangement.spacedBy(10.dp)) {
            if(members.isEmpty()) Text("Üye listesi yükleniyor…")
            members.forEach { m -> Row(verticalAlignment=Alignment.CenterVertically) {
                Text("●",color=if(m.online) Color(0xFF24B34B) else Color.Gray)
                Spacer(Modifier.width(8.dp))
                Column { Text(m.name,fontWeight=FontWeight.SemiBold); Text(if(m.online) "Aktif" else "Çevrimdışı") }
            }}
        }},
        confirmButton={TextButton(onClick={open=false}){Text("KAPAT")}}
    )
}
"""
p.write_text(s)
b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz.v30"',t,count=1)
t=re.sub(r'versionCode\s*=\s*\d+','versionCode = 3001',t,count=1)
t=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "30.1"',t,count=1)
b.write_text(t)
assert "RealMembersPanel(session)" in s and "get_melehat_members" in s and "melehat_heartbeat" in s
print("V30_REAL_MEMBERS_READY")
