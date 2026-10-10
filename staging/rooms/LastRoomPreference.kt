package com.saomi.telsiz.rooms

import android.content.Context
import com.saomi.telsiz.model.ChannelInfo

/**
 * One remembered room PER authenticated member on this phone.
 * A brand-new account defaults to public ORTAK KANAL; the first existing
 * signed-in user may claim the pre-upgrade legacy room choice once.
 *
 * Room IDs are validated, but access to private rooms remains enforced
 * separately by the existing server-issued LiveKit room tokens.
 */
class LastRoomPreference(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences(
        "melehat_last_selected_room_v1348", Context.MODE_PRIVATE
    )

    private fun memberKey(userId: String) = "room_" + userId.trim()
    private fun titleKey(userId: String) = "title_" + userId.trim()
    private fun validId(id: String): Boolean =
        id == "ortak" || id.matches(Regex("kanal-[a-z0-9-]{1,64}"))

    private fun canonical(room: ChannelInfo): ChannelInfo =
        if (!validId(room.id)) publicRoom()
        else ChannelInfo(
            room.id,
            if (room.id == "ortak") "ORTAK KANAL"
                else room.name.trim().ifEmpty { room.id },
            room.memberCount
        )

    fun publicRoom() = ChannelInfo("ortak", "ORTAK KANAL")

    @Synchronized
    fun loadOrInitialize(userId: String, preUpgradeSelection: ChannelInfo): ChannelInfo {
        if (userId.isBlank()) return publicRoom()
        val key = memberKey(userId)
        val savedId = prefs.getString(key, null)
        if (savedId != null) {
            return canonical(ChannelInfo(
                savedId,
                prefs.getString(titleKey(userId), "ORTAK KANAL").orEmpty()
            ))
        }

        // One-time migration for the already signed-in member when upgrading
        // from v1.3.47. Every newly registered account defaults to ORTAK.
        val wasClaimed = prefs.getBoolean("legacy_preference_claimed", false)
        val initial = if (!wasClaimed) canonical(preUpgradeSelection) else publicRoom()
        prefs.edit()
            .putBoolean("legacy_preference_claimed", true)
            .putString(key, initial.id)
            .putString(titleKey(userId), initial.name)
            .commit()
        return initial
    }

    @Synchronized
    fun remember(userId: String, room: ChannelInfo) {
        if (userId.isBlank()) return
        val normalized = canonical(room)
        prefs.edit()
            .putBoolean("legacy_preference_claimed", true)
            .putString(memberKey(userId), normalized.id)
            .putString(titleKey(userId), normalized.name)
            .commit()
    }
}
