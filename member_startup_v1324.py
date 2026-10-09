from pathlib import Path
p = Path("app/src/main/java/com/saomi/telsiz/ui/AppRoot.kt")
s = p.read_text()
old = '''    var directory by remember { mutableStateOf<List<MemberDirectoryProfile>>(emptyList()) }
    var showMembers by remember { mutableStateOf(false) }'''
new = '''    var directory by remember { mutableStateOf<List<MemberDirectoryProfile>>(emptyList()) }
    var directoryLoaded by remember { mutableStateOf(false) }
    var showMembers by remember { mutableStateOf(false) }'''
if old not in s: raise SystemExit("Member state anchor missing")
s=s.replace(old,new,1)
old_loop='''            backend.fetchMemberDirectory(active).onSuccess { directory = it }
            delay(1000)'''
new_loop='''            backend.fetchMemberDirectory(active).onSuccess {
                directory = it
                directoryLoaded = true
            }
            delay(if (directoryLoaded) 3000 else 500)'''
if old_loop not in s: raise SystemExit("Member polling anchor missing")
s=s.replace(old_loop,new_loop,1)
# Distinguish not-yet-loaded from a real empty member directory.
s=s.replace('Text("ÜYELER\\n${directory.size}"', 'Text("ÜYELER\\n${if (directoryLoaded) directory.size.toString() else "…"}"')
p.write_text(s)
print("MELEHAT_MEMBER_LOADING_FIX_OK")
