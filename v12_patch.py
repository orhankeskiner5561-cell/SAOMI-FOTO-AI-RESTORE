from pathlib import Path

# Android 16 / MIUI: AudioFocusRequest cannot request delayed focus or
# pause-on-duck unless an OnAudioFocusChangeListener is attached.
# PTT does not need delayed focus; request immediate transient focus instead.
changed = []
for p in Path("app/src").rglob("*.kt"):
    s = p.read_text()
    old = s
    s = s.replace(".setAcceptsDelayedFocusGain(true)", ".setAcceptsDelayedFocusGain(false)")
    s = s.replace(".setWillPauseWhenDucked(true)", ".setWillPauseWhenDucked(false)")
    if s != old:
        p.write_text(s)
        changed.append(str(p))

if not changed:
    raise SystemExit("AudioFocusRequest pattern not found; refusing blind build")

# bump visible/app version
ui = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = ui.read_text()
s = s.replace("v0.11 •", "v0.12 •").replace("MELEHAT TELSİZ v0.11", "MELEHAT TELSİZ v0.12")
ui.write_text(s)

b = Path("app/build.gradle.kts")
s = b.read_text()
s = s.replace("versionCode = 11", "versionCode = 12")
s = s.replace('versionName = "0.11.0"', 'versionName = "0.12.0"')
b.write_text(s)

print("Fixed:", *changed)
