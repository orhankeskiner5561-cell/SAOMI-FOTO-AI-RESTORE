#!/usr/bin/env python3
# MELEHAT 1.3.65: accurate P2P room occupancy and microphone status.
# Keeps the tested 2-user P2P engine, LiveKit, volume-key safety, channel permissions
# and permanent signing identical to v1.3.64.
from pathlib import Path
root=Path("app/src/main/java/com/saomi/telsiz")
room=root/"rooms/MelehatRoomApi.kt"
ui=root/"ui/AppRoot.kt"
p2p=root/"p2p/P2pRadioClient.kt"
for path in (room,ui,p2p):
    assert path.is_file(),f"Missing protected file {path}"

def sub(path,old,new,tag):
    s=path.read_text(encoding="utf-8")
    assert s.count(old)==1,f"{path.name}: {tag} anchor count {s.count(old)}"
    path.write_text(s.replace(old,new,1),encoding="utf-8")

activity=r'''
    // Authenticated activity for currently selected P2P/legacy rooms.
    // Names are resolved from the existing directory, not exposed by the RPC.
    suspend fun activeP2pRoomActivity(
        session: AuthSession
    ): Result<Pair<Map<String, String>, Set<String>>> =
        withContext(Dispatchers.IO) {
            runCatching {
                val raw = executeWithRefresh(session) { fresh ->
                    auth("/rest/v1/rpc/melehat_p2p_room_activity_rpc",fresh)
                        .header("Content-Type","application/json")
                        .post("{}".toRequestBody(jsonType))
                        .build()
                }
                val arr=JSONArray(raw)
                val location=mutableMapOf<String,String>()
                val speakers=mutableSetOf<String>()
                for (i in 0 until arr.length()) {
                    val obj=arr.getJSONObject(i)
                    val id=obj.optString("user_id")
                    val channelId=obj.optString("room_id")
                    if(id.isBlank() || channelId.isBlank())continue
                    location[id]=channelId
                    if(obj.optBoolean("speaking",false)) speakers.add(id)
                }
                location.toMap() to speakers.toSet()
            }
        }
'''
sub(room,'    suspend fun activeRoomByUser(session: AuthSession): Result<Map<String, String>> =',
    activity+"\n    suspend fun activeRoomByUser(session: AuthSession): Result<Map<String, String>> =",
    "activity API")

sub(ui,
'''    var activeRoomByUser by remember { mutableStateOf<Map<String, String>>(emptyMap()) }''',
'''    var activeRoomByUser by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    var currentSpeakers by remember { mutableStateOf<Set<String>>(emptySet()) }''',
"speaker ui state")
sub(ui,
'''            roomApi.activeRoomByUser(currentSession)
                .onSuccess { activeRoomByUser = it }
                .onFailure { activeRoomByUser = emptyMap() }''',
'''            roomApi.activeP2pRoomActivity(currentSession)
                .onSuccess {
                    activeRoomByUser = it.first
                    currentSpeakers = it.second
                }
                .onFailure {
                    // Don't flicker online users to zero on transient mobile timeouts.
                }''',
"realtime P2P room activity")
sub(ui,
'''    val visibleMemberIds = if (commonRoomSelected) liveParticipants.map { it.identity }.toSet()
        else selectedRoomMembers''',
'''    val visibleMemberIds = if (commonRoomSelected)
        activeRoomByUser.filterValues { it == selectedRoomId }.keys +
            liveParticipants.map { it.identity }
        else selectedRoomMembers''',
"common room presence")
sub(ui,
'''    val selectedMemberCount = if (commonRoomSelected) {
        if (radioOn && liveStatus == "LIVE") liveParticipants.size else 0
    } else selectedRoomMembers.size''',
'''    val selectedMemberCount = if (commonRoomSelected) {
        activeRoomByUser.values.count { it == selectedRoomId }
    } else selectedRoomMembers.size''',
"common room count")
sub(ui,
'''                                Text("ORTAK KANAL • Üyelerin ortak alanı",''',
'''                                Text("ORTAK KANAL • Üyelerin ortak alanı",''',
"common room header") if False else None
# The common-room count is inside the room picker, not the signed-in member total.
common='''                                Text("ORTAK KANAL • Üyelerin ortak alanı",
'''
u=ui.read_text(encoding="utf-8")
if u.count(common)==1:
    u=u.replace(common,common+'''                                Text(
                                    "Şu anda aktif: " +
                                        activeRoomByUser.values.count { it == "ortak" },
                                    fontSize = 12.sp
                                )
''',1)
    ui.write_text(u,encoding="utf-8")
else:
    raise RuntimeError("Common room header changed")
sub(ui,
'''                                        Text(
                                            "Şu anda aktif: " +
                                                activeRoomByUser.values.count { it == item.roomId },
                                            fontSize = 12.sp
                                        )''',
'''                                        Text(
                                            "Şu anda aktif: " +
                                                activeRoomByUser.values.count { it == item.roomId },
                                            fontSize = 12.sp
                                        )
                                        val roomUsers = directory
                                            .filter { activeRoomByUser[it.userId] == item.roomId }
                                        if (roomUsers.isNotEmpty()) {
                                            Text(
                                                "Odada: " +
                                                    roomUsers.joinToString(", ") { it.fullName },
                                                fontSize = 12.sp,
                                                maxLines = 3
                                            )
                                            val speakingHere = roomUsers
                                                .filter { it.userId in currentSpeakers }
                                            if (speakingHere.isNotEmpty()) {
                                                Text(
                                                    "🎙 Konuşuyor: " +
                                                        speakingHere.joinToString(", ") { it.fullName },
                                                    fontSize = 12.sp,
                                                    fontWeight = FontWeight.Bold
                                                )
                                            }
                                        }''',
"room list speakers and presence")
sub(ui,
'''                                        (if (online) "🟢 " else "⚪ ") + member.fullName,''',
'''                                        (if (online) "🟢 " else "⚪ ") + member.fullName +
                                            (if (online && member.userId in currentSpeakers)
                                                " 🎙 KONUŞUYOR" else ""),''',
"visible live speaker on member list")

sub(p2p,
'''        if(!enabled) {forceMute();return true}''',
'''        if(!enabled) {
            forceMute()
            if(running) runCatching { presence("talk_off") }
            return true
        }''',
"talk-off signal")
sub(p2p,
'''        track?.setEnabled(true)
        return track?.enabled()==true''',
'''        track?.setEnabled(true)
        val ready=track?.enabled()==true
        if(ready) scope.launch { runCatching { presence("talk_on") } }
        return ready''',
"talk-on signal")
for file, required in [
 (p2p,["talk_on","talk_off","class P2pRadioClient","fun forceMute()"]),
 (room,["activeP2pRoomActivity","SessionRefresher","activeRoomByUser"]),
 (ui,["P2P BAĞLANIYOR","🎙 KONUŞUYOR","Şu anda aktif: ","onPtt(true)","onPtt(false)"]),
]:
 s=file.read_text(encoding="utf-8")
 for x in required:assert x in s, str(file)+" missing "+x
assert 'applicationId = "com.melehat.telsiz"' in Path("app/build.gradle.kts").read_text()
print("MELEHAT_1365_P2P_ROOM_ACTIVITY_AND_SPEAKING_READY")
