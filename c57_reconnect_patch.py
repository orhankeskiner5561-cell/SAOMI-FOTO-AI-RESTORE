from pathlib import Path
import re

# C57: refresh stale auth before presence calls and retry once after refresh.
p=Path("app/src/main/java/com/saomi/telsiz/data/MemberStatusApi.kt")
s=p.read_text()
if "SessionRefresher" not in s:
    s=s.replace("import com.saomi.telsiz.auth.AuthSession","import com.saomi.telsiz.auth.AuthSession\nimport com.saomi.telsiz.auth.SessionRefresher")
# This API currently has no Context; keep network retry in AppRoot using existing SessionRefresher.
p.write_text(s)

ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
u=ui.read_text()
if "import com.saomi.telsiz.auth.SessionRefresher" not in u:
    u=u.replace("import com.saomi.telsiz.data.SessionStore","import com.saomi.telsiz.data.SessionStore\nimport com.saomi.telsiz.auth.SessionRefresher")
u=u.replace("    val memberApi = remember { MemberStatusApi() }","    val memberApi = remember { MemberStatusApi() }\n    val sessionRefresher = remember { SessionRefresher(context) }")
old='''        val current = session ?: return@LaunchedEffect
        while (true) {
            memberApi.heartbeat(current)
            members = memberApi.members(current)
            delay(30000)
        }'''
new='''        while (true) {
            val current = sessionRefresher.refresh() ?: session ?: return@LaunchedEffect
            memberApi.heartbeat(current)
            val freshMembers = memberApi.members(current)
            if (freshMembers.isNotEmpty()) members = freshMembers
            delay(30000)
        }'''
if old not in u: raise SystemExit("presence loop marker missing")
u=u.replace(old,new,1)
u=u.replace("C56 • PTT + Otomatik Güncelleme","C57 • PTT + Otomatik Yeniden Bağlanma")
u=u.replace("MELEHAT TELSİZ C56","MELEHAT TELSİZ C57")
ui.write_text(u)

b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz.c57"',t,count=1)
t=re.sub(r'versionCode\s*=\s*\d+','versionCode = 57',t,count=1)
t=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "C57"',t,count=1)
b.write_text(t)
print("C57 stale-session recovery patch applied")
