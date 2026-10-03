from pathlib import Path
import re

p=Path('app/src/main/java/com/saomi/telsiz/data/BackendApi.kt')
s=p.read_text()
s=s.replace(r'"\\${base()}/rest/v1/rpc/acquire_channel_floor"', r'"${base()}/rest/v1/rpc/acquire_channel_floor"')
s=s.replace(r'"Bearer \\${active.accessToken}"', r'"Bearer ${active.accessToken}"')
s=s.replace(r'"\\${base()}/rest/v1/rpc/release_channel_floor"', r'"${base()}/rest/v1/rpc/release_channel_floor"')
p.write_text(s)

b=Path('app/build.gradle.kts')
t=b.read_text()
t=re.sub(r'applicationId\\s*=\\s*"[^"]+"', 'applicationId = "com.melehat.telsiz.v24"', t)
t=re.sub(r'versionCode\\s*=\\s*\\d+', 'versionCode = 24', t)
t=re.sub(r'versionName\\s*=\\s*"[^"]+"', 'versionName = "0.24.0"', t)
b.write_text(t)

ui=Path('app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt')
u=ui.read_text()
u=u.replace('v0.23 • Güvenli Ses Tuşu PTT','v0.24 • PTT + Oturum Yenileme Düzeltmesi')
u=u.replace('MELEHAT TELSİZ v0.23','MELEHAT TELSİZ v0.24')
ui.write_text(u)

print('v0.24 PTT crash fix applied')