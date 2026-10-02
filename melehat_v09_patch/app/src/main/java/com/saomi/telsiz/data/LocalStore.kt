package com.saomi.telsiz.data

import android.content.Context
import com.saomi.telsiz.model.ChannelInfo
import com.saomi.telsiz.model.UserProfile

class LocalStore(context: Context) {
    private val prefs=context.getSharedPreferences("melehat_telsiz",Context.MODE_PRIVATE)
    fun saveProfile(profile:UserProfile){ prefs.edit().putString("phone",profile.phone).putString("email",profile.email).putString("full_name",profile.fullName).putString("photo_uri",profile.photoUri).apply() }
    fun loadProfile():UserProfile=UserProfile(prefs.getString("phone","")?:"",prefs.getString("email","")?:"",prefs.getString("full_name","")?:"",prefs.getString("photo_uri","")?:"")
    fun clearProfile(){ prefs.edit().remove("phone").remove("email").remove("full_name").remove("photo_uri").apply() }
    fun saveActiveChannel(channel:ChannelInfo){ prefs.edit().putString("channel_id",channel.id).putString("channel_name",channel.name).putInt("channel_members",channel.memberCount).apply() }
    fun loadActiveChannel():ChannelInfo=ChannelInfo(prefs.getString("channel_id","kanal-1")?:"kanal-1",prefs.getString("channel_name","KANAL 1")?:"KANAL 1",prefs.getInt("channel_members",1))
    fun setRadioEnabled(enabled:Boolean){ prefs.edit().putBoolean("radio_enabled",enabled).apply() }
    fun isRadioEnabled():Boolean=prefs.getBoolean("radio_enabled",false)
}