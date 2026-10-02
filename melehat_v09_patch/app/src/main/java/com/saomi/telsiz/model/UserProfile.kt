package com.saomi.telsiz.model

data class UserProfile(
    val phone: String = "",
    val email: String = "",
    val fullName: String = "",
    val photoUri: String = ""
) {
    val isComplete: Boolean
        get() = phone.isNotBlank() && email.isNotBlank() && fullName.isNotBlank() && photoUri.isNotBlank()
}