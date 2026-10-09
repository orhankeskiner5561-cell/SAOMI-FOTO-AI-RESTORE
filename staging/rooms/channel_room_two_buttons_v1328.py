from pathlib import Path

# Adjust ONLY navigation layout. Never touch LiveKit/PTT, member list, or signing.
ui = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = ui.read_text()
old = '''            TextButton(onClick = {
                roomMessage = ""
                roomRefresh += 1
                showChannelRoomsPreview = true
            }) { Text("KANALLAR  •  KANAL AÇ", color = Color(0xFF6A4CAF)) }'''
if old not in s:
    raise SystemExit("Existing room navigation anchor missing")
s = s.replace(old, "", 1)

button = s.find('Text("Kanala Gir")')
if button >= 0:
    insert_at = s.rfind("            Button(", 0, button)
else:
    insert_at = -1
if insert_at < 0:
    status = s.find('Text("Telsiz durumu"')
    if status < 0:
        raise SystemExit("Neither join button nor status anchor found")
    insert_at = s.rfind("            Row(", 0, status)
if insert_at < 0:
    raise SystemExit("Could not safely locate navigation position")

if "import androidx.compose.foundation.layout.height" not in s:
    eol = s.find("\n", s.find("package "))
    s = s[:eol+1] + "import androidx.compose.foundation.layout.height\n" + s[eol+1:]
    # Re-evaluate position after added import.
    button = s.find('Text("Kanala Gir")')
    if button >= 0:
        insert_at = s.rfind("            Button(", 0, button)
    else:
        insert_at = s.rfind("            Row(", 0, s.find('Text("Telsiz durumu"'))
    if insert_at < 0:
        raise SystemExit("Navigation insertion changed unexpectedly")

menu = '''            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Button(
                    modifier = Modifier.weight(1f).height(64.dp),
                    onClick = {
                        roomMessage = ""
                        roomRefresh += 1
                        showChannelRoomsPreview = true
                    }
                ) { Text("KANALLAR", fontSize = 15.sp, maxLines = 1) }
                Button(
                    modifier = Modifier.weight(1f).height(64.dp),
                    onClick = { showCreateRoomPreview = true }
                ) { Text("KANAL AÇ  +", fontSize = 15.sp, maxLines = 1) }
            }

'''
s = s[:insert_at] + menu + s[insert_at:]
ui.write_text(s)
print("MELEHAT_TWO_PRIMARY_ROOM_BUTTONS_OK")
