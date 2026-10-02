package com.saomi.telsiz.ui

import android.graphics.BitmapFactory
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.saomi.telsiz.auth.SupabaseAuthClient
import com.saomi.telsiz.data.*
import com.saomi.telsiz.model.ChannelInfo
import com.saomi.telsiz.model.UserProfile
import kotlinx.coroutines.launch

@Composable
fun AppRoot(onRadioToggle:(Boolean)->Unit,onPtt:(Boolean)->Unit){
 val context=LocalContext.current; val scope=rememberCoroutineScope(); val localStore=remember{LocalStore(context)}; val sessionStore=remember{SessionStore(context)}; val auth=remember{SupabaseAuthClient()}; val backend=remember{BackendApi(context)}
 var session by remember{mutableStateOf(sessionStore.load())}; var loginPhone by remember{mutableStateOf(session?.phone.orEmpty())}; var loginEmail by remember{mutableStateOf(session?.email.orEmpty())}; var otpCode by remember{mutableStateOf("")}; var otpSent by remember{mutableStateOf(false)}; var authMessage by remember{mutableStateOf("")}
 var profile by remember{mutableStateOf(localStore.loadProfile())}; var activeChannel by remember{mutableStateOf(localStore.loadActiveChannel())}; var radioOn by remember{mutableStateOf(localStore.isRadioEnabled())}; var transmitting by remember{mutableStateOf(false)}
 var fullName by remember{mutableStateOf(profile.fullName)}; var photoUri by remember{mutableStateOf(profile.photoUri)}; var channelText by remember{mutableStateOf(activeChannel.name)}
 val picker=rememberLauncherForActivityResult(ActivityResultContracts.GetContent()){uri:Uri?->uri?.let{photoUri=it.toString()}}
 val infinite=rememberInfiniteTransition(label="rings"); val pulse by infinite.animateFloat(initialValue=.80f,targetValue=1.25f,animationSpec=infiniteRepeatable(tween(900),RepeatMode.Reverse),label="pulse")
 Scaffold(topBar={Surface(shadowElevation=2.dp){Column(Modifier.fillMaxWidth().padding(18.dp)){Text("MELEHAT TELSİZ",fontSize=26.sp,fontWeight=FontWeight.Bold);Text("v0.9 • E-posta OTP • Profil • Kanal • PTT",style=MaterialTheme.typography.bodySmall)}}}){pad->
  Column(Modifier.padding(pad).fillMaxSize().padding(18.dp),horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.spacedBy(12.dp)){
   if(session==null){
    Text("Hesaba giriş",fontSize=22.sp,fontWeight=FontWeight.Bold); Text("Telefon numaranızı ve e-postanızı girin. Doğrulama kodu e-postaya gönderilir.")
    OutlinedTextField(loginPhone,{loginPhone=it},label={Text("Telefon (+90...)")},singleLine=true,modifier=Modifier.fillMaxWidth())
    OutlinedTextField(loginEmail,{loginEmail=it.trim()},label={Text("E-posta")},singleLine=true,modifier=Modifier.fillMaxWidth())
    if(otpSent) OutlinedTextField(otpCode,{otpCode=it.filter(Char::isDigit).take(6)},label={Text("E-postadaki 6 haneli kod")},singleLine=true,modifier=Modifier.fillMaxWidth())
    Button(onClick={scope.launch{authMessage="İşleniyor…"; if(!otpSent){val r=auth.sendEmailOtp(loginEmail);otpSent=r.isSuccess;authMessage=r.exceptionOrNull()?.message?:"Kod e-postanıza gönderildi."}else{auth.verifyEmailOtp(loginPhone,loginEmail,otpCode).onSuccess{verified->backend.fetchMyProfile(verified).onSuccess{existing->if(existing!=null&&existing.phone.isNotBlank()&&normalizePhone(existing.phone)!=normalizePhone(loginPhone)){sessionStore.clear();authMessage="Bu e-posta başka bir telefon numarasıyla kayıtlı."}else{sessionStore.save(verified);session=verified;if(existing!=null){localStore.saveProfile(existing);profile=existing;fullName=existing.fullName;photoUri=existing.photoUri;authMessage="Hesap doğrulandı."}else{profile=UserProfile(loginPhone.trim(),loginEmail.trim().lowercase());authMessage="E-posta doğrulandı. Profilinizi tamamlayın."}}}.onFailure{authMessage=it.message.orEmpty()}}.onFailure{authMessage=it.message.orEmpty()}}}},enabled=loginPhone.isNotBlank()&&loginEmail.contains("@")&&(!otpSent||otpCode.length==6),modifier=Modifier.fillMaxWidth()){Text(if(otpSent)"Kodu Doğrula" else "E-postaya Kod Gönder")}
    if(otpSent) TextButton(onClick={otpSent=false;otpCode="";authMessage=""}){Text("Telefon veya e-postayı değiştir")}; if(authMessage.isNotBlank()) Text(authMessage,style=MaterialTheme.typography.bodySmall); return@Column
   }
   if(!profile.isComplete){
    Text("Profilini tamamla",fontSize=22.sp,fontWeight=FontWeight.Bold);Text("Ad-soyad ve profil fotoğrafı zorunludur.")
    OutlinedTextField(session!!.phone,{},label={Text("Telefon")},enabled=false,modifier=Modifier.fillMaxWidth());OutlinedTextField(session!!.email,{},label={Text("Doğrulanmış e-posta")},enabled=false,modifier=Modifier.fillMaxWidth())
    OutlinedTextField(fullName,{fullName=it},label={Text("Ad Soyad")},singleLine=true,modifier=Modifier.fillMaxWidth());Button(onClick={picker.launch("image/*")},modifier=Modifier.fillMaxWidth()){Text(if(photoUri.isBlank())"Profil Fotoğrafı Seç" else "Fotoğrafı Değiştir")}
    photoUri.takeIf(String::isNotBlank)?.let{u->val bmp=remember(u){runCatching{context.contentResolver.openInputStream(Uri.parse(u))?.use(BitmapFactory::decodeStream)}.getOrNull()};bmp?.let{Image(it.asImageBitmap(),null,Modifier.size(96.dp),contentScale=ContentScale.Crop)}}
    Button(onClick={val p=UserProfile(session!!.phone,session!!.email,fullName.trim(),photoUri);scope.launch{backend.uploadProfilePhoto(session!!,p.photoUri).onSuccess{url->val cp=p.copy(photoUri=url);backend.upsertProfile(session!!,cp).onSuccess{localStore.saveProfile(cp);profile=cp}}}},enabled=fullName.isNotBlank()&&photoUri.isNotBlank(),modifier=Modifier.fillMaxWidth()){Text("Profili Kaydet")};return@Column
   }
   Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Column{Text(profile.fullName,fontWeight=FontWeight.Bold);Text(profile.phone,style=MaterialTheme.typography.bodySmall);Text(profile.email,style=MaterialTheme.typography.bodySmall)};TextButton(onClick={if(radioOn){radioOn=false;localStore.setRadioEnabled(false);onRadioToggle(false)};sessionStore.clear();localStore.clearProfile();session=null;profile=UserProfile();loginPhone="";loginEmail="";otpSent=false;otpCode=""}){Text("Çıkış")}}
   OutlinedTextField(channelText,{channelText=it.uppercase()},label={Text("Kanal")},modifier=Modifier.fillMaxWidth(),singleLine=true);Button(onClick={val c=ChannelInfo(slug(channelText.ifBlank{"KANAL 1"}),channelText.ifBlank{"KANAL 1"});activeChannel=c;localStore.saveActiveChannel(c);scope.launch{backend.joinChannel(session!!,c)}},modifier=Modifier.fillMaxWidth()){Text("Kanala Gir")}
   Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween,verticalAlignment=Alignment.CenterVertically){Column{Text("Telsiz durumu",fontWeight=FontWeight.SemiBold);Text(if(radioOn)"AÇIK • ${activeChannel.name}" else "KAPALI")};Switch(radioOn,{radioOn=it;localStore.setRadioEnabled(it);onRadioToggle(it)})}
   Box(Modifier.size(270.dp),contentAlignment=Alignment.Center){if(radioOn&&!transmitting) Canvas(Modifier.fillMaxSize()){val c=Offset(size.width/2,size.height/2);drawCircle(Color(0x5534C759),size.minDimension*.34f*pulse,c);drawCircle(Color(0x3334C759),size.minDimension*.44f*pulse,c)};Surface(Modifier.size(185.dp).pointerInput(radioOn){detectTapGestures(onPress={if(!radioOn)return@detectTapGestures;transmitting=true;onPtt(true);tryAwaitRelease();transmitting=false;onPtt(false)})},shape=CircleShape,color=when{!radioOn->Color(0xFFE0E0E0);transmitting->Color(0xFFD32F2F);else->Color(0xFF34C759)},shadowElevation=8.dp){Box(contentAlignment=Alignment.Center){Column(horizontalAlignment=Alignment.CenterHorizontally){Text(when{!radioOn->"TELSİZ KAPALI";transmitting->"SES GİDİYOR";else->"BAS KONUŞ"},fontWeight=FontWeight.Bold,color=if(radioOn)Color.White else Color.DarkGray);if(radioOn)Text(if(transmitting)"Kırmızı = Yayın" else "Yeşil = Hazır",color=Color.White,style=MaterialTheme.typography.bodySmall)}}}}
   Surface(Modifier.fillMaxWidth(),shape=RoundedCornerShape(16.dp),color=Color(0xFFF2F2F7)){Column(Modifier.padding(16.dp)){Text("MELEHAT TELSİZ v0.9",fontWeight=FontWeight.Bold);Text("• SMS yok, ücretli SMS sağlayıcısı yok");Text("• Doğrulama kodu e-postaya gelir");Text("• Aynı cihazda oturum hatırlanır");Text("• Yeni telefonda e-posta koduyla teyit edilir");Text("• Kayıtlı telefon numarası eşleşmelidir");Text("• Profil fotoğrafı zorunlu")}}
  }
 }
}
private fun normalizePhone(value:String)=value.filter(Char::isDigit).removePrefix("0")
private fun slug(value:String)=value.lowercase().replace("ç","c").replace("ğ","g").replace("ı","i").replace("ö","o").replace("ş","s").replace("ü","u").replace(Regex("[^a-z0-9]+"),"-").trim('-').ifBlank{"kanal-1"}