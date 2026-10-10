from pathlib import Path

# MELEHAT 1.3.40 – only an Android Compose layout correction.
# The long "Kanala Gir" button on the HOME screen reselects the current
# channel and adds no useful behavior. Remove it on every channel screen.
# Actual room switching inside KANALLAR remains intact.
ui = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = ui.read_text(encoding="utf-8")

legacy_button = '''            Button(
                onClick = {
                    val current = localStore.loadActiveChannel()
                    roomSelection = current.id to current.name
                },
                modifier = Modifier.fillMaxWidth()
            ) { Text("Kanala Gir") }'''

if s.count(legacy_button) != 1:
    raise SystemExit(
        "MELEHAT 1340: expected one redundant main-channel join button, found " +
        str(s.count(legacy_button))
    )

s = s.replace(legacy_button, "", 1)

# The existing two-line status display and toggle are already one aligned
# horizontal row. Moving them into the vacated spot is achieved by removing
# the intervening button; don't move/clone any switch or change its binding.
assert 'Text("Telsiz durumu"' in s
assert "KANALLAR" in s and "KANAL AÇ  +" in s
assert 'Text("KANALA GİR")' in s      # Keep real room-selection controls.
assert 'Text("ORTAK KANALA GİR")' in s # Keep common-room entry.
assert 'Text("Kanala Gir")' not in s   # No redundant main button.
assert "roomSelection = item.roomId to item.title" in s
assert "onRadioToggle" in s
assert "activeRoomByUser" in s
assert "MelehatPendingRequestBadge" in s
assert "VideoCallMonitor.latestMissed" in s
assert "proportionalTitleSize" in s

status_pos = s.index('Text("Telsiz durumu"')
menu_pos = s.index('Text("KANAL AÇ  +"')
if menu_pos > status_pos or status_pos - menu_pos > 3500:
    raise SystemExit("MELEHAT 1340: unexpected status-row position")

ui.write_text(s, encoding="utf-8")
print("MELEHAT_1340_STATUS_ROW_NOW_UNDER_CHANNEL_BUTTONS_OK")
