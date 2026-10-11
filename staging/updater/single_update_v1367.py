#!/usr/bin/env python3
# MELEHAT 1.3.67: one in-app updater, resume install, truthful radio status.
# Does not modify signing, installed package identity, LiveKit, P2P audio,
# channel admission, LastRoomPreference or foreground radio service.
from pathlib import Path
p=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=p.read_text(encoding="utf-8")

def sub(a,b,label):
    global s
    assert s.count(a)==1, f"{label}: expected one anchor, got {s.count(a)}"
    s=s.replace(a,b,1)

# Remove the older Supabase-hosted duplicate prompt. The GitHub-backed
# updater card already compares the CURRENT installed APK's versionCode.
sub('''                    UpdateChecker()
''','', "single updater entry")

# Static green 'P2P' text was misleading when the transport was only polling.
sub('''                    Text(
                        "BAĞLANTI: YEREL P2P • ANA BAS KONUŞ",
                        color = Color(0xFF206E50),
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold
                    )''',
'''                    Text(
                        when {
                            !radioOn -> "MELEHAT • TELSİZ HAZIR"
                            liveStatus == "LIVE" -> "MELEHAT • SES BAĞLANTISI KURULDU"
                            else -> "MELEHAT • BAĞLANTI HAZIRLANIYOR"
                        },
                        color = if (radioOn && liveStatus == "LIVE")
                            Color(0xFF206E50) else Color(0xFF665477),
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold
                    )''',
"honest user-facing radio status")

# Don't advertise the update as trusted based solely on any https URL.
sub('''            updateAvailable = code.toLong() > updateContext.packageManager.getPackageInfo(updateContext.packageName, 0).longVersionCode && url.startsWith("https://")''',
'''            updateAvailable =
                code.toLong() > updateContext.packageManager
                    .getPackageInfo(updateContext.packageName, 0).longVersionCode &&
                url.startsWith("https://github.com/orhankeskiner5561-cell/SAOMI-FOTO-AI-RESTORE/releases/download/") &&
                url.endsWith("/MELEHAT-TELSIZ.apk")''',
"trusted update endpoint and installed version")

sub('''    var pendingInstallPath by remember { mutableStateOf("") }''',
'''    var pendingInstallPath by remember { mutableStateOf("") }
    var updateInstallError by remember { mutableStateOf("") }''',
"install continuation state")

# Android can require explicit permission to install app updates.
# After enabling "allow from this source", the app must show a retry control.
sub('''                            LinearProgressIndicator(progress = { updateProgress / 100f }, modifier = Modifier.fillMaxWidth())
                        } else {
                            Button(onClick = {''',
'''                            LinearProgressIndicator(progress = { updateProgress / 100f }, modifier = Modifier.fillMaxWidth())
                            if (pendingInstallPath.isNotBlank()) {
                                Button(onClick = {
                                    val apk = File(pendingInstallPath)
                                    if (!apk.exists() || apk.length() < 1000000L) {
                                        updateInstallError = "İndirilen APK bulunamadı. Tekrar indirin."
                                        pendingInstallPath = ""
                                        updateDownloading = false
                                    } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O &&
                                        !updateContext.packageManager.canRequestPackageInstalls()) {
                                        val allow = Intent(
                                            Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                                            Uri.parse("package:" + updateContext.packageName)
                                        )
                                        updateContext.startActivity(allow)
                                    } else {
                                        val apkUri = FileProvider.getUriForFile(
                                            updateContext,
                                            updateContext.packageName + ".fileprovider",
                                            apk
                                        )
                                        val install = Intent(Intent.ACTION_VIEW).apply {
                                            setDataAndType(apkUri, "application/vnd.android.package-archive")
                                            addFlags(
                                                Intent.FLAG_GRANT_READ_URI_PERMISSION or
                                                    Intent.FLAG_ACTIVITY_NEW_TASK
                                            )
                                        }
                                        updateContext.startActivity(install)
                                    }
                                }) { Text("KURULUMU TAMAMLA", fontSize = 10.sp) }
                            }
                        } else {
                            Button(onClick = {''',
"installer permission return button")

sub('''                                            } else if (status == DownloadManager.STATUS_FAILED) done = true''',
'''                                            } else if (status == DownloadManager.STATUS_FAILED) {
                                                done = true
                                                Handler(Looper.getMainLooper()).post {
                                                    updateDownloading = false
                                                    pendingInstallPath = ""
                                                    updateInstallError = "İndirme başarısız. Tekrar deneyin."
                                                }
                                            }''',
"download failure recovery")

sub('''                    } else if (!updateCheckDone) {
                        Text("🟠 GÜNCELLEME KONTROL EDİLİYOR…", fontWeight = FontWeight.Bold)''',
'''                        if (updateInstallError.isNotBlank())
                            Text(updateInstallError, fontSize = 11.sp)
                    } else if (!updateCheckDone) {
                        Text("🟠 GÜNCELLEME KONTROL EDİLİYOR…", fontWeight = FontWeight.Bold)''',
"updater error visibility")

# The user always speaks using the MAIN circular PTT, not a browser panel.
for token in (
 "MELEHAT_UPDATE_MANIFEST",
 "pointerInput(radioOn, liveStatus)",
 "onPtt(true)", "onPtt(false)",
 "P2P BAĞLANIYOR",
 "activeP2pRoomActivity",
 "currentSpeakers",
 "p2pGroupEnabled",
 "LastRoomPreference",
 "MELEHAT • SES BAĞLANTISI KURULDU",
 "KURULUMU TAMAMLA",
):
    assert token in s, "Protected feature missing: "+token
assert '                    UpdateChecker()' not in s
assert 'com.melehat.telsiz' in Path("app/build.gradle.kts").read_text(encoding="utf-8")
p.write_text(s,encoding="utf-8")
print("MELEHAT_1367_SINGLE_UPDATE_AND_INSTALL_CONTINUATION_READY")
