from pathlib import Path
m=Path("app/src/main/AndroidManifest.xml")
s=m.read_text()
block='''        <service
            android:name=".service.C42AccessibilityService"
            android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE"
            android:exported="false" />
'''
if "C42AccessibilityService" not in s:
    s=s.replace("</application>",block+"    </application>")
    m.write_text(s)
print("C43 minimal manifest service registration only")
