from pathlib import Path

# MELEHAT v1.3.42: ONLY move the two bottom cards downward.
# ~2 cm of visual breathing space: 120dp spacer above the shared cards row.
# The parent Row keeps GUNCEL and UYELER horizontally aligned.
# Preserve PTT, LiveKit, camera, channel selection and member callbacks.
ui = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = ui.read_text(encoding="utf-8")
anchor = '''            Spacer(Modifier.height(12.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.Top) {'''
replacement = '''            Spacer(Modifier.height(120.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.Top) {'''
if s.count(anchor) != 1:
    raise SystemExit("MELEHAT_1342: bottom cards spacer/row not found exactly once")
s = s.replace(anchor, replacement, 1)

assert "showMembers = true" in s
assert 'Text("Telsiz durumu"' in s
assert 'Text("Kanala Gir")' not in s
assert "pointerInput(radioOn)" in s
assert "VideoCallMonitor.latestMissed" in s
assert "MelehatPendingRequestBadge" in s
assert s.count('Spacer(Modifier.height(120.dp))') == 1
ui.write_text(s, encoding="utf-8")
print("MELEHAT_1342_ONLY_GUNCEL_AND_UYELER_CARDS_120DP_LOWER_OK")
