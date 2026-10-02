from pathlib import Path
import re

root=Path('.')

p=root/'app/build.gradle.kts'
s=p.read_text()
s=s.replace('versionCode = 9','versionCode = 10').replace('versionName = "0.9.0"','versionName = "0.10.0"')
p.write_text(s)

p=root/'app/src/main/AndroidManifest.xml'
s=p.read_text()
if 'android:launchMode="singleTop"' not in s:
    s=s.replace('android:screenOrientation="portrait">','android:screenOrientation="portrait"\n            android:launchMode="singleTop">')
if 'android:scheme="melehat"' not in s:
    marker='''            <intent-filter>\n                <action android:name="android.intent.action.MAIN"/>\n                <category android:name="android.intent.category.LAUNCHER"/>\n            </intent-filter>'''
    repl=marker+'''\n            <intent-filter>\n                <action android:name="android.intent.action.VIEW"/>\n                <category android:name="android.intent.category.DEFAULT"/>\n                <category android:name="android.intent.category.BROWSABLE"/>\n                <data android:scheme="melehat" android:host="auth-callback"/>\n            </intent-filter>'''
    s=s.replace(marker,repl)
p.write_text(s)

(root/'app/src/main/java/com/saomi/telsiz/auth/SupabaseAuthClient.kt').write_text(r'''package com.saomi.telsiz.auth

import android.net.Uri
import android.util.Base64
import com.saomi.telsiz.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.net.URLEncoder

class SupabaseAuthClient {
    private val http=OkHttpClient()
    private val json="application/json; charset=utf-8".toMediaType()
    private fun base()=BuildConfig.SUPABASE_URL.trimEnd('/')
    private fun key()=BuildConfig.SUPABASE_PUBLISHABLE_KEY
    fun isConfigured()=base().isNotBlank()&&key().isNotBlank()

    suspend fun sendMagicLink(email:String):Result<Unit> = withContext(Dispatchers.IO){
        if(!isConfigured()) return@withContext Result.failure(IllegalStateException("Supabase bağlantısı henüz yapılandırılmadı."))
        val redirect=URLEncoder.encode("melehat://auth-callback","UTF-8")
        val body=JSONObject().put("email",email.trim().lowercase()).put("create_user",true).toString().toRequestBody(json)
        val request=Request.Builder().url("${base()}/auth/v1/otp?redirect_to=$redirect").addHeader("apikey",key()).addHeader("Authorization","Bearer ${key()}").post(body).build()
        runCatching{http.newCall(request).execute().use{r->val raw=r.body?.string().orEmpty();if(!r.isSuccessful) error("Onay bağlantısı gönderilemedi: ${r.code} ${raw.take(160)}")}}
    }

    fun sessionFromMagicLink(uri:Uri,phone:String,fallbackEmail:String):Result<AuthSession> = runCatching{
        if(uri.scheme!="melehat"||uri.host!="auth-callback") error("Geçersiz MELEHAT giriş bağlantısı.")
        val values=linkedMapOf<String,String>()
        listOfNotNull(uri.query,uri.fragment).joinToString("&").split("&").forEach{pair->val i=pair.indexOf('=');if(i>0) values[Uri.decode(pair.substring(0,i))]=Uri.decode(pair.substring(i+1))}
        values["error_description"]?.takeIf{it.isNotBlank()}?.let{error(it)}
        val access=values["access_token"].orEmpty(); val refresh=values["refresh_token"].orEmpty(); if(access.isBlank()) error("Onay bağlantısında oturum bilgisi bulunamadı.")
        val part=access.split('.').getOrNull(1).orEmpty(); if(part.isBlank()) error("Oturum anahtarı okunamadı.")
        val padded=part+"=".repeat((4-part.length%4)%4)
        val jwt=JSONObject(String(Base64.decode(padded,Base64.URL_SAFE or Base64.NO_WRAP),Charsets.UTF_8))
        val userId=jwt.optString("sub"); val email=jwt.optString("email").ifBlank{fallbackEmail.trim().lowercase()}; if(userId.isBlank()) error("Kullanıcı kimliği alınamadı.")
        AuthSession(access,refresh,userId,phone.trim(),email)
    }
}
''')

(root/'app/src/main/java/com/saomi/telsiz/data/SessionStore.kt').write_text(r'''package com.saomi.telsiz.data

import android.content.Context
import com.saomi.telsiz.auth.AuthSession

class SessionStore(context:Context){
 private val prefs=context.getSharedPreferences("melehat_telsiz_auth",Context.MODE_PRIVATE)
 fun save(s:AuthSession){prefs.edit().putString("access_token",s.accessToken).putString("refresh_token",s.refreshToken).putString("user_id",s.userId).putString("phone",s.phone).putString("email",s.email).apply()}
 fun load():AuthSession?{val a=prefs.getString("access_token","").orEmpty();val id=prefs.getString("user_id","").orEmpty();if(a.isBlank()||id.isBlank())return null;return AuthSession(a,prefs.getString("refresh_token","").orEmpty(),id,prefs.getString("phone","").orEmpty(),prefs.getString("email","").orEmpty())}
 fun savePending(phone:String,email:String){prefs.edit().putString("pending_phone",phone.trim()).putString("pending_email",email.trim().lowercase()).apply()}
 fun pendingPhone()=prefs.getString("pending_phone","").orEmpty()
 fun pendingEmail()=prefs.getString("pending_email","").orEmpty()
 fun clearPending(){prefs.edit().remove("pending_phone").remove("pending_email").apply()}
 fun clear()=prefs.edit().clear().apply()
}
''')

(root/'app/src/main/java/com/saomi/telsiz/MainActivity.kt').write_text(r'''package com.saomi.telsiz

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.view.KeyEvent
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.MaterialTheme
import androidx.core.content.ContextCompat
import com.saomi.telsiz.auth.SupabaseAuthClient
import com.saomi.telsiz.data.LocalStore
import com.saomi.telsiz.data.SessionStore
import com.saomi.telsiz.service.PttForegroundService
import com.saomi.telsiz.ui.AppRoot

class MainActivity:ComponentActivity(){
 private var volumePttDown=false
 private var authCallbackNonce=0
 private val permissions=registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()){}
 override fun onCreate(savedInstanceState:Bundle?){super.onCreate(savedInstanceState);requestRequiredPermissions();handleAuthIntent(intent);if(LocalStore(this).isRadioEnabled())sendServiceAction(PttForegroundService.ACTION_START);render()}
 override fun onNewIntent(intent:Intent){super.onNewIntent(intent);setIntent(intent);handleAuthIntent(intent);authCallbackNonce++;render()}
 private fun render(){val nonce=authCallbackNonce;setContent{MaterialTheme{AppRoot(authCallbackNonce=nonce,onRadioToggle={sendServiceAction(if(it)PttForegroundService.ACTION_START else PttForegroundService.ACTION_STOP)},onPtt={sendServiceAction(if(it)PttForegroundService.ACTION_PTT_DOWN else PttForegroundService.ACTION_PTT_UP)})}}}
 private fun handleAuthIntent(intent:Intent?){val uri:Uri=intent?.data?:return;if(uri.scheme!="melehat"||uri.host!="auth-callback")return;val store=SessionStore(this);SupabaseAuthClient().sessionFromMagicLink(uri,store.pendingPhone(),store.pendingEmail()).onSuccess{store.save(it);store.clearPending()}}
 private fun requestRequiredPermissions(){val list=mutableListOf(Manifest.permission.RECORD_AUDIO);if(android.os.Build.VERSION.SDK_INT>=33)list+=Manifest.permission.POST_NOTIFICATIONS;if(android.os.Build.VERSION.SDK_INT>=31)list+=Manifest.permission.BLUETOOTH_CONNECT;if(list.any{ContextCompat.checkSelfPermission(this,it)!=PackageManager.PERMISSION_GRANTED})permissions.launch(list.toTypedArray())}
 private fun sendServiceAction(action:String){ContextCompat.startForegroundService(this,Intent(this,PttForegroundService::class.java).apply{this.action=action})}
 override fun onKeyDown(keyCode:Int,event:KeyEvent?):Boolean{if(keyCode==KeyEvent.KEYCODE_VOLUME_UP&&!volumePttDown){volumePttDown=true;sendServiceAction(PttForegroundService.ACTION_PTT_DOWN);return true};return super.onKeyDown(keyCode,event)}
 override fun onKeyUp(keyCode:Int,event:KeyEvent?):Boolean{if(keyCode==KeyEvent.KEYCODE_VOLUME_UP&&volumePttDown){volumePttDown=false;sendServiceAction(PttForegroundService.ACTION_PTT_UP);return true};return super.onKeyUp(keyCode,event)}
}
''')

p=root/'app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt'
s=p.read_text()
s=s.replace('fun AppRoot(onRadioToggle:(Boolean)->Unit,onPtt:(Boolean)->Unit){','fun AppRoot(authCallbackNonce:Int,onRadioToggle:(Boolean)->Unit,onPtt:(Boolean)->Unit){')
s=s.replace('var session by remember{mutableStateOf(sessionStore.load())}; var loginPhone by remember{mutableStateOf(session?.phone.orEmpty())}; var loginEmail by remember{mutableStateOf(session?.email.orEmpty())}; var otpCode by remember{mutableStateOf("")}; var otpSent by remember{mutableStateOf(false)}; var authMessage by remember{mutableStateOf("")}', 'var session by remember(authCallbackNonce){mutableStateOf(sessionStore.load())}; var loginPhone by remember{mutableStateOf(session?.phone.orEmpty())}; var loginEmail by remember{mutableStateOf(session?.email.orEmpty())}; var linkSent by remember{mutableStateOf(false)}; var authMessage by remember{mutableStateOf("")}')
s=s.replace('Text("v0.9 • E-posta OTP • Profil • Kanal • PTT"','Text("v0.10 • E-posta bağlantısı • Profil • Kanal • PTT"')
s=s.replace('Text("Telefon numaranızı ve e-postanızı girin. Doğrulama kodu e-postaya gönderilir.")','Text("Telefon numaranızı ve e-postanızı girin. E-postaya gelen güvenli giriş bağlantısına dokunun.")')
s=re.sub(r'\s*if\(otpSent\) OutlinedTextField\(otpCode,\{otpCode=it\.filter\(Char::isDigit\)\.take\(6\)\},label=\{Text\("E-postadaki 6 haneli kod"\)\},singleLine=true,modifier=Modifier\.fillMaxWidth\(\)\)\n','\n',s)
old=re.search(r'    Button\(onClick=\{scope\.launch\{authMessage="İşleniyor…"; if\(!otpSent\).*?\}\},enabled=loginPhone\.isNotBlank\(\)&&loginEmail\.contains\("@"\)&&\(!otpSent\|\|otpCode\.length==6\),modifier=Modifier\.fillMaxWidth\(\)\)\{Text\(if\(otpSent\)"Kodu Doğrula" else "E-postaya Kod Gönder"\)\}',s)
if not old: raise SystemExit('login button pattern not found')
new='''    Button(onClick={scope.launch{authMessage="Gönderiliyor…";sessionStore.savePending(loginPhone,loginEmail);auth.sendMagicLink(loginEmail).onSuccess{linkSent=true;authMessage="Giriş bağlantısı e-postanıza gönderildi. Maildeki bağlantıya dokunun; MELEHAT TELSİZ otomatik açılır."}.onFailure{authMessage=it.message.orEmpty()}}},enabled=loginPhone.isNotBlank()&&loginEmail.contains("@"),modifier=Modifier.fillMaxWidth()){Text(if(linkSent)"Bağlantıyı Tekrar Gönder" else "E-postaya Giriş Bağlantısı Gönder")}'''
s=s[:old.start()]+new+s[old.end():]
s=s.replace('    if(otpSent) TextButton(onClick={otpSent=false;otpCode="";authMessage=""}){Text("Telefon veya e-postayı değiştir")}; if(authMessage.isNotBlank()) Text(authMessage,style=MaterialTheme.typography.bodySmall); return@Column','    if(linkSent) Text("Bağlantıyı aynı telefondan açın. Onaylanınca uygulama otomatik döner.",style=MaterialTheme.typography.bodySmall); if(authMessage.isNotBlank()) Text(authMessage,style=MaterialTheme.typography.bodySmall); return@Column')
s=s.replace('session=null;profile=UserProfile();loginPhone="";loginEmail="";otpSent=false;otpCode=""','session=null;profile=UserProfile();loginPhone="";loginEmail="";linkSent=false;authMessage=""')
s=s.replace('Text("MELEHAT TELSİZ v0.9"','Text("MELEHAT TELSİZ v0.10"').replace('Text("• Doğrulama kodu e-postaya gelir")','Text("• E-posta güvenli giriş bağlantısı")').replace('Text("• Yeni telefonda e-posta koduyla teyit edilir")','Text("• Yeni telefonda aynı e-postaya yeni bağlantı gönderilir")')
needle=' val picker=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){uri:Uri?->uri?.let{photoUri=it.toString()}}\n'
insert=''' val picker=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){uri:Uri?->uri?.let{photoUri=it.toString()}}\n LaunchedEffect(session?.userId,authCallbackNonce){val current=session?:return@LaunchedEffect;backend.fetchMyProfile(current).onSuccess{existing->if(existing!=null){if(existing.phone.isNotBlank()&&normalizePhone(existing.phone)!=normalizePhone(current.phone)){sessionStore.clear();localStore.clearProfile();session=null;profile=UserProfile();authMessage="Bu e-posta başka bir telefon numarasıyla kayıtlı."}else{localStore.saveProfile(existing);profile=existing;fullName=existing.fullName;photoUri=existing.photoUri}}else{val fresh=UserProfile(current.phone,current.email,"","");localStore.saveProfile(fresh);profile=fresh}}.onFailure{authMessage=it.message.orEmpty()}}\n'''
if needle not in s: raise SystemExit('picker needle not found')
s=s.replace(needle,insert)
p.write_text(s)
print('v0.10 patch applied')
