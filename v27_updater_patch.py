from pathlib import Path
import re

# Add updater UI and checker into the existing Compose root.
p=Path('app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt')
s=p.read_text()

# imports
imports='''
import android.content.Intent
import android.net.Uri
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.TextButton
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import com.saomi.telsiz.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
'''
for line in imports.strip().splitlines():
    if line not in s:
        idx=s.find('\n', s.find('package '))
        s=s[:idx+1]+line+'\n'+s[idx+1:]

# Inject state/check at first @Composable function body that is AppRoot-like.
m=re.search(r'(@Composable\s*\n\s*fun\s+\w+\s*\([^)]*\)\s*\{)', s)
if not m:
    raise SystemExit('No root composable found')

inject=r'''
    val updateUrl = remember { mutableStateOf<String?>(null) }
    val updateVersion = remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) {
        val info = withContext(Dispatchers.IO) {
            runCatching {
                val client = OkHttpClient()
                val request = Request.Builder()
                    .url("https://ecbzcexhpzntgrfpizxc.supabase.co/storage/v1/object/public/app-updates/melehat/latest.json")
                    .build()
                client.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) return@use null
                    val obj = JSONObject(response.body?.string().orEmpty())
                    val code = obj.optInt("versionCode", 0)
                    val version = obj.optString("versionName")
                    val apk = obj.optString("apkUrl")
                    if (code > BuildConfig.VERSION_CODE && apk.startsWith("https://")) version to apk else null
                }
            }.getOrNull()
        }
        if (info != null) {
            updateVersion.value = info.first
            updateUrl.value = info.second
        }
    }

    if (updateUrl.value != null) {
        AlertDialog(
            onDismissRequest = { updateUrl.value = null },
            title = { Text("MELEHAT TELSİZ güncellemesi") },
            text = { Text("Yeni sürüm ${updateVersion.value ?: ""} hazır. İndirip güncellemek ister misiniz?") },
            confirmButton = {
                TextButton(onClick = {
                    val url = updateUrl.value
                    if (url != null) {
                        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                    }
                }) { Text("GÜNCELLE") }
            },
            dismissButton = {
                TextButton(onClick = { updateUrl.value = null }) { Text("SONRA") }
            }
        )
    }
'''

# Determine context variable. Most app roots already use LocalContext; ensure one exists.
bodypos=bodypos+1
prefix=s[bodypos:bodypos+1200]
if not re.search(r'\bcontext\s*=\s*LocalContext\.current', prefix):
    if 'import androidx.compose.ui.platform.LocalContext' not in s:
        idx=s.find('\n', s.find('package '))
        s=s[:idx+1]+'import androidx.compose.ui.platform.LocalContext\n'+s[idx+1:]
    inject='\n    val context = LocalContext.current\n'+inject
s=s[:bodypos]+inject+s[bodypos:]

# Consistent version display.
s=re.sub(r'MELEHAT TELSİZ v0\.\d+(?:\.\d+)?', 'MELEHAT TELSİZ v0.27', s)
s=re.sub(r'v0\.\d+(?:\.\d+)?\s*•\s*[^"\n]*', 'v0.27 • PTT + Otomatik Güncelleme', s)
p.write_text(s)

# Version/package.
b=Path('app/build.gradle.kts')
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"', 'applicationId = "com.melehat.telsiz.v27"', t)
t=re.sub(r'versionCode\s*=\s*\d+', 'versionCode = 27', t)
t=re.sub(r'versionName\s*=\s*"[^"]+"', 'versionName = "0.27.0"', t)
b.write_text(t)

print('v0.27 in-app update checker added')