from pathlib import Path
import re

auth=Path("app/src/main/java/com/saomi/telsiz/auth/SupabaseAuthClient.kt")
s=auth.read_text()

if "class EmailRateLimitException" not in s:
    s=s.replace("class SupabaseAuthClient {", """class EmailRateLimitException(val retryAfterSeconds:Int): Exception("429 email rate limit")

class SupabaseAuthClient {""")

pattern=r'''    suspend fun sendMagicLink\(email:String\):Result<Unit> = withContext\(Dispatchers\.IO\)\{.*?\n    \}\n\n    fun sessionFromMagicLink'''
replacement='''    suspend fun sendMagicLink(email:String):Result<Unit> = withContext(Dispatchers.IO){
        if(!isConfigured()) return@withContext Result.failure(IllegalStateException("Supabase bağlantısı henüz yapılandırılmadı."))
        val redirect=URLEncoder.encode("melehat://auth-callback","UTF-8")
        val body=JSONObject().put("email",email.trim().lowercase()).put("create_user",true).toString().toRequestBody(json)
        val request=Request.Builder().url("\${base()}/auth/v1/otp?redirect_to=\$redirect").addHeader("apikey",key()).addHeader("Authorization","Bearer \${key()}").post(body).build()
        runCatching {
            http.newCall(request).execute().use { resp ->
                val raw = resp.body?.string().orEmpty()
                if (!resp.isSuccessful) {
                    if (resp.code == 429) {
                        val retry = resp.header("Retry-After")?.trim()?.toIntOrNull()
                            ?: resp.header("X-RateLimit-Reset")?.trim()?.toLongOrNull()?.let { reset ->
                                ((reset * 1000L - System.currentTimeMillis()) / 1000L).toInt().coerceAtLeast(1)
                            }
                            ?: 300
                        throw EmailRateLimitException(retry.coerceIn(1, 3600))
                    }
                    error("Onay bağlantısı gönderilemedi: \${resp.code} \${raw.take(160)}")
                }
            }
        }
    }

    fun sessionFromMagicLink'''
s2,n=re.subn(pattern,replacement,s,count=1,flags=re.S)
if n!=1:
    raise SystemExit("sendMagicLink function not found")
auth.write_text(s2)

ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=ui.read_text()
if "EmailRateLimitException" not in s:
    s=s.replace("import com.saomi.telsiz.auth.SupabaseAuthClient\n","import com.saomi.telsiz.auth.SupabaseAuthClient\nimport com.saomi.telsiz.auth.EmailRateLimitException\n")

s=s.replace("v0.12 •","v0.13 •").replace("MELEHAT TELSİZ v0.12","MELEHAT TELSİZ v0.13")

old='''    var resendSeconds by remember { mutableStateOf(0) }
    var cooldownFinished by remember { mutableStateOf(false) }
'''
new='''    val cooldownPrefs = remember { context.getSharedPreferences("melehat_mail_cooldown", android.content.Context.MODE_PRIVATE) }
    var resendSeconds by remember {
        val until = cooldownPrefs.getLong("until_ms", 0L)
        mutableStateOf(((until - System.currentTimeMillis()) / 1000L).toInt().coerceAtLeast(0))
    }
    var cooldownFinished by remember { mutableStateOf(resendSeconds == 0 && cooldownPrefs.getLong("until_ms", 0L) > 0L) }
'''
if old not in s: raise SystemExit("cooldown state pattern not found")
s=s.replace(old,new,1)

s=s.replace(
'''                                    linkSent = true
                                    resendSeconds = 60
                                    authMessage = "Giriş bağlantısı e-postanıza gönderildi. Maildeki bağlantıya dokunun; MELEHAT TELSİZ otomatik açılır."''',
'''                                    linkSent = true
                                    resendSeconds = 60
                                    cooldownPrefs.edit().putLong("until_ms", System.currentTimeMillis() + 60_000L).apply()
                                    authMessage = "Giriş bağlantısı e-postanıza gönderildi. Maildeki bağlantıya dokunun; MELEHAT TELSİZ otomatik açılır."''',1)

old='''                                    val raw = error.message.orEmpty()
                                    if (raw.contains("429") || raw.contains("rate limit", ignoreCase = true) || raw.contains("over_email_send_rate_limit")) {
                                        resendSeconds = 60
                                        authMessage = "Çok fazla deneme yapıldı. Yeni bağlantı istemeden kısa süre bekleyin."
                                    } else {'''
new='''                                    val raw = error.message.orEmpty()
                                    if (error is EmailRateLimitException || raw.contains("429") || raw.contains("rate limit", ignoreCase = true) || raw.contains("over_email_send_rate_limit")) {
                                        val wait = (error as? EmailRateLimitException)?.retryAfterSeconds ?: 300
                                        resendSeconds = wait
                                        cooldownPrefs.edit().putLong("until_ms", System.currentTimeMillis() + wait * 1000L).apply()
                                        authMessage = "Supabase yeni e-posta için bekleme süresi uyguladı. Sayaç bu süreye göre ayarlandı."
                                    } else {'''
if old not in s: raise SystemExit("429 handler pattern not found")
s=s.replace(old,new,1)

old='''            if (resendSeconds == 0) cooldownFinished = true'''
new='''            if (resendSeconds == 0) {
                cooldownFinished = true
                cooldownPrefs.edit().remove("until_ms").apply()
            }'''
if old not in s: raise SystemExit("countdown finish pattern not found")
s=s.replace(old,new,1)

s=s.replace('''                    resendSeconds = 0
                    cooldownFinished = false
                    authMessage = ""''','''                    resendSeconds = 0
                    cooldownFinished = false
                    cooldownPrefs.edit().remove("until_ms").apply()
                    authMessage = ""''',1)
ui.write_text(s)

b=Path("app/build.gradle.kts")
s=b.read_text().replace("versionCode = 12","versionCode = 13").replace('versionName = "0.12.0"','versionName = "0.13.0"')
b.write_text(s)
print("v0.13 Supabase-synced cooldown patch applied")
