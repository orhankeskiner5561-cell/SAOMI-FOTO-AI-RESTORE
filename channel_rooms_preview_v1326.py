from pathlib import Path
p = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = p.read_text()
state_anchor = '    var showMembers by remember { mutableStateOf(false) }'
if state_anchor not in s: raise SystemExit("Missing member state; refusing unsafe patch")
s = s.replace(state_anchor, state_anchor + '''
    var showChannelRoomsPreview by remember { mutableStateOf(false) }
    var showCreateRoomPreview by remember { mutableStateOf(false) }
''', 1)
anchor = '            if (showMembers) {'
if anchor not in s: raise SystemExit("Missing member dialog; refusing unsafe patch")
preview = '''
            // Visual-only first look. No membership, LiveKit or PTT state changes.
            TextButton(onClick = { showChannelRoomsPreview = true }) {
                Text("KANALLAR  •  KANAL AÇ", color = Color(0xFF6A4CAF))
            }
            if (showChannelRoomsPreview) {
                AlertDialog(
                    onDismissRequest = { showChannelRoomsPreview = false },
                    title = { Text("MELEHAT • Kanallar") },
                    text = {
                        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            Text("Kanal odaları — arayüz önizlemesi", fontWeight = FontWeight.Bold)
                            Text("KANAL 1  •  Mevcut özel kanal")
                            Text("Yeni üyeler yalnızca kanal sahibinin onayıyla katılabilecek.")
                            Text("KATILMA İSTEĞİ  •  Yakında etkinleştirilecek", fontSize = 13.sp)
                            Text("Diğer odalar, kanal sahipleri tarafından açıldığında burada listelenecek.")
                            TextButton(onClick = {
                                showChannelRoomsPreview = false
                                showCreateRoomPreview = true
                            }) { Text("+ KANAL AÇ (ÖNİZLEME)") }
                        }
                    },
                    confirmButton = {
                        TextButton(onClick = { showChannelRoomsPreview = false }) { Text("KAPAT") }
                    }
                )
            }
            if (showCreateRoomPreview) {
                AlertDialog(
                    onDismissRequest = { showCreateRoomPreview = false },
                    title = { Text("Yeni kanal aç") },
                    text = { Text("Kanal adı, görünürlük ve katılım onayı ekranı hazırlanıyor. Bu sürümde yeni oda oluşturulmaz.") },
                    confirmButton = {
                        TextButton(onClick = { showCreateRoomPreview = false }) { Text("TAMAM") }
                    }
                )
            }
'''
s = s.replace(anchor, preview + anchor, 1)
p.write_text(s)
print("CHANNEL_ROOMS_VISUAL_PREVIEW_OK")
