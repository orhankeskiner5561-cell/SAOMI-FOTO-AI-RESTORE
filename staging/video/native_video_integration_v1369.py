#!/usr/bin/env python3
# MELEHAT v1.3.69 native video-p2p rollout for 1:1 calls only.
# Keep original VideoCallActivity.kt, LiveKit video pipeline, two-person
# walkie-talkie, channel approvals, installed package and signing untouched.
from pathlib import Path
root=Path("app/src/main")
src=root/"java/com/saomi/telsiz"
api=src/"video/VideoCallApi.kt"
old=src/"video/VideoCallActivity.kt"
incoming=src/"video/IncomingVideoCallActivity.kt"
ui=src/"ui/AppRoot.kt"
manifest=root/"AndroidManifest.xml"
dest=src/"video/P2pVideoCallActivity.kt"
assert old.is_file() and incoming.is_file() and ui.is_file() and manifest.is_file()
assert not dest.exists(), "new P2P video activity already installed"
dest.write_text(Path("../staging/video/P2pVideoCallActivity.kt").read_text(encoding="utf-8"),encoding="utf-8")

def sub(path,old,new,label,expected=1):
 s=path.read_text(encoding="utf-8")
 if s.count(old)!=expected:
  raise RuntimeError(label+" expected "+str(expected)+" got "+str(s.count(old)))
 path.write_text(s.replace(old,new),encoding="utf-8")

sub(api,
'''    suspend fun credentials(callId: String): MelehatVideoCredentials {''',
'''    // Authenticated P2P signaling: never sends camera or microphone data
    // through the backend; only offer/answer SDP and ICE addresses.
    suspend fun videoExchange(
        callId:String, action:String, sdp:String?=null, revision:Int=0
    ):JSONObject {
        val data=JSONObject().put("p_call",callId).put("p_action",action)
            .put("p_revision",revision)
        if(sdp!=null)data.put("p_sdp",sdp)
        return JSONObject(post("/rest/v1/rpc/melehat_video_p2p_exchange",data))
    }

    suspend fun videoPresence(roomId:String, sessionId:String, active:Boolean):Boolean =
        rpc("melehat_video_online_presence_rpc",
            JSONObject().put("p_room",roomId)
                .put("p_session",sessionId)
                .put("p_active",active))=="true"

    suspend fun credentials(callId: String): MelehatVideoCredentials {''',
"video call secure signaling API")

# The old video implementation is left in place as source-level fallback,
# but new 1-to-1 invitations open the real Android WebRTC screen.
sub(incoming,"VideoCallActivity::class.java","P2pVideoCallActivity::class.java",
    "callee screen class")
sub(incoming,"VideoCallActivity.EXTRA_CALL_ID","P2pVideoCallActivity.EXTRA_CALL_ID",
    "callee call id")
sub(incoming,"VideoCallActivity.EXTRA_HOST","P2pVideoCallActivity.EXTRA_HOST",
    "callee host indicator")
sub(ui,"import com.saomi.telsiz.video.VideoCallActivity",
    "import com.saomi.telsiz.video.P2pVideoCallActivity","caller screen import")
sub(ui,"VideoCallActivity::class.java","P2pVideoCallActivity::class.java",
    "outgoing call screens",2)
sub(ui,"VideoCallActivity.EXTRA_CALL_ID","P2pVideoCallActivity.EXTRA_CALL_ID",
    "outgoing call ids",2)
sub(ui,"VideoCallActivity.EXTRA_HOST","P2pVideoCallActivity.EXTRA_HOST",
    "outgoing host flags",2)

sub(manifest,
'''        <activity
            android:name="com.saomi.telsiz.video.VideoCallActivity"
            android:exported="false"
            android:screenOrientation="portrait" />''',
'''        <activity
            android:name="com.saomi.telsiz.video.VideoCallActivity"
            android:exported="false"
            android:screenOrientation="portrait" />
        <activity
            android:name="com.saomi.telsiz.video.P2pVideoCallActivity"
            android:exported="false"
            android:screenOrientation="portrait" />''',
"declare secured P2P video Activity")

assert "P2pVideoCallActivity::class.java" in ui.read_text()
assert "P2pVideoCallActivity::class.java" in incoming.read_text()
assert "class VideoCallActivity : ComponentActivity()" in old.read_text()
for word in ["onPtt(true)","onPtt(false)","activeP2pRoomActivity",
             "MELEHAT_UPDATE_MANIFEST","LastRoomPreference","roomApi.listRequests"]:
 assert word in ui.read_text(),word
assert "class P2pVideoCallActivity" in dest.read_text()
assert 'applicationId = "com.melehat.telsiz"' in Path("app/build.gradle.kts").read_text()
print("MELEHAT_1369_DIRECT_P2P_VIDEO_AND_PRESENCE_READY")
