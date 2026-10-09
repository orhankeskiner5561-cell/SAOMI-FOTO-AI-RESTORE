# MELEHAT private video call architecture (development plan)
# Current implementation: member selection UI only. No outgoing call is sent yet.
#
# Security invariants:
# - Caller and callee must be authenticated MELEHAT member user IDs.
# - A trusted backend validates both identities and issues short-lived LiveKit tokens.
# - Private room IDs must be generated server-side and scoped to exactly two identities.
# - Caller cannot create a room token for an arbitrary third party.
# - Signal lifecycle: ringing -> accepted/rejected/expired -> connected -> ended.
# - Incoming call requires push signaling (FCM) when app is in background.
# - Camera/mic permissions are requested on joining the private call, not for PTT.
# - Never reuse Kanal 1 room tokens for private video calls.
# - Maintain PTT audio route and restore channel behavior after a call.
#
# Next backend tasks:
# 1. authenticated call invitation endpoint and persistent call state;
# 2. recipient notification and accept/reject endpoint;
# 3. server-issued two-party LiveKit room credentials;
# 4. Android private call screen, media controls and lifecycle cleanup.
