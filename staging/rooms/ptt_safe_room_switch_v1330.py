from pathlib import Path

# v1.3.30 - Safe foreground PTT room switch.
# Keep the same PttForegroundService class, notification, keystore,
# microphone publish path and PTT button-down/up behavior.
root=Path("app/src/main/java/com/saomi/telsiz")
path=root/"service/PttForegroundService.kt"
s=path.read_text(encoding="utf-8")
def fix(old,new,expected=1):
    global s
    if s.count(old)!=expected:
        raise SystemExit("PTT service anchor mismatch ("+str(s.count(old))+"): "+old[:95])
    s=s.replace(old,new,expected)

fix('import com.saomi.telsiz.voice.LiveKitPttClient',
'''import com.saomi.telsiz.voice.LiveKitPttClient
import com.saomi.telsiz.voice.LiveChannelUiState
import com.saomi.telsiz.model.ChannelInfo
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock''')
fix('    private var keepAliveJob: Job? = null',
'''    private var keepAliveJob: Job? = null
    private val roomMutex = Mutex()
    @Volatile private var roomSwitching = false
    private var roomSwitchJob: Job? = null''')

# Network callback and ACTION_START must not reconnect the previous room
# halfway through a switch; the existing connected-room creation is retained.
fix('''val ok = ptt.connect(store.loadProfile(), store.loadActiveChannel())''',
'''val ok = roomMutex.withLock {
                            if (started && !roomSwitching) {
                                ptt.connect(store.loadProfile(), store.loadActiveChannel())
                            } else false
                        }''', expected=2)

fix('''if (!ptt.isConnected()) ptt.ensureConnected()''',
'''if (!ptt.isConnected()) {
                                roomMutex.withLock {
                                    if (started && !roomSwitching && !ptt.isConnected()) {
                                        ptt.ensureConnected()
                                    }
                                }
                            }''')

switch = '''
            ACTION_SWITCH_ROOM -> {
                val roomId = intent.getStringExtra(EXTRA_ROOM_ID).orEmpty()
                val roomName = intent.getStringExtra(EXTRA_ROOM_NAME).orEmpty()
                // A specific, server-authorized room ID only; never join by a
                // free-text field or a display name.
                if (started && !roomSwitching &&
                    (roomId == "ortak" || roomId.matches(Regex("kanal-[a-z0-9-]{1,64}"))) &&
                    roomName.isNotBlank()
                ) {
                    roomSwitching = true
                    pttHeld = false
                    transmitRequestId += 1
                    beginJob?.cancel()
                    beginJob = null
                    roomSwitchJob?.cancel()
                    roomSwitchJob = scope.launch {
                        try {
                            roomMutex.withLock {
                                if (!started) return@withLock
                                // Releasing the existing floor ALWAYS precedes the
                                // new LiveKit connection. No cross-room PTT.
                                if (transmitting) endTransmit()
                                else ptt.setTransmitting(false)
                                val previous = store.loadActiveChannel()
                                val target = ChannelInfo(roomId, roomName)
                                if (previous.id == target.id && ptt.isConnectedTo(roomId)) {
                                    updateNotification("Kanal dinlemede • Bas-konuş hazır")
                                    return@withLock
                                }
                                ptt.disconnect()
                                val ok = ptt.connect(store.loadProfile(), target)
                                if (ok && started) {
                                    store.saveActiveChannel(target)
                                    updateNotification("$roomName • Bas-konuş hazır")
                                } else {
                                    ptt.disconnect()
                                    if (started) {
                                        val recovered = ptt.connect(store.loadProfile(), previous)
                                        updateNotification(
                                            if (recovered) "Kanal geçişi reddedildi • Eski kanaldasınız"
                                            else "Kanal bağlantısı bekleniyor"
                                        )
                                    }
                                    LiveChannelUiState.notice("Kanal bağlantısı kurulamadı.")
                                }
                            }
                        } finally {
                            roomSwitching = false
                        }
                    }
                }
            }

'''
fix('''            ACTION_STOP -> {''', switch+'''            ACTION_STOP -> {''')
# Complete an in-flight room switch before fully stopping.
fix('''                scope.launch { stopRadio() }''',
'''                started = false
                pttHeld = false
                transmitRequestId += 1
                beginJob?.cancel()
                scope.launch { roomMutex.withLock { stopRadio() } }''')

fix('''if (started) {
                    pttHeld = true''',
'''if (started && !roomSwitching) {
                    pttHeld = true''',expected=1)
fix('''if (started) {
                    if (transmitting || pttHeld) {''',
'''if (started && !roomSwitching) {
                    if (transmitting || pttHeld) {''')

fix('''        val channel = store.loadActiveChannel()

        if (session == null) {''',
'''        val channel = store.loadActiveChannel()
        if (roomSwitching || !ptt.isConnectedTo(channel.id)) {
            updateNotification("Kanal bağlantısı hazırlanıyor")
            return
        }

        if (session == null) {''')
# Supabase floor grants are validated by server; prevent old connection
# from publishing into a newly selected room when PTT release races.
fix('''if (!pttHeld || requestId != transmitRequestId || !started)''',
'''if (!pttHeld || requestId != transmitRequestId || !started ||
            roomSwitching || !ptt.isConnectedTo(channel.id))''',expected=2)

fix('''    override fun onDestroy() {
        pttHeld = false''',
'''    override fun onDestroy() {
        roomSwitchJob?.cancel()
        pttHeld = false''')
fix('''        const val ACTION_START = "com.saomi.telsiz.START"''',
'''        const val ACTION_SWITCH_ROOM = "com.saomi.telsiz.SWITCH_ROOM"
        const val EXTRA_ROOM_ID = "melehat.room.id"
        const val EXTRA_ROOM_NAME = "melehat.room.name"
        const val ACTION_START = "com.saomi.telsiz.START"''')
# PttForegroundService already imported LiveChannelUiState in older builds.
# Keep one copy of every import to avoid conflicting-import errors.
seen_imports=set()
unique_lines=[]
for line in s.splitlines(keepends=True):
    if line.startswith("import "):
        name=line.strip()
        if name in seen_imports:
            continue
        seen_imports.add(name)
    unique_lines.append(line)
s="".join(unique_lines)
path.write_text(s,encoding="utf-8")

# Existing Activity launches the same foreground service and keeps its volume
# button handler. Move legacy preference to the new common room on update.
activity=root/"MainActivity.kt"
s=activity.read_text(encoding="utf-8")
old='''        if (LocalStore(this).isRadioEnabled()) {'''
new='''        val localStore = LocalStore(this)
        localStore.migrateDefaultRoomToCommonOnce()
        if (localStore.isRadioEnabled()) {'''
if s.count(old)!=1:raise SystemExit("MainActivity migration anchor missing")
s=s.replace(old,new,1)
activity.write_text(s,encoding="utf-8")
print("MELEHAT_1330_SAFE_SWITCH_SERVICE_OK")
