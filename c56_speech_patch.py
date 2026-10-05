from pathlib import Path
p=Path("app/src/main/java/com/saomi/telsiz/voice/LiveKitPttClient.kt")
s=p.read_text()
s=s.replace("import io.livekit.android.room.Room","import io.livekit.android.room.Room\nimport io.livekit.android.events.RoomEvent\nimport io.livekit.android.events.collect\nimport kotlinx.coroutines.*\nimport kotlinx.coroutines.flow.MutableStateFlow")
s=s.replace("class LiveKitPttClient(private val context: Context) {","data class RemoteSpeechState(val name:String=\"\",val level:Float=0f,val speaking:Boolean=false)\nobject RemoteSpeechBus { val state=MutableStateFlow(RemoteSpeechState()) }\n\nclass LiveKitPttClient(private val context: Context) {\n    private val eventScope=CoroutineScope(SupervisorJob()+Dispatchers.Default)\n    private var speakerJob:Job?=null")
old="            r.localParticipant.setMicrophoneEnabled(false)\n            room = r"
new="""            r.localParticipant.setMicrophoneEnabled(false)
            eventScope.launch {
                r.events.collect { e ->
                    if (e is RoomEvent.ActiveSpeakersChanged) {
                        val sp=e.speakers.firstOrNull { it != r.localParticipant }
                        speakerJob?.cancel()
                        if(sp==null) RemoteSpeechBus.state.value=RemoteSpeechState()
                        else speakerJob=eventScope.launch {
                            while(isActive && sp.isSpeaking) {
                                RemoteSpeechBus.state.value=RemoteSpeechState(sp.name.orEmpty(),sp.audioLevel.coerceIn(0f,1f),true)
                                delay(70)
                            }
                            RemoteSpeechBus.state.value=RemoteSpeechState()
                        }
                    }
                }
            }
            room = r"""
if old not in s: raise SystemExit("marker missing")
p.write_text(s.replace(old,new))
print("C56 speech source applied")
