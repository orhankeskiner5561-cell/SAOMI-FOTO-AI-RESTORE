from pathlib import Path
import re

p=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=p.read_text()

# Keep the existing v0.27 audio/PTT/LiveKit screen; only add a visible updater card.
imports=[
"import android.content.Intent",
"import android.net.Uri",
"import android.app.DownloadManager",
"import android.content.Context",
"import android.os.Build",
"import android.provider.Settings",
"import android.os.Handler",
"import android.os.Looper",
"import androidx.core.content.FileProvider",
"import java.io.File",
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
    var updateAvailable by remember { mutableStateOf(false) }\n    var updateCheckDone by remember { mutableStateOf(false) }\n    var updateCheckFailed by remember { mutableStateOf(false) }
    var updateVersion by remember { mutableStateOf("") }
    var updateUrl by remember { mutableStateOf("") }
    var updateDownloading by remember { mutableStateOf(false) }
    var updateProgress by remember { mutableStateOf(0) }\n    var pendingInstallPath by remember { mutableStateOf("") }
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
                    Triple(code, name, url)
                }
            }.getOrNull()
        }
        if (info != null) {
            val code = info.first
            val name = info.second
            val url = info.third
            updateAvailable = code > 141 && url.startsWith("https://")
            if (updateAvailable) {
                updateVersion = name
                updateUrl = url
            }
            updateCheckFailed = false
        } else {
            updateAvailable = false
            updateCheckFailed = true
        }
        updateCheckDone = true
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
                Modifier.weight(1f).heightIn(min = 64.dp),
                shape = RoundedCornerShape(14.dp),
                color = if (updateAvailable) Color(0xFFFFE5E5) else Color(0xFFE8F5E9)
            ) {
                Column(Modifier.padding(horizontal = 10.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    if (updateAvailable) {
                        Text("🔴 YENİ GÜNCELLEME VAR", fontWeight = FontWeight.Bold, color = Color(0xFFB00020), fontSize = 13.sp)
                        Text("MELEHAT TELSİZ " + updateVersion, fontSize = 12.sp)
                        if (updateDownloading) {
                            Text("APK indiriliyor… %" + updateProgress)
                        } else {
                            Button(onClick = {
                                val dm = updateContext.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
                                val fileName = "MELEHAT-TELSIZ-" + updateVersion + ".apk"
                                val request = DownloadManager.Request(Uri.parse(updateUrl))
                                    .setTitle("MELEHAT TELSİZ " + updateVersion)
                                    .setDescription("Güncelleme indiriliyor")
                                    .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE)
                                    .setDestinationInExternalFilesDir(updateContext, "updates", fileName)
                                val id = dm.enqueue(request)
                                updateDownloading = true
                                Thread {
                                    var done = false
                                    while (!done) {
                                        val c = dm.query(DownloadManager.Query().setFilterById(id))
                                        if (c.moveToFirst()) {
                                            val status = c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))
                                            val total = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES))
                                            val got = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR))
                                            if (total > 0) Handler(Looper.getMainLooper()).post { updateProgress = ((got * 100) / total).toInt() }
                                            if (status == DownloadManager.STATUS_SUCCESSFUL) {
                                                done = true
                                                val apk = File(updateContext.getExternalFilesDir("updates"), fileName)
                                                Handler(Looper.getMainLooper()).post {
                                                    pendingInstallPath = apk.absolutePath
                                                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !updateContext.packageManager.canRequestPackageInstalls()) {
                                                        val permissionIntent = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + updateContext.packageName))
                                                        updateContext.startActivity(permissionIntent)
                                                    } else {
                                                        val uri = FileProvider.getUriForFile(updateContext, updateContext.packageName + ".fileprovider", apk)
                                                        val install = Intent(Intent.ACTION_VIEW).apply {
                                                            setDataAndType(uri, "application/vnd.android.package-archive")
                                                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
                                                        }
                                                        updateContext.startActivity(install)
                                                    }
                                                }
                                            } else if (status == DownloadManager.STATUS_FAILED) done = true
                                        }
                                        c.close()
                                        if (!done) Thread.sleep(500)
                                    }
                                }.start()
                            }) { Text("GÜNCELLE") }
                        }
                    } else if (!updateCheckDone) {
                        Text("🟠 GÜNCELLEME KONTROL EDİLİYOR…", fontWeight = FontWeight.Bold)
                    } else if (updateCheckFailed) {
                        Text("⚠️ GÜNCELLEME KONTROLÜ BAŞARISIZ", fontWeight = FontWeight.Bold)
                        Text("İnternet bağlantısını kontrol edip uygulamayı yeniden açın.")
                    } else {
                        Text("🟢 UYGULAMA GÜNCEL", fontWeight = FontWeight.Bold, fontSize = 13.sp)
                        Text("MELEHAT TELSİZ v1.3.11", fontSize = 12.sp)
                    }
                }
            }

'''
    # Requested layout: members button ABOVE the update card, both full width.
    member_block='''            Button(
                onClick = { showMembers = true },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("ÜYELER: ${directory.size}")
            }
'''
    if member_block not in s:
        raise SystemExit("member button block missing")
    members_above_update = member_block + card
    s=s.replace(member_block, members_above_update, 1)
# Final requested header-only UI change; do not touch PTT/LiveKit/members.
# Move only the visible top title below the Android status bar. Preserve the radio core.
if 'Text("MELEHAT TELSİZ", fontSize = 26.sp, fontWeight = FontWeight.Bold)' not in s:
    raise SystemExit("Visible title anchor missing")
s=s.replace('Text("MELEHAT TELSİZ", fontSize = 26.sp, fontWeight = FontWeight.Bold)', 'Text("MELE - HAT TELSİZ", fontSize = 26.sp, fontWeight = FontWeight.Bold, modifier = Modifier.statusBarsPadding().padding(top = 18.dp))', 1)
# Show LiveKit join/leave/reconnect notices directly under the title.
notice_anchor='Text("MELE - HAT TELSİZ", fontSize = 26.sp, fontWeight = FontWeight.Bold, modifier = Modifier.statusBarsPadding().padding(top = 18.dp))'
if notice_anchor not in s:
    raise SystemExit("MELE-HAT title missing after replacement")
s=s.replace(notice_anchor, notice_anchor + '''
            if (liveNotice.isNotBlank()) {
                Text(liveNotice, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = Color(0xFF6A4CAF))
            }''', 1)
s=s.replace("1.2 • GERÇEK CANLI KANAL 1 • v0.27 SES/PTT", "", 1)
p.write_text(s)

# Keep permanent identity; updater bootstrap is 1.2.2.
g=Path("app/build.gradle.kts")
w=g.read_text()
w=re.sub(r'versionCode\s*=\s*\d+','versionCode = 141',w,count=1)
w=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "1.3.11"',w,count=1)
if 'applicationId = "com.melehat.telsiz"' not in w:
    raise SystemExit("permanent applicationId changed")
g.write_text(w)
print("IN_APP_UPDATE_UI_128_OK")
