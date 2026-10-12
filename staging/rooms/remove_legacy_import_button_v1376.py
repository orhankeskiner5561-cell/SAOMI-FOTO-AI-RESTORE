#!/usr/bin/env python3
"""MELEHAT 1.3.76: Remove legacy '4 ÜYEYİ AKTAR' channel-owner button only.

This is a UI-only cleanup. It deliberately leaves the old database import
function, channel members, channel deletion controls, PTT, video, package ID,
keystore and update system unchanged.
"""
from pathlib import Path

p = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = p.read_text(encoding="utf-8")

legacy_button = '''                                                    if (item.roomId == "kanal-74170df4-f887-4319-a111-f0268598844a") {
                                                        TextButton(
                                                            enabled = !roomBusy,
                                                            onClick = {
                                                                roomCommand = Triple("import", item.roomId, false)
                                                            }
                                                        ) { Text("4 ÜYEYİ AKTAR") }
                                                    }
'''

assert s.count(legacy_button) == 1, (
    "Cannot safely identify exactly one legacy import button in generated AppRoot.kt"
)
s = s.replace(legacy_button, "", 1)

for expected in (
    'Text("KANALI SİL", color = Color(0xFFB00020))',
    'Text("KANALA GİR")',
    'roomApi.importLegacyMembers(active, cmd.second)',
    'roomApi.deleteRoom(active, cmd.second)',
    'onPtt(true)', 'onPtt(false)',
    'activeP2pRoomActivity', 'P2pVideoCallActivity',
    'MELEHAT_UPDATE_MANIFEST', 'LastRoomPreference',
):
    assert expected in s, "Protected functionality missing: " + expected

assert "4 ÜYEYİ AKTAR" not in s, "Old button still present"

gradle = Path("app/build.gradle.kts").read_text(encoding="utf-8")
assert 'applicationId = "com.melehat.telsiz"' in gradle
p.write_text(s, encoding="utf-8")
print("MELEHAT_1376_REMOVE_LEGACY_4_MEMBERS_IMPORT_BUTTON_OK")
