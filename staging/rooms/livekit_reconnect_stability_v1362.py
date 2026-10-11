from pathlib import Path
root=Path("app/src/main/java/com/saomi/telsiz")
client=root/"voice/LiveKitPttClient.kt"
service=root/"service/PttForegroundService.kt"
ui=root/"ui/AppRoot.kt"

def rep(path,old,new,expected=1):
    s=path.read_text(encoding="utf-8")
    actual=s.count(old)
    if actual!=expected:
        raise RuntimeError(f"v1362: {path.name}: expected {expected} anchors, found {actual}")
    path.write_text(s.replace(old,new,1),encoding="utf-8")

# LiveKit Room.release() frees native WebRTC resources (including callbacks).
rep(client,'            runCatching { r.disconnect() }\n            false',
           '            eventJob?.cancel()\n            eventJob = null\n            runCatching { r.release() }\n            false')
rep(client,'        runCatching { room?.disconnect() }\n        eventJob?.cancel()',
           '        runCatching { room?.release() }\n        eventJob?.cancel()')
rep(client,'        runCatching { room?.disconnect() }\n        room = null',
           '        runCatching { room?.release() }\n        room = null')

# Only display sanitized error categories: never surface private tokens,
# connection URLs or raw exception messages.
rep(client,'''            val type = failure.javaClass.simpleName.lowercase()
            val category = when {
                "timeout" in type -> "BAGLANTI_ZAMAN_ASIMI"
                "unknownhost" in type -> "SUNUCU_ADRESI_COZULEMEDI"
                "ssl" in type || "certificate" in type -> "TLS_SERTIFIKA"
                "unauthor" in type || "security" in type -> "YETKI_REDDEDILDI"
                else -> "LIVEKIT_BAGLANTI_HATASI_" +
                    failure.javaClass.simpleName.take(45)
            }''','''            val chain = generateSequence(failure as Throwable?) { it.cause }
                .take(5).toList()
            val type = chain.joinToString(" ") { it.javaClass.simpleName.lowercase() }
            val details = chain.joinToString(" ") { it.message.orEmpty().lowercase() }
            val category = when {
                Regex("(^|[^0-9])429([^0-9]|$)").containsMatchIn(details) ||
                    "too many requests" in details || "rate limit" in details -> "SUNUCU_429_ISTEK_SINIRI"
                Regex("(^|[^0-9])503([^0-9]|$)").containsMatchIn(details) -> "SUNUCU_503_GECICI_HATA"
                Regex("(^|[^0-9])401([^0-9]|$)").containsMatchIn(details) -> "SUNUCU_401_YETKI_HATASI"
                "timeout" in type -> "BAGLANTI_ZAMAN_ASIMI"
                "unknownhost" in type -> "SUNUCU_ADRESI_COZULEMEDI"
                "ssl" in type || "certificate" in type -> "TLS_SERTIFIKA"
                "unauthor" in type || "security" in type -> "YETKI_REDDEDILDI"
                else -> "LIVEKIT_CONNECT_HATASI"
            }''')

# A failed connection must never initiate a new Room every five seconds.
# Sequence of waits: 15s, 30s, 60s, 120s (until recovered).
rep(service,'    private var keepAliveJob: Job? = null\n    private val roomMutex = Mutex()','''    private var keepAliveJob: Job? = null
    private var reconnectFailures = 0
    private fun reconnectDelayMs(): Long = when (reconnectFailures) {
        0 -> 15000L
        1 -> 30000L
        2 -> 60000L
        else -> 120000L
    }
    private val roomMutex = Mutex()''')
rep(service,'''                            if (started && !roomSwitching) {
                                ptt.connect(store.loadProfile(), store.loadActiveChannel())
                            } else false''','''                            if (started && !roomSwitching) {
                                if (ptt.isConnected()) true else
                                    ptt.connect(store.loadProfile(), store.loadActiveChannel())
                            } else false''',expected=2)
rep(service,'''                        updateNotification(
                            if (ok) "Bağlantı geri geldi • Bas-konuş hazır"''','''                        if (ok) reconnectFailures = 0
                        updateNotification(
                            if (ok) "Bağlantı geri geldi • Bas-konuş hazır"''')
rep(service,'''                    updateNotification(
                        if (ok) "Kanal 1 CANLI • Bas-konuş hazır"
                        else "Ses sunucusu bağlantısı bekleniyor"
                    )
                    keepAliveJob?.cancel()
                    keepAliveJob = scope.launch {
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
                    }''','''                    reconnectFailures = 0
                    updateNotification(
                        if (ok) "Kanal 1 CANLI • Bas-konuş hazır"
                        else "Ses sunucusu bağlantısı bekleniyor"
                    )
                    keepAliveJob?.cancel()
                    keepAliveJob = scope.launch {
                        while (started) {
                            delay(if (ptt.isConnected()) 15000L else reconnectDelayMs())
                            if (!started) break
                            if (ptt.isConnected()) {
                                reconnectFailures = 0
                            } else {
                                val recovered = roomMutex.withLock {
                                    if (started && !roomSwitching && !ptt.isConnected()) {
                                        ptt.ensureConnected()
                                    } else ptt.isConnected()
                                }
                                if (recovered) reconnectFailures = 0
                                else if (!roomSwitching) reconnectFailures =
                                    (reconnectFailures + 1).coerceAtMost(3)
                            }
                        }
                    }''')
rep(service,'''        keepAliveJob?.cancel()
        keepAliveJob = null
        store.setRadioEnabled(false)''','''        keepAliveJob?.cancel()
        keepAliveJob = null
        reconnectFailures = 0
        store.setRadioEnabled(false)''')

# Keep the diagnostic away from the ON/OFF switch and make it user-readable.
rep(ui,'''                        Text(
                            "Bağlantı teşhisi: " +
                            (if (liveConnectProblem.isBlank())
                                "SERVIS_YANITI_BEKLENIYOR" else liveConnectProblem)
                        )''','''                        Text(
                            "Bağlantı: " + when (liveConnectProblem) {
                                "SUNUCU_429_ISTEK_SINIRI" -> "Sunucu 429 • tekrar denenecek"
                                "SUNUCU_503_GECICI_HATA" -> "Sunucu 503 • tekrar denenecek"
                                "SUNUCU_401_YETKI_HATASI" -> "Sunucu kimliği reddetti"
                                "LIVEKIT_CONNECT_HATASI" -> "LiveKit bağlantı kurulamadı"
                                "TOKEN_ALINAMADI" -> "Oda giriş izni alınamadı"
                                "TOKEN_ISTENIYOR" -> "Oda giriş izni isteniyor"
                                "TOKEN_ALINDI_CANLI_BAGLANTI_BEKLENIYOR" -> "Ses sunucusu bekleniyor"
                                "BAGLANTI_ZAMAN_ASIMI" -> "Bağlantı zaman aşımı"
                                "" -> "Sunucudan yanıt bekleniyor"
                                else -> liveConnectProblem.replace('_', ' ').take(48)
                            },
                            modifier = Modifier.widthIn(max = 220.dp),
                            maxLines = 2,
                            overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis,
                            fontSize = 12.sp
                        )''')
for p,need in [
 (client,["r.release()","SUNUCU_429_ISTEK_SINIRI","room?.release()"]),
 (service,["reconnectDelayMs()","reconnectFailures + 1","ptt.ensureConnected()"]),
 (ui,["Modifier.widthIn(max = 220.dp)","Bağlantı: ","Sunucu 429"])
]:
    s=p.read_text(encoding="utf-8")
    for item in need:
        if item not in s: raise RuntimeError(f"v1362 missing {item} in {p.name}")
print("MELEHAT_V1362_RELEASE_RETRY_AND_LAYOUT_OK")
