from pathlib import Path
import base64
import re

# MELEHAT v1.3.50: launcher art only. Audio, PTT, channels, permissions and
# package identity remain untouched.
data_file = Path("../staging/launcher/melehat_yellow_launcher.webp.b64")
bitmap = base64.b64decode(data_file.read_text(encoding="ascii").strip(), validate=True)
if not (bitmap[:4] == b"RIFF" and bitmap[8:12] == b"WEBP"):
    raise SystemExit("Launcher art must be a valid WebP file")
out = Path("app/src/main/res/drawable-nodpi/melehat_launcher.webp")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(bitmap)

manifest = Path("app/src/main/AndroidManifest.xml")
xml = manifest.read_text(encoding="utf-8")
m = re.search(r"<application\b[^>]*>", xml, flags=re.S)
if not m:
    raise SystemExit("Android application manifest node not found")
tag = m.group(0)
for attr in ("android:icon", "android:roundIcon"):
    replacement = f'{attr}="@drawable/melehat_launcher"'
    if re.search(r'\b' + attr + r'\s*=\s*"[^"]*"', tag):
        tag = re.sub(r'\b' + attr + r'\s*=\s*"[^"]*"', replacement, tag, count=1)
    else:
        tag = tag[:-1] + " " + replacement + ">"
xml = xml[:m.start()] + tag + xml[m.end():]
manifest.write_text(xml, encoding="utf-8")
assert xml.count('android:icon="@drawable/melehat_launcher"') == 1
assert xml.count('android:roundIcon="@drawable/melehat_launcher"') == 1
print(f"MELEHAT_YELLOW_LAUNCHER_READY bytes={len(bitmap)}")
