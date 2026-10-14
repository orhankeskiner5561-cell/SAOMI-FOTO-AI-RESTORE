#!/usr/bin/env python3
"""MELEHAT v1.3.90. Transparent always-visible in-app update controls.
Do not modify PTT, LiveKit, P2P, video, membership, microphone or signing.
"""
from pathlib import Path
p=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=p.read_text("utf-8")
def one(old,new,label):
 global s
 n=s.count(old)
 if n!=1: raise RuntimeError(f"1390 {label}: expected one anchor, found {n}")
 s=s.replace(old,new,1)

one('    var updateRefreshNonce by remember { mutableIntStateOf(0) }',
'''    var updateRefreshNonce by remember { mutableIntStateOf(0) }
    var updateServerVersion by remember { mutableStateOf("") }
    var updateServerCode by remember { mutableIntStateOf(0) }
    var updateLastCheck by remember { mutableStateOf("") }''',
"remote status")

one('''                    if (item != null && item.first > 0 &&
                        item.second.isNotBlank() &&
                        item.third.startsWith(
                            "https://github.com/orhankeskiner5561-cell/" +
                                "SAOMI-FOTO-AI-RESTORE/releases/download/"
                        ) && item.third.endsWith("/MELEHAT-TELSIZ.apk")) {
                        found = item
                        break
                    }''',
'''                    if (item != null && item.first > 0 &&
                        item.second.isNotBlank() &&
                        item.third.startsWith(
                            "https://github.com/orhankeskiner5561-cell/" +
                                "SAOMI-FOTO-AI-RESTORE/releases/download/"
                        ) && item.third.endsWith("/MELEHAT-TELSIZ.apk") &&
                        (found == null || item.first > (found?.first ?: 0))) {
                        // Never stop at the first cached GitHub response.
                        // Choose the newest trusted manifest from either host.
                        found = item
                    }''',
"latest GitHub response")

one('''            if (info != null) {
                val installed = runCatching {''',
'''            updateLastCheck = java.text.SimpleDateFormat(
                "HH:mm:ss", java.util.Locale.getDefault()
            ).format(java.util.Date())
            if (info != null) {
                updateServerVersion = info.second
                updateServerCode = info.first
                val installed = runCatching {''',
"update diagnostics")

one('''                        TextButton(onClick = { updateRefreshNonce += 1 }) {
                            Text("TEKRAR KONTROL ET", fontSize = 11.sp, maxLines = 1)
                        }
''',"","remove redundant failed check")
one('''                        TextButton(onClick = { updateRefreshNonce += 1 }) {
                            Text("GÜNCELLEME ARA", fontSize = 10.sp, maxLines = 1)
                        }
''',"","remove redundant current check")

one('''                    }
                }
            }
                }
                Column(Modifier.weight(1f)) {
            Button(
                onClick = { showMembers = true },''',
'''                    }
                    if (updateServerVersion.isNotBlank()) {
                        Text(
                            "Sunucuda: v" + updateServerVersion +
                                " (" + updateServerCode + ") • " + updateLastCheck,
                            fontSize = 9.sp, maxLines = 2,
                            overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                        )
                    }
                    // Never hide the manual check when the server or CDN fails.
                    TextButton(onClick = { updateRefreshNonce += 1 },
                        modifier = Modifier.fillMaxWidth()) {
                        Text("GÜNCELLEME ARA", fontSize = 10.sp, maxLines = 1)
                    }
                    // User can install from the official GitHub releases page
                    // even if the installed APK is too old to recognize OTA.
                    TextButton(onClick = {
                        val releases = Intent(Intent.ACTION_VIEW,
                            Uri.parse("https://github.com/orhankeskiner5561-cell/" +
                                "SAOMI-FOTO-AI-RESTORE/releases/latest"))
                        runCatching { updateContext.startActivity(releases) }
                    }, modifier = Modifier.fillMaxWidth()) {
                        Text("SÜRÜMLER", fontSize = 10.sp, maxLines = 1)
                    }
                }
            }
                }
                Column(Modifier.weight(1f)) {
            Button(
                onClick = { showMembers = true },''',
"always visible updater controls")
for invariant in (
 "onPtt(true)", "onPtt(false)", "MELEHAT_UPDATE_MANIFEST",
 "KURULUMU TAMAMLA", "DownloadManager", "LastRoomPreference",
 "P2pVideoCallActivity", "showMembers = true", "GÜNCELLEME ARA",
 "SÜRÜMLER", "android.util.Base64.decode", "LaunchedEffect(updateRefreshNonce)"
):
 if invariant not in s: raise RuntimeError("1390 protected feature missing: "+invariant)
if s.count('Text("GÜNCELLEME ARA", fontSize = 10.sp, maxLines = 1)')!=1:
 raise RuntimeError("1390 duplicate update checker")
assert 'applicationId = "com.melehat.telsiz"' in Path("app/build.gradle.kts").read_text("utf-8")
p.write_text(s,"utf-8")
print("MELEHAT_1390_VISIBLE_CHECK_FRESH_MANIFEST_FALLBACK_READY")
