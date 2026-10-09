package com.saomi.telsiz.rooms

/**
 * UI state models for the next MELEHAT channel-room screen.
 * Staged source: not compiled into the current v1.3.25 Android app.
 * Backend approval, not these UI models, must control LiveKit access.
 */
data class ChannelRoom(
    val id: String,
    val title: String,
    val ownerUserId: String,
    val memberCount: Int,
    val listed: Boolean = true,
    val requiresApproval: Boolean = true
)

enum class JoinRequestStatus { NONE, PENDING, APPROVED, REJECTED }

data class RoomJoinRequest(
    val requestId: String,
    val channelId: String,
    val requesterUserId: String,
    val requesterName: String,
    val status: JoinRequestStatus
)

sealed interface RoomLobbyState {
    data object Loading : RoomLobbyState
    data class Ready(
        val availableRooms: List<ChannelRoom>,
        val myRequests: List<RoomJoinRequest>,
        val ownedRooms: List<ChannelRoom>
    ) : RoomLobbyState
    data class Error(val message: String) : RoomLobbyState
}

/** Request commands are intents only; server must authenticate and authorize. */
sealed interface RoomAction {
    data class CreateRoom(val name: String, val listed: Boolean = true) : RoomAction
    data class RequestJoin(val channelId: String) : RoomAction
    data class Approve(val requestId: String) : RoomAction
    data class Reject(val requestId: String) : RoomAction
}
