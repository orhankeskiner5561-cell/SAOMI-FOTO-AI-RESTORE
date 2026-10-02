from pathlib import Path
import re

auth = Path("app/src/main/java/com/saomi/telsiz/auth/SupabaseAuthClient.kt")
auth.write_text(r'''package com.saomi.telsiz.auth

import com.saomi.telsiz.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

class EmailRateLimitException(val retryAfterSeconds: Int) : Exception("E-posta gönderim sınırı")

class SupabaseAuthClient {
    private val http = OkHttpClient()
    private val json = "application/json; charset=utf-8".toMediaType()
    private fun base() = BuildConfig.SUPABASE_URL.trimEnd('/')
    private fun key() = BuildConfig.SUPABASE_PUBLISHABLE_KEY

    suspend fun sendEmailOtp(email: String): Result<Unit> = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("email", email.trim().lowercase())
            .put("create_user", true)
            .toString()
            .toRequestBody(json)

        val request = Request.Builder()
            .url(base() + "/auth/v1/otp")
            .addHeader("apikey", key())
            .addHeader("Authorization", "Bearer " + key())
            .post(body)
            .build()

        runCatching {
            http.newCall(request).execute().use { response ->
                val raw = response.body?.string().orEmpty()
                if (!response.isSuccessful) {
                    if (response.code == 429) {
                        val retry = response.header("Retry-After")?.trim()?.toIntOrNull()
                            ?: response.header("X-RateLimit-Reset")?.trim()?.toLongOrNull()?.let { reset ->
                                ((reset * 1000L - System.currentTimeMillis()) / 1000L).toInt().coerceAtLeast(1)
                            }
                            ?: 300
                        throw EmailRateLimitException(retry.coerceIn(1, 3600))
                    }
                    error("Kod gönderilemedi: " + response.code + " " + raw.take(160))
                }
            }
        }
    }

    suspend fun verifyEmailOtp(phone: String, email: String, code: String): Result<AuthSession> =
        withContext(Dispatchers.IO) {
            val body = JSONObject()
                .put("email", email.trim().lowercase())
                .put("token", code.trim())
                .put("type", "email")
                .toString()
                .toRequestBody(json)

            val request = Request.Builder()
                .url(base() + "/auth/v1/verify")
                .addHeader("apikey", key())
                .addHeader("Authorization", "Bearer " + key())
                .post(body)
                .build()

            runCatching {
                http.newCall(request).execute().use { response ->
                    val raw = response.body?.string().orEmpty()
                    if (!response.isSuccessful) error("Güvenlik kodu doğrulanamadı: " + response.code)
                    val obj = JSONObject(raw)
                    val user = obj.optJSONObject("user")
                    AuthSession(
                        accessToken = obj.getString("access_token"),
                        refreshToken = obj.optString("refresh_token"),
                        userId = user?.optString("id").orEmpty(),
                        phone = phone.trim(),
                        email = user?.optString("email").orEmpty().ifBlank { email.trim().lowercase() }
                    )
                }
            }
        }
}
''')

ui = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = ui.read_text()

if "import kotlinx.coroutines.delay" not in s:
    s = s.replace("import kotlinx.coroutines.launch\n", "import kotlinx.coroutines.launch\nimport kotlinx.coroutines.delay\n")
if "EmailRateLimitException" not in s:
    s = s.replace(
        "import com.saomi.telsiz.auth.SupabaseAuthClient\n",
        "import com.saomi.telsiz.auth.SupabaseAuthClient\nimport com.saomi.telsiz.auth.EmailRateLimitException\n"
    )

s = s.replace(
'''    var linkSent by remember { mutableStateOf(false) }
    var authMessage by remember { mutableStateOf("") }
''',
'''    var otpSent by remember { mutableStateOf(false) }
    var otpCode by remember { mutableStateOf("") }
    var authMessage by remember { mutableStateOf("") }
    val cooldownPrefs = remember {
        context.getSharedPreferences("melehat_mail_cooldown", android.content.Context.MODE_PRIVATE)
    }
    var resendSeconds by remember {
        val until = cooldownPrefs.getLong("until_ms", 0L)
        mutableStateOf(((until - System.currentTimeMillis()) / 1000L).toInt().coerceAtLeast(0))
    }
    var cooldownFinished by remember {
        mutableStateOf(resendSeconds == 0 && cooldownPrefs.getLong("until_ms", 0L) > 0L)
    }
''', 1)

needle = '''    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        uri?.let { photoUri = it.toString() }
    }

'''
insert = needle + '''    LaunchedEffect(resendSeconds) {
        if (resendSeconds > 0) {
            delay(1000)
            resendSeconds -= 1
            if (resendSeconds == 0) {
                cooldownFinished = true
                cooldownPrefs.edit().remove("until_ms").apply()
            }
        }
    }

'''
if needle not in s: raise SystemExit("picker block not found")
s = s.replace(needle, insert, 1)

s = s.replace(
    'Text("v0.10 • E-posta bağlantısı • Profil • Kanal • PTT", style = MaterialTheme.typography.bodySmall)',
    'Text("v0.14 • 6 Haneli E-posta Kodu • Profil • Kanal • PTT", style = MaterialTheme.typography.bodySmall)'
)
s = s.replace(
    'Text("Telefon numaranızı ve e-postanızı girin. E-postaya gelen güvenli giriş bağlantısına dokunun.")',
    'Text("Telefon numaranızı ve e-postanızı girin. E-postanıza gelen 6 haneli güvenlik kodunu aşağıya yazın.")'
)

old = '''                Button(
                    onClick = {
                        scope.launch {
                            authMessage = "Gönderiliyor…"
                            sessionStore.savePending(loginPhone, loginEmail)
                            auth.sendMagicLink(loginEmail)
                                .onSuccess {
                                    linkSent = true
                                    authMessage = "Giriş bağlantısı e-postanıza gönderildi. Maildeki bağlantıya dokunun; MELEHAT TELSİZ otomatik açılır."
                                }
                                .onFailure { authMessage = it.message.orEmpty() }
                        }
                    },
                    enabled = loginPhone.isNotBlank() && loginEmail.contains("@"),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(if (linkSent) "Bağlantıyı Tekrar Gönder" else "E-postaya Giriş Bağlantısı Gönder")
                }

                if (linkSent) {
                    Text(
                        "Bağlantıyı aynı telefondan açın. Doğrulama tamamlanınca uygulama doğrudan hesabınıza döner.",
                        style = MaterialTheme.typography.bodySmall
                    )
                }

'''
new = '''                if (otpSent) {
                    OutlinedTextField(
                        value = otpCode,
                        onValueChange = { otpCode = it.filter(Char::isDigit).take(6) },
                        label = { Text("6 haneli güvenlik kodu") },
                        supportingText = { Text("E-postadaki 6 rakamı buraya yazın") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )

                    Button(
                        onClick = {
                            scope.launch {
                                authMessage = "Kod kontrol ediliyor…"
                                auth.verifyEmailOtp(loginPhone, loginEmail, otpCode)
                                    .onSuccess { verified ->
                                        backend.fetchMyProfile(verified)
                                            .onSuccess { existing ->
                                                if (existing != null && existing.phone.isNotBlank() &&
                                                    normalizePhone(existing.phone) != normalizePhone(loginPhone)) {
                                                    sessionStore.clear()
                                                    authMessage = "Bu e-posta başka bir telefon numarasıyla kayıtlı."
                                                } else {
                                                    sessionStore.save(verified)
                                                    session = verified
                                                    if (existing != null) {
                                                        localStore.saveProfile(existing)
                                                        profile = existing
                                                        fullName = existing.fullName
                                                        photoUri = existing.photoUri
                                                    } else {
                                                        val fresh = UserProfile(
                                                            phone = loginPhone.trim(),
                                                            email = loginEmail.trim().lowercase(),
                                                            fullName = "",
                                                            photoUri = ""
                                                        )
                                                        localStore.saveProfile(fresh)
                                                        profile = fresh
                                                    }
                                                    authMessage = "Hesap doğrulandı."
                                                }
                                            }
                                            .onFailure { authMessage = it.message.orEmpty() }
                                    }
                                    .onFailure {
                                        authMessage = "Kod yanlış veya süresi dolmuş. E-postadaki son 6 haneli kodu kontrol edin."
                                    }
                            }
                        },
                        enabled = otpCode.length == 6,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text("Hesabı Doğrula")
                    }
                }

                val canSend = loginPhone.isNotBlank() && loginEmail.contains("@") && resendSeconds == 0

                Button(
                    onClick = {
                        scope.launch {
                            cooldownFinished = false
                            authMessage = "Kod gönderiliyor…"
                            auth.sendEmailOtp(loginEmail)
                                .onSuccess {
                                    otpSent = true
                                    otpCode = ""
                                    resendSeconds = 60
                                    cooldownPrefs.edit()
                                        .putLong("until_ms", System.currentTimeMillis() + 60000L)
                                        .apply()
                                    authMessage = "6 haneli güvenlik kodu e-postanıza gönderildi."
                                }
                                .onFailure { error ->
                                    if (error is EmailRateLimitException) {
                                        val wait = error.retryAfterSeconds
                                        resendSeconds = wait
                                        cooldownPrefs.edit()
                                            .putLong("until_ms", System.currentTimeMillis() + wait * 1000L)
                                            .apply()
                                        authMessage = "E-posta gönderim sınırı aktif. Sayaç Supabase süresine göre ayarlandı."
                                    } else {
                                        authMessage = "Kod gönderilemedi. İnternet bağlantınızı kontrol edip tekrar deneyin."
                                    }
                                }
                        }
                    },
                    enabled = canSend,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = when {
                            resendSeconds > 0 -> Color(0xFFBDBDBD)
                            cooldownFinished -> Color(0xFF2E7D32)
                            else -> MaterialTheme.colorScheme.primary
                        },
                        disabledContainerColor = Color(0xFFBDBDBD)
                    ),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        when {
                            resendSeconds > 0 -> "Tekrar göndermek için " + resendSeconds + " sn"
                            cooldownFinished -> "Süre doldu, tekrar deneyin"
                            otpSent -> "Yeni Kod Gönder"
                            else -> "E-postaya 6 Haneli Kod Gönder"
                        }
                    )
                }

                if (otpSent) {
                    Text(
                        "Maildeki bağlantıya basmanız gerekmez. Yalnızca 6 haneli güvenlik kodunu okuyup yukarıdaki kutuya yazın.",
                        style = MaterialTheme.typography.bodySmall
                    )
                }

'''
if old not in s: raise SystemExit("magic-link login block not found")
s = s.replace(old, new, 1)

s = s.replace("linkSent = false", "otpSent = false\\n                    otpCode = \\\"\\\"")\ns = s.replace("MELEHAT TELSİZ v0.10", "MELEHAT TELSİZ v0.14")
s = s.replace("• E-posta güvenli giriş bağlantısı", "• E-postaya 6 haneli güvenlik kodu")
s = s.replace("• Yeni telefonda aynı e-postaya yeni bağlantı gönderilir", "• Yeni telefonda aynı e-postaya yeni 6 haneli kod gönderilir")

ui.write_text(s)

b = Path("app/build.gradle.kts")
t = b.read_text().replace("versionCode = 10", "versionCode = 14").replace('versionName = "0.10.0"', 'versionName = "0.14.0"')
b.write_text(t)

print("v0.14 six-digit email OTP patch applied")
