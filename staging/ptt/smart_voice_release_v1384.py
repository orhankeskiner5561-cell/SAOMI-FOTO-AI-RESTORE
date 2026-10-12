#!/usr/bin/env python3
"""MELEHAT v1.3.84: optional consent-based 2-second-quiet smart Volume+ PTT.

One Android-provided first KEY_DOWN starts existing radio floor+microphone.
Live local WebRTC audio frames feed a bounded voice/noise heuristic; speech
stopping for 2 seconds releases radio. Never starts its own AudioRecord,
records/retains speech, bypasses Android key restrictions, or auto-restarts.
Noise suppression cannot identify a speaker; absolute max TX is 15 seconds.
"""
from pathlib import Path

root=Path("app/src/main/java/com/saomi/telsiz")
acc=root/"service/VolumePttAccessibilityService.kt"
service=root/"service/PttForegroundService.kt"
duo=root/"p2p/P2pRadioClient.kt"
mesh=root/"p2p/P2pMeshRadioClient.kt"
compat=root/"compat/DeviceCompatibilityActivity.kt"
smart=root/"service/SmartExternalVoiceGate.kt"

def patch(path,before,after,why,n=1):
    s=path.read_text(encoding="utf-8")
    k=s.count(before)
    if k!=n: raise RuntimeError(f"{why}: expected {n}, got {k}")
    s=s.replace(before,after,n)
    path.write_text(s,encoding="utf-8")

assert not smart.exists()
smart.write_text(r'''package com.saomi.telsiz.service

import android.content.Context
import android.media.AudioFormat
import android.os.SystemClock
import com.saomi.telsiz.data.LocalStore
import kotlin.math.max
import kotlin.math.sqrt

/**
 * Voluntary standalone, screen-off, short speech-burst mode.
 * One in-app radio track supplies PCM frames; no second microphone is opened.
 * The filter is NOT voice identification or reliable distance measurement.
 */
object SmartExternalPttMode {
    private const val PREFS="melehat_smart_external_ptt"
    private fun prefs(ctx:Context)=ctx.getSharedPreferences(PREFS,Context.MODE_PRIVATE)

    fun enabled(ctx:Context):Boolean=prefs(ctx).getBoolean("enabled",false)
    fun setEnabled(ctx:Context,value:Boolean) {
        prefs(ctx).edit().putBoolean("enabled",value).apply()
    }
    fun allowed(ctx:Context):Boolean =
        enabled(ctx) && ScreenOffPttEligibility.consent(ctx) &&
        ctx.getSharedPreferences("melehat_external_ptt",Context.MODE_PRIVATE)
            .getBoolean("enabled",false) &&
        ctx.getSharedPreferences("melehat_p2p_transport",Context.MODE_PRIVATE)
            .getBoolean("native_p2p_enabled",true) &&
        LocalStore(ctx).isRadioEnabled() &&
        !NativeVolumeProbe.isActive(ctx) && !ShizukuRawPttState.enabled

    fun markClosed(ctx:Context) {
        prefs(ctx).edit().putLong(
            "closed_at_uptime_ms",SystemClock.uptimeMillis()).apply()
    }
    fun closedAfter(ctx:Context,downUptimeMs:Long):Boolean =
        prefs(ctx).getLong("closed_at_uptime_ms",0L)>downUptimeMs
}

object SmartExternalVoiceGate {
    private var active=false
    private var started=0L
    private var lastFrame=0L
    private var lastVoice=0L
    private var noiseRms=0.012f
    private var voicedStreak=0
    private var hadVoice=false

    private const val MAX_TALK_MS=15000L
    private const val QUIET_MS=2000L
    private const val START_SPEAK_MS=3300L
    private const val NO_SAMPLES_MS=1700L

    @Synchronized fun start() {
        active=true
        started=SystemClock.elapsedRealtime()
        lastFrame=0L
        lastVoice=started
        noiseRms=0.012f
        voicedStreak=0
        hadVoice=false
    }
    @Synchronized fun stop() { active=false }

    @Synchronized fun onPcm(audioFormat:Int,data:ByteArray) {
        if(!active || audioFormat!=AudioFormat.ENCODING_PCM_16BIT ||
            data.size<160) return
        // 16-bit little-endian PCM; sample only every 4th frame for low CPU.
        var energy=0.0
        var crossings=0
        var previous=0
        var count=0
        var i=0
        while(i+1<data.size) {
            val raw=(data[i].toInt() and 255) or (data[i+1].toInt() shl 8)
            val value=raw.toShort().toInt()
            energy+=value.toDouble()*value.toDouble()
            if(count>0 && (value>=0)!=(previous>=0)) crossings++
            previous=value
            count++
            i+=8
        }
        if(count==0)return
        val rms=(sqrt(energy/count.toDouble())/32768.0).toFloat()
        val zcr=crossings.toFloat()/count
        val now=SystemClock.elapsedRealtime()
        lastFrame=now

        // Strong near-microphone speech is generally higher energy than a
        // background floor. WebRTC AGC can change this relationship; don't
        // claim speaker recognition or perfect far-voice rejection.
        val speech=(rms>max(0.029f,noiseRms*2.8f) &&
            zcr in 0.008f..0.49f)
        if(speech) {
            voicedStreak=(voicedStreak+1).coerceAtMost(40)
            if(voicedStreak>=4) {
                hadVoice=true
                lastVoice=now
            }
        } else {
            voicedStreak=(voicedStreak-1).coerceAtLeast(0)
            // Only adjust noise estimate during frames without speech.
            noiseRms=(noiseRms*0.995f+rms*0.005f).coerceIn(0.005f,0.11f)
        }
    }

    /** null while speech window valid, reason when microphone must close. */
    @Synchronized fun stopReason():String? {
        if(!active)return "NOT_ACTIVE"
        val now=SystemClock.elapsedRealtime()
        if(now-started>=MAX_TALK_MS)return "MAX_15_SECONDS"
        if(lastFrame==0L && now-started>=NO_SAMPLES_MS)return "NO_MIC_AUDIO_SAMPLES"
        if(lastFrame!=0L && now-lastFrame>=NO_SAMPLES_MS)return "AUDIO_SAMPLES_LOST"
        if(hadVoice && now-lastVoice>=QUIET_MS)return "TWO_SECONDS_QUIET"
        if(!hadVoice && now-started>=START_SPEAK_MS)return "NO_CLOSE_SPEECH"
        return null
    }
}
''',encoding="utf-8")

for file,initial in ((duo,"        val module = JavaAudioDeviceModule.builder(context.applicationContext)\n            .createAudioDeviceModule()"),
                     (mesh,"        val audio=JavaAudioDeviceModule.builder(context.applicationContext)\n            .createAudioDeviceModule()")):
    replacement=initial.replace(".createAudioDeviceModule()",
        '''.setSamplesReadyCallback { samples ->
                com.saomi.telsiz.service.SmartExternalVoiceGate.onPcm(
                    samples.audioFormat, samples.data)
            }
            .createAudioDeviceModule()''')
    patch(file,initial,replacement,"reuse native WebRTC raw samples")
    
patch(acc,
'''        if (!power.isInteractive && !ScreenOffPttEligibility.allowed(this)) {''',
'''        if (!power.isInteractive &&
            !ScreenOffPttEligibility.allowed(this) &&
            !SmartExternalPttMode.allowed(this)) {''',"consensual smart screen-off first DOWN")
patch(acc,
'''                // Fresh physical DOWN only; a late repeated event cannot
                // accidentally restart after an automatic release.
                if (!held && event.repeatCount == 0) {''',
'''                // After an automatic 2-second-quiet close, next separate
                // physical press (repeatCount=0) may start a NEW session.
                // KEY_REPEAT cannot restart after a lost KEY_UP.
                if (held && event.repeatCount == 0 &&
                    SmartExternalPttMode.closedAfter(this,lastDownAt)) {
                    held=false
                    repeatEvents=false
                    handler.removeCallbacks(timeout)
                }
                if (!held && event.repeatCount == 0) {''',"rearm after quiet timeout")
patch(acc,
'''                    if (!dispatch(PttForegroundService.ACTION_PTT_DOWN)) {''',
'''                    if (!dispatch(PttForegroundService.ACTION_PTT_DOWN)) {''',"preserve dispatch")
patch(acc,
'''    private fun holdTimeoutMs() =
        if (repeatEvents) REPEAT_SILENCE_MS else NO_REPEAT_LIMIT_MS''',
'''    private fun holdTimeoutMs() =
        if (SmartExternalPttMode.allowed(this) &&
            !getSystemService(android.os.PowerManager::class.java).isInteractive)
            15000L
        else if (repeatEvents) REPEAT_SILENCE_MS else NO_REPEAT_LIMIT_MS''',"bounded smart physical press")
patch(acc,
'''                if (held && event.repeatCount > 0) {''',
'''                if (held && event.repeatCount > 0) {''',"preserve repeat branch")
# Pure smart mode does not depend on Android KEY_UP/REPEAT; those are not
# synthesized. It re-arms only on a NEW Android KEY_DOWN after closure.
patch(acc,
'''                    if (now - lastHeartbeatAt >= 700L) {
                        lastHeartbeatAt = now
                        dispatch(PttForegroundService.ACTION_EXTERNAL_PTT_HEARTBEAT)
                    }''',
'''                    if (now - lastHeartbeatAt >= 700L) {
                        lastHeartbeatAt = now
                        if (!SmartExternalPttMode.allowed(this) ||
                            getSystemService(android.os.PowerManager::class.java).isInteractive)
                            dispatch(PttForegroundService.ACTION_EXTERNAL_PTT_HEARTBEAT)
                    }''',"don't fake smart KEY_UP")

svc=service.read_text("utf-8")
old="ScreenOffPttEligibility.allowed(this)"
assert svc.count(old)==4, "Expected four screen-off authorization checks"
svc=svc.replace(old,"(ScreenOffPttEligibility.allowed(this) || SmartExternalPttMode.allowed(this))")
service.write_text(svc,"utf-8")

patch(service,
'''    private var externalHeld = false''',
'''    private var externalHeld = false
    private var smartExternal = false
    private var smartMonitorJob: Job? = null

    private fun closeSmartExternal(reason:String) {
        if (!smartExternal) return
        ExternalPttDiagnostics.record(this,"audio","SMART_EXTERNAL_END "+reason)
        smartExternal=false
        smartMonitorJob=null
        SmartExternalVoiceGate.stop()
        SmartExternalPttMode.markClosed(this)
        ptt.forceMute()
        clearExternalGuard()
        pttHeld=false
        transmitRequestId+=1
        beginJob?.cancel()
        beginJob=null
        scope.launch { endTransmit() }
    }

    private fun startSmartVoiceMonitor(requestId:Long) {
        smartMonitorJob?.cancel()
        SmartExternalVoiceGate.start()
        smartMonitorJob=scope.launch {
            while(isActive && smartExternal && started && transmitting &&
                pttHeld && requestId==transmitRequestId) {
                delay(100L)
                val reason=SmartExternalVoiceGate.stopReason()
                if(reason!=null) {
                    closeSmartExternal(reason)
                    break
                }
            }
        }
    }''',"smart quiet listener state")
patch(service,
'''            val maxWait = if (externalRepeating) 4500L else 9000L''',
'''            val maxWait = if (smartExternal) 15000L
                else if (externalRepeating) 4500L else 9000L''',"bounded service watchdog")
patch(service,
'''            if (externalRepeating) 4500L else 9000L)''',
'''            if (smartExternal) 15000L
            else if (externalRepeating) 4500L else 9000L)''',"no repeat service max")
patch(service,
'''                if (externalKey) {
                    ExternalPttDiagnostics.record(this, "service",
                        "DOWN_RECEIVED started=" + started +''',
'''                if (externalKey) {
                    ExternalPttDiagnostics.record(this, "service",
                        "DOWN_RECEIVED started=" + started +''',"preserve radio dispatch")
patch(service,
'''                if (started && !roomSwitching) {
                    if (externalKey) refreshExternalGuard(false)
                    pttHeld = true''',
'''                if (started && !roomSwitching) {
                    if (externalKey) {
                        smartExternal =
                            !getSystemService(PowerManager::class.java).isInteractive &&
                            SmartExternalPttMode.allowed(this) &&
                            intent?.getBooleanExtra("melehat.shizuku_raw",false)!=true
                        refreshExternalGuard(false)
                    }
                    pttHeld = true''',"voice-gated hardware PTT selected only screen off")
patch(service,
'''                        beginJob = scope.launch { beginTransmit(requestId, externalKey) }''',
'''                        beginJob = scope.launch { beginTransmit(requestId, externalKey) }''',"preserve begin")
patch(service,
'''                if (started && !roomSwitching && externalHeld &&
                    intent?.getBooleanExtra("melehat.external_ptt",false) == true) {''',
'''                if (started && !roomSwitching && externalHeld && !smartExternal &&
                    intent?.getBooleanExtra("melehat.external_ptt",false) == true) {''',"no key-repeat required for smart")
patch(service,
'''        transmitting = true
        if (external) ExternalPttDiagnostics.record(this, "audio",
            "PTT_STARTED " + ExternalPttDiagnostics.screenState(this))''',
'''        transmitting = true
        if (external && smartExternal) startSmartVoiceMonitor(requestId)
        if (external) ExternalPttDiagnostics.record(this, "audio",
            "PTT_STARTED " + ExternalPttDiagnostics.screenState(this))''',"start on existing microphone track")
patch(service,
'''    private suspend fun endTransmit() {
        ptt.forceMute()''',
'''    private suspend fun endTransmit() {
        // Required even when screen turns on, another member gets the floor,
        // network drops or the user switches channels during a smart burst.
        smartMonitorJob?.cancel()
        smartMonitorJob=null
        SmartExternalVoiceGate.stop()
        if (smartExternal) {
            SmartExternalPttMode.markClosed(this)
            smartExternal=false
        }
        ptt.forceMute()''',"revoke gate on every radio stop")
patch(service,
'''    private suspend fun stopRadio() {
        pttHeld = false''',
'''    private suspend fun stopRadio() {
        SmartExternalVoiceGate.stop()
        smartMonitorJob?.cancel()
        smartMonitorJob=null
        if(smartExternal)SmartExternalPttMode.markClosed(this)
        smartExternal=false
        pttHeld = false''',"radio stop safe")

# A separate opt-in; existing accessible screen-on PTT remains default.
patch(compat,
'''        panel.addView(externalSwitch)
        val expected = android.content.ComponentName(''',
'''        panel.addView(externalSwitch)
        line("AKILLI DIŞ MANDAL • Ekran kapalıyken 2 sn sessizlik",18f,true)
        line("Ses+ tuşunun ilk basma olayı ulaşırsa seçili kanalda " +
             "konuşma başlar. WebRTC'nin mevcut mikrofon sesindeki " +
             "konuşma benzeri sesler izlenir. Yakın/uzak ses ayrımı yaklaşık " +
             "olduğu için ortam gürültüsü de algılanabilir. Konuşma bittikten " +
             "2 saniye sonra yayın kapanır; 15 saniyede zorla sona erer. " +
             "Ses kaydı ayrı saklanmaz. Yeni bir konuşma için tuşa tekrar basın.")
        val smartSwitch=android.widget.Switch(this).apply {
            text="Akıllı Ses+ (isteğe bağlı)"
            isChecked=com.saomi.telsiz.service.SmartExternalPttMode.enabled(
                this@DeviceCompatibilityActivity)
            setOnCheckedChangeListener { button,checked ->
                if(!checked) {
                    com.saomi.telsiz.service.SmartExternalPttMode.setEnabled(
                        this@DeviceCompatibilityActivity,false)
                    runCatching {
                        startService(Intent(this@DeviceCompatibilityActivity,
                            com.saomi.telsiz.service.PttForegroundService::class.java)
                            .setAction(
                                com.saomi.telsiz.service.PttForegroundService.ACTION_PTT_UP))
                    }
                } else {
                    button.isChecked=false
                    if (!com.saomi.telsiz.service.ScreenOffPttEligibility.consent(
                        this@DeviceCompatibilityActivity) ||
                        !externalPrefs.getBoolean("enabled",false)) {
                        android.widget.Toast.makeText(
                            this@DeviceCompatibilityActivity,
                            "Önce Dış Mandal ve erişilebilirlik kullanım onayını açın.",
                            android.widget.Toast.LENGTH_LONG).show()
                    } else {
                        android.app.AlertDialog.Builder(this@DeviceCompatibilityActivity)
                            .setTitle("Akıllı Dış Mandal • Açık onay")
                            .setMessage(
                                "Ekran kapalıyken Ses+ ilk basışı alındığında mikrofon " +
                                "en fazla 15 saniye seçili kanala yayın yapabilir. " +
                                "Kayıt yapılmaz; yalnızca konuşma sesi seviyesinin " +
                                "bir tahmini cihaz içinde hesaplanır. 2 saniye " +
                                "konuşma benzeri ses gelmezse veya ses örnekleri " +
                                "kesilirse mikrofon kapanır. Başkalarının konuşması " +
                                "ya da gürültü süreyi etkileyebilir. Sistem Ses+ " +
                                "basışını iletmezse özellik çalışmaz. Bu modu " +
                                "istediğiniz zaman kapatabilirsiniz."
                            )
                            .setNegativeButton("VAZGEÇ",null)
                            .setPositiveButton("AKILLI MANDALI AÇ") { _,_ ->
                                com.saomi.telsiz.service.SmartExternalPttMode.setEnabled(
                                    this@DeviceCompatibilityActivity,true)
                                render()
                            }.show()
                    }
                }
            }
        }
        panel.addView(smartSwitch)
        val expected = android.content.ComponentName(''',"smart mode explicit on/off")
for name,code in (("VolumePttAccessibilityService.kt",acc),("PttForegroundService.kt",service)):
    text=code.read_text("utf-8")
    assert "SCREEN_OFF" in text and "ACTION_PTT_UP" in text
assert "onPtt(true)" in (root/"ui/AppRoot.kt").read_text()
assert "onPtt(false)" in (root/"ui/AppRoot.kt").read_text()
assert 'applicationId = "com.melehat.telsiz"' in Path("app/build.gradle.kts").read_text()
print("MELEHAT_1384_SMART_EXTERNAL_2SEC_QUIET_15SEC_FAILCLOSED_READY")
