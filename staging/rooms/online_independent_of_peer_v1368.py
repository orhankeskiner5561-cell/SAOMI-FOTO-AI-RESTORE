#!/usr/bin/env python3
from pathlib import Path
p=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=p.read_text("utf-8")
def one(old,new,label):
 global s
 if s.count(old)!=1: raise RuntimeError(label+" found "+str(s.count(old)))
 s=s.replace(old,new,1)
one('''    var currentSpeakers by remember { mutableStateOf<Set<String>>(emptySet()) }''',
'''    var currentSpeakers by remember { mutableStateOf<Set<String>>(emptySet()) }
    var successfulPresenceAt by remember { mutableStateOf(0L) }''',"fresh presence")
one('''                    activeRoomByUser = it.first
                    currentSpeakers = it.second''',
'''                    activeRoomByUser = it.first
                    currentSpeakers = it.second
                    successfulPresenceAt = android.os.SystemClock.elapsedRealtime()''',"online poll")
one('''                .onFailure {
                    // Don't flicker online users to zero on transient mobile timeouts.
                }''',
'''                .onFailure {
                    if (android.os.SystemClock.elapsedRealtime()-successfulPresenceAt>15000L) {
                        activeRoomByUser = emptyMap()
                        currentSpeakers = emptySet()
                    }
                }''',"stale poll")
one('''    val selectedRoomTitle = if (radioOn && liveStatus == "LIVE") liveRoomName
        else localStore.loadActiveChannel().name''',
'''    val selectedRoomTitle = if (radioOn && liveStatus == "LIVE") liveRoomName
        else localStore.loadActiveChannel().name
    // Online means server acknowledged the user in the channel, even if alone.
    // LIVE remains a separate true WebRTC audio transport state for microphone.
    val radioOnline = radioOn &&
        (session?.userId?.let { activeRoomByUser[it] == selectedRoomId } == true) &&
        android.os.SystemClock.elapsedRealtime()-successfulPresenceAt<15000L''',
"peer-independent online")
start=s.index('                    Text(\n                        when {\n                            !radioOn -> "MELEHAT • TELSİZ HAZIR"')
status=s.index('                    Text(\n                        when {\n                            !radioOn -> "⚪ TELSİZ KAPALI"',start)
end=s.index('                }\n                Switch(',status)
if "2 KİŞİLİ P2P" not in s[start:status] or "Çoklu modu değiştirmek" not in s[start:status]:
 raise RuntimeError("expected obsolete group switches not found")
s=s[:start]+'''                    Text(
                        when {
                            !radioOn -> "⚪ TELSİZ KAPALI"
                            radioOnline -> "🟢 " + selectedRoomTitle + " • ÇEVRİMİÇİ"
                            else -> "🟠 " + selectedRoomTitle + " • BAĞLANIYOR"
                        }
                    )
'''+s[end:]
one('''                                    liveStatus != "LIVE" -> "P2P BAĞLANIYOR"
''',"","hide P2P technical mode from main PTT")
one('''                                    if (transmitting) "Koyu = Yayın" else "Sütlü kahve = Hazır",''',
'''                                    when {
                                        transmitting -> "Koyu = Yayın"
                                        liveStatus == "LIVE" -> "Sütlü kahve = Hazır"
                                        else -> "Üyeler bekleniyor"
                                    },''',"accurate no listener label")
one('''    val transportPrefs = remember(roomsContext) {
        roomsContext.getSharedPreferences(
            "melehat_p2p_transport", android.content.Context.MODE_PRIVATE)
    }
    var p2pGroupEnabled by remember {
        mutableStateOf(transportPrefs.getBoolean("p2p_mesh_enabled", false))
    }
''',"","hide group mode state")
for needed in ("onPtt(true)","onPtt(false)","pointerInput(radioOn, liveStatus)",
 "activeP2pRoomActivity","LastRoomPreference","roomApi.listRequests",
 "showVideoCallInfo","MELEHAT_UPDATE_MANIFEST","KURULUMU TAMAMLA",
 'roomSelection = "ortak" to "ORTAK KANAL"'):
 if needed not in s:raise RuntimeError("Protected source missing "+needed)
assert 'if (!radioOn || liveStatus != "LIVE") return@detectTapGestures' in s
for bad in ("2 KİŞİLİ P2P","ÇOKLU P2P AÇIK","P2P BAĞLANIYOR",
            "BAĞLANTI: YEREL P2P"):
 assert bad not in s, bad
assert 'applicationId = "com.melehat.telsiz"' in Path("app/build.gradle.kts").read_text()
p.write_text(s,encoding="utf-8")
print("MELEHAT_1368_SINGLE_RADIO_AND_SOLO_ONLINE_READY")
