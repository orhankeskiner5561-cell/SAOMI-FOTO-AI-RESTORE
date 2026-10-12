#!/usr/bin/env python3
"""MELEHAT v1.3.86 — reliable repeated GitHub update checks.
Only AppRoot updater check and user-initiated retry; does not modify
signing, channels, PTT, mic, Shizuku, smart voice, camera or room state.
"""
from pathlib import Path
p=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=p.read_text(encoding="utf-8")
old='''    // MELEHAT_UPDATE_MANIFEST
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
            updateAvailable =
                code.toLong() > updateContext.packageManager
                    .getPackageInfo(updateContext.packageName, 0).longVersionCode &&
                url.startsWith("https://github.com/orhankeskiner5561-cell/SAOMI-FOTO-AI-RESTORE/releases/download/") &&
                url.endsWith("/MELEHAT-TELSIZ.apk")
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
    }'''
new='''    // MELEHAT_UPDATE_MANIFEST
    // Keep the screen up-to-date while MELEHAT stays open in the background.
    // A request with a cache-busting query also avoids stale CDN JSON.
    // The secondary GitHub Contents API is used ONLY when raw access fails.
    var updateRefreshNonce by remember { mutableIntStateOf(0) }
    val updateHttp = remember {
        OkHttpClient.Builder()
            .callTimeout(10L, java.util.concurrent.TimeUnit.SECONDS)
            .build()
    }
    LaunchedEffect(updateRefreshNonce) {
        while (true) {
            val info = withContext(Dispatchers.IO) {
                val stamp = System.currentTimeMillis().toString()
                val endpoints = listOf(
                    "https://raw.githubusercontent.com/orhankeskiner5561-cell/" +
                        "SAOMI-FOTO-AI-RESTORE/main/melehat-update.json?refresh=" + stamp,
                    "https://api.github.com/repos/orhankeskiner5561-cell/" +
                        "SAOMI-FOTO-AI-RESTORE/contents/melehat-update.json?ref=main&refresh=" + stamp
                )
                var found: Triple<Int, String, String>? = null
                for (endpoint in endpoints) {
                    val item = runCatching {
                        val req = Request.Builder()
                            .url(endpoint)
                            .header("Cache-Control", "no-cache, no-store, max-age=0")
                            .header("Pragma", "no-cache")
                            .build()
                        updateHttp.newCall(req).execute().use { response ->
                            if (!response.isSuccessful) return@use null
                            val body = response.body?.string().orEmpty()
                            val envelope = JSONObject(body)
                            val payload = if (envelope.has("content") &&
                                !envelope.has("versionCode")) {
                                String(
                                    android.util.Base64.decode(
                                        envelope.getString("content"),
                                        android.util.Base64.DEFAULT
                                    ),
                                    Charsets.UTF_8
                                )
                            } else body
                            val json = JSONObject(payload)
                            Triple(
                                json.optInt("versionCode", 0),
                                json.optString("versionName", ""),
                                json.optString("apkUrl", "")
                            )
                        }
                    }.getOrNull()
                    if (item != null && item.first > 0 &&
                        item.second.isNotBlank() &&
                        item.third.startsWith(
                            "https://github.com/orhankeskiner5561-cell/" +
                                "SAOMI-FOTO-AI-RESTORE/releases/download/"
                        ) && item.third.endsWith("/MELEHAT-TELSIZ.apk")) {
                        found = item
                        break
                    }
                }
                found
            }
            if (info != null) {
                val installed = runCatching {
                    updateContext.packageManager.getPackageInfo(
                        updateContext.packageName, 0
                    ).longVersionCode
                }.getOrDefault(0L)
                updateAvailable = info.first.toLong() > installed
                if (updateAvailable) {
                    updateVersion = info.second
                    updateUrl = info.third
                } else {
                    updateVersion = ""
                    updateUrl = ""
                }
                updateCheckFailed = false
            } else {
                // Temporary network failure must not hide an already-known update.
                updateCheckFailed = true
            }
            updateCheckDone = true
            kotlinx.coroutines.delay(if (info == null) 30_000L else 90_000L)
        }
    }'''
assert s.count(old)==1, "Existing updater changed: refusing unsafe replacement"
s=s.replace(old,new,1)
fail='''                        Text("İnternet bağlantısını kontrol edip uygulamayı yeniden açın.")'''
replacement='''                        Text("İnternet bağlantısını kontrol edin. Tekrar deneyebilirsiniz.")
                        TextButton(onClick = { updateRefreshNonce += 1 }) {
                            Text("TEKRAR KONTROL ET", fontSize = 11.sp, maxLines = 1)
                        }'''
assert s.count(fail)==1
s=s.replace(fail,replacement,1)
good='''                            "v" + (updateContext.packageManager.getPackageInfo(updateContext.packageName, 0).versionName ?: ""),
                            fontSize = 12.sp, maxLines = 1,
                            overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                        )
                    }'''
newgood='''                            "v" + (updateContext.packageManager.getPackageInfo(updateContext.packageName, 0).versionName ?: ""),
                            fontSize = 12.sp, maxLines = 1,
                            overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                        )
                        TextButton(onClick = { updateRefreshNonce += 1 }) {
                            Text("GÜNCELLEME ARA", fontSize = 10.sp, maxLines = 1)
                        }
                    }'''
assert s.count(good)==1, "Updater card manual retry anchor missing"
s=s.replace(good,newgood,1)
for token in (
    "onPtt(true)", "onPtt(false)", "P2pVideoCallActivity",
    "YENİ ABONELER", "GÜNCELLE",
    "KURULUMU TAMAMLA", "DownloadManager",
    "LastRoomPreference", "markDecisionNoticesSeen",
    "raw.githubusercontent.com", "api.github.com",
    "Text(\"GÜNCELLEME ARA\""
):
    assert token in s, "Protected feature missing: "+token
assert "applicationId = \"com.melehat.telsiz\"" in Path("app/build.gradle.kts").read_text("utf-8")
p.write_text(s,encoding="utf-8")
print("MELEHAT_1386_PERIODIC_CACHE_BUSTED_UPDATER_AND_MANUAL_RETRY_OK")
