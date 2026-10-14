#!/usr/bin/env python3
"""MELEHAT v1.3.88 -- opt-in, 90-second MediaSession/VolumeProvider diagnostic.

This checks whether Android routes VOLUME_ADJUST requests to a remote-volume
session while the display is genuinely noninteractive. VolumeProvider does not
expose physical KEY_UP, so no mandal / microphone control is enabled.
The probe only runs on explicit consent. It forwards the volume step to
STREAM_MUSIC while testing, and restores the original Android routing by
releasing the session on stop or expiration. This forwarding is not guaranteed
to mirror every OEM's usual volume destination, and the user is warned.
"""
from pathlib import Path

root=Path("app/src/main/java/com/saomi/telsiz")
access=root/"service/VolumePttAccessibilityService.kt"
activity=root/"MainActivity.kt"
ui=root/"compat/DeviceCompatibilityActivity.kt"
diag=root/"service/MediaVolumeProbe.kt"

def patch(path, old, new, label):
    s=path.read_text("utf-8")
    n=s.count(old)
    if n!=1:
        raise SystemExit(f"MELEHAT_1388 {label}: expected 1 anchor, found {n}")
    path.write_text(s.replace(old,new,1),"utf-8")

if diag.exists():
    raise SystemExit("MELEHAT_1388 probe already exists")

diag.write_text('''package com.saomi.telsiz.service

import android.app.KeyguardManager
import android.content.Context
import android.media.AudioManager
import android.media.VolumeProvider
import android.media.session.MediaSession
import android.media.session.PlaybackState
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock

/**
 * Diagnostic only. MediaSession's VolumeProvider provides volume adjustment
 * requests, NOT physical KeyEvent ACTION_DOWN / ACTION_UP.
 * Does not send PTT commands, open the mic, record sound, or store audio.
 * A temporary REMOTE session can alter which audio volume is controlled, even
 * though adjustments are forwarded to STREAM_MUSIC. This is consent-gated.
 */
object MediaVolumeProbe {
    private const val PREF="melehat_media_volume_probe"
    private const val DURATION_MS=90_000L
    private val handler=Handler(Looper.getMainLooper())
    private var activeSession: MediaSession?=null
    private var until: Long=0L
    private var expiry: Runnable?=null

    private fun prefs(ctx:Context)=ctx.getSharedPreferences(PREF,Context.MODE_PRIVATE)

    private fun displayState(ctx:Context):String {
        val pm=ctx.getSystemService(PowerManager::class.java)
        if (!pm.isInteractive) return "SCREEN_OFF"
        val km=ctx.getSystemService(Context.KEYGUARD_SERVICE) as? KeyguardManager
        return if (km?.isKeyguardLocked==true) "SCREEN_LOCKED_ON" else "SCREEN_ON"
    }

    @Synchronized fun isActive(ctx:Context):Boolean {
        if(activeSession!=null && SystemClock.elapsedRealtime()>=until) stop()
        return activeSession!=null
    }

    @Synchronized fun start(ctx:Context):String {
        if(isActive(ctx)) return "MediaSession testi zaten açık"
        if(NativeVolumeProbe.isActive(ctx))
            return "Önce ANDROID YEREL TUŞ TESTİNİ BİTİR"
        if(ShizukuRawPttState.enabled)
            return "Önce SHIZUKU DIŞ MANDALI KAPAT"
        val app=ctx.applicationContext
        val audio=app.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        if(audio.mode!=AudioManager.MODE_NORMAL)
            return "Çağrı sırasında bu test açılamaz"
        val max=audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC).coerceAtLeast(1)
        val vol=audio.getStreamVolume(AudioManager.STREAM_MUSIC).coerceIn(0,max)
        val p=prefs(app)
        p.edit().clear().putLong("test_time",System.currentTimeMillis()).apply()
        until=SystemClock.elapsedRealtime()+DURATION_MS
        val provider=object:VolumeProvider(VOLUME_CONTROL_RELATIVE,max,vol) {
            override fun onAdjustVolume(direction:Int) {
                if(!isActive(app)) return
                if(direction!=AudioManager.ADJUST_RAISE &&
                    direction!=AudioManager.ADJUST_LOWER) return
                val state=displayState(app)
                val field=state+(if(direction==AudioManager.ADJUST_RAISE)
                    "_plus" else "_minus")
                val pr=prefs(app)
                pr.edit().putInt(field,pr.getInt(field,0)+1)
                    .putString("last","VolumeProvider "+
                        (if(direction==AudioManager.ADJUST_RAISE) "+" else "-")+
                        " "+state+" time="+System.currentTimeMillis()).apply()
                // While this temporary remote session owns volume requests,
                // forward the same step to the normal music volume. This MAY
                // differ from the OEM's usual selected stream; test only.
                runCatching {
                    audio.adjustStreamVolume(AudioManager.STREAM_MUSIC,direction,0)
                    setCurrentVolume(audio.getStreamVolume(
                        AudioManager.STREAM_MUSIC).coerceIn(0,max))
                }
            }
        }
        return try {
            val s=MediaSession(app,"MELEHAT_1388_MEDIA_VOLUME_PROBE")
            activeSession=s
            s.setPlaybackToRemote(provider)
            s.setPlaybackState(
                PlaybackState.Builder()
                    .setState(PlaybackState.STATE_PLAYING,0L,1.0f)
                    .setActions(0L)
                    .build())
            s.isActive=true
            val task=Runnable { stop() }
            expiry=task
            handler.postDelayed(task,DURATION_MS)
            "90 sn tanılama başladı: ses iletilmez, geçici ses yönlendirmesi açık"
        } catch (err:Exception) {
            stop()
            "MediaSession başlatılamadı: "+(err.message ?: err.javaClass.simpleName)
        }
    }

    @Synchronized fun stop() {
        expiry?.let { handler.removeCallbacks(it) }
        expiry=null
        val s=activeSession
        activeSession=null
        until=0L
        if(s!=null) runCatching {
            s.isActive=false
            s.release()
        }
    }

    fun report(ctx:Context):String {
        val p=prefs(ctx)
        val active=isActive(ctx)
        val time=if(active) ((until-SystemClock.elapsedRealtime())/1000L)
            .coerceAtLeast(0L) else 0L
        return (if(active) "TEST AÇIK ("+time+" sn)" else "TEST KAPALI")+
            " | KARANLIK +:"+p.getInt("SCREEN_OFF_plus",0)+
            " -:"+p.getInt("SCREEN_OFF_minus",0)+
            " | KİLİTLİ AYDINLIK +:"+p.getInt("SCREEN_LOCKED_ON_plus",0)+
            " -:"+p.getInt("SCREEN_LOCKED_ON_minus",0)+
            " | AÇIK EKRAN +:"+p.getInt("SCREEN_ON_plus",0)+
            " -:"+p.getInt("SCREEN_ON_minus",0)+
            "\\nSon olay: "+p.getString("last","Henüz MediaSession ses komutu yok")+
            "\\nNOT: Bu API KEY_UP/bırakma vermez. + isteği PTT başarısı değildir."
    }
}
''',encoding="utf-8")

# Accessibility must not start a normal external PTT hold during the test.
# Return FALSE, allowing system routing, rather than consuming the key.
patch(access,
'''        if (ShizukuRawPttState.enabled) {''',
'''        if (MediaVolumeProbe.isActive(this)) return false
        if (ShizukuRawPttState.enabled) {''',
"accessibility nontransmitting route")

# Disable Activity's fallback PTT route for the short diagnostic too.
patch(activity,
'''            if (com.saomi.telsiz.service.NativeVolumeProbe.isActive(this))
                return super.onKeyDown(keyCode, event)''',
'''            if (com.saomi.telsiz.service.NativeVolumeProbe.isActive(this) ||
                com.saomi.telsiz.service.MediaVolumeProbe.isActive(this))
                return super.onKeyDown(keyCode, event)''',
"Activity KEY_DOWN bypass")
patch(activity,
'''        if (keyCode == KeyEvent.KEYCODE_VOLUME_UP &&
            com.saomi.telsiz.service.NativeVolumeProbe.isActive(this))
            return super.onKeyUp(keyCode, event)''',
'''        if (keyCode == KeyEvent.KEYCODE_VOLUME_UP &&
            (com.saomi.telsiz.service.NativeVolumeProbe.isActive(this) ||
             com.saomi.telsiz.service.MediaVolumeProbe.isActive(this)))
            return super.onKeyUp(keyCode, event)''',
"Activity KEY_UP bypass")

# One probe at a time.
patch(ui,
'''        action("ANDROID YEREL TUŞ TESTİNİ BAŞLAT") {
            if (com.saomi.telsiz.service.ShizukuRawPttState.enabled) {''',
'''        action("ANDROID YEREL TUŞ TESTİNİ BAŞLAT") {
            if (com.saomi.telsiz.service.MediaVolumeProbe.isActive(this)) {
                android.widget.Toast.makeText(this,
                    "Önce MediaSession testini bitir",
                    android.widget.Toast.LENGTH_LONG).show()
            } else if (com.saomi.telsiz.service.ShizukuRawPttState.enabled) {''',
"do not overlap native test")

patch(ui,
'''        line("SHIZUKU SES + MANDAL • BASILI KONUŞ", 18f, true)''',
'''        line("MELEHAT 1.3.88 • MEDİASESSION SES TUŞU TESTİ",18f,true)
        line("Bu deney Android'in ses ARTIR/AZALT isteğini MediaSession'a " +
            "gönderip göndermediğini kontrol eder. Tuş bırakmayı (KEY_UP) " +
            "tespit EDEMEZ; dolayısıyla telsiz mandalı değildir. " +
            "Mikrofon açılmaz, konuşma gönderilmez. " +
            "90 saniyelik deney sırasında medya ses kontrolünün " +
            "davranışı geçici olarak değişebilir. Başka medya " +
            "oynatırken veya görüşme yaparken başlatmayın.")
        line(com.saomi.telsiz.service.MediaVolumeProbe.report(this))
        action("MEDİASESSION TESTİNİ BAŞLAT (90 sn)") {
            android.app.AlertDialog.Builder(this)
                .setTitle("Geçici Android ses kontrolü deneyi")
                .setMessage("90 saniye boyunca telefon ses tuşlarının " +
                    "yönlendirilmesi geçici değişebilir. Test ses " +
                    "GÖNDERMEZ ve fiziksel tuşun BIRAKMA olayını ölçmez. " +
                    "Onaylıyor musunuz?")
                .setPositiveButton("TESTİ BAŞLAT") { _, _ ->
                    val result=com.saomi.telsiz.service.MediaVolumeProbe.start(this)
                    android.widget.Toast.makeText(this,result,
                        android.widget.Toast.LENGTH_LONG).show()
                    render()
                }
                .setNegativeButton("VAZGEÇ",null)
                .show()
        }
        action("MEDİASESSION TESTİNİ BİTİR") {
            com.saomi.telsiz.service.MediaVolumeProbe.stop()
            render()
        }
        action("MEDİASESSION KAYDINI YENİLE") { render() }
        line("Testi başlatıp Ses+ tuşuna ekran açıkken üç, " +
            "kilitli aydınlık ekranda üç, tamamen karanlık ekranda " +
            "on kez basın. Ekranı açıp kaydı yenileyin. " +
            "Karanlıkta + sayısı 0 kalırsa bu yöntem de " +
            "tuşu uygulamaya iletmiyor. Sayı artsa dahi " +
            "KEY_UP gelmediğinden basılı konuş PTT'ye bağlanmaz.")
        line("SHIZUKU SES + MANDAL • BASILI KONUŞ", 18f, true)''',
"explicit opt-in MediaSession controls")

for src, phrases in {
    access:["MediaVolumeProbe.isActive(this) return false",
            "NativeVolumeProbe.observe(this, event)"],
    activity:["MediaVolumeProbe.isActive(this)","NativeVolumeProbe.isActive(this)"],
    ui:["MEDİASESSION TESTİNİ BAŞLAT","MEDİASESSION TESTİNİ BİTİR",
        "ANDROID YEREL TUŞ TESTİNİ BAŞLAT","SHIZUKU SES + MANDAL"],
    diag:["object MediaVolumeProbe","MediaSession(app","VolumeProvider(",
         "SCREEN_OFF_plus","s.release()","KEY_UP","90_000L"],
}.items():
    s=src.read_text("utf-8")
    for phrase in phrases:
        # whitespace-tolerant validation of the accessibility guard
        if phrase=="MediaVolumeProbe.isActive(this) return false":
            phrase="MediaVolumeProbe.isActive(this)) return false"
        if phrase not in s:
            raise SystemExit(f"MELEHAT_1388 missing {src.name}: {phrase}")

assert "ACTION_PTT_DOWN" in (root/"service/PttForegroundService.kt").read_text("utf-8")
assert "onPtt(true)" in (root/"ui/AppRoot.kt").read_text("utf-8")
assert "onPtt(false)" in (root/"ui/AppRoot.kt").read_text("utf-8")
assert 'applicationId = "com.melehat.telsiz"' in Path("app/build.gradle.kts").read_text("utf-8")
print("MELEHAT_1388_90S_MEDIASESSION_VOLUME_PROBE_READY")
