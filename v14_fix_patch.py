from pathlib import Path

# Compatibility for the old deep-link handler still present in MainActivity.
auth=Path("app/src/main/java/com/saomi/telsiz/auth/SupabaseAuthClient.kt")
s=auth.read_text()
if "import android.net.Uri" not in s:
    s=s.replace("package com.saomi.telsiz.auth\n\n","package com.saomi.telsiz.auth\n\nimport android.net.Uri\n")
if "fun sessionFromMagicLink" not in s:
    marker="    suspend fun verifyEmailOtp(phone: String, email: String, code: String): Result<AuthSession> ="
    compat='''    fun sessionFromMagicLink(uri: Uri, phone: String, fallbackEmail: String): Result<AuthSession> =
        Result.failure(IllegalStateException("Bu sürüm 6 haneli e-posta kodu kullanıyor."))

'''
    if marker not in s: raise SystemExit("verifyEmailOtp marker not found")
    s=s.replace(marker,compat+marker,1)
auth.write_text(s)

# Repair a literal backslash-n accidentally introduced by the patch generator.
ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=ui.read_text()
s=s.replace('otpSent = false\\n                    otpCode = \\\"\\\"','otpSent = false\n                    otpCode = ""')
ui.write_text(s)

print("v0.14 compile fixes applied")
