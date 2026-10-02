from pathlib import Path

root = Path("app/src/main/java")
changed = []

for p in root.rglob("*.kt"):
    s = p.read_text(encoding="utf-8")
    old = s

    # Android throws IllegalStateException when delayed focus or pause-on-duck
    # is requested without an AudioManager.OnAudioFocusChangeListener.
    s = s.replace(".setAcceptsDelayedFocusGain(true)", ".setAcceptsDelayedFocusGain(false)")
    s = s.replace(".setWillPauseWhenDucked(true)", ".setWillPauseWhenDucked(false)")

    # Defensive replacements for line-broken/spaced Kotlin.
    s = s.replace("setAcceptsDelayedFocusGain( true )", "setAcceptsDelayedFocusGain(false)")
    s = s.replace("setWillPauseWhenDucked( true )", "setWillPauseWhenDucked(false)")

    if s != old:
        p.write_text(s, encoding="utf-8")
        changed.append(str(p))

b = Path("app/build.gradle.kts")
if b.exists():
    t = b.read_text(encoding="utf-8")
    t = t.replace("versionCode = 11", "versionCode = 12")
    t = t.replace('versionName = "0.11.0"', 'versionName = "0.12.0"')
    b.write_text(t, encoding="utf-8")

ui = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
if ui.exists():
    t = ui.read_text(encoding="utf-8")
    t = t.replace("v0.11 •", "v0.12 •")
    t = t.replace("MELEHAT TELSİZ v0.11", "MELEHAT TELSİZ v0.12")
    ui.write_text(t, encoding="utf-8")

print("Audio-focus patched files:")
for x in changed:
    print(x)
if not changed:
    raise SystemExit("No matching audio focus flags found; inspect service source.")
