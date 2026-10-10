package com.saomi.telsiz.compat

import android.Manifest
import android.app.Activity
import android.app.NotificationManager
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import java.util.Locale

/**
 * Device-specific guidance. No hidden settings are changed automatically;
 * Android/OEM restrictions and force-stop semantics must be respected.
 */
class DeviceCompatibilityActivity : Activity() {
    private lateinit var panel: LinearLayout
    private val maker = (Build.MANUFACTURER ?: "").lowercase(Locale.ROOT)
    private val brand = (Build.BRAND ?: "").lowercase(Locale.ROOT)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "MELEHAT Telefon Uyumluluğu"
        panel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(20, 24, 20, 28)
        }
        // Android 15/16 draws apps edge-to-edge, including behind clock,
        // camera cutout and gesture navigation. Explicitly apply safe insets.
        WindowCompat.setDecorFitsSystemWindows(window, false)
        val scroll = ScrollView(this).apply {
            addView(panel)
            clipToPadding = false
        }
        ViewCompat.setOnApplyWindowInsetsListener(scroll) { view, insets ->
            val safe = insets.getInsets(
                WindowInsetsCompat.Type.systemBars() or
                    WindowInsetsCompat.Type.displayCutout()
            )
            view.setPadding(safe.left, safe.top, safe.right, safe.bottom)
            insets
        }
        setContentView(scroll)
        ViewCompat.requestApplyInsets(scroll)
        render()
    }

    override fun onResume() {
        super.onResume()
        if (::panel.isInitialized) render()
    }

    private fun line(value: String, size: Float = 15f, bold: Boolean = false) {
        panel.addView(TextView(this).apply {
            text = value
            textSize = size
            setTextColor(if (bold) Color.rgb(19, 58, 85) else Color.DKGRAY)
            if (bold) setTypeface(null, android.graphics.Typeface.BOLD)
            setPadding(0, 8, 0, 8)
        })
    }

    private fun action(label: String, block: () -> Unit) {
        panel.addView(Button(this).apply {
            text = label
            isAllCaps = false
            setOnClickListener { block() }
        }, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { bottomMargin = 10 })
    }

    private fun appDetails() = Intent(
        Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
        Uri.parse("package:" + packageName)
    )

    private fun openSettings(intent: Intent) {
        val ok = runCatching { startActivity(intent) }.isSuccess
        if (!ok) runCatching { startActivity(appDetails()) }
    }

    private fun group(): String = when {
        listOf("xiaomi", "redmi", "poco", "black shark").any {
            maker.contains(it) || brand.contains(it)
        } -> "Xiaomi / Redmi / POCO"
        maker.contains("samsung") -> "Samsung"
        listOf("oppo", "realme", "oneplus").any {
            maker.contains(it) || brand.contains(it)
        } -> "OPPO / realme / OnePlus"
        listOf("vivo", "iqoo").any {
            maker.contains(it) || brand.contains(it)
        } -> "vivo / iQOO"
        listOf("huawei", "honor").any {
            maker.contains(it) || brand.contains(it)
        } -> "Huawei / Honor"
        listOf("tecno", "infinix", "itel", "transsion").any {
            maker.contains(it) || brand.contains(it)
        } -> "TECNO / Infinix / itel"
        listOf("google", "motorola", "nokia", "hmd").any {
            maker.contains(it) || brand.contains(it)
        } -> "Pixel / Motorola / Nokia"
        else -> "Standart Android"
    }

    private fun manufacturerInstructions(g: String) = when (g) {
        "Xiaomi / Redmi / POCO" ->
            "MELEHAT > Pil tasarrufu: Kısıtlama yok. Güvenlik / İzinler / " +
            "Otomatik başlatma: izin verin. Arka plan verisini açık tutun. " +
            "HyperOS sürümüne göre menüler farklı olabilir."
        "Samsung" ->
            "MELEHAT > Pil: Kısıtlanmamış. Pil ve cihaz bakımı > Pil > " +
            "Arka plan kullanım sınırları: Uykuya alınmayan uygulamalara ekleyin."
        "OPPO / realme / OnePlus" ->
            "MELEHAT > Pil kullanımı: Arka plan etkinliğine izin verin. " +
            "Otomatik başlatma ve pil optimizasyonu kısıtlamalarını kaldırın."
        "vivo / iQOO" ->
            "Uygulama yöneticisi > MELEHAT > Arka planda çalışma ve " +
            "Otomatik başlatmayı açın. Pil kısıtlamasını kaldırın."
        "Huawei / Honor" ->
            "Pil > Uygulama başlatma > MELEHAT: Elle yönet; Otomatik başlatma, " +
            "İkincil başlatma ve Arka planda çalışmayı etkinleştirin."
        "TECNO / Infinix / itel" ->
            "MELEHAT > Pil: Kısıtlama yok. Phone Master / Pil yöneticisinde " +
            "arka plan temizleme ve otomatik başlatma kısıtlarını kaldırın."
        else ->
            "Uygulamalar > MELEHAT > Pil: Kısıtlanmamış / Sınırsız. " +
            "Bildirimler, mikrofon ve arka plan veri erişimini açık tutun."
    }

    private fun hasPermission(permission: String) =
        ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED

    private fun render() {
        panel.removeAllViews()
        val g = group()
        // Short, responsive heading on smaller phone widths.
        line("MELEHAT • Uyumluluk Kontrolü", 19f, true)
        line("Marka: " + Build.MANUFACTURER + " / " + Build.BRAND +
            "\nModel: " + Build.MODEL +
            "\nAndroid: " + Build.VERSION.RELEASE + " (API " + Build.VERSION.SDK_INT + ")" +
            "\nCihaz grubu: " + g)
        line("İzinleri cihazınızda kontrol edebilirsiniz. Hiçbir sistem izni " +
             "kendiliğinden verilmez ve model uyumu gerçek test olmadan garanti edilemez.")

        line("İzinler ve pil ayarları", 18f, true)
        val mic = hasPermission(Manifest.permission.RECORD_AUDIO)
        line("Mikrofon: " + if (mic) "✓ İzinli" else "⚠ İzin gerekli")
        if (!mic) action("Mikrofon izni iste") {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 1461)
        }

        val nm = getSystemService(NotificationManager::class.java)
        val notifPerm = Build.VERSION.SDK_INT < 33 ||
            hasPermission(Manifest.permission.POST_NOTIFICATIONS)
        val notif = notifPerm && nm.areNotificationsEnabled()
        line("Telsiz ve arama bildirimleri: " + if (notif) "✓ Açık" else "⚠ Kontrol gerekli")
        if (!notifPerm && Build.VERSION.SDK_INT >= 33) action("Bildirim izni iste") {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1462)
        }
        action("Bildirim ayarlarını aç") {
            if (Build.VERSION.SDK_INT >= 26) openSettings(
                Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                    .putExtra(Settings.EXTRA_APP_PACKAGE, packageName)
            ) else openSettings(appDetails())
        }

        if (Build.VERSION.SDK_INT >= 31) {
            val bt = hasPermission(Manifest.permission.BLUETOOTH_CONNECT)
            line("Bluetooth kulaklık izni: " + if (bt) "✓ İzinli" else "⚠ İzin gerekli")
            if (!bt) action("Bluetooth izni iste") {
                requestPermissions(arrayOf(Manifest.permission.BLUETOOTH_CONNECT), 1463)
            }
        }

        val power = getSystemService(PowerManager::class.java)
        val exempt = power.isIgnoringBatteryOptimizations(packageName)
        line("Android pil optimizasyonu muafiyeti: " +
            if (exempt) "✓ Muaf" else "⚠ Muaf değil; kontrol edilmeli")
        action("Android pil optimizasyon ayarları") {
            openSettings(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
        }

        if (Build.VERSION.SDK_INT >= 34) {
            val full = nm.canUseFullScreenIntent()
            line("Kilit ekranı tam ekran çağrı: " + if (full) "✓ Etkin" else "⚠ İzin gerekli")
            if (!full) action("Tam ekran arama ayarları") {
                openSettings(Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT,
                    Uri.parse("package:" + packageName)))
            }
        }

        line(g + " • Arka plan çalışma önerileri", 18f, true)
        line(manufacturerInstructions(g))
        line("Üretici otomatik başlatma ve uyku listesini Android SDK üzerinden " +
            "güvenilir olarak okuyamayız; bu seçenekler elle kontrol edilmelidir.")
        action("MELEHAT uygulama ayarlarını aç") { openSettings(appDetails()) }
        line("Not: 'Zorla durdur' seçildiğinde Android uygulamayı kullanıcı " +
            "yeniden açana kadar otomatik başlatmayı engelleyebilir.")
        action("MELEHAT'a geri dön") { finish() }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<out String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        render()
    }
}
