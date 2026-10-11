from pathlib import Path

# MELEHAT v1.3.61: observe why two radio clients stay "BAĞLANIYOR".
# Preserve v1.3.58+ LiveKit media path, PTT, Shizuku, channel identity and
# keep-alive/reconnect policy. User-visible diagnostics contain no tokens, URLs
# or names. This version does not claim to fix a network failure.
root=Path("app/src/main/java/com/saomi/telsiz")
state=root/"voice/LiveChannelUiState.kt"
client=root/"voice/LiveKitPttClient.kt"
ui=root/"ui/AppRoot.kt"

def change(path,a,b,n=1):
 s=path.read_text(encoding="utf-8")
 if s.count(a)!=n: raise SystemExit(f"v1361 anchor {path.name}: expected {n}, found {s.count(a)}: {a[:100]}")
 path.write_text(s.replace(a,b,n),encoding="utf-8")

change(state,
'''    fun status(value: String) { _status.value = value }''',
'''    private val _connectionProblem = MutableStateFlow("")
    val connectionProblem: StateFlow<String> = _connectionProblem

    fun connectionProblem(value: String) { _connectionProblem.value = value }
    fun status(value: String) { _status.value = value }''')

change(client,
'''        if (!profile.isComplete) return false

        val session = SessionStore(context).load() ?: return false''',
'''        if (!profile.isComplete) {
            LiveChannelUiState.connectionProblem("PROFIL_EKSIK")
            return false
        }

        val session = SessionStore(context).load() ?: run {
            LiveChannelUiState.connectionProblem("OTURUM_BULUNAMADI")
            return false
        }''')
change(client,
'''        val identity = session.userId
        LiveChannelUiState.status("CONNECTING")''',
'''        val identity = session.userId
        LiveChannelUiState.status("CONNECTING")
        LiveChannelUiState.connectionProblem("TOKEN_ISTENIYOR")''')
change(client,
'''                participantIdentity = identity
            )
        } ?: return false''',
'''                participantIdentity = identity
            )
        } ?: run {
            LiveChannelUiState.connectionProblem("TOKEN_ALINAMADI")
            return false
        }
        LiveChannelUiState.connectionProblem("TOKEN_ALINDI_CANLI_BAGLANTI_BEKLENIYOR")''')
change(client,
'''        return runCatching {
            r.connect(credentials.serverUrl, credentials.participantToken)''',
'''        return runCatching {
            r.connect(credentials.serverUrl, credentials.participantToken)''')
# Kotlin failure category deliberately excludes exception messages (which
# can contain usernames, URLs, headers and other sensitive data).
change(client,
'''        }.getOrElse {
            connected = false
            connectedChannelId = null
            LiveChannelUiState.status("CONNECTING")
            runCatching { r.disconnect() }
            false
        }''',
'''        }.getOrElse { failure ->
            connected = false
            connectedChannelId = null
            val type = failure.javaClass.simpleName.lowercase()
            val category = when {
                "timeout" in type -> "BAGLANTI_ZAMAN_ASIMI"
                "unknownhost" in type -> "SUNUCU_ADRESI_COZULEMEDI"
                "ssl" in type || "certificate" in type -> "TLS_SERTIFIKA"
                "unauthor" in type || "security" in type -> "YETKI_REDDEDILDI"
                else -> "LIVEKIT_BAGLANTI_HATASI_" +
                    failure.javaClass.simpleName.take(45)
            }
            LiveChannelUiState.connectionProblem(category)
            LiveChannelUiState.status("CONNECTING")
            runCatching { r.disconnect() }
            false
        }''')
# We clear reasons only upon real LiveKit connection, never merely token receipt.
s=client.read_text(encoding="utf-8")
needle='''            LiveChannelUiState.status("LIVE")'''
if s.count(needle)<1:raise SystemExit("v1361 expected LiveKit LIVE status")
s=s.replace(needle,needle+'''
            LiveChannelUiState.connectionProblem("")''')
client.write_text(s,encoding="utf-8")

change(ui,
'''    val liveStatus by LiveChannelUiState.status.collectAsState()''',
'''    val liveStatus by LiveChannelUiState.status.collectAsState()
    val liveConnectProblem by LiveChannelUiState.connectionProblem.collectAsState()''')
change(ui,
'''                    Text("Telsiz durumu", fontWeight = FontWeight.SemiBold)''',
'''                    Text("Telsiz durumu", fontWeight = FontWeight.SemiBold)
                    if (radioOn && liveStatus != "LIVE") {
                        Text(
                            "Bağlantı teşhisi: " +
                            (if (liveConnectProblem.isBlank())
                                "SERVIS_YANITI_BEKLENIYOR" else liveConnectProblem)
                        )
                    }''')
for f,pieces in [
 (state,["connectionProblem: StateFlow<String>","fun connectionProblem(value: String)"]),
 (client,["TOKEN_ALINAMADI","TOKEN_ALINDI_CANLI_BAGLANTI_BEKLENIYOR","LIVEKIT_BAGLANTI_HATASI_","connectedChannelId = null"]),
 (ui,["Bağlantı teşhisi: ","LiveChannelUiState.connectionProblem.collectAsState()","BAS KONUŞ"])
]:
 s=f.read_text(encoding="utf-8")
 for item in pieces:
  if item not in s:raise SystemExit("v1361 safety: "+f.name+" missing "+item)
print("MELEHAT_1361_LIVEKIT_FAILURE_REASON_DIAGNOSTICS_READY")
