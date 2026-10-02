package com.saomi.telsiz.auth

data class AuthSession(
    val accessToken: String,
    val refreshToken: String,
    val userId: String,
    val phone: String,
    val email: String
)

sealed interface AuthStatus {
    data object SignedOut : AuthStatus
    data class OtpSent(val email: String) : AuthStatus
    data class SignedIn(val session: AuthSession) : AuthStatus
    data class Error(val message: String) : AuthStatus
}