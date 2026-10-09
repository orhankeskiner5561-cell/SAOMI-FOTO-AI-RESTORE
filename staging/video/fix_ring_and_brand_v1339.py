from pathlib import Path

# MELEHAT 1.3.39: restore audible native incoming-call ringtone and
# make common/private/future channel title fit the complete screen width.
# PTT floor, LiveKit audio/video and channel membership are untouched.
root=Path("app/src/main/java/com/saomi/telsiz")
ui=root/"ui/AppRoot.kt"
s=ui.read_text(encoding="utf-8")

# Foreground AppRoot shows caller name and Accept/Decline, but its previous
# ringtone effect must not play a second sound. A single process-wide ring
# now lives in VideoCallMonitor and works with a locked screen as well.
old = '''    DisposableEffect(incomingVideoCall?.id) {
        val ringing = incomingVideoCall
        val sound = if (ringing != null &&
            !com.saomi.telsiz.video.VideoCallMonitor.notificationsEnabled(callContext)) {
            runCatching {
                android.media.RingtoneManager.getRingtone(
                    callContext,
                    android.media.RingtoneManager.getDefaultUri(
                        android.media.RingtoneManager.TYPE_RINGTONE
                    )
                ).also { it?.play() }
            }.getOrNull()
        } else null
        onDispose { sound?.stop() }
    }'''
if s.count(old) != 1:
    raise SystemExit("MELEHAT ringtone double-play guard source changed")
s = s.replace(old, '''    // Ringing belongs to VideoCallMonitor (one ringtone for foreground,
    // background and lockscreen). Keep the existing call Accept/Decline dialog.
''',1)

title = '''Text(
                        buildAnnotatedString {
                            withStyle(SpanStyle(color = Color(0xFF215E8A))) { append("MELE - HAT ") }
                            withStyle(SpanStyle(color = Color(0xFFE47732))) { append("TELSİZ") }
                        },
                        fontSize = 26.sp, fontWeight = FontWeight.Bold,
                        modifier = Modifier.statusBarsPadding().padding(top = 18.dp)
                    )'''
new_title = '''BoxWithConstraints(
                        modifier = Modifier.fillMaxWidth()
                            .statusBarsPadding()
                            .padding(start = 10.dp, end = 10.dp, top = 18.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        // One shared header for ORTAK KANAL and every private
                        // channel, including rooms created in the future.
                        // Width-relative text prevents camera/status-bar overlap.
                        val proportionalTitleSize =
                            (maxWidth.value * 0.068f).coerceIn(18f, 29f).sp
                        Text(
                            text = buildAnnotatedString {
                                withStyle(SpanStyle(color = Color(0xFF215E8A))) {
                                    append("MELE - HAT ")
                                }
                                withStyle(SpanStyle(color = Color(0xFFE47732))) {
                                    append("TELSİZ")
                                }
                            },
                            fontSize = proportionalTitleSize,
                            fontWeight = FontWeight.Bold,
                            maxLines = 1,
                            softWrap = false,
                            overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis,
                            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }'''
if s.count(title) != 1:
    raise SystemExit("MELEHAT two-color header expected exactly once")
s=s.replace(title,new_title,1)

assert 'VideoCallMonitor.latestMissed.collectAsState()' in s
assert 'MelehatPendingRequestBadge' in s
assert 'KANAL AÇ  +' in s
assert 'AÇ / KABUL ET' in s and 'REDDET / KAPAT' in s
assert 'roomSelection = createdId to cmd.second' in s
ui.write_text(s,encoding="utf-8")
print("MELEHAT_1339_SINGLE_RING_AND_RESPONSIVE_CHANNEL_BRAND_OK")
