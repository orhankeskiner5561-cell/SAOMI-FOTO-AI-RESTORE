#!/usr/bin/env python3
# MELEHAT v1.3.63 — first isolated in-APK P2P WebRTC entry.
# This screen uses the independently verified P2P 2.0 HTTPS web client.
# No changes to LiveKit, on-screen PTT, background service, authorization,
# channel routing, update package ID, Android signing, or Shizuku key handling.
from pathlib import Path

root=Path("app/src/main")
java=root/"java/com/saomi/telsiz"
ui=java/"ui/AppRoot.kt"
manifest=root/"AndroidManifest.xml"
activity=java/"p2p/MelehatP2pActivity.kt"
version=Path("app/build.gradle.kts")
assert ui.is_file() and manifest.is_file() and version.is_file(), "MELEHAT base Android source missing"
assert not activity.exists(), "P2P Activity already exists: stopping to avoid overwriting"

app=ui.read_text(encoding="utf-8")
anchor='''                    Text("Telsiz durumu", fontWeight = FontWeight.SemiBold)'''
assert app.count(anchor)==1, f"PTT panel UI placement changed, found {app.count(anchor)} anchors"
extra='''                    // Isolated in-app WebRTC pilot: original PTT and LiveKit remain unchanged.
                    TextButton(onClick = {
                        roomsContext.startActivity(
                            android.content.Intent(
                                roomsContext,
                                com.saomi.telsiz.p2p.MelehatP2pActivity::class.java
                            )
                        )
                    }) {
                        Text("P2P SES • DOĞRUDAN GÖRÜŞME", fontWeight = FontWeight.SemiBold)
                    }
'''
app=app.replace(anchor,anchor+"\n"+extra,1)
for check in ("onPtt(true)", "onPtt(false)", "MELEHAT_UPDATE_MANIFEST", "LiveChannelUiState.connectionProblem.collectAsState()"):
    assert check in app, "Protected UI component missing: "+check

m=manifest.read_text(encoding="utf-8")
assert m.count("</application>")==1, "AndroidManifest application structure changed"
permission='<uses-permission android:name="android.permission.RECORD_AUDIO"'
if permission not in m:
    m=m.replace("<application", permission + " />\n    <application",1)
activity_tag='''        <activity
            android:name="com.saomi.telsiz.p2p.MelehatP2pActivity"
            android:exported="false"
            android:label="MELEHAT P2P SES"
            android:usesCleartextTraffic="false" />
'''
m=m.replace("    </application>",activity_tag+"    </application>",1)

activity.parent.mkdir(parents=True,exist_ok=True)
activity.write_text(r'''package com.saomi.telsiz.p2p

import android.Manifest
import android.app.Activity
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import org.json.JSONTokener

/**
 * Isolated first-stage Android integration of the verified MELEHAT P2P browser
 * engine. No LiveKit microphone, foreground PTT service or channel selection
 * logic is replaced. Android app retains the existing signing identity.
 *
 * Audio goes through the WebRTC connection in the loaded HTTPS page. The
 * Supabase endpoint exchanges offer/answer only; it never transports speech.
 * This does NOT yet implement member-authenticated native channel routing.
 */
class MelehatP2pActivity : Activity() {
    private val baseUrl = "https://melehat-p2p-auto.vercel.app/"
    private val host = "melehat-p2p-auto.vercel.app"
    private val permissionId = 6451
    private var pendingCapture: PermissionRequest? = null
    private lateinit var web: WebView
    private lateinit var inviteInput: EditText

    private fun dp(p: Int): Int = (p * resources.displayMetrics.density).toInt()
    private fun message(t: String) =
        Toast.makeText(this, t, Toast.LENGTH_LONG).show()

    private fun validInvite(input: String): String? {
        return try {
            val uri = Uri.parse(input.trim())
            val secret = uri.getQueryParameter("room") ?: return null
            if (uri.scheme != "https" || uri.host != host ||
                !secret.matches(Regex("[a-f0-9]{48}"))) null
            else baseUrl + "?room=" + secret
        } catch (_: Exception) { null }
    }

    private fun toolbarButton(text: String, action: () -> Unit): Button =
        Button(this).apply {
            this.text = text
            this.isAllCaps = false
            setOnClickListener { action() }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "MELEHAT • P2P SES"
        window.statusBarColor = Color.rgb(38, 65, 89)
        window.navigationBarColor = Color.rgb(38, 65, 89)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.rgb(248, 245, 249))
        }
        setContentView(root)

        val header = TextView(this).apply {
            text = "MELEHAT • P2P SES"
            setTextColor(Color.rgb(39, 68, 95))
            textSize = 19f
            gravity = Gravity.CENTER
            setPadding(dp(12), dp(12), dp(12), dp(10))
        }
        root.addView(header, LinearLayout.LayoutParams(-1, dp(50)))

        val notes = TextView(this).apply {
            text = "İlk deneme: İki kişinin doğrudan konuşması. Mevcut telsiz kanalları değişmedi."
            setTextColor(Color.DKGRAY)
            textSize = 12f
            setPadding(dp(13), 0, dp(13), dp(5))
        }
        root.addView(notes)
        inviteInput = EditText(this).apply {
            hint = "Karşı telefondan gelen davet bağlantısını buraya yapıştırın"
            setSingleLine(true)
            textSize = 12f
            setPadding(dp(8), dp(5), dp(8), dp(5))
        }
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val fromClipboard = toolbarButton("PANODAN AL") {
            val manager = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            val text = manager.primaryClip?.getItemAt(0)?.coerceToText(this)?.toString()
            if (text.isNullOrBlank()) message("Önce davet bağlantısını kopyalayın.")
            else inviteInput.setText(text)
        }
        val join = toolbarButton("DAVETE GİT") {
            val url = validInvite(inviteInput.text.toString())
            if (url == null) message("Geçerli MELEHAT P2P davet bağlantısını yapıştırın.")
            else web.loadUrl(url)
        }
        row.addView(fromClipboard,LinearLayout.LayoutParams(0,dp(48),1f))
        row.addView(join,LinearLayout.LayoutParams(0,dp(48),1f))
        root.addView(inviteInput,LinearLayout.LayoutParams(-1,dp(46)))
        root.addView(row)

        val actions = LinearLayout(this).apply { orientation=LinearLayout.HORIZONTAL }
        actions.addView(toolbarButton("YENİ DAVET") { web.loadUrl(baseUrl) },
            LinearLayout.LayoutParams(0,dp(48),1f))
        actions.addView(toolbarButton("DAVETİ PAYLAŞ") { shareFromPage() },
            LinearLayout.LayoutParams(0,dp(48),1f))
        root.addView(actions)

        web = WebView(this)
        web.settings.javaScriptEnabled = true
        web.settings.domStorageEnabled = true
        web.settings.mediaPlaybackRequiresUserGesture = false
        web.settings.allowFileAccess = false
        web.settings.allowContentAccess = false
        web.settings.javaScriptCanOpenWindowsAutomatically = false
        web.settings.setSupportMultipleWindows(false)
        web.settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(
                view: WebView, request: android.webkit.WebResourceRequest
            ): Boolean {
                val u = request.url
                return u.scheme != "https" || u.host != host
            }
            override fun onReceivedSslError(
                view: WebView, handler: android.webkit.SslErrorHandler,
                error: android.net.http.SslError
            ) {
                handler.cancel()
                message("Güvenli bağlantı doğrulanamadı.")
            }
        }
        web.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: PermissionRequest) {
                runOnUiThread {
                    val origin=request.origin
                    if (origin.scheme!="https" || origin.host!=host ||
                        !request.resources.contains(PermissionRequest.RESOURCE_AUDIO_CAPTURE)) {
                        request.deny()
                        return@runOnUiThread
                    }
                    val mic = PermissionRequest.RESOURCE_AUDIO_CAPTURE
                    if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED)
                        request.grant(arrayOf(mic))
                    else {
                        pendingCapture?.deny()
                        pendingCapture=request
                        requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), permissionId)
                    }
                }
            }
            override fun onPermissionRequestCanceled(request: PermissionRequest) {
                if (pendingCapture===request) pendingCapture=null
            }
        }
        root.addView(web, LinearLayout.LayoutParams(-1,0,1f))
        web.loadUrl(baseUrl)
    }

    private fun shareFromPage() {
        web.evaluateJavascript(
            "(function(){var e=document.getElementById('invite');return e?e.value:''})()"
        ) { encoded ->
            val url = try { JSONTokener(encoded).nextValue() as? String } catch (_: Exception) {null}
            val valid=url?.let {validInvite(it)}
            if (valid == null) {
                message("Önce web sayfasında ODA OLUŞTUR'a basıp daveti hazırlayın.")
            } else {
                val share=Intent(Intent.ACTION_SEND).apply {
                    type="text/plain"
                    putExtra(Intent.EXTRA_TEXT, "MELEHAT P2P ses daveti: $valid")
                }
                startActivity(Intent.createChooser(share, "P2P davetini gönder"))
            }
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<out String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode,permissions,grantResults)
        if(requestCode==permissionId) {
            val pending=pendingCapture
            pendingCapture=null
            if(grantResults.firstOrNull()==PackageManager.PERMISSION_GRANTED)
                pending?.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE))
            else {
                pending?.deny()
                message("Mikrofon izni olmadan P2P konuşma yapılamaz.")
            }
        }
    }

    override fun onPause() {
        super.onPause()
        // The web app mutes on visibility change. Do not transmit in background.
        web.evaluateJavascript(
            "document.dispatchEvent(new Event('visibilitychange'))", null
        )
        web.onPause()
    }

    override fun onResume() {
        super.onResume()
        if (::web.isInitialized) web.onResume()
    }

    override fun onDestroy() {
        pendingCapture?.deny()
        pendingCapture=null
        if(::web.isInitialized) {
            web.loadUrl("about:blank")
            web.stopLoading()
            web.destroy()
        }
        super.onDestroy()
    }
}
''',encoding="utf-8")

ui.write_text(app,encoding="utf-8")
manifest.write_text(m,encoding="utf-8")
for filename,snippets in (
    (ui, ("P2P SES • DOĞRUDAN GÖRÜŞME", "onPtt(true)", "onPtt(false)")),
    (manifest, ("MelehatP2pActivity", "com.saomi.telsiz")),
    (activity, ("onPermissionRequest", "RESOURCE_AUDIO_CAPTURE", "validInvite", "shareFromPage")),
):
    data=filename.read_text(encoding="utf-8")
    for item in snippets:
        assert item in data, f"Safety validation: {filename.name} missing {item}"

print("MELEHAT_1363_P2P_IN_APP_WEBRTC_ENTRY_READY")
