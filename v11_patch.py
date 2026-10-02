from pathlib import Path
p=Path('app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt')
s=p.read_text()

if 'import kotlinx.coroutines.delay' not in s:
    s=s.replace('import kotlinx.coroutines.launch\n','import kotlinx.coroutines.launch\nimport kotlinx.coroutines.delay\n')

s=s.replace('v0.10 • E-posta bağlantısı • Profil • Kanal • PTT','v0.11 • E-posta bağlantısı • Profil • Kanal • PTT')
s=s.replace('MELEHAT TELSİZ v0.10','MELEHAT TELSİZ v0.11')

old='''    var linkSent by remember { mutableStateOf(false) }\n    var authMessage by remember { mutableStateOf(\"\") }\n'''
new='''    var linkSent by remember { mutableStateOf(false) }\n    var authMessage by remember { mutableStateOf(\"\") }\n    var resendSeconds by remember { mutableStateOf(0) }\n    var cooldownFinished by remember { mutableStateOf(false) }\n'''
if old not in s: raise SystemExit('state pattern not found')
s=s.replace(old,new)

needle='''    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->\n        uri?.let { photoUri = it.toString() }\n    }\n\n'''
insert=needle+'''    LaunchedEffect(resendSeconds) {\n        if (resendSeconds > 0) {\n            delay(1000)\n            resendSeconds -= 1\n            if (resendSeconds == 0) cooldownFinished = true\n        }\n    }\n\n'''
if needle not in s: raise SystemExit('picker pattern not found')
s=s.replace(needle,insert,1)

old='''                Button(\n                    onClick = {\n                        scope.launch {\n                            authMessage = \"Gönderiliyor…\"\n                            sessionStore.savePending(loginPhone, loginEmail)\n                            auth.sendMagicLink(loginEmail)\n                                .onSuccess {\n                                    linkSent = true\n                                    authMessage = \"Giriş bağlantısı e-postanıza gönderildi. Maildeki bağlantıya dokunun; MELEHAT TELSİZ otomatik açılır.\"\n                                }\n                                .onFailure { authMessage = it.message.orEmpty() }\n                        }\n                    },\n                    enabled = loginPhone.isNotBlank() && loginEmail.contains(\"@\"),\n                    modifier = Modifier.fillMaxWidth()\n                ) {\n                    Text(if (linkSent) \"Bağlantıyı Tekrar Gönder\" else \"E-postaya Giriş Bağlantısı Gönder\")\n                }\n'''
new='''                val canSend = loginPhone.isNotBlank() && loginEmail.contains(\"@\") && resendSeconds == 0\n                Button(\n                    onClick = {\n                        scope.launch {\n                            cooldownFinished = false\n                            authMessage = \"Gönderiliyor…\"\n                            sessionStore.savePending(loginPhone, loginEmail)\n                            auth.sendMagicLink(loginEmail)\n                                .onSuccess {\n                                    linkSent = true\n                                    resendSeconds = 60\n                                    authMessage = \"Giriş bağlantısı e-postanıza gönderildi. Maildeki bağlantıya dokunun; MELEHAT TELSİZ otomatik açılır.\"\n                                }\n                                .onFailure { error ->\n                                    val raw = error.message.orEmpty()\n                                    if (raw.contains(\"429\") || raw.contains(\"rate limit\", ignoreCase = true) || raw.contains(\"over_email_send_rate_limit\")) {\n                                        resendSeconds = 60\n                                        authMessage = \"Çok fazla deneme yapıldı. Yeni bağlantı istemeden kısa süre bekleyin.\"\n                                    } else {\n                                        authMessage = \"Bağlantı gönderilemedi. İnternet bağlantınızı kontrol edip tekrar deneyin.\"\n                                    }\n                                }\n                        }\n                    },\n                    enabled = canSend,\n                    colors = ButtonDefaults.buttonColors(\n                        containerColor = when {\n                            resendSeconds > 0 -> Color(0xFFBDBDBD)\n                            cooldownFinished -> Color(0xFF2E7D32)\n                            else -> MaterialTheme.colorScheme.primary\n                        },\n                        disabledContainerColor = Color(0xFFBDBDBD)\n                    ),\n                    modifier = Modifier.fillMaxWidth()\n                ) {\n                    Text(\n                        when {\n                            resendSeconds > 0 -> \"Tekrar göndermek için ${resendSeconds} sn\"\n                            cooldownFinished -> \"Süre doldu, tekrar deneyin\"\n                            linkSent -> \"Bağlantıyı Tekrar Gönder\"\n                            else -> \"E-postaya Giriş Bağlantısı Gönder\"\n                        }\n                    )\n                }\n'''
if old not in s: raise SystemExit('button pattern not found')
s=s.replace(old,new,1)

s=s.replace('linkSent = false\n                    authMessage = \"\"','linkSent = false\n                    resendSeconds = 0\n                    cooldownFinished = false\n                    authMessage = \"\"')
p.write_text(s)

b=Path('app/build.gradle.kts')
t=b.read_text().replace('versionCode = 10','versionCode = 11').replace('versionName = \"0.10.0\"','versionName = \"0.11.0\"')
b.write_text(t)
print('v0.11 cooldown patch applied')
