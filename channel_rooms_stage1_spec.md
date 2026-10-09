# MELEHAT TELSIZ — multi-room channel UI stage 1
# This file is intentionally NOT wired into the production Android workflow.
# Existing v1.3.25 APK, package ID, keystore, LiveKit/PTT and member list remain unchanged.
#
# UI models and screens to integrate after backend membership checks are implemented:
#
# SCREEN A: LOBBY (registered member with no channel)
#   - "Kanal Aç" -> channel name, description, public listing, owner approval required
#   - "Kanallar" -> discoverable channel directory
#   - "İsteklerim" -> pending / accepted / rejected requests
#   - PTT disabled until backend verifies membership and issues channel-scoped token
#
# SCREEN B: CHANNEL DIRECTORY
#   - Channel name, owner, member count (no member identities for non-members)
#   - "Katılma İsteği Gönder" button, disabled when request already pending
#   - Publicly listed channels are NOT publicly joinable
#
# SCREEN C: OWNER INBOX
#   - Requester account ID, display name, request timestamp
#   - "Kabul Et" / "Reddet"
#   - Approval/rejection must be validated and executed by trusted backend
#
# SCREEN D: ACTIVE CHANNEL
#   - Existing PTT and LiveKit audio UI reused WITHOUT replacing existing client
#   - Leave channel, owner moderation and member roster
#
# BACKEND CONTRACT (future work; DO NOT TRUST CLIENT-SIDE FLAGS)
#   channels: id, name, owner_user_id, listed, approval_required, created_at
#   channel_members: channel_id, user_id, role, created_at
#   channel_join_requests: id, channel_id, requester_user_id, status, reviewed_by, reviewed_at
#   RLS: owner-only accept/reject, unique pending request per user/channel
#   LiveKit room tokens issued ONLY after server verifies approved membership
#   All status changes must be persisted and surfaced to requester.
#
# MIGRATION REQUIREMENT:
#   Existing KANAL 1 is listed but requires owner approval.
#   Its four existing members remain approved and are not automatically removed.
#   Owner identity must be verified against the actual registered account, not hardcoded.
#   New signups start in the lobby and cannot access existing audio by default.
#
# RELEASE INVARIANTS:
#   applicationId com.melehat.telsiz; same permanent signing secrets and keystore
#   monotonic versionCode; in-place upgrade; no new package name or key
#   never publish an untested release or switch melehat-update.json early.
