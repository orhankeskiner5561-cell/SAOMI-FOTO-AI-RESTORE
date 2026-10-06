from pathlib import Path
import re

# C59: legacy v0.27 peers do not heartbeat. Treat a real LiveKit remote participant
# as online and surface that state to the UI.
lk=Path("app/src/main/java/com/saomi/telsiz/voice/LiveKitPttClient.kt")
s=lk.read_text()
# expose connected remote identities from the actual room
insert='''

    fun connectedRemoteIdentities(): Set<String> =
        room?.remoteParticipants?.values
            ?.map { it.identity.toString() }
            ?.toSet()
            ?: emptySet()
'''
pos=s.rfind("\n}")
if "connectedRemoteIdentities" not in s:
    s=s[:pos]+insert+s[pos:]
lk.write_text(s)

# Service broadcasts real room presence so legacy clients count as active.
svc=Path("app/src/main/java/com/saomi/telsiz/service/PttForegroundService.kt")
u=svc.read_text()
# helper broadcaster
pos=u.rfind("\n}")
helper='''

    private fun broadcastLiveKitPresence() {
        val ids = ptt.connectedRemoteIdentities().joinToString(",")
        sendBroadcast(Intent("com.saomi.telsiz.LIVEKIT_PRESENCE").apply {
            setPackage(packageName)
            putExtra("remote_ids", ids)
        })
    }
'''
if "broadcastLiveKitPresence" not in u:
    u=u[:pos]+helper+u[pos:]
# broadcast after successful connect paths
u=u.replace('updateNotification("Hazır")','updateNotification("Hazır")\n            broadcastLiveKitPresence()')
u=u.replace('updateNotification("Bas konuş hazır")','updateNotification("Bas konuş hazır")\n            broadcastLiveKitPresence()')
svc.write_text(u)

ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
v=ui.read_text()
if "legacyLiveIds" not in v:
    v=v.replace("    var showMembers by remember { mutableStateOf(false) }","    var showMembers by remember { mutableStateOf(false) }\n    var legacyLiveIds by remember { mutableStateOf<Set<String>>(emptySet()) }")
    # Receiver imports
    for imp in ["import android.content.BroadcastReceiver","import android.content.Context","import android.content.IntentFilter"]:
        if imp not in v:
            p=v.find("\n",v.find("package "))
            v=v[:p+1]+imp+"\n"+v[p+1:]
    marker="    LaunchedEffect(session?.userId) {"
    receiver='''    DisposableEffect(Unit) {
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(c: Context?, intent: Intent?) {
                val raw = intent?.getStringExtra("remote_ids").orEmpty()
                legacyLiveIds = raw.split(",").filter { it.isNotBlank() }.toSet()
            }
        }
        context.registerReceiver(receiver, IntentFilter("com.saomi.telsiz.LIVEKIT_PRESENCE"), Context.RECEIVER_NOT_EXPORTED)
        onDispose { runCatching { context.unregisterReceiver(receiver) } }
    }

'''
    v=v.replace(marker,receiver+marker,1)
# Legacy participant identity is user UUID; combine heartbeat + actual room presence.
v=v.replace("if (m.online) Color(0xFF34C759) else Color.Gray","if (m.online || legacyLiveIds.contains(m.id)) Color(0xFF34C759) else Color.Gray")
v=v.replace('if (m.online) "Aktif" else "Çevrimdışı"','if (m.online || legacyLiveIds.contains(m.id)) "Aktif" else "Çevrimdışı"')
v=v.replace("C58 • v0.27 Uyumlu Yeniden Bağlanma","C59 • v0.27 Canlı Durum Uyumlu")
v=v.replace("MELEHAT TELSİZ C58","MELEHAT TELSİZ C59")
ui.write_text(v)

b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz.c59"',t,count=1)
t=re.sub(r'versionCode\s*=\s*\d+','versionCode = 59',t,count=1)
t=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "C59"',t,count=1)
b.write_text(t)
print("C59 legacy LiveKit presence compatibility applied")
