from pathlib import Path

p=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=p.read_text()

s=s.replace(
'''onValueChange = { otpCode = it.filter(Char::isDigit).take(6) },''',
'''onValueChange = { otpCode = it.filter(Char::isDigit).take(8) },'''
)
s=s.replace(
'''label = { Text("6 haneli güvenlik kodu") },''',
'''label = { Text("Güvenlik kodu") },'''
)
s=s.replace(
'''supportingText = { Text("E-postadaki 6 rakamı buraya yazın") },''',
'''supportingText = { Text("E-postadaki kodun tamamını buraya yazın") },'''
)
s=s.replace(
'''enabled = otpCode.length == 6,''',
'''enabled = otpCode.length in 6..8,''',
)
s=s.replace(
'''authMessage = "Kod yanlış veya süresi dolmuş. E-postadaki son 6 haneli kodu kontrol edin."''',
'''authMessage = "Kod yanlış veya süresi dolmuş. E-postadaki kodun tamamını kontrol edin."'''
)
s=s.replace(
'''Maildeki bağlantıya basmanız gerekmez. Yalnızca 6 haneli güvenlik kodunu okuyup yukarıdaki kutuya yazın.''',
'''Maildeki bağlantıya basmanız gerekmez. E-postadaki güvenlik kodunun tamamını yukarıdaki kutuya yazın.'''
)
s=s.replace("v0.14 • 6 Haneli E-posta Kodu", "v0.15 • E-posta Güvenlik Kodu")
s=s.replace("MELEHAT TELSİZ v0.14", "MELEHAT TELSİZ v0.15")
p.write_text(s)

b=Path("app/build.gradle.kts")
t=b.read_text().replace("versionCode = 14","versionCode = 15").replace('versionName = "0.14.0"','versionName = "0.15.0"')
b.write_text(t)

print("v0.15 flexible 6-8 digit OTP patch applied")
