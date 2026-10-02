package com.saomi.telsiz.data

import android.content.Context
import com.saomi.telsiz.auth.AuthSession

class SessionStore(context: Context) {
    private val prefs = context.getSharedPreferences("melehat_telsiz_auth", Context.MODE_PRIVATE)
    fun save(session: AuthSession) { prefs.edit().putString("access_token",session.accessToken).putString("refresh_token",session.refreshToken).putString("user_id",session.userId).putString("phone",session.phone).putString("email",session.email).apply() }
    fun load(): AuthSession? {
        val access=prefs.getString("access_token","").orEmpty(); val userId=prefs.getString("user_id","").orEmpty(); if(access.isBlank()||userId.isBlank()) return null
        return AuthSession(access,prefs.getString("refresh_token","").orEmpty(),userId,prefs.getString("phone","").orEmpty(),prefs.getString("email","").orEmpty())
    }
    fun clear()=prefs.edit().clear().apply()
}