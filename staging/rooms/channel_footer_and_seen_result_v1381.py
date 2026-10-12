from pathlib import Path
p=Path('app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt')
s=p.read_text(encoding='utf-8')
start='''            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Spacer(Modifier.weight(1f))
                TextButton(onClick = {'''
end='''            if (showLegacyChannelPicker) {'''
assert s.count(start)==1 and s.count(end)==1
old_start=s.index(start)
old_end=s.index(end,old_start)
old=s[old_start:old_end]
assert old.count('Text("Çıkış")')==1
button_start=old.index('                TextButton(onClick = {')
button_end=old.index(') { Text("Çıkış") }',button_start)+len(') { Text("Çıkış") }')
button=old[button_start:button_end]
button=button.replace('Text("Çıkış")','Text("ÇIKIŞ")',1)
button=button.replace('TextButton(onClick = {','TextButton(onClick = {\n                    showChannelRoomsPreview = false',1)
s=s[:old_start]+s[old_end:]
old_footer='''                    confirmButton = {
                        Row {
                            // New rooms are created with the permanent
                            // KANAL AÇ + button on the home screen.

                            // No manual refresh required; list refreshes on
                            // every operation and periodically in the background.
                            TextButton(onClick = { showChannelRoomsPreview = false }) {
                                Text("KAPAT")
                            }
                        }
                    }
                )
            }
            if (deleteTarget != null) {'''
assert s.count(old_footer)==1
new_footer='''                    confirmButton = {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
'''+button+'''
                            TextButton(onClick = { showChannelRoomsPreview = false }) {
                                Text("KAPAT")
                            }
                        }
                    }
                )
            }
            if (deleteTarget != null) {'''
s=s.replace(old_footer,new_footer,1)
for result in ('approved','rejected'):
    old_line='myLatestJoinRequest?.status == "'+result+'") {'
    new_line='myLatestJoinRequest?.status == "'+result+'" &&\n                                            myLatestJoinRequest?.resultSeenAt == null) {'
    assert s.count(old_line)==1,old_line
    s=s.replace(old_line,new_line,1)
assert s.count('Text("ÇIKIŞ")')==1
assert 'Text("Çıkış")' not in s
assert s.count('myLatestJoinRequest?.resultSeenAt == null')==2
assert s.count('markDecisionNoticesSeen(me, unseenIds)')==1
for word in ('onPtt(true)','onPtt(false)','Color(0xFF654333)','Color(0xFFD32F2F)','YENİ ABONELER','GÜNCELLE','LastRoomPreference'):
    assert word in s,word
p.write_text(s,encoding='utf-8')
print('MELEHAT_1381_CHANNEL_LOGOUT_AND_ONCE_DECISION_NOTICES_OK')
