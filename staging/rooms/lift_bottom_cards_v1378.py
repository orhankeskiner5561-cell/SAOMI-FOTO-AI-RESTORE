#!/usr/bin/env python3
"""MELEHAT v1.3.78 — lift GÜNCEL and ÜYELER as one pair ~0.5 cm.

The row is translated visually by 30dp (Android's nominal half-centimeter).
Compose offset does not alter measurement, reflow or other control positions.
Existing 120dp spacer and PTT +60dp displacement leave >=30dp separation.
No changes to callbacks, media, auth, members, subscriptions or updater.
"""
from pathlib import Path

ui = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = ui.read_text(encoding="utf-8")
old = 'Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.Top) {'
new = 'Row(Modifier.fillMaxWidth().offset(y = (-30).dp), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.Top) {'
assert s.count(old) == 1, "Expected exactly one shared GÜNCEL/ÜYELER row"
assert s.count('Spacer(Modifier.height(120.dp))') == 1, "Card clearance must stay reserved"
assert s.count('Box(Modifier.size(210.dp).offset(y = 60.dp), contentAlignment = Alignment.Center)') == 1, "PTT circle must stay exactly where it is"
assert 'import androidx.compose.foundation.layout.offset' in s, "offset import missing"
before, after = s.split(old, 1)
assert 'Spacer(Modifier.height(120.dp))' in before[-160:], "Not the row immediately following PTT spacer"
assert 'showMembers = true' in after, "Member button callback not found after row"
assert '🟢 GÜNCEL' in after, "Update card not found after row"
s = before + new + after

for marker in (
    'onPtt(true)', 'onPtt(false)', 'pointerInput(radioOn, liveStatus)',
    'showMembers = true', 'MELEHAT_UPDATE_MANIFEST',
    'P2pVideoCallActivity', 'activeP2pRoomActivity', 'YENİ ABONELER',
    'RecentSubscriberApi', 'roomApi.listRequests', 'LastRoomPreference',
):
    assert marker in s, "Protected feature missing: " + marker
gradle = Path("app/build.gradle.kts").read_text(encoding="utf-8")
assert 'applicationId = "com.melehat.telsiz"' in gradle
assert s.count(new) == 1
ui.write_text(s, encoding="utf-8")
print("MELEHAT_1378_BOTH_LOWER_CARDS_UP_30DP_PTT_UNCHANGED_OK")
