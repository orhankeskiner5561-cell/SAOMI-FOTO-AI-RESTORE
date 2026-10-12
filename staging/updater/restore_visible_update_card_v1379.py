#!/usr/bin/env python3
"""MELEHAT v1.3.79: repair truncated update card using measured layout space.
Keep PTT, channels, members, subscriber list, DownloadManager and signing unchanged.
"""
from pathlib import Path
p=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=p.read_text("utf-8")
def one(old,new,tag):
    global s
    count=s.count(old)
    if count!=1:
        raise RuntimeError(tag + ": expected one anchor, found "+str(count))
    s=s.replace(old,new,1)

# Allow vertical scrolling on shorter screens / larger text. No gesture code
# on PTT is changed and the top bar stays fixed.
one(
    '            Modifier.padding(pad).fillMaxSize().padding(18.dp),\n            horizontalAlignment = Alignment.CenterHorizontally,',
    '            Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(18.dp),\n            horizontalAlignment = Alignment.CenterHorizontally,',
    "avoid bottom content clipping"
)
# The 30dp up-shift is now real reserved space, not offset drawing.
one(
    '            Spacer(Modifier.height(120.dp))\n            Row(Modifier.fillMaxWidth().offset(y = (-30).dp), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.Top) {',
    '''            // Keep both cards ~0.5 cm higher without moving PTT.
            // Unlike offset, a real spacer change preserves the card height.
            Spacer(Modifier.height(90.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.Top) {''',
    "measured bottom card position"
)
one(
    '''            Surface(
                Modifier.fillMaxWidth().heightIn(min = 74.dp),
                shape = RoundedCornerShape(14.dp),
                color = if (updateAvailable) Color(0xFFFFE5E5) else Color(0xFFE8F5E9)
            ) {
                Column(Modifier.padding(horizontal = 10.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {''',
    '''            Surface(
                Modifier.fillMaxWidth().heightIn(min = 86.dp),
                shape = RoundedCornerShape(14.dp),
                color = if (updateAvailable) Color(0xFFFFE5E5) else Color(0xFFE8F5E9)
            ) {
                Column(
                    Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {''',
    "updater minimum content clearance"
)
# Leave the original GÜNCELLE button and its real downloading callback in place.
one(
    '''                    if (updateAvailable) {
                        Text("🔴 YENİ", fontWeight = FontWeight.Bold, color = Color(0xFFB00020), fontSize = 11.sp, maxLines = 1)
                        Text("v" + updateVersion, fontSize = 11.sp, maxLines = 1)''',
    '''                    if (updateAvailable) {
                        Text(
                            "YENİ SÜRÜM: v" + updateVersion,
                            color = Color(0xFFB00020),
                            fontWeight = FontWeight.Bold,
                            fontSize = 11.sp,
                            maxLines = 1,
                            overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                        )''',
    "new version compact heading"
)
one(
    '''                            }) { Text("GÜNCELLE", fontSize = 12.sp, maxLines = 1) }''',
    '''                            }, modifier = Modifier.heightIn(min = 40.dp)) {
                                Text("GÜNCELLE", fontSize = 12.sp, maxLines = 1)
                            }''',
    "readable button without changing downloader action"
)
one(
    '''                        Text("🟢 GÜNCEL", fontWeight = FontWeight.Bold, fontSize = 11.sp, maxLines = 1)
                        Text("v" + (updateContext.packageManager.getPackageInfo(updateContext.packageName, 0).versionName ?: ""), fontSize = 11.sp)''',
    '''                        Text("🟢 GÜNCEL", fontWeight = FontWeight.Bold, fontSize = 13.sp, maxLines = 1)
                        Text(
                            "v" + (updateContext.packageManager.getPackageInfo(updateContext.packageName, 0).versionName ?: ""),
                            fontSize = 12.sp, maxLines = 1,
                            overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                        )''',
    "installed version readable and not cropped"
)
one(
    '''                modifier = Modifier.fillMaxWidth().heightIn(min = 74.dp)
            ) {
                Text("ÜYELER''',
    '''                modifier = Modifier.fillMaxWidth().heightIn(min = 86.dp)
            ) {
                Text("ÜYELER''',
    "aligned member card"
)
for token in (
    "onPtt(true)", "onPtt(false)", "pointerInput(radioOn, liveStatus)",
    "Box(Modifier.size(210.dp).offset(y = 60.dp), contentAlignment = Alignment.Center)",
    "Surface(\n                    modifier = Modifier\n                        .size(185.dp)",
    "showMembers = true", "YENİ ABONELER", "RecentSubscriberApi",
    "MELEHAT_UPDATE_MANIFEST", "KURULUMU TAMAMLA",
    "DownloadManager", "FileProvider.getUriForFile",
    "P2pVideoCallActivity", "activeP2pRoomActivity",
    "LastRoomPreference", "roomApi.listRequests"
):
    assert token in s, "Protected feature missing: "+token
assert s.count('Text("GÜNCELLE", fontSize = 12.sp, maxLines = 1)') == 1
assert s.count('Spacer(Modifier.height(90.dp))') == 1
assert 'Row(Modifier.fillMaxWidth().offset(y = (-30).dp)' not in s
assert 'applicationId = "com.melehat.telsiz"' in Path("app/build.gradle.kts").read_text("utf-8")
p.write_text(s,"utf-8")
print("MELEHAT_1379_UNCLIPPED_UPDATE_CARD_AND_REAL_DOWNLOAD_ACTION_OK")
