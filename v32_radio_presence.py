from pathlib import Path
import re
p=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=p.read_text()
s=s.replace("V31 • v0.27 SES/PTT • CANLI ÜYELER","V32 • v0.27 SES/PTT • CANLI ÜYELER")
s=s.replace("MELEHAT TELSİZ V31","MELEHAT TELSİZ V32")
s=s.replace("RealMembersPanel(session)","RealMembersPanel(session, radioOn)")
s=s.replace("private fun RealMembersPanel(session: AuthSession?) {","private fun RealMembersPanel(session: AuthSession?, radioOn: Boolean) {")
s=s.replace("LaunchedEffect(session?.userId) {","LaunchedEffect(session?.userId, radioOn) {")
old='''        val active = session ?: return@LaunchedEffect
        while (true) {
            withContext(Dispatchers.IO) {
                runCatching {
'''
new='''        val active = session ?: return@LaunchedEffect
        if (!radioOn) {
            withContext(Dispatchers.IO) {
                runCatching {
                    val base = BuildConfig.SUPABASE_URL.trimEnd('/') + "/rest/v1/rpc/"
                    val body = "{}".toRequestBody("application/json".toMediaType())
                    val req = Request.Builder().url(base+"melehat_offline")
                        .addHeader("apikey",BuildConfig.SUPABASE_PUBLISHABLE_KEY)
                        .addHeader("Authorization","Bearer "+active.accessToken)
                        .addHeader("Content-Type","application/json").post(body).build()
                    client.newCall(req).execute().close()
                }
            }
        }
        while (radioOn) {
            withContext(Dispatchers.IO) {
                runCatching {
'''
if old not in s: raise SystemExit("presence loop anchor missing")
s=s.replace(old,new,1)
p.write_text(s)
b=Path("app/build.gradle.kts")
t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz.v32"',t,count=1)
t=re.sub(r'versionCode\s*=\s*\d+','versionCode = 3201',t,count=1)
t=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "32.1"',t,count=1)
b.write_text(t)
assert "RealMembersPanel(session, radioOn)" in s
assert "while (radioOn)" in s
assert "melehat_offline" in s
print("V32_RADIO_PRESENCE_READY")
