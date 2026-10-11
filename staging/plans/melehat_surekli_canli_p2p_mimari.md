# MELEHAT — Sürekli Canlı Telsiz ve P2P Ses Mimarisi

## Kullanıcı için görünüm (değişmez kural)
- Üye girişte tek MELEHAT telsiz ekranını görür; P2P, ICE, TURN, WebRTC, mod seçimleri gösterilmez.
- Büyük BAS KONUŞ: yalnızca mevcut seçili odaya gönderir, bırakınca mikrofon anında kapanır. Doğrulanmış bağlantı yoksa yayın başlatmaz.
- İlk üyelikten sonra ilk oda ORTAK KANAL. Aynı üyenin sonraki girişlerinde kayıtlı son yetkili odası. Kanal değiştirince önce eski ses akışını kapat, yeni kanala bağlan.
- Ortak kanal tüm üyelerin katılabileceği yerdir; açık uygulama veya kullanıcı tarafından açık tutulan Android foreground telsiz servisi bağlanabilir.
- Liste: her odanın gerçekte aktif kullanıcı sayısı, kimler orada, konuşmacı simgesi; eski kayıtlı üye toplamından farklı.
- Özel kanala giriş: istekte bulun; yalnız kanal sahibi onay/red verir; her iki sonuç başvurana iletilir. Onay olmadan özel ses ve SDP geçişi reddedilir.
- Üye kanal oluşturabilir; yetkili kullanıcılar arasında gizli konuşma odaları üyelik listesine göre izole kalır.
- Telsiz AÇIK olduğu sürece bağlantıyı foreground servis korur; cihaz ve Android sistem politikaları, ağ değişimi, pil ayarları nedeniyle kesinti olabilir; yeniden bağlanma ve durum görünürlüğü gerekir.

## Mevcut doğrulanmış ve sınırları
- v1.3.64: gerçek cihazlarda iki kişilik native P2P ses, farklı odalar, ortak BAS KONUŞ doğrulandı.
- v1.3.65: odalarda P2P üyelik/konuşma durumunu izleyen servis kuruldu.
- v1.3.66: 2 kişi varsayılan; 4 kişilik P2P mesh opsiyonel, fakat gerçek 3-4 cihazla henüz doğrulanmadı.
- STUN-only P2P tüm operatörlerde çalışmaz. CGNAT / kurumsal ağlar TURN gerektirebilir.
- Tek bir mobil telefondan sınırsız sayıda kişiye doğrudan ses dağıtımı mümkün değildir; mesh bağlantı ve işlem yükü katılımcı sayısıyla büyür. Ülke geneline çok kullanıcılı ortak kanallar için SFU/relay altyapısı gerekir.
- Bütün üyelerin aynı kanalda her zaman konuşması kesin şartsa uygun medya yönlendirici gerekir; ücretsiz, kotasız ve her NAT türünde garantili bir P2P sunumu vaat edilmez.

## Uygulama geçiş hedefi
1. **Giriş/başlangıç**: izinli son kanal veya yeni üyede ortak kanal, telsiz AÇIK ise servis bağlantısını devam ettir.
2. **Tek durum kaynağı**: sunucu presence kaydına göre aktif üyeler (son 15-20 sn); 'BAĞLANIYOR' ile gerçek ICE CONNECTED durumlarını ayır. Yalnız bağlı katılımcıları 'ses hazır' say.
3. **Otomatik ses taşıma seçimi**: düğmesiz UI, 2-4 kişi sınırındaki mesh protokolünü önceden anlaşılmış uyumlu sürümlerle test et; istemcilerin karışık protokol kullanmasını önle. Güvenli kapatma, her edge için farklı SDP / ICE oturumu.
4. **4+ kişi**: SFU veya eşdeğer kontrollü ses dağıtım altyapısına geçiş; ayrı kanal izolasyonu, floor-control, tek konuşmacı yönetimi, tüm dinleyiciler için fan-out.
5. **NAT başarısızlığı**: özelleştirilmiş TURN veya SFU yedek planı, ekran üzerinde anlaşılır ağ durumu; ses gerçekten gitmiyorken 'CANLI' dememe.
6. **Güvenilirlik ve güvenlik**: Android foreground service, açık kullanıcı tercihi ve izin, ekran kapalı tuş UP eksikse fail-closed PTT, watchdog, ağ değişiminde yeniden eşleşme, dinlemede mikrofon kapalı, özel kanal üyelik kontrolü.
7. **Dağıtım**: com.melehat.telsiz ve kalıcı imza sertifikası aynı; yalnız sürüm kodunu artır; önce GitHub Actions APK/sertifika testleri; sonra GitHub release, en son melehat-update.json duyurusunu atomik olarak yayınla.
8. **Kabul testleri**: 2 cihaz Wi-Fi/mobil veri; 3 ve 4 cihaz gerçek ortak kanal; farklı operatörler; 10+ kişi ölçek; kanal geçişi; başvuru onayı/red; PTT bırakma; ekran kapanınca güvenli mikrofon; APK üstüne güncelleme; saatlerce bağlı kalma ve ağ değişimi.

Bu dosya ürün/uygulama tasarım kılavuzudur; yapılmamış çok-kullanıcılı sunucu yeteneklerini çalışıyor gibi göstermez.
