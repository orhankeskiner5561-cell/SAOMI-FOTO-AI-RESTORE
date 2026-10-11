from pathlib import Path

# MELEHAT v1.3.62: Bounded retry on real LiveKit connect failure, concise
# connection feedback. No modification to PTT floor, microphone, Shizuku,
# channels, member identity, signing, or application ID.
root = Path('app/src/main/java/com/saomi/telsiz')
client = root/'voice/LiveKitPttClient.kt'
service = root/'service/PttForegroundService.kt'
ui = root/'ui/AppRoot.kt'

def swap(p, old, new):
    s = p.read_text(encoding='utf-8')
    if s.count(old) != 1:
        raise SystemExit(f'v1362 source changed {p.name} count={s.count(old)}: {old[:90]}')
    p.write_text(s.replace(old,new,1),encoding='utf-8')

swap(client,
'''            val type = failure.javaClass.simpleName.lowercase()
            val category = when {
                "timeout" in type -> "BAGLANTI_ZAMAN_ASIMI"
                "unknownhost" in type -> "SUNUCU_ADRESI_COZULEMEDI"
                "ssl" in type || "certificate" in type -> "TLS_SERTIFIKA"
                "unauthor" in type || "security" in type -> "YETKI_REDDEDILDI"
                else -> "LIVEKIT_BAGLANTI_HATASI_" +
                    failure.javaClass.simpleName.take(45)
            }
            LiveChannelUiState.connectionProblem(category)
            LiveChannelUiState.status("CONNECTING")
            runCatching { r.disconnect() }
            false''',
'''            // Consider nested Java/OkHttp causes and HTTP status hints, but
            // NEVER include raw exception messages (may contain sensitive URL
            // or token information) in diagnostics.
            val causes = generateSequence(failure) { it.cause }.take(6).toList()
            val types = causes.joinToString(" ") { it.javaClass.simpleName.lowercase() }
            val hints = causes.joinToString(" ") { it.message.orEmpty() }
            val category = when {
                Regex("(^|[^0-9])429([^0-9]|$)").containsMatchIn(hints) ||
                    hints.contains("too many requests", ignoreCase = true) -> "SUNUCU_ISTEK_SINIRI_429"
                "unknownhost" in types -> "SUNUCU_ADRESI_COZULEMEDI"
                "ssl" in types || "certificate" in types -> "TLS_SERTIFIKA"
                "timeout" in types -> "BAGLANTI_ZAMAN_ASIMI"
                "connectexception" in types -> "SUNUCU_SOCKET_BAGLANTI_REDDEDILDI"
                "security" in types || "unauthor" in types -> "YETKI_REDDEDILDI"
                else -> "LIVEKIT_SES_KANALI_BAGLANAMADI"
            }
            eventJob?.cancel()
            eventJob = null
            LiveChannelUiState.connectionProblem(category)
            LiveChannelUiState.status("CONNECTING")
            runCatching { r.disconnect() }
            false''')

swap(service,
'''            ACTION_START -> {
                sessions.load()?.userId?.let { currentUser ->''',
'''            ACTION_START -> {
                // Starting twice must not create duplicate LiveKit signaling
                // joins or reset the existing watchdog/reconnect coroutine.
                if (started) return START_STICKY
                sessions.load()?.userId?.let { currentUser ->''')

swap(service,
'''                    keepAliveJob = scope.launch {
                        while (started) {
                            delay(5000)
                            if (!ptt.isConnected()) {
                                roomMutex.withLock {
                                    if (started && !roomSwitching && !ptt.isConnected()) {
                                        ptt.ensureConnected()
                                    }
                                }
                            }
                        }
                    }''',
'''                    keepAliveJob = scope.launch {
                        // A failed socket/429 must not generate another join
                        // every 5 seconds. Back off up to 2 minutes, and reset
                        // on a confirmed LiveKit connection.
                        var retryDelayMs = 10_000L
                        while (started) {
                            delay(retryDelayMs +
                                (android.os.SystemClock.uptimeMillis() % 2_000L))
                            if (ptt.isConnected()) {
                                retryDelayMs = 10_000L
                                continue
                            }
                            val ok = roomMutex.withLock {
                                if (started && !roomSwitching && !ptt.isConnected()) {
                                    ptt.ensureConnected()
                                } else ptt.isConnected()
                            }
                            if (!ok && started && !roomSwitching) {
                                updateNotification("Ses bağlantısı bekleniyor • Tekrar denenecek")
                            }
                            retryDelayMs = if (ok) 10_000L
                                else (retryDelayMs * 2).coerceAtMost(120_000L)
                        }
                    }''')

swap(ui,
'''                        Text(
                            "Bağlantı teşhisi: " +
                            (if (liveConnectProblem.isBlank())
                                "SERVIS_YANITI_BEKLENIYOR" else liveConnectProblem)
                        )''',
'''                        val connectionLabel = when (liveConnectProblem) {
                            "SUNUCU_ISTEK_SINIRI_429" -> "Sunucu yoğun (429), yeniden denenecek"
                            "SUNUCU_SOCKET_BAGLANTI_REDDEDILDI" -> "Ses sunucusu bağlantıyı reddetti"
                            "SUNUCU_ADRESI_COZULEMEDI" -> "Sunucu adresi çözümlenemedi"
                            "BAGLANTI_ZAMAN_ASIMI" -> "Ses bağlantısı zaman aşımı"
                            "TLS_SERTIFIKA" -> "Güvenli ses bağlantısı hatası"
                            "TOKEN_ALINAMADI" -> "Kanal oturumu alınamadı"
                            "TOKEN_ALINDI_CANLI_BAGLANTI_BEKLENIYOR" -> "Ses odasına bağlanılıyor"
                            "TOKEN_ISTENIYOR" -> "Kanal bağlantısı hazırlanıyor"
                            "YETKI_REDDEDILDI" -> "Kanal bağlantısı reddedildi"
                            else -> "Ses bağlantısı kurulamadı"
                        }
                        Text(
                            "Bağlantı: $connectionLabel",
                            modifier = Modifier.widthIn(max = 220.dp),
                            maxLines = 3,
                            fontSize = 12.sp,
                            softWrap = true
                        )''')

for p,items in [
    (client,["SUNUCU_ISTEK_SINIRI_429","eventJob?.cancel()","setMicrophoneEnabled(false)","roomTokenClient.fetch"]),
    (service,["120_000L","ptt.ensureConnected()","rawPttEnable()","ACTION_SWITCH_ROOM","if (started) return START_STICKY"]),
    (ui,["Modifier.widthIn(max = 220.dp)","BAS KONUŞ","KANAL AÇ  +"])
]:
    s=p.read_text(encoding='utf-8')
    for v in items:
        if v not in s:raise SystemExit('v1362 protected behavior lost: '+v)
print('MELEHAT_1362_BACKOFF_AND_UI_OK')
