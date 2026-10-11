package com.saomi.telsiz.p2p

import android.content.Context
import com.saomi.telsiz.model.ChannelInfo
import com.saomi.telsiz.model.UserProfile
import com.saomi.telsiz.voice.LiveKitPttClient

/**
 * Keep the complete legacy LiveKit implementation intact for safe rollback.
 * Native P2P is selected by default. Never silently fall back from P2P to
 * LiveKit when service credits are exhausted.
 */
class HybridRadioClient(context: Context) {
    private val native=P2pRadioClient(context.applicationContext)
    private val legacy=LiveKitPttClient(context.applicationContext)
    private val prefs=context.getSharedPreferences("melehat_p2p_transport", Context.MODE_PRIVATE)
    private var useP2p=true

    suspend fun connect(profile:UserProfile, channel:ChannelInfo):Boolean {
        val enabled=prefs.getBoolean("native_p2p_enabled",true)
        if(enabled!=useP2p) {
            native.disconnect()
            legacy.disconnect()
        }
        useP2p=enabled
        return if(useP2p) native.connect(profile,channel) else legacy.connect(profile,channel)
    }
    suspend fun ensureConnected():Boolean =
        if(useP2p) native.ensureConnected() else legacy.ensureConnected()

    suspend fun setTransmitting(enabled:Boolean):Boolean =
        if(useP2p) native.setTransmitting(enabled) else legacy.setTransmitting(enabled)

    fun forceMute() {
        if(useP2p) native.forceMute()
    }

    fun isConnected():Boolean =
        if(useP2p) native.isConnected() else legacy.isConnected()

    fun isConnectedTo(room:String):Boolean =
        if(useP2p) native.isConnectedTo(room) else legacy.isConnectedTo(room)

    suspend fun disconnect() {
        native.disconnect()
        legacy.disconnect()
    }
}
