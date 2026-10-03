from pathlib import Path
import re

p=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=p.read_text()

imports = [
"import android.content.Intent",
"import android.net.Uri",
"import androidx.compose.material3.AlertDialog",
"import androidx.compose.material3.TextButton",
"import androidx.compose.runtime.LaunchedEffect",
"import androidx.compose.ui.platform.LocalContext",
"import kotlinx.coroutines.Dispatchers",
"import kotlinx.coroutines.withContext",
"import okhttp3.OkHttpClient",
"import okhttp3.Request",
"import org.json.JSONObject",
]
for line in imports:
    if line not in s:
        pos=s.find("\\n", s.find("package "))
        s=s[:pos+1]+line+"\\n"+s[pos+1:]

marker='Text("v0.26 • Temiz PTT + Oturum Yenileme"'
if marker not in s:
    raise SystemExit("v0.26 version marker not found")
s=s.replace(marker, 'UpdateChecker()\\n                Text("v0.27 • PTT + Otomatik Güncelleme"', 1)

s += r'''

@Composable
private fun UpdateChecker() {
    val context = LocalContext.current
    var updateUrl by remember { mutableStateOf<String?>(null) }
    var updateVersion by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        val info = withContext(Dispatchers.IO) {
            runCatching {
                val request = Request.Builder()
                    .url("https://ecbzcexhpzntgrfpizxc.supabase.co/storage/v1/object/public/app-updates/melehat/latest.json")
                    .build()
                OkHttpClient().newCall(request).execute().use { response ->
                    if (!response.isSuccessful) return@use null
                    val obj = JSONObject(response.body?.string().orEmpty())
                    val code = obj.optInt("versionCode", 0)
                    val version = obj.optString("versionName")
                    val apk = obj.optString("apkUrl")
                    if (code > 27 && apk.startsWith("https://")) version to apk else null
                }
            }.getOrNull()
        }
        if (info != null) {
            updateVersion = info.first
            updateUrl = info.second
        }
    }

    if (updateUrl != null) {
        AlertDialog(
            onDismissRequest = { updateUrl = null },
            title = { Text("MELEHAT TELSİZ güncellemesi") },
            text = { Text("Yeni sürüm $updateVersion hazır. İndirip güncellemek ister misiniz?") },
            confirmButton = {
                TextButton(onClick = {
                    updateUrl?.let { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(it))) }
                }) { Text("GÜNCELLE") }
            },
            dismissButton = {
                TextButton(onClick = { updateUrl = null }) { Text("SONRA") }
            }
        )
    }
}
'''

p.write_text(s)

b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\\s*=\\s*"[^"]+"', 'applicationId = "com.melehat.telsiz.v27"', t)
t=re.sub(r'versionCode\\s*=\\s*\\d+', 'versionCode = 27', t)
t=re.sub(r'versionName\\s*=\\s*"[^"]+"', 'versionName = "0.27.0"', t)
b.write_text(t)
print("v0.27 updater applied")
