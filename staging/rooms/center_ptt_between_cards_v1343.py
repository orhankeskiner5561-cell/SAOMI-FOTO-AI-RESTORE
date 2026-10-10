from pathlib import Path

# MELEHAT v1.3.43 – move ONLY the large BAS KONUŞ circle 60dp lower.
# Visual offset keeps layout positions of top channel buttons, status row,
# and the GUNCEL/ÜYELER cards unchanged. 60dp approximates one centimeter.
# With 120dp after the PTT, moving PTT 60dp makes the gaps balanced.
ui = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = ui.read_text(encoding="utf-8")
old = "Box(Modifier.size(210.dp), contentAlignment = Alignment.Center)"
new = "Box(Modifier.size(210.dp).offset(y = 60.dp), contentAlignment = Alignment.Center)"

if s.count(old) != 1:
    raise SystemExit("MELEHAT 1343: expected one PTT container; refusing ambiguous edit")
if s.count("Spacer(Modifier.height(120.dp))") != 1:
    raise SystemExit("MELEHAT 1343: existing two-card clearance changed")
if "import androidx.compose.foundation.layout.offset" not in s:
    raise SystemExit("MELEHAT 1343: Compose offset import missing")
s = s.replace(old, new, 1)

assert "pointerInput(radioOn)" in s
assert 'Text("Telsiz durumu"' in s
assert "showMembers = true" in s
assert "MelehatPendingRequestBadge" in s
assert "VideoCallMonitor.latestMissed" in s
assert "roomSelection = item.roomId to item.title" in s
assert s.count(new) == 1
ui.write_text(s, encoding="utf-8")
print("MELEHAT_1343_PTT_60DP_DOWN_ONLY_OK")
