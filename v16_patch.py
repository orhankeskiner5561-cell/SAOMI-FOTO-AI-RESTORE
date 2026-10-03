from pathlib import Path

p=Path("app/src/main/java/com/saomi/telsiz/service/PttForegroundService.kt")
s=p.read_text()

s=s.replace(
'''    private var started = false
    private var transmitting = false
    private var leaseJob: Job? = null
''',
'''    private var started = false
    private var transmitting = false
    @Volatile private var pttHeld = false
    private var transmitRequestId = 0L
    private var beginJob: Job? = null
    private var leaseJob: Job? = null
''')

s=s.replace(
'''            ACTION_PTT_DOWN -> {
                if (started && !transmitting) scope.launch { beginTransmit() }
            }

            ACTION_PTT_UP -> {
                if (started && transmitting) scope.launch { endTransmit() }
            }

            ACTION_TOGGLE_PTT -> {
                if (started) {
                    if (transmitting) scope.launch { endTransmit() }
                    else scope.launch { beginTransmit() }
                }
            }
''',
'''            ACTION_PTT_DOWN -> {
                if (started) {
                    pttHeld = true
                    transmitRequestId += 1
                    val requestId = transmitRequestId
                    if (!transmitting) {
                        beginJob?.cancel()
                        beginJob = scope.launch { beginTransmit(requestId) }
                    }
                }
            }

            ACTION_PTT_UP -> {
                if (started) {
                    pttHeld = false
                    transmitRequestId += 1
                    beginJob?.cancel()
                    beginJob = null
                    scope.launch { endTransmit() }
                }
            }

            ACTION_TOGGLE_PTT -> {
                if (started) {
                    if (transmitting || pttHeld) {
                        pttHeld = false
                        transmitRequestId += 1
                        beginJob?.cancel()
                        beginJob = null
                        scope.launch { endTransmit() }
                    } else {
                        pttHeld = true
                        transmitRequestId += 1
                        val requestId = transmitRequestId
                        beginJob?.cancel()
                        beginJob = scope.launch { beginTransmit(requestId) }
                    }
                }
            }
''')

s=s.replace(
'''    private suspend fun beginTransmit() {
''',
'''    private suspend fun beginTransmit(requestId: Long) {
''')

s=s.replace(
'''        val floor = backend.acquireFloor(session, channel.id, 15)
        if (!floor) {
            updateNotification("KANAL MEŞGUL • Başka biri konuşuyor")
            return
        }

        val enabled = ptt.setTransmitting(true)
''',
'''        val floor = backend.acquireFloor(session, channel.id, 15)
        if (!floor) {
            if (pttHeld && requestId == transmitRequestId) {
                updateNotification("KANAL MEŞGUL • Başka biri konuşuyor")
            }
            return
        }

        // Kritik güvenlik: kullanıcı kilit alınırken mandalı bıraktıysa
        // mikrofonu hiçbir koşulda açma.
        if (!pttHeld || requestId != transmitRequestId || !started) {
            backend.releaseFloor(session, channel.id)
            ptt.setTransmitting(false)
            updateNotification("Kanal dinlemede • Bas-konuş hazır")
            return
        }

        val enabled = ptt.setTransmitting(true)
''')

s=s.replace(
'''        transmitting = true
        updateNotification("YAYINDA • Ses karşıya gidiyor")
''',
'''        // Mikrofon açılırken bile mandal bırakılmış olabilir; tekrar kontrol et.
        if (!pttHeld || requestId != transmitRequestId || !started) {
            ptt.setTransmitting(false)
            backend.releaseFloor(session, channel.id)
            transmitting = false
            updateNotification("Kanal dinlemede • Bas-konuş hazır")
            return
        }

        transmitting = true
        updateNotification("YAYINDA • Ses karşıya gidiyor")
''')

s=s.replace(
'''    private suspend fun endTransmit() {
        transmitting = false
''',
'''    private suspend fun endTransmit() {
        pttHeld = false
        transmitting = false
''')

s=s.replace(
'''    private suspend fun stopRadio() {
        if (transmitting) endTransmit()
        started = false
''',
'''    private suspend fun stopRadio() {
        pttHeld = false
        transmitRequestId += 1
        beginJob?.cancel()
        beginJob = null
        if (transmitting) endTransmit() else ptt.setTransmitting(false)
        started = false
''')

s=s.replace(
'''    override fun onDestroy() {
        leaseJob?.cancel()
''',
'''    override fun onDestroy() {
        pttHeld = false
        transmitRequestId += 1
        beginJob?.cancel()
        leaseJob?.cancel()
''')

p.write_text(s)

ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
u=ui.read_text().replace("v0.15 • E-posta Güvenlik Kodu","v0.16 • PTT Güvenli Bas-Konuş").replace("MELEHAT TELSİZ v0.15","MELEHAT TELSİZ v0.16")
ui.write_text(u)

b=Path("app/build.gradle.kts")
t=b.read_text().replace("versionCode = 15","versionCode = 16").replace('versionName = "0.15.0"','versionName = "0.16.0"')
b.write_text(t)

print("v0.16 strict hold-to-talk race fix applied")
