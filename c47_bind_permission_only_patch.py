from pathlib import Path
m=Path("app/src/main/AndroidManifest.xml")
s=m.read_text()
old='''        <service
            android:name=".service.C42AccessibilityService"
            android:exported="false" />
'''
new='''        <service
            android:name=".service.C42AccessibilityService"
            android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE"
            android:exported="false" />
'''
if old not in s: raise SystemExit("C45 service block not found")
m.write_text(s.replace(old,new))
print("C47 isolation: BIND_ACCESSIBILITY_SERVICE only")
