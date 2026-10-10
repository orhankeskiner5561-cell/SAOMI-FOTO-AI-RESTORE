from pathlib import Path

# MELEHAT v1.3.52: screen-off external PTT diagnostics and safe service dispatch.
# Add only external-key instrumentation and existing foreground-service delivery.
# Never replace the v1.3.51 LiveKit/PTT/routing implementation.
root = Path("app/src/main/java/com/saomi/telsiz")
acc = root / "service/VolumePttAccessibilityService.kt"
fgs = root / "service/PttForegroundService.kt"
compat = root / "compat/DeviceCompatibilityActivity.kt"
for p in (acc, fgs, compat):
    if not p.exists():
        raise SystemExit("v1352: missing live v1.3.51 source " + str(p))

# Local-only diagnostic snapshots, no microphone audio or personal information.
diag = root / "service/ExternalPttDiagnostics.kt"
if diag.exists():
    raise SystemExit("v1352: diagnostics module already exists")
diag.write_text('''package com.saomi.telsiz.service

import android.content.Context
import android.os.PowerManager

/** Debugging only: last external-key/dispatch/service/audio events on this device. */
object ExternalPttDiagnostics {
    private const val PREFS = "melehat_external_ptt_diagnostics"
    fun record(context: Context, stage: String, detail: String) {
        val key = when (stage) {
            "key", "dispatch", "service", "audio", "watchdog" -> stage
            else -> return
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putLong(key + "_at", System.currentTimeMillis())
            .putString(key + "_result", detail.take(160))
            .apply()
    }

    fun screenState(context: Context): String {
        val pm = context.getSystemService(PowerManager::class.java)
        return if (pm.isInteractive) "SCREEN_ON" else "SCREEN_OFF"
    }

    fun describe(context: Context, stage: String): String {
        val p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val ms = p.getLong(stage + "_at", 0)
        if (ms == 0L) return "Kayıt yok"
        val time = java.text.SimpleDateFormat(
            "HH:mm:ss", java.util.Locale.getDefault()
        ).format(java.util.Date(ms))
        return "$time • " + p.getString(stage + "_result", "").orEmpty()
    }
}
''', encoding="utf-8")

s = acc.read_text(encoding="utf-8")
def edit(source, old, new, label, n=1):
    if source.count(old) != n:
        raise SystemExit("v1352: unexpected " + label + " anchor " + str(source.count(old)))
    return source.replace(old, new, n)

s=edit(s,
'''            if (elapsed >= RELEASE_TIMEOUT_MS || !isArmed()) {
                release()''',
'''            if (elapsed >= RELEASE_TIMEOUT_MS || !isArmed()) {
                ExternalPttDiagnostics.record(this@VolumePttAccessibilityService,
                    "watchdog", "AUTO_RELEASE " + ExternalPttDiagnostics.screenState(this@VolumePttAccessibilityService))
                release()''', "watchdog")
s=edit(s,
'''        if (event.keyCode != KeyEvent.KEYCODE_VOLUME_UP) return false
        if (!isArmed()) {''',
'''        if (event.keyCode != KeyEvent.KEYCODE_VOLUME_UP) return false
        ExternalPttDiagnostics.record(this, "key",
            (if (event.action == KeyEvent.ACTION_DOWN) "DOWN"
             else if (event.action == KeyEvent.ACTION_UP) "UP" else "OTHER") +
            " repeat=" + event.repeatCount + " " +
            ExternalPttDiagnostics.screenState(this))
        if (!isArmed()) {''', "key capture")
s=edit(s,
'''            // Never turn the radio on from a key press; only signal the
            // existing authorized foreground radio service.
            val intent = Intent(this, PttForegroundService::class.java).setAction(action)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent)
            } else {
                startService(intent)
            }
            true''',
'''            // The microphone-type foreground service MUST already be running
            // from a visible activity. Sending to that existing service with
            // startService avoids an Android 12+ background FGS *launch*.
            // Never start a new microphone foreground service on a locked phone.
            val intent = Intent(this, PttForegroundService::class.java)
                .setAction(action)
                .putExtra("melehat.external_ptt", true)
            val result = startService(intent)
            val delivered = result != null
            ExternalPttDiagnostics.record(this, "dispatch",
                (if (delivered) "SERVICE_START_ACCEPTED " else "SERVICE_NOT_FOUND ") +
                action.substringAfterLast('.') + " " + ExternalPttDiagnostics.screenState(this))
            delivered''', "service dispatch")
s=edit(s,
'''            Log.w(TAG, "External PTT action unavailable: " + action, it)
            false''',
'''            Log.w(TAG, "External PTT action unavailable: " + action, it)
            ExternalPttDiagnostics.record(this, "dispatch",
                "SERVICE_ERROR " + it.javaClass.simpleName + " " +
                ExternalPttDiagnostics.screenState(this))
            false''', "service dispatch exception")
# Preserve original release watchdog and all key-hold semantics for now.
for guard in ("RELEASE_TIMEOUT_MS = 1800L", "KEYCODE_VOLUME_UP",
              "isArmed()", "ACTION_PTT_UP", "ACTION_PTT_DOWN"):
    if guard not in s: raise SystemExit("v1352: old accessibility safety removed: " + guard)
acc.write_text(s,encoding="utf-8")

s = fgs.read_text(encoding="utf-8")
s=edit(s,
'''            ACTION_PTT_DOWN -> {
                if (started && !roomSwitching) {''',
'''            ACTION_PTT_DOWN -> {
                val externalKey = intent?.getBooleanExtra("melehat.external_ptt", false) == true
                if (externalKey) {
                    ExternalPttDiagnostics.record(this, "service",
                        "DOWN_RECEIVED started=" + started +
                        " switching=" + roomSwitching + " " +
                        ExternalPttDiagnostics.screenState(this))
                }
                if (started && !roomSwitching) {''', "fgs down")
s=edit(s,
'''                        beginJob = scope.launch { beginTransmit(requestId) }
                    }
                }
            }

            ACTION_PTT_UP -> {''',
'''                        beginJob = scope.launch { beginTransmit(requestId, externalKey) }
                    }
                }
            }

            ACTION_PTT_UP -> {''', "external begin")
s=edit(s,
'''            ACTION_PTT_UP -> {
                if (started) {''',
'''            ACTION_PTT_UP -> {
                if (intent?.getBooleanExtra("melehat.external_ptt", false) == true) {
                    ExternalPttDiagnostics.record(this, "service",
                        "UP_RECEIVED " + ExternalPttDiagnostics.screenState(this))
                }
                if (started) {''', "fgs up")
s=edit(s,
'''    private suspend fun beginTransmit(requestId: Long) {''',
'''    private suspend fun beginTransmit(requestId: Long, external: Boolean = false) {''',
"begin transmit signature")
s=edit(s,
'''        if (roomSwitching || !ptt.isConnectedTo(channel.id)) {
            updateNotification("Kanal bağlantısı hazırlanıyor")''',
'''        if (roomSwitching || !ptt.isConnectedTo(channel.id)) {
            if (external) ExternalPttDiagnostics.record(this, "audio",
                "ROOM_NOT_CONNECTED")
            updateNotification("Kanal bağlantısı hazırlanıyor")''', "room guard")
s=edit(s,
'''        if (!floor) {
            if (pttHeld && requestId == transmitRequestId) {''',
'''        if (!floor) {
            if (external) ExternalPttDiagnostics.record(this, "audio", "FLOOR_NOT_GRANTED")
            if (pttHeld && requestId == transmitRequestId) {''', "floor guard")
s=edit(s,
'''        val enabled = ptt.setTransmitting(true)
        if (!enabled) {''',
'''        val enabled = ptt.setTransmitting(true)
        if (external) ExternalPttDiagnostics.record(this, "audio",
            if (enabled) "MIC_API_ENABLED" else "MIC_API_FAILED")
        if (!enabled) {''', "mic outcome")
s=edit(s,
'''        transmitting = true
        updateNotification("YAYINDA • Ses karşıya gidiyor")''',
'''        transmitting = true
        if (external) ExternalPttDiagnostics.record(this, "audio",
            "PTT_STARTED " + ExternalPttDiagnostics.screenState(this))
        updateNotification("YAYINDA • Ses karşıya gidiyor")''', "tx outcome")
# Existing floor guards must remain in place.
for guard in ("roomSwitching || !ptt.isConnectedTo(channel.id)",
              "pttHeld || requestId != transmitRequestId",
              "backend.releaseFloor(session, channel.id)",
              "ACTION_SWITCH_ROOM", "return START_STICKY"):
    if guard not in s: raise SystemExit("v1352: protected PTT core missing: " + guard)
fgs.write_text(s,encoding="utf-8")

s = compat.read_text(encoding="utf-8")
anchor = '        line("İzinler ve pil ayarları", 18f, true)'
panel = '''        line("Kilit ekranı dış mandal teşhisi", 18f, true)
        for (stage in listOf("key", "dispatch", "service", "audio", "watchdog")) {
            val name = when (stage) {
                "key" -> "Tuş algılandı"
                "dispatch" -> "Servise gönderim"
                "service" -> "PTT komutu ulaştı"
                "audio" -> "Mikrofon / kanal"
                else -> "Güvenlik bırakması"
            }
            line(name + ": " +
                com.saomi.telsiz.service.ExternalPttDiagnostics.describe(this, stage))
        }
        action("Dış mandal test kaydını yenile") { render() }
        line("Ekranı kilitleyip Ses + tuşuna 3 saniye basılı tutun. " +
             "Sonra ekranı açıp buraya dönün ve test kaydını yenileyin. " +
             "Bunlar Android'in bildirdiği olaylardır; uygulama " +
             "sistem tarafından gizlenen ses tuşu olaylarını zorla alamaz.")
'''
s=edit(s,anchor,panel+anchor,"diagnostic panel")
compat.write_text(s,encoding="utf-8")
print("MELEHAT_1352_EXTERNAL_SCREEN_OFF_DIAGNOSTICS_AND_SERVICE_DISPATCH_READY")
