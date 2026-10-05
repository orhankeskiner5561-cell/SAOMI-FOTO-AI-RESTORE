from pathlib import Path

root = Path(".")
manifest = root / "app/src/main/AndroidManifest.xml"

candidates = list((root / "app/src/main/java").rglob("MainActivity.kt"))
if not candidates:
    raise SystemExit("MainActivity.kt not found")
main = candidates[0]
pkg = ""
for line in main.read_text().splitlines():
    if line.startswith("package "):
        pkg = line.split()[1]
        break
if not pkg:
    raise SystemExit("package not found")

service_dir = main.parent / "service"
service_dir.mkdir(parents=True, exist_ok=True)
service = service_dir / "C40AccessibilityService.kt"
service.write_text(f"""package {pkg}.service

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent

class C40AccessibilityService : AccessibilityService() {{
    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit
    override fun onInterrupt() = Unit
}}
""")

m = manifest.read_text()
block = """        <service
            android:name=".service.C40AccessibilityService"
            android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE"
            android:exported="true">
            <intent-filter>
                <action android:name="android.accessibilityservice.AccessibilityService" />
            </intent-filter>
        </service>
"""
if "C40AccessibilityService" not in m:
    m = m.replace("</application>", block + "    </application>")
    manifest.write_text(m)

print("C40: empty accessibility service only")
