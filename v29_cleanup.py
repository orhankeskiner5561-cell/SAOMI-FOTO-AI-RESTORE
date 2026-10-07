from pathlib import Path
p=Path("app/src/main/java/com/saomi/telsiz/net/MemberStatusApi.kt")
if p.exists():
    p.unlink()
print("V29 cleanup complete")
