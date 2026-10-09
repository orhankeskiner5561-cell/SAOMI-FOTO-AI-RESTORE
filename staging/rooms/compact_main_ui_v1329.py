from pathlib import Path

# Compact visual adjustment to the user's approved ORTAK-KANAL reference.
# Strictly UI only: do NOT touch authentication, PTT gestures, LiveKit rooms,
# foreground service, member directory, or updater logic.
p = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = p.read_text(encoding="utf-8")

title = 'Text("MELE - HAT TELSİZ", fontSize = 26.sp, fontWeight = FontWeight.Bold, modifier = Modifier.statusBarsPadding().padding(top = 18.dp))'
if s.count(title) != 1:
    raise SystemExit("Original title not found exactly once; refusing unsafe UI patch")
for imp in ("import androidx.compose.ui.text.buildAnnotatedString",
            "import androidx.compose.ui.text.SpanStyle",
            "import androidx.compose.ui.text.withStyle"):
    if imp not in s:
        pos = s.find("\n", s.find("package "))
        s = s[:pos+1] + imp + "\n" + s[pos+1:]

new_title = '''Text(
                        buildAnnotatedString {
                            withStyle(SpanStyle(color = Color(0xFF215E8A))) { append("MELE - HAT ") }
                            withStyle(SpanStyle(color = Color(0xFFE47732))) { append("TELSİZ") }
                        },
                        fontSize = 26.sp, fontWeight = FontWeight.Bold,
                        modifier = Modifier.statusBarsPadding().padding(top = 18.dp)
                    )'''
s = s.replace(title, new_title, 1)

profile = '''                Column {
                    Text(profile.fullName, fontWeight = FontWeight.Bold)
                    Text(profile.phone, style = MaterialTheme.typography.bodySmall)
                    Text(profile.email, style = MaterialTheme.typography.bodySmall)
                }
                TextButton(onClick = {'''
if s.count(profile) != 1:
    raise SystemExit("Original logged-in profile header not found; refusing unsafe patch")
# Keep the log-out on the top right and retain profile data in state.
s = s.replace(profile, '''                Spacer(Modifier.weight(1f))
                TextButton(onClick = {''', 1)

legacy = '''            OutlinedTextField(
                value = channelText,
                onValueChange = { channelText = it.uppercase() },
                label = { Text("Kanal") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )'''
if s.count(legacy) != 1:
    raise SystemExit("Original manual channel selector not found; refusing unsafe patch")

state = '    var showChannelRoomsPreview by remember { mutableStateOf(false) }'
if s.count(state) != 1:
    raise SystemExit("Room menu state not found; refusing unsafe patch")
s = s.replace(state, state + '''
    var showLegacyChannelPicker by remember { mutableStateOf(false) }''', 1)

# Collapse the old free-text channel field but keep it reachable from KANALLAR
# until server-approved audio room switching is connected.
s = s.replace(legacy, '''            if (showLegacyChannelPicker) {
''' + legacy + '''
            }''', 1)

btn = 'modifier = Modifier.weight(1f).height(64.dp),'
if s.count(btn) != 2:
    raise SystemExit("Two primary channel buttons not found; refusing unsafe patch")
s = s.replace(btn, '''modifier = Modifier.weight(1f).height(58.dp),
                    shape = RoundedCornerShape(12.dp),
                    border = androidx.compose.foundation.BorderStroke(2.dp, Color.White),''', 2)
s = s.replace('Text("KANALLAR", fontSize = 15.sp, maxLines = 1)',
              'Text("KANALLAR  ☷", fontSize = 14.sp, maxLines = 1)', 1)

# The legacy field remains available in the KANALLAR menu to preserve current
# functionality while multi-room LiveKit is being integrated.
menu_anchor = '''                            TextButton(onClick = { roomRefresh += 1 }) { Text("YENİLE") }'''
if s.count(menu_anchor) != 1:
    raise SystemExit("Channel dialog action anchor not found; refusing unsafe patch")
s = s.replace(menu_anchor, '''                            TextButton(onClick = {
                                showLegacyChannelPicker = !showLegacyChannelPicker
                                showChannelRoomsPreview = false
                            }) { Text("KANAL SEÇ") }
''' + menu_anchor, 1)

# No misleading rename: the current PTT still really connects to KANAL 1.
assert 'Text("ORTAK KANAL • CANLI")' not in s
assert 'showMembers = true' in s
assert 'MELEHAT_UPDATE_MANIFEST' in s
assert 'onPtt(' in s or 'pttHeld' in s or 'pointerInput(radioOn)' in s
p.write_text(s, encoding="utf-8")
print("MELEHAT_COMPACT_UI_VISUAL_ONLY_OK")
