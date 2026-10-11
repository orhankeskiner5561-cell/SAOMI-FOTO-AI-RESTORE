#!/usr/bin/env python3
# MELEHAT 1.3.70: status row layout stabilization only.
# No WebRTC/PTT/room auth, videos, Android package, keystore or updater changes.
from pathlib import Path

p=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=p.read_text(encoding="utf-8")
def one(old,new,label):
 global s
 n=s.count(old)
 if n!=1: raise RuntimeError(f"{label}: expected one anchor, got {n}")
 s=s.replace(old,new,1)

one('''            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
''','''            // A long channel name may not change the status-row height or
            // steal the physical on/off switch's reserved 54dp column.
            Row(
                modifier = Modifier.fillMaxWidth().height(68.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(
                    modifier = Modifier.weight(1f).fillMaxHeight(),
                    verticalArrangement = Arrangement.Center
                ) {
''',"stable status row")

one('''                    Text("Telsiz durumu", fontWeight = FontWeight.SemiBold)
                    // Main-channel microphone now uses the real native P2P engine.
                    // The separate test page is no longer the radio voice path.
                    Text(
                        when {
                            !radioOn -> "⚪ TELSİZ KAPALI"
                            radioOnline -> "🟢 " + selectedRoomTitle + " • ÇEVRİMİÇİ"
                            else -> "🟠 " + selectedRoomTitle + " • BAĞLANIYOR"
                        }
                    )
                }
                Switch(
                    checked = radioOn,
''','''                    Text(
                        "Telsiz durumu",
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1,
                        softWrap = false,
                        overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                    )
                    // Ellipsis affects this label only: full room title remains in
                    // the channel chooser, directory and member-list dialog.
                    Text(
                        text = when {
                            !radioOn -> "⚪ TELSİZ KAPALI"
                            radioOnline -> "🟢 " + selectedRoomTitle + " • ÇEVRİMİÇİ"
                            else -> "🟠 " + selectedRoomTitle + " • BAĞLANIYOR"
                        },
                        modifier = Modifier.fillMaxWidth(),
                        maxLines = 1,
                        softWrap = false,
                        overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis,
                        fontSize = 15.sp
                    )
                }
                Switch(
                    modifier = Modifier.width(54.dp),
                    checked = radioOn,
''',"single-line ellipsized channel status")

one('''            if (liveNotice.isNotBlank()) {
                Text(liveNotice, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = Color(0xFF6A4CAF))
            }
''','''            // Always reserve the same height for a transient status message.
            // This prevents a notice appearing/disappearing from moving PTT.
            Box(Modifier.fillMaxWidth().height(19.dp)) {
                Text(
                    liveNotice,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = Color(0xFF6A4CAF),
                    maxLines = 1,
                    softWrap = false,
                    overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis,
                    modifier = Modifier.fillMaxWidth()
                )
            }
''',"reserved-height notification")

for marker in [
    'pointerInput(radioOn, liveStatus)',
    'onPtt(true)', 'onPtt(false)',
    'P2pVideoCallActivity', 'activeP2pRoomActivity',
    'MELEHAT_UPDATE_MANIFEST', 'KURULUMU TAMAMLA',
    'LastRoomPreference', 'roomApi.listRequests',
    'modifier = Modifier.width(54.dp)',
    'Modifier.weight(1f).fillMaxHeight()',
    'maxLines = 1'
]:
 assert marker in s, "Expected unmodified system missing: "+marker
assert 'applicationId = "com.melehat.telsiz"' in Path("app/build.gradle.kts").read_text()
p.write_text(s,encoding="utf-8")
print("MELEHAT_1370_FIXED_STATUS_ROW_AND_ELLIPSIS_READY")
