from pathlib import Path

# v1.3.57 — opt-in Shizuku RAW Volume+ diagnostics only.
# No PTT microphone actions from Shizuku. User picks Shizuku-exported files
# through Android document picker. No new applicationId or keystore.

base=Path("app")
root=base/"src/main"
src=root/"java/com/saomi/telsiz"
manifest=root/"AndroidManifest.xml"
gradle=base/"build.gradle.kts"
compat=src/"compat/DeviceCompatibilityActivity.kt"
service=src/"service/PttForegroundService.kt"
diag=src/"service/ExternalPttDiagnostics.kt"

def patch(path,old,new):
    content=path.read_text(encoding="utf-8")
    if content.count(old)!=1:
        raise SystemExit(f"v1357 anchor {path} found {content.count(old)} expected 1: {old[:100]}")
    path.write_text(content.replace(old,new,1),encoding="utf-8")

patch(gradle,
'    implementation("io.livekit:livekit-android:2.29.0")',
'''    implementation("io.livekit:livekit-android:2.29.0")
    implementation("dev.rikka.shizuku:api:13.1.5")
    implementation("dev.rikka.shizuku:provider:13.1.5")''')
patch(manifest,'    <application',
'''    <uses-permission android:name="moe.shizuku.manager.permission.API_V23" />
    <application''')
patch(manifest,'</application>',
'''    <provider
        android:name="rikka.shizuku.ShizukuProvider"
        android:authorities="com.melehat.telsiz.shizuku"
        android:multiprocess="false"
        android:enabled="true"
        android:exported="true"
        android:permission="android.permission.INTERACT_ACROSS_USERS_FULL" />
    </application>''')
patch(diag,'"key", "dispatch", "service", "audio", "watchdog", "access", "screen" -> stage',
           '"key", "dispatch", "service", "audio", "watchdog", "access", "screen", "shizuku" -> stage')

probe=src/"service/ShizukuRawKeyProbe.kt"
probe.write_text(r'''package com.saomi.telsiz.service

import android.content.Context
import android.content.pm.PackageManager
import android.system.Os
import rikka.shizuku.Shizuku
import java.io.File

/**
 * TEST-ONLY bridge: observes actual kernel KEY_VOLUMEUP DOWN/UP while locked.
 * It never starts, stops or changes an audio transmission.
 *
 * User supplies unmodified files exported from their own installed Shizuku:
 * filesDir/shizuku/rish and rish_shizuku.dex.
 */
class ShizukuRawKeyProbe(private val context: Context) {
    @Volatile private var running = false
    @Volatile private var process: Process? = null
    @Volatile private var keyDown = false
    private val lock = Any()

    fun start() {
        if (running) return
        val dir = File(context.filesDir, "shizuku")
        val script = File(dir, "rish")
        val dex = File(dir, "rish_shizuku.dex")
        if (!script.isFile || !dex.isFile || script.length() < 50 || dex.length() < 1000) {
            record("DOSYALAR_EKSIK: rish ve rish_shizuku.dex seçin")
            return
        }
        if (!runCatching { Shizuku.pingBinder() && Shizuku.checkSelfPermission() ==
                    PackageManager.PERMISSION_GRANTED }.getOrDefault(false)) {
            record("SHIZUKU_YETKISI_GEREKLI")
            return
        }
        if (!runCatching { Os.chmod(dex.absolutePath, 0x100) }.isSuccess) {
            record("DEX_CHMOD_HATASI")
            return
        }
        running = true
        Thread({
            try {
                // Discover KEY_VOLUMEUP device rather than assuming event0.
                val dollar = '$'
                val cmd = "vol=''; for d in /dev/input/event*; do " +
                    "if /system/bin/getevent -pl \"" + dollar + "d\" 2>/dev/null | " +
                    "/system/bin/grep -q KEY_VOLUMEUP; then vol=\"" + dollar + "d\"; break; fi; done; " +
                    "[ -n \"" + dollar + "vol\" ] || exit 10; " +
                    "exec /system/bin/getevent -lt \"" + dollar + "vol\""
                val p = ProcessBuilder("/system/bin/sh", script.absolutePath,
                    "-c", cmd).apply {
                    environment()["RISH_APPLICATION_ID"] = context.packageName
                    redirectErrorStream(true)
                }.start()
                process = p
                record("RAW_READER_STARTED")
                p.inputStream.bufferedReader().use { reader ->
                    while (running) {
                        val line = reader.readLine() ?: break
                        parse(line)
                    }
                }
                val exit = p.waitFor()
                if (running) record("RAW_READER_EXIT_" + exit)
            } catch (e: Exception) {
                if (running) record("RAW_READER_ERROR_" + e.javaClass.simpleName)
            } finally {
                running = false
                process?.destroy()
                process = null
                synchronized(lock) { keyDown = false }
            }
        }, "melehat-shizuku-raw-diag").apply { isDaemon=true; start() }
    }

    fun stop() {
        running = false
        process?.destroy()
        process = null
        synchronized(lock) { keyDown=false }
        record("RAW_READER_STOPPED")
    }

    private fun parse(line: String) {
        if (!line.contains("EV_KEY") || !line.contains("KEY_VOLUMEUP")) return
        val event = line.trim().substringAfterLast(' ')
        if (event != "DOWN" && event != "UP" && event != "REPEAT") return
        synchronized(lock) {
            if (event=="DOWN" && keyDown) return
            if (event=="UP" && !keyDown) {
                record("RAW_KEY_UP_WITHOUT_DOWN")
                return
            }
            if (event=="DOWN") keyDown=true
            if (event=="UP") keyDown=false
            if (event!="REPEAT")
                record("RAW_KEY_" + event + " " + ExternalPttDiagnostics.screenState(context))
        }
    }

    private fun record(message:String) =
        ExternalPttDiagnostics.record(context,"shizuku",message)
}
''',encoding="utf-8")

patch(service,
'    private var started = false',
'''    private var shizukuRawProbe: ShizukuRawKeyProbe? = null
    private var started = false''')
patch(service,
'        when (resolvedAction) {',
'''        when (resolvedAction) {
            ACTION_SHIZUKU_DIAG_START -> {
                if (!started || !store.isRadioEnabled()) {
                    ExternalPttDiagnostics.record(this,"shizuku","TELSIZ_ACIK_OLMALI")
                } else {
                    if (shizukuRawProbe==null) shizukuRawProbe=ShizukuRawKeyProbe(this)
                    shizukuRawProbe?.start()
                }
            }
            ACTION_SHIZUKU_DIAG_STOP -> {
                shizukuRawProbe?.stop()
                shizukuRawProbe=null
            }''')
patch(service,
'    override fun onDestroy() {\n        if (externalScreenReceiverRegistered)',
'''    override fun onDestroy() {
        shizukuRawProbe?.stop()
        shizukuRawProbe=null
        if (externalScreenReceiverRegistered)''')
patch(service,
'        const val ACTION_START = "com.saomi.telsiz.START"',
'''        const val ACTION_SHIZUKU_DIAG_START = "com.saomi.telsiz.SHIZUKU_DIAG_START"
        const val ACTION_SHIZUKU_DIAG_STOP = "com.saomi.telsiz.SHIZUKU_DIAG_STOP"
        const val ACTION_START = "com.saomi.telsiz.START"''')

# SAF: import two Shizuku-exported files to MELEHAT private storage.
patch(compat,
'    private lateinit var panel: LinearLayout',
'''    private lateinit var panel: LinearLayout
    private val rishRequest = 13571
    private val dexRequest = 13572''')
patch(compat,
'    private fun appDetails() = Intent(',
'''    private fun pickShizukuFile(requestCode:Int) {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "*/*"
        }
        startActivityForResult(intent, requestCode)
    }

    override fun onActivityResult(requestCode:Int, resultCode:Int, data:Intent?) {
        super.onActivityResult(requestCode,resultCode,data)
        if ((requestCode != rishRequest && requestCode != dexRequest) ||
            resultCode != Activity.RESULT_OK || data?.data == null) return
        val name = if (requestCode == rishRequest) "rish" else "rish_shizuku.dex"
        val saved=runCatching {
            val directory=java.io.File(filesDir,"shizuku")
            directory.mkdirs()
            val dst=java.io.File(directory,name)
            if (dst.exists() && !dst.delete()) error("Could not replace old file")
            contentResolver.openInputStream(data.data!!)?.use { source ->
                dst.outputStream().use { output -> source.copyTo(output) }
            } ?: error("Unable to open selected document")
            val header=dst.inputStream().use { it.readBytes().take(4).toByteArray() }
            val valid=if (name=="rish") header.size>=2 &&
                    header[0]==35.toByte() && header[1]==33.toByte()
                else header.size>=4 && header.contentEquals(
                    byteArrayOf(100,101,120,10))
            if (!valid) {
                dst.delete()
                error("Invalid rish file")
            }
            if (name.endsWith(".dex")) android.system.Os.chmod(dst.absolutePath, 0x100)
            true
        }.getOrElse {
            com.saomi.telsiz.service.ExternalPttDiagnostics.record(
                this,"shizuku","DOSYA_HATASI_"+it.javaClass.simpleName)
            false
        }
        if(saved) com.saomi.telsiz.service.ExternalPttDiagnostics.record(
            this,"shizuku","DOSYA_HAZIR_"+name)
        render()
    }

    private fun appDetails() = Intent(''')
patch(compat,
'        line("Kilit ekranı dış mandal teşhisi", 18f, true)',
'''        line("SHIZUKU HAM TUŞ TESTİ • mikrofonu kontrol etmez", 18f, true)
        val shizukuAvailable = runCatching { rikka.shizuku.Shizuku.pingBinder() }
            .getOrDefault(false)
        val shizukuGranted = shizukuAvailable && runCatching {
            rikka.shizuku.Shizuku.checkSelfPermission()==PackageManager.PERMISSION_GRANTED
        }.getOrDefault(false)
        val userFiles=java.io.File(filesDir,"shizuku")
        val hasRish=java.io.File(userFiles,"rish").isFile
        val hasDex=java.io.File(userFiles,"rish_shizuku.dex").isFile
        line("Shizuku bağlantısı: " + if (shizukuAvailable) "ÇALIŞIYOR" else "KAPALI")
        line("MELEHAT Shizuku yetkisi: " + if (shizukuGranted) "İZİNLİ" else "İZİN GEREKLİ")
        action("MELEHAT için Shizuku izni iste") {
            runCatching { rikka.shizuku.Shizuku.requestPermission(13573) }
                .onFailure { com.saomi.telsiz.service.ExternalPttDiagnostics.record(
                    this,"shizuku","IZIN_HATASI_"+it.javaClass.simpleName) }
        }
        line("Shizuku dosyaları: rish=" + hasRish + " / dex=" + hasDex)
        action("Shizuku klasöründen rish dosyasını seç") { pickShizukuFile(rishRequest) }
        action("Shizuku klasöründen rish_shizuku.dex seç") { pickShizukuFile(dexRequest) }
        action("HAM TUŞ TESTİNİ BAŞLAT (SES GÖNDERMEZ)") {
            if (!shizukuGranted || !hasRish || !hasDex) {
                com.saomi.telsiz.service.ExternalPttDiagnostics.record(
                    this,"shizuku","IZIN_VEYA_DOSYA_EKSIK")
            } else {
                val intent=Intent(this,com.saomi.telsiz.service.PttForegroundService::class.java)
                    .setAction(com.saomi.telsiz.service.PttForegroundService.ACTION_SHIZUKU_DIAG_START)
                runCatching { startService(intent) }
            }
            render()
        }
        action("HAM TUŞ TESTİNİ DURDUR") {
            val intent=Intent(this,com.saomi.telsiz.service.PttForegroundService::class.java)
                .setAction(com.saomi.telsiz.service.PttForegroundService.ACTION_SHIZUKU_DIAG_STOP)
            runCatching { startService(intent) }
            render()
        }
        line("Testi başlatın, ekranı kilitleyip Ses + tuşuna üç kez basıp bırakın. " +
            "Ardından kaydı yenileyin. RAW_KEY_DOWN ve RAW_KEY_UP görünmesi gerekiyor.")
        line("Shizuku ham tuş: " +
            com.saomi.telsiz.service.ExternalPttDiagnostics.describe(this,"shizuku"))
        line("Kilit ekranı dış mandal teşhisi", 18f, true)''')

for important,path in [
("LiveKitPttClient(applicationContext)",service),
("ACTION_PTT_DOWN",service),
("ACTION_PTT_UP",service),
("ACTION_SWITCH_ROOM",service),
("SCREEN_OFF_PTT_BLOCKED_FOR_SAFETY",service),
("SHIZUKU_DIAG_START",service),
("ShizukuRawKeyProbe",probe),
("ACTION_OPEN_DOCUMENT",compat),
("HAM TUŞ TESTİNİ BAŞLAT",compat),
("rikka.shizuku.ShizukuProvider",manifest),
('applicationId = "com.melehat.telsiz"',gradle)
]:
    if important not in path.read_text(encoding="utf-8"):
        raise SystemExit("v1357 preserved feature missing "+important)
print("MELEHAT_1357_SHIZUKU_DIAGNOSTIC_ONLY_READY")
