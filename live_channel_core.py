from pathlib import Path
import re
p=Path("app/src/main/java/com/saomi/telsiz/voice/LiveKitPttClient.kt")
s=p.read_text()
s=s.replace("private var connected = false","private var connected = false\n    private var lastProfile: UserProfile? = null\n    private var lastChannel: ChannelInfo? = null",1)
s=s.replace("suspend fun connect(profile: UserProfile, channel: ChannelInfo): Boolean {","suspend fun connect(profile: UserProfile, channel: ChannelInfo): Boolean {\n        lastProfile = profile\n        lastChannel = channel",1)
s=s.replace("fun isConnected(): Boolean = connected","suspend fun ensureConnected(): Boolean {\n        if (connected && room != null) return true\n        val p = lastProfile ?: return false\n        val c = lastChannel ?: return false\n        connected = false\n        room = null\n        return connect(p, c)\n    }\n\n    fun isConnected(): Boolean = connected",1)
p.write_text(s)

q=Path("app/src/main/java/com/saomi/telsiz/service/PttForegroundService.kt")
t=q.read_text()
t=t.replace("private var leaseJob: Job? = null","private var leaseJob: Job? = null\n    private var keepAliveJob: Job? = null",1)
needle="updateNotification(\n                        if (ok) \"Kanal dinlemede • Bas-konuş hazır\"\n                        else \"Ses sunucusu bağlantısı bekleniyor\"\n                    )"
repl=needle+"\n                    keepAliveJob?.cancel()\n                    keepAliveJob = scope.launch {\n                        while (started) {\n                            delay(5000)\n                            if (!ptt.isConnected()) ptt.ensureConnected()\n                        }\n                    }"
t=t.replace(needle,repl,1)
t=t.replace("started = false\n        store.setRadioEnabled(false)","started = false\n        keepAliveJob?.cancel()\n        keepAliveJob = null\n        store.setRadioEnabled(false)",1)
q.write_text(t)

u=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
v=u.read_text().replace("1.0 • v0.27 SES/PTT TEMELİ","1.1 • CANLI KANAL 1 • v0.27 SES/PTT")
u.write_text(v)

g=Path("app/build.gradle.kts")
w=g.read_text()
w=re.sub(r'versionCode\s*=\s*\d+','versionCode = 110',w,count=1)
w=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "1.1.0"',w,count=1)
g.write_text(w)
print("LIVE_CHANNEL_CORE_OK")
