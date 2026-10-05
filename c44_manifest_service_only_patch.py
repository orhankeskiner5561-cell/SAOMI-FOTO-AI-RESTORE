from pathlib import Path
m=Path("app/src/main/AndroidManifest.xml")
s=m.read_text()
block='''        <service
            android:name=".service.C42AccessibilityService"
            android:exported="false" />
'''
if "C42AccessibilityService" not in s:
    s=s.replace("</application>",block+"    </application>")
    m.write_text(s)
print("C44 isolation: manifest service only, no BIND_ACCESSIBILITY_SERVICE permission")
