from pathlib import Path
import re

p=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=p.read_text()

# Keep the existing v0.27 audio/PTT/LiveKit screen; only add a visible updater card.
imports=[
"import android.content.Intent",
"import android.net.Uri",
"import androidx.compose.ui.graphics.Color",
"import androidx.compose.ui.platform.LocalContext",
"import kotlinx.coroutines.Dispatchers",
"import kotlinx.coroutines.withContext",
"import okhttp3.OkHttpClient",
"import okhttp3.Request",
"import org.json.JSONObject",
]
for line in imports:
    if line not in s:
        pos=s.find("\n",s.find("package "))
        s=s[:pos+1]+line+"\n"+s[pos+1:]

# Add updater state beside existing live state.
needle='var showMembers by remember { mutableStateOf(false) }'
if needle in s and 'updateAvailable by remember' not in s:
    s=s.replace(needle, needle+'''
    var updateAvailable by remember { mutableStateOf(false) }
    var updateVersion by remember { mutableStateOf("") }
    var updateUrl by remember { mutableStateOf("") }
    val updateContext = LocalContext.current''',1)

# Check GitHub-hosted update manifest without touching radio/audio.
# Insert check directly beside updater state; never silently skip it.
# This is a UI-only change and does not touch members, audio or LiveKit.
if 'MELEHAT_UPDATE_MANIFEST' not in s:
    anchor='    val updateContext = LocalContext.current'
    if anchor not in s:
        raise SystemExit("Updater state anchor missing; refusing incomplete APK")
    updater='''

    // MELEHAT_UPDATE_MANIFEST
    LaunchedEffect(Unit) {
        val info = withContext(Dispatchers.IO) {
            runCatching {
                val req = Request.Builder()
                    .url("https://raw.githubusercontent.com/orhankeskiner5561-cell/SAOMI-FOTO-AI-RESTORE/main/melehat-update.json")
                    .header("Cache-Control", "no-cache")
                    .build()
                OkHttpClient().newCall(req).execute().use { r ->
                    if (!r.isSuccessful) return@use null
                    val o = JSONObject(r.body?.string().orEmpty())
                    val code = o.optInt("versionCode", 0)
                    val name = o.optString("versionName", "")
                    val url = o.optString("apkUrl", "")
                    if (code > 127 && url.startsWith("https://")) Pair(name, url) else null
                }
            }.getOrNull()
        }
        if (info != null) {
            updateVersion = info.first
            updateUrl = info.second
            updateAvailable = true
        }
    }
'''
    s=s.replace(anchor,anchor+updater,1)
if 'MELEHAT_UPDATE_MANIFEST' not in s:
    raise SystemExit("Update checker missing")

# Put updater card directly above member button.
member='''            Button(
                onClick = { showMembers = true },
                modifier = Modifier.fillMaxWidth()
            ) {'''
if member not in s:
    raise SystemExit("member button anchor missing")
if 'YENİ GÜNCELLEME VAR' not in s:
    card='''            Surface(
                Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(14.dp),
                color = if (updateAvailable) Color(0xFFFFE5E5) else Color(0xFFE8F5E9)
            ) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (updateAvailable) {
                        Text("🔴 YENİ GÜNCELLEME VAR", fontWeight = FontWeight.Bold, color = Color(0xFFB00020))
                        Text("MELEHAT TELSİZ " + updateVersion)
                        Button(onClick = {
                            updateContext.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(updateUrl)))
                        }) { Text("GÜNCELLE") }
                    } else {
                        Text("🟢 UYGULAMA GÜNCEL", fontWeight = FontWeight.Bold)
                        Text("MELEHAT TELSİZ v1.2.7")
                    }
                }
            }

'''
    s=s.replace(member,card+member,1)
p.write_text(s)

# Keep permanent identity; updater bootstrap is 1.2.2.
g=Path("app/build.gradle.kts")
w=g.read_text()
w=re.sub(r'versionCode\s*=\s*\d+','versionCode = 127',w,count=1)
w=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "1.2.7"',w,count=1)
if 'applicationId = "com.melehat.telsiz"' not in w:
    raise SystemExit("permanent applicationId changed")
g.write_text(w)
print("IN_APP_UPDATE_UI_127_OK")
