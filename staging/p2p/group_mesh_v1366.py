#!/usr/bin/env python3
# MELEHAT v1.3.66 group mesh opt-in and safe two-person fallback.
# Existing P2pRadioClient (proven 2-party) and all LiveKit/video code kept.
from pathlib import Path
root=Path("app/src/main/java/com/saomi/telsiz")
p2p=root/"p2p"
mesh=p2p/"P2pMeshRadioClient.kt"
assert not mesh.exists(),"Group engine already exists"
mesh.write_text(Path("../staging/p2p/P2pMeshRadioClient.kt").read_text(encoding="utf-8"),
                encoding="utf-8")
hybrid=p2p/"HybridRadioClient.kt"
ui=root/"ui/AppRoot.kt"
def exactly(path,old,new):
 s=path.read_text(encoding="utf-8")
 assert s.count(old)==1,f"{path.name}: expected one anchor {old[:90]}, got {s.count(old)}"
 path.write_text(s.replace(old,new,1),encoding="utf-8")

# Keep a reliable two-person fallback selectable from the main screen.
hybrid.write_text(r'''package com.saomi.telsiz.p2p

import android.content.Context
import com.saomi.telsiz.model.ChannelInfo
import com.saomi.telsiz.model.UserProfile
import com.saomi.telsiz.voice.LiveKitPttClient

/**
 * Group mode can be switched OFF while radio is stopped. Keeps the tested
 * two-person P2P path and the original LiveKit class for source rollback.
 */
class HybridRadioClient(context:Context){
    private val duo=P2pRadioClient(context.applicationContext)
    private val group=P2pMeshRadioClient(context.applicationContext)
    private val legacy=LiveKitPttClient(context.applicationContext)
    private val prefs=context.getSharedPreferences(
        "melehat_p2p_transport",Context.MODE_PRIVATE)
    private var useP2p=true
    private var useGroup=false

    suspend fun connect(profile:UserProfile,channel:ChannelInfo):Boolean {
        val p2p=prefs.getBoolean("native_p2p_enabled",true)
        val mesh=prefs.getBoolean("p2p_mesh_enabled",false)
        if(p2p!=useP2p||mesh!=useGroup) {
            group.disconnect()
            duo.disconnect()
            legacy.disconnect()
        }
        useP2p=p2p;useGroup=mesh
        return when {
            !useP2p->legacy.connect(profile,channel)
            useGroup->group.connect(profile,channel)
            else->duo.connect(profile,channel)
        }
    }
    suspend fun ensureConnected():Boolean=when {
        !useP2p->legacy.ensureConnected()
        useGroup->group.ensureConnected()
        else->duo.ensureConnected()
    }
    suspend fun setTransmitting(enabled:Boolean):Boolean=when {
        !useP2p->legacy.setTransmitting(enabled)
        useGroup->group.setTransmitting(enabled)
        else->duo.setTransmitting(enabled)
    }
    fun forceMute() {
        if(useP2p) {
            group.forceMute()
            duo.forceMute()
        }
    }
    fun isConnected():Boolean=when{
        !useP2p->legacy.isConnected()
        useGroup->group.isConnected()
        else->duo.isConnected()
    }
    fun isConnectedTo(roomId:String):Boolean=when{
        !useP2p->legacy.isConnectedTo(roomId)
        useGroup->group.isConnectedTo(roomId)
        else->duo.isConnectedTo(roomId)
    }
    suspend fun disconnect(){
        group.disconnect()
        duo.disconnect()
        legacy.disconnect()
    }
}
''',encoding="utf-8")

exactly(ui,
'''    val roomApi = remember(roomsContext) { MelehatRoomApi(roomsContext) }''',
'''    val roomApi = remember(roomsContext) { MelehatRoomApi(roomsContext) }
    val transportPrefs = remember(roomsContext) {
        roomsContext.getSharedPreferences(
            "melehat_p2p_transport", android.content.Context.MODE_PRIVATE)
    }
    var p2pGroupEnabled by remember {
        mutableStateOf(transportPrefs.getBoolean("p2p_mesh_enabled", false))
    }''')
exactly(ui,
'''                    Text(
                        "BAĞLANTI: YEREL P2P • ANA BAS KONUŞ",
                        color = Color(0xFF206E50),
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold
                    )''',
'''                    Text(
                        "BAĞLANTI: YEREL P2P • ANA BAS KONUŞ",
                        color = Color(0xFF206E50),
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                    TextButton(
                        enabled = !radioOn,
                        onClick = {
                            p2pGroupEnabled = !p2pGroupEnabled
                            transportPrefs.edit()
                                .putBoolean("p2p_mesh_enabled",p2pGroupEnabled)
                                .apply()
                        }
                    ) {
                        Text(
                            if (p2pGroupEnabled)
                                "ÇOKLU P2P AÇIK • EN FAZLA 4 ÜYE"
                            else "2 KİŞİLİ P2P • ÇOKLU MODU AÇ",
                            fontSize=12.sp
                        )
                    }
                    if (radioOn) {
                        Text(
                            "Çoklu modu değiştirmek için önce telsizi kapatın.",
                            fontSize=11.sp
                        )
                    }''')
assert 'onPtt(true)' in ui.read_text()
assert 'onPtt(false)' in ui.read_text()
assert 'applicationId = "com.melehat.telsiz"' in Path("app/build.gradle.kts").read_text()
for protected in ["LiveKitPttClient.kt","RoomTokenClient.kt"]:
 assert (root/"voice"/protected).exists()
for item in ("P2pRadioClient.kt","P2pMeshRadioClient.kt","HybridRadioClient.kt"):
 assert (p2p/item).stat().st_size>500
print("MELEHAT_1366_OPTIONAL_FOUR_USER_P2P_MESH_READY")
