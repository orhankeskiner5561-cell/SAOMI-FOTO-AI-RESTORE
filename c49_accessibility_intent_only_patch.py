from pathlib import Path
import re
p=Path("app/build.gradle.kts")
if not p.exists(): p=Path("app/build.gradle")
s=p.read_text()
s,n=re.subn(r'applicationId\s*=\s*["\'][^"\']+["\']','applicationId = "com.melehat.telsiz.c49isolated"',s,count=1)
if n==0: raise SystemExit("applicationId not found")
p.write_text(s)
m=Path("app/src/main/AndroidManifest.xml")
x=m.read_text()
old='''        <service
            android:name=".service.C42AccessibilityService"
            android:exported="false" />
'''
new='''        <service
            android:name=".service.C42AccessibilityService"
            android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE"
            android:exported="true">
            <intent-filter>
                <action android:name="android.accessibilityservice.AccessibilityService" />
            </intent-filter>
        </service>
'''
if old not in x: raise SystemExit("base service block not found")
m.write_text(x.replace(old,new))
print("C49 fresh package + standard accessibility intent filter, no metadata")
