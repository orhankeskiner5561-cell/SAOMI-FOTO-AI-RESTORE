from pathlib import Path

# v1.3.20 stage 1: member-to-member video call entry point.
# Preserve all existing PTT, LiveKit channel, authentication and updater logic.
ui = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = ui.read_text()
old = '''                                Text((if (online) "🟢 " else "⚪ ") + member.fullName +
                                    if (online) " — Aktif" else " — Çevrimdışı")'''
new = '''                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    Text(
                                        (if (online) "🟢 " else "⚪ ") + member.fullName,
                                        modifier = Modifier.weight(1f),
                                        maxLines = 2
                                    )
                                    if (member.userId != session?.userId) {\n                                    TextButton(onClick = {
                                        selectedVideoMemberName = member.fullName\n                                        selectedVideoMemberId = member.userId
                                        showVideoCallInfo = true
                                    }) { Text("📹 ARA") }\n                                    }
                                }'''
if old not in s:
    raise SystemExit("Member row anchor changed; refuse unsafe patch")
s = s.replace(old, new, 1)
anchor = '    var showMembers by remember { mutableStateOf(false) }'
if anchor not in s:
    raise SystemExit("Member state anchor missing")
s = s.replace(anchor, anchor + '''
    var selectedVideoMemberName by remember { mutableStateOf("") }\n    var selectedVideoMemberId by remember { mutableStateOf("") }
    var showVideoCallInfo by remember { mutableStateOf(false) }''', 1)
dialog = '''            if (showVideoCallInfo) {
                AlertDialog(
                    onDismissRequest = { showVideoCallInfo = false },
                    title = { Text("Özel görüntülü görüşme") },
                    text = { Text(selectedVideoMemberName + " ile görüntülü arama bağlantısı hazırlanıyor. Henüz arama başlatılmadı.") },
                    confirmButton = {
                        TextButton(onClick = { showVideoCallInfo = false }) { Text("TAMAM") }
                    }
                )
            }
'''
anchor2 = '            if (showMembers) {'
if anchor2 not in s:
    raise SystemExit("Member dialog anchor missing")
s = s.replace(anchor2, dialog + anchor2, 1)
ui.write_text(s)
print("VIDEO_MEMBER_ENTRY_STAGE1_OK")
