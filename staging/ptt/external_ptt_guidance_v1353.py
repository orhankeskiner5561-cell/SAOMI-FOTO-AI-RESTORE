from pathlib import Path
root=Path("app/src/main/java/com/saomi/telsiz")
main=root/"MainActivity.kt"
compat=root/"compat/DeviceCompatibilityActivity.kt"
access=root/"service/VolumePttAccessibilityService.kt"
diag=root/"service/ExternalPttDiagnostics.kt"
fgs=root/"service/PttForegroundService.kt"
def edit(path,old,new):
    s=path.read_text(encoding="utf-8")
    if s.count(old)!=1: raise SystemExit("1353 anchor mismatch: "+str(path)+" count="+str(s.count(old))+" "+old[:80])
    path.write_text(s.replace(old,new,1),encoding="utf-8")

edit(main, '        offerBrandCompatibilityCheckOnce()\n',
'''        // Show external PTT setup once after upgrading, without modifying
        // the working LiveKit microphone or normal PTT button.
        if (!offerExternalPttSetupOnce()) offerBrandCompatibilityCheckOnce()
''')
edit(main, '    private fun offerBrandCompatibilityCheckOnce() {',
'''    private fun offerExternalPttSetupOnce(): Boolean {
        val prefs = getSharedPreferences("melehat_external_ptt", MODE_PRIVATE)
        if (prefs.getBoolean("v1353_setup_prompt_seen", false)) return false
        val expected = android.content.ComponentName(
            this, com.saomi.telsiz.service.VolumePttAccessibilityService::class.java
        ).flattenToString()
        val accessOn = android.provider.Settings.Secure.getString(
            contentResolver,
            android.provider.Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        ).orEmpty().split(':').any { it.equals(expected, ignoreCase = true) }
        if (accessOn && prefs.getBoolean("enabled", false)) {
            prefs.edit().putBoolean("v1353_setup_prompt_seen", true).apply()
            return false
        }
        window.decorView.post {
            if (isFinishing || isDestroyed) return@post
            android.app.AlertDialog.Builder(this)
                .setTitle("MELEHAT • Dış mandal kurulumu")
                .setMessage(
                    "Erişilebilirlik izni tek başına Ses + mandalını etkinleştirmez. " +
                    "Dış Mandal AÇIK anahtarını da etkinleştirin. " +
                    "Gerekli izinleri kontrol etmek için Dış Mandal Ayarlarını açın. " +
                    "Kilitli ekranda tuş yakalama cihaz üreticisine bağlıdır."
                )
                .setPositiveButton("DIŞ MANDAL AYARLARINA GİT") { _, _ ->
                    startActivity(android.content.Intent(
                        this, com.saomi.telsiz.compat.DeviceCompatibilityActivity::class.java
                    ))
                }
                .setNegativeButton("SONRA", null)
                .show()
            prefs.edit().putBoolean("v1353_setup_prompt_seen", true).apply()
        }
        return true
    }

    private fun offerBrandCompatibilityCheckOnce() {''')

edit(diag,'"key", "dispatch", "service", "audio", "watchdog" -> stage',
          '"key", "dispatch", "service", "audio", "watchdog", "access" -> stage')
edit(access,'''        serviceInfo = serviceInfo.apply {
            flags = flags or AccessibilityServiceInfo.FLAG_REQUEST_FILTER_KEY_EVENTS
        }
    }
''','''        serviceInfo = serviceInfo.apply {
            flags = flags or AccessibilityServiceInfo.FLAG_REQUEST_FILTER_KEY_EVENTS
        }
        ExternalPttDiagnostics.record(this, "access", "SERVICE_CONNECTED " +
            ExternalPttDiagnostics.screenState(this))
    }
''')
edit(access,'    override fun onInterrupt() = release()',
'''    override fun onInterrupt() {
        ExternalPttDiagnostics.record(this, "access", "SERVICE_INTERRUPTED")
        release()
    }''')
edit(access,'''    override fun onDestroy() {
        release()
        super.onDestroy()
    }
''','''    override fun onDestroy() {
        ExternalPttDiagnostics.record(this, "access", "SERVICE_DESTROYED")
        release()
        super.onDestroy()
    }
''')
edit(access,'''        if (!isArmed()) {
            release()
            return false // Volume+ remains a normal volume key when disarmed.
        }
''','''        if (!isArmed()) {
            ExternalPttDiagnostics.record(this, "dispatch",
                "IGNORED: external switch or radio OFF")
            release()
            return false // Normal volume adjustment if not armed.
        }
''')
edit(compat,'        line("DIŞ MANDAL • Ses +", 18f, true)',
'''        line("DIŞ MANDAL • Ses +", 18f, true)
        line("Erişilebilirlik izni ile MELEHAT'ın Dış Mandal anahtarı " +
            "ayrıdır; her ikisini de açın.")''')
edit(compat,'''        line("Erişilebilirlik / İndirilen uygulamalar: " +
            if (accessOn) "✓ Etkin" else "⚠ Kapalı")''',
'''        val externalEnabled = externalPrefs.getBoolean("enabled", false)
        val radioEnabled = com.saomi.telsiz.data.LocalStore(this).isRadioEnabled()
        val allEnabled = externalEnabled && accessOn && radioEnabled
        line("DIŞ MANDAL: " + if (allEnabled) "✓ AÇIK" else "⚠ AKTİF DEĞİL", 17f, true)
        line("Dış Mandal anahtarı: " + if (externalEnabled) "✓ AÇIK" else "⚠ KAPALI")
        line("Erişilebilirlik: " + if (accessOn) "✓ İzinli" else "⚠ İzin gerekli")
        line("Telsiz: " + if (radioEnabled) "✓ AÇIK" else "⚠ KAPALI")''')
edit(compat,'''        action("Dış mandal erişilebilirlik iznini aç") {
            openSettings(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }''',
'''        action("Erişilebilirlik > İndirilen uygulamaları aç") {
            openSettings(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }
        action("Uygulama bilgisi > Kısıtlı ayarlar") {
            openSettings(appDetails())
        }''')
edit(compat,'        line("Kilit ekranı dış mandal teşhisi", 18f, true)',
'''        line("Kilit ekranı dış mandal teşhisi", 18f, true)
        line("Ekran kapalıyken Android ses tuşunu iletmezse " +
             "burada SCREEN_OFF tuş kaydı oluşmaz.")''')
edit(compat,'for (stage in listOf("key", "dispatch", "service", "audio", "watchdog"))',
            'for (stage in listOf("access", "key", "dispatch", "service", "audio", "watchdog"))')
edit(compat,'                "key" -> "Tuş algılandı"',
'''                "access" -> "Erişilebilirlik servisi"
                "key" -> "Tuş algılandı"''')
edit(fgs,'                "Telefon Uyumluluğu",','                "Dış Mandal Ayarları",')
s=fgs.read_text()
for name in ('ACTION_PTT_DOWN','ACTION_PTT_UP','ACTION_SWITCH_ROOM','roomMutex.withLock',
             'ptt.setTransmitting(true)','return START_STICKY','VideoCallMonitor.start(applicationContext)'):
    if name not in s: raise SystemExit("v1353 protected radio function missing: "+name)
assert 'RELEASE_TIMEOUT_MS = 1800L' in access.read_text()
print("MELEHAT_1353_EXTERNAL_PTT_GUIDANCE_AND_DIAGNOSTICS_READY")