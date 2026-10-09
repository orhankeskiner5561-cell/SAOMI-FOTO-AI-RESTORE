package com.saomi.telsiz.rooms

/**
 * Pure Kotlin routing assertions for the next integration test build.
 * This does not connect to LiveKit or modify the current Android app.
 */
fun checkChannelRoutingContract() {
    val onCommon = ChannelRoutingState(
        focusedChannelId = "ortak",
        followedChannelIds = setOf("kanal-1"),
        microphoneChannelId = "ortak"
    )
    check(onCommon.modeOf("ortak") == ChannelAudioMode.FOCUSED_TALK_AND_LISTEN)
    check(onCommon.modeOf("kanal-1") == ChannelAudioMode.FOLLOWED_LISTEN_ONLY)
    check(onCommon.canTransmitTo("ortak"))
    check(!onCommon.canTransmitTo("kanal-1"))

    val inPrivateRoom = ChannelRoutingState(
        focusedChannelId = "kanal-1",
        followedChannelIds = emptySet(),
        microphoneChannelId = null
    )
    check(!inPrivateRoom.canTransmitTo("kanal-1"))
    check(inPrivateRoom.modeOf("ortak") == ChannelAudioMode.DISCONNECTED)
}
