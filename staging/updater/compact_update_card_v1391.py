#!/usr/bin/env python3
"""MELEHAT v1.3.91: compact equal-height bottom cards.

Only the bottom update and members card layout changes. Preserve updater
network/version logic, DownloadManager, installer, PTT, radio, LiveKit, video,
users, signing and stable Android package.
"""
from pathlib import Path

p = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = p.read_text(encoding="utf-8")

def one(before: str, after: str, label: str) -> None:
    global s
    count = s.count(before)
    if count != 1:
        raise RuntimeError(f"v1391 {label}: expected 1 source anchor, found {count}")
    s = s.replace(before, after, 1)

one(
    '''                Column(
                    Modifier.fillMaxWidth().padding(horizontal = 9.dp, vertical = 10.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    if (updateAvailable) {''',
    '''                Column(
                    Modifier.fillMaxWidth().padding(horizontal = 9.dp, vertical = 7.dp),
                    verticalArrangement = Arrangement.spacedBy(2.dp)
                ) {
                    if (updateAvailable) {''',
    "reduce update card vertical padding"
)

one(
    '''            Surface(
                Modifier.fillMaxWidth().heightIn(min = 90.dp),
                shape = RoundedCornerShape(14.dp),
                color = if (updateAvailable) Color(0xFFFFE5E5) else Color(0xFFE8F5E9)
            ) {''',
    '''            Surface(
                Modifier.fillMaxWidth().heightIn(min = 110.dp),
                shape = RoundedCornerShape(14.dp),
                color = if (updateAvailable) Color(0xFFFFE5E5) else Color(0xFFE8F5E9)
            ) {''',
    "compact update card min height"
)

one(
    '''                modifier = Modifier.fillMaxWidth().heightIn(min = 90.dp),
                contentPadding = PaddingValues(horizontal = 8.dp, vertical = 8.dp)''',
    '''                modifier = Modifier.fillMaxWidth().heightIn(min = 110.dp),
                contentPadding = PaddingValues(horizontal = 8.dp, vertical = 8.dp)''',
    "align member card to compact update card"
)

one(
    '''                            fontSize = 9.sp, maxLines = 2,
                            overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                        )
                    }
                    // Never hide the manual check when the server or CDN fails.''',
    '''                            fontSize = 9.sp, maxLines = 1,
                            overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                        )
                    }
                    // Never hide the manual check when the server or CDN fails.''',
    "prevent long server status from stretching card"
)

one(
    '''                    // Never hide the manual check when the server or CDN fails.
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
                    }''',
    '''                    // Place secondary actions NEXT TO each other, not one
                    // below the other. Their previous 2 x 48dp touch rows made
                    // the green card visibly hang far below ÜYELER.
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(2.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        TextButton(
                            onClick = { updateRefreshNonce += 1 },
                            modifier = Modifier.weight(1f),
                            contentPadding = PaddingValues(horizontal = 1.dp, vertical = 0.dp)
                        ) {
                            Text("ARA", fontSize = 10.sp, maxLines = 1)
                        }
                        TextButton(
                            onClick = {
                                val releases = Intent(Intent.ACTION_VIEW,
                                    Uri.parse("https://github.com/orhankeskiner5561-cell/" +
                                        "SAOMI-FOTO-AI-RESTORE/releases/latest"))
                                runCatching { updateContext.startActivity(releases) }
                            },
                            modifier = Modifier.weight(1f),
                            contentPadding = PaddingValues(horizontal = 1.dp, vertical = 0.dp)
                        ) {
                            Text("SÜRÜMLER", fontSize = 9.sp, maxLines = 1)
                        }
                    }''',
    "put update actions in one compact row"
)

# Fail closed when the radio/PTT or updater actions have been accidentally touched.
for marker in (
    'onPtt(true)', 'onPtt(false)', 'pointerInput(radioOn, liveStatus)',
    'DownloadManager', 'Text("GÜNCELLE", fontSize = 12.sp',
    'KURULUMU TAMAMLA', 'Text("ARA", fontSize = 10.sp',
    'Text("SÜRÜMLER", fontSize = 9.sp',
    'LaunchedEffect(updateRefreshNonce)', 'MELEHAT_UPDATE_MANIFEST',
    'P2pVideoCallActivity', 'selectedMemberCount',
    'RoomPresenceReporter', 'LastRoomPreference',
):
    if marker not in s:
        # RoomPresenceReporter is in another source file, not AppRoot.
        if marker == "RoomPresenceReporter":
            continue
        raise RuntimeError("v1391 protected feature absent: " + marker)
if 'applicationId = "com.melehat.telsiz"' not in Path("app/build.gradle.kts").read_text():
    raise RuntimeError("v1391 application identity changed")
p.write_text(s, encoding="utf-8")
print("MELEHAT_1391_COMPACT_UPDATE_CARD_MEMBERS_ALIGNED_OK")
