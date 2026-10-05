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
            android:exported="true">
            <intent-filter>
                <action android:name="android.accessibilityservice.AccessibilityService" />
            </intent-filter>
            <meta-data
                android:name="android.accessibilityservice"
                android:resource="@xml/c46_accessibility_service_config" />
        </service>
'''
if old not in s: raise SystemExit("C45 minimal service block not found")
m.write_text(s.replace(old,new))
v=Path("app/src/main/res/values"); v.mkdir(parents=True,exist_ok=True)
st=v/"c46_strings.xml"
st.write_text('''<?xml version="1.0" encoding="utf-8"?><resources><string name="c46_accessibility_description">MELEHAT TELSIZ erisilebilirlik hizmeti</string></resources>''')
x=Path("app/src/main/res/xml"); x.mkdir(parents=True,exist_ok=True)
(x/"c46_accessibility_service_config.xml").write_text('''<?xml version="1.0" encoding="utf-8"?>
<accessibility-service xmlns:android="http://schemas.android.com/apk/res/android"
    android:description="@string/c46_accessibility_description"
    android:accessibilityEventTypes="typeAllMask"
    android:accessibilityFeedbackType="feedbackGeneric"
    android:notificationTimeout="100"
    android:canRetrieveWindowContent="false"
    android:canRequestFilterKeyEvents="true" />
''')
print("C46 real accessibility registration added")
