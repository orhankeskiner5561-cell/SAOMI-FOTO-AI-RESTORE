from pathlib import Path
import re

p=Path("c28_v27_external_ptt_patch.py")
s=p.read_text()
s=s.replace("RELEASE_QUIET_MS = 1400L", "RELEASE_QUIET_MS = 800L")
s=s.replace('Text("C28 • v0.27 TABAN • Dış Mandal"', 'Text("C29 • v0.27 TABAN • Kilit Ekranı PTT"')
s=s.replace('"MELEHAT TELSİZ C28"', '"MELEHAT TELSİZ C29"')
s=s.replace("'versionCode = 28'", "'versionCode = 29'")
s=s.replace("'versionName = \"C28-v27-base-accessibility\"'", "'versionName = \"C29-screenoff-release-failsafe\"'")
p.write_text(s)
print("C29: screen-off PTT release failsafe set to 800ms; C-series metadata updated")
