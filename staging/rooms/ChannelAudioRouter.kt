package com.saomi.telsiz.rooms

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Staging implementation: never attach to the existing PTT service until tested.
 * Transport opens an independent LiveKit Room for each channel; a receive-only
 * room must be given a server-issued token without publishing permission.
 */
interface MultiRoomTransport {
    suspend fun connect(channelId: String, receiveOnly: Boolean): Boolean
    suspend fun disconnect(channelId: String)
    suspend fun microphone(channelId: String, enabled: Boolean): Boolean
}

/** Server authorization must independently confirm current room membership. */
interface RoomAccess {
    suspend fun allowed(channelId: String): Boolean
}

class ChannelAudioRouter(
    private val transport: MultiRoomTransport,
    private val access: RoomAccess
) {
    private val mutex = Mutex()
    private var selected: String? = null
    private val retained = mutableSetOf<String>()
    private val listening = mutableSetOf<String>()
    private var transmitting = false

    suspend fun select(channelId: String): Boolean = mutex.withLock {
        if (!access.allowed(channelId)) return@withLock false
        if (selected == channelId) return@withLock true
        val old = selected
        if (old != null) {
            if (transmitting) transport.microphone(old, false)
            transmitting = false
            transport.disconnect(old)
            selected = null
            if (old in retained && access.allowed(old)) {
                if (transport.connect(old, receiveOnly = true)) listening.add(old)
            }
        }
        if (channelId in listening) {
            transport.disconnect(channelId)
            listening.remove(channelId)
        }
        if (!transport.connect(channelId, receiveOnly = false)) return@withLock false
        selected = channelId
        true
    }

    suspend fun keepActive(channelId: String, enabled: Boolean): Boolean = mutex.withLock {
        if (channelId == "ortak" || !access.allowed(channelId)) return@withLock false
        if (enabled) {
            retained.add(channelId)
            if (selected != channelId && channelId !in listening &&
                transport.connect(channelId, receiveOnly = true)
            ) listening.add(channelId)
        } else {
            retained.remove(channelId)
            if (listening.remove(channelId)) transport.disconnect(channelId)
        }
        true
    }

    suspend fun ptt(pressed: Boolean): Boolean = mutex.withLock {
        val channelId = selected ?: return@withLock false
        if (pressed && !access.allowed(channelId)) return@withLock false
        // Never send microphone traffic to a receive-only background room.
        val ok = transport.microphone(channelId, pressed)
        if (ok) transmitting = pressed
        ok
    }

    suspend fun refreshMembership() = mutex.withLock {
        for (roomId in listening.toList()) {
            if (!access.allowed(roomId)) {
                transport.disconnect(roomId)
                listening.remove(roomId)
                retained.remove(roomId)
            }
        }
        val focus = selected
        if (focus != null && !access.allowed(focus)) {
            transport.microphone(focus, false)
            transmitting = false
            transport.disconnect(focus)
            selected = null
        }
    }

    suspend fun state(): ChannelRoutingState = mutex.withLock {
        ChannelRoutingState(
            focusedChannelId = selected ?: "ortak",
            followedChannelIds = listening.toSet(),
            microphoneChannelId = if (transmitting) selected else null
        )
    }
}
