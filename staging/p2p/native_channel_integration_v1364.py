#!/usr/bin/env python3
from pathlib import Path
root=Path("app/src/main/java/com/saomi/telsiz")
p2p=root/"p2p"
voice=root/"voice"
service=root/"service/PttForegroundService.kt"
ui=root/"ui/AppRoot.kt"
p2p.mkdir(exist_ok=True)
assert (p2p/"MelehatP2pActivity.kt").exists(), "Expected current v1.3.63 Android source"
for filename in ("P2pRadioClient.kt","HybridRadioClient.kt"):
    source=Path("../staging/p2p")/filename
    assert source.is_file(),str(source)
    dest=p2p/filename
    assert not dest.exists(), "Refusing to overwrite "+str(dest)
    dest.write_text(source.read_text(encoding="utf-8"),encoding="utf-8")

s=service.read_text(encoding="utf-8")
def replace_exact(s,old,new,desc):
    n=s.count(old)
    if n!=1:raise RuntimeError(desc+" expected 1 match but found "+str(n))
    return s.replace(old,new,1)
s=replace_exact(s,
    "import com.saomi.telsiz.voice.LiveKitPttClient",
    "import com.saomi.telsiz.p2p.HybridRadioClient",
    "radio service import")
s=replace_exact(s,
    "    private lateinit var ptt: LiveKitPttClient",
    "    private lateinit var ptt: HybridRadioClient",
    "radio transport type")
s=replace_exact(s,
    "        ptt = LiveKitPttClient(applicationContext)",
    "        ptt = HybridRadioClient(applicationContext)",
    "radio transport initialize")
# The existing release watchdog stays in charge of all native/external
# PTT. Always mute synchronously upon UP before any floor lease RPC.
s=replace_exact(s,
'''            ACTION_PTT_UP -> {
                val wasExternal''',
'''            ACTION_PTT_UP -> {
                ptt.forceMute()
                val wasExternal''',
"instant microphone release")
s=replace_exact(s,
'''            ACTION_STOP -> {
                if (rawPttEnabled)''',
'''            ACTION_STOP -> {
                ptt.forceMute()
                if (rawPttEnabled)''',
"instant radio stop mute")
s=replace_exact(s,
'''            ACTION_SWITCH_ROOM -> {
                if (rawPttEnabled)''',
'''            ACTION_SWITCH_ROOM -> {
                ptt.forceMute()
                if (rawPttEnabled)''',
"instant room-switch mute")
s=replace_exact(s,
'''        pttHeld = false
        transmitting = false
        leaseJob?.cancel()''',
'''        ptt.forceMute()
        pttHeld = false
        transmitting = false
        leaseJob?.cancel()''',
"endTransmit safety")
service.write_text(s,encoding="utf-8")

u=ui.read_text(encoding="utf-8")
old='''                    // Isolated in-app WebRTC pilot: original PTT and LiveKit remain unchanged.
                    TextButton(onClick = {
                        roomsContext.startActivity(
                            android.content.Intent(
                                roomsContext,
                                com.saomi.telsiz.p2p.MelehatP2pActivity::class.java
                            )
                        )
                    }) {
                        Text("P2P SES • DOĞRUDAN GÖRÜŞME", fontWeight = FontWeight.SemiBold)
                    }
'''
replacement='''                    // Main-channel microphone now uses the real native P2P engine.
                    // The separate test page is no longer the radio voice path.
                    Text(
                        "BAĞLANTI: YEREL P2P • ANA BAS KONUŞ",
                        color = Color(0xFF206E50),
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold
                    )
'''
u=replace_exact(u,old,replacement,"remove obsolete embedded browser test entry")
u=replace_exact(u,
'''                        .pointerInput(radioOn) {
                            detectTapGestures(onPress = {
                                if (!radioOn) return@detectTapGestures''',
'''                        .pointerInput(radioOn, liveStatus) {
                            detectTapGestures(onPress = {
                                if (!radioOn || liveStatus != "LIVE") return@detectTapGestures''',
"only turn on mic on actual P2P connection")
u=replace_exact(u,
'''                                    !radioOn -> "TELSİZ KAPALI"
                                    transmitting -> "SES GİDİYOR"
                                    else -> "BAS KONUŞ"''',
'''                                    !radioOn -> "TELSİZ KAPALI"
                                    liveStatus != "LIVE" -> "P2P BAĞLANIYOR"
                                    transmitting -> "SES GİDİYOR"
                                    else -> "BAS KONUŞ"''',
"live PTT button status")
assert "onPtt(true)" in u and "onPtt(false)" in u
assert "MELEHAT_UPDATE_MANIFEST" in u
assert 'P2P SES • DOĞRUDAN GÖRÜŞME' not in u
ui.write_text(u,encoding="utf-8")

# Keep the full legacy LiveKitPttClient.kt unchanged.
assert (voice/"LiveKitPttClient.kt").exists()
assert "MELEHAT_1364" not in (voice/"LiveKitPttClient.kt").read_text()
# Signing/package values remain untouched in this stage.
gradle=Path("app/build.gradle.kts").read_text()
assert 'applicationId = "com.melehat.telsiz"' in gradle
manifest=Path("app/src/main/AndroidManifest.xml").read_text()
assert 'android.permission.RECORD_AUDIO' in manifest
print("MELEHAT_1364_NATIVE_MAIN_PTT_P2P_WIRED")
