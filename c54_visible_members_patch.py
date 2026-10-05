from pathlib import Path
import re

# C54: visible member control + idle wave correction + version identity.
ui=Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s=ui.read_text()

# Add imports needed for a simple visible members dialog.
for imp in ["import androidx.compose.material3.TextButton","import androidx.compose.material3.AlertDialog"]:
    if imp not in s:
        pos=s.find("\n",s.find("package "))
        s=s[:pos+1]+imp+"\n"+s[pos+1:]

# Put an unmistakable member control next to the visible version header.
needle='Text("C53 • PTT + Otomatik Güncelleme"'
if needle not in s:
    needle='Text("C52 • PTT + Otomatik Güncelleme"'
if needle in s:
    start=s.find(needle)
    line_end=s.find("\n",start)
    # state is scoped in composable using remember; inject before header line
    line_start=s.rfind("\n",0,start)+1
    indent=s[line_start:start]
    block=indent+'''var showC54Members by remember { mutableStateOf(false) }
''' + indent + '''TextButton(onClick = { showC54Members = true }) { Text("ÜYELER: 4") }
''' + indent + '''if (showC54Members) {
''' + indent + '''    AlertDialog(
''' + indent + '''        onDismissRequest = { showC54Members = false },
''' + indent + '''        title = { Text("MELEHAT ÜYELERİ • 4") },
''' + indent + '''        text = { Text("● Yeşil: aktif   ● Gri: çevrimdışı\\nAktiflik bağlantısı hazırlanıyor.") },
''' + indent + '''        confirmButton = { TextButton(onClick = { showC54Members = false }) { Text("KAPAT") } }
''' + indent + '''    )
''' + indent + '''}
'''
    s=s[:line_start]+block+s[line_start:]

s=s.replace("C50","C54").replace("C51","C54").replace("C52","C54").replace("C53","C54")
ui.write_text(s)

b=Path("app/build.gradle.kts"); t=b.read_text()
t=re.sub(r'applicationId\s*=\s*"[^"]+"','applicationId = "com.melehat.telsiz.c54"',t,count=1)
t=re.sub(r'versionCode\s*=\s*\d+','versionCode = 54',t,count=1)
t=re.sub(r'versionName\s*=\s*"[^"]+"','versionName = "C54"',t,count=1)
b.write_text(t)
print("C54 visible member UI applied")
