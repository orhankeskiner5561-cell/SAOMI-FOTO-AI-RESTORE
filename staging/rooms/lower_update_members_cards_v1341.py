from pathlib import Path

# MELEHAT 1.3.41 - a small vertical gap ONLY between the green BAS KONUS
# button and the pair of update/members cards.
# Do not touch button callbacks, radio/LiveKit, room switching or card texts.
ui = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = ui.read_text(encoding="utf-8")
anchor = '''            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.Top) {'''
if s.count(anchor) != 1:
    raise SystemExit("MELEHAT1341: expected one bottom-card row, found " + str(s.count(anchor)))
# 12 dp increases only the gap below the PTT button.
s = s.replace(anchor, '''            Spacer(Modifier.height(12.dp))
''' + anchor, 1)
assert "showMembers = true" in s
assert "🟢 GÜNCEL" in s
assert "Text(\"Telsiz durumu\"" in s
assert "Text(\"Kanala Gir\")" not in s
assert "onRadioToggle" in s
assert "pointerInput(radioOn)" in s
assert "VideoCallMonitor.latestMissed" in s
ui.write_text(s, encoding="utf-8")
print("MELEHAT_1341_ONLY_BOTTOM_CARDS_LOWERED_12DP_OK")
