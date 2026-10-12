#!/usr/bin/env python3
"""MELEHAT v1.3.75: preserve a user-enabled radio session across Android
backgrounding and Wi-Fi/mobile handoffs. Existing main PTT, signing,
camera, membership and video hangup are untouched.

Android FGS remains START_STICKY and stopWithTask=false. This patch makes
the two live WebRTC engines recover from network changes, instead of leaving
a stale peer and false LIVE state. Session heartbeat remains authenticated.
"""
from pathlib import Path

base=Path("app/src/main")
dir_=base/"java/com/saomi/telsiz/p2p"
duo=dir_/"P2pRadioClient.kt"
mesh=dir_/"P2pMeshRadioClient.kt"
manifest=base/"AndroidManifest.xml"
service=base/"java/com/saomi/telsiz/service/PttForegroundService.kt"

def one(s,old,new,label):
 n=s.count(old)
 if n!=1:raise RuntimeError(label+" expected one anchor, found "+str(n))
 return s.replace(old,new,1)

src=duo.read_text(encoding="utf-8")
src=one(src,
'''import android.Manifest
''',
'''import android.Manifest
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import kotlinx.coroutines.CancellationException
import java.util.concurrent.atomic.AtomicBoolean
''',"duo network imports")
src=one(src,
'''    private var generation = 0''',
'''    private var generation = 0
    private val networkReset = AtomicBoolean(false)
    @Volatile private var currentNetwork: Network? = null
    private var networkCallback: ConnectivityManager.NetworkCallback? = null

    private fun registerNetworkRecovery() {
        if(networkCallback!=null)return
        val cm=context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val callback=object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network:Network) {
                val previous=currentNetwork
                currentNetwork=network
                if(previous!=null && previous!=network) {
                    // A new IP route requires a fresh ICE + SDP exchange.
                    forceMute()
                    networkReset.set(true)
                }
            }
            override fun onLost(network:Network) {
                if(currentNetwork==network) {
                    currentNetwork=null
                    forceMute()
                    networkReset.set(true)
                }
            }
            override fun onCapabilitiesChanged(network:Network,caps:NetworkCapabilities) {
                if(currentNetwork==network && !caps.hasCapability(
                        NetworkCapabilities.NET_CAPABILITY_VALIDATED)) {
                    forceMute()
                    networkReset.set(true)
                }
            }
        }
        cm.registerDefaultNetworkCallback(callback)
        networkCallback=callback
    }

    private fun unregisterNetworkRecovery() {
        val callback=networkCallback?:return
        networkCallback=null
        runCatching {
            val cm=context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            cm.unregisterNetworkCallback(callback)
        }
        currentNetwork=null
        networkReset.set(false)
    }''',"duo callback state")
src=one(src,
'''            running=true
            loop=scope.launch { watchPeers(generation) }''',
'''            running=true
            // A foreground radio outlives the Activity. Watch Android's default
            // network and rebuild ICE after switching Wi-Fi/mobile data.
            runCatching { registerNetworkRecovery() }
            loop=scope.launch { watchPeers(generation) }''',"duo subscribe while radio on")
src=one(src,
'''        while(scope.isActive && running && generation==epoch) {
            try {
                val heartbeat=presence("beat")''',
'''        while(scope.isActive && running && generation==epoch) {
            try {
                if(networkReset.getAndSet(false)) {
                    stopPeer()
                    peerId=""
                    peerSession=""
                    lastAttempt=0L
                    LiveChannelUiState.connectionProblem("P2P_AG_YENILENIYOR")
                }
                val heartbeat=presence("beat")''',"duo recover each live network")
src=one(src,
'''            } catch(e:Exception) {
                if(running)LiveChannelUiState.connectionProblem(
                    "P2P_AG_HATASI_" + e.javaClass.simpleName.take(22))
                delay(2500L)
            }
            delay(2500L)''',
'''            } catch(e:CancellationException) {
                throw e
            } catch(e:Exception) {
                if(running) {
                    // A stale peer cannot keep showing "LIVE" through an
                    // outage. Stop sending and renegotiate automatically.
                    stopPeer()
                    peerId=""
                    peerSession=""
                    lastAttempt=0L
                    LiveChannelUiState.connectionProblem("P2P_AG_YENIDEN_BAGLANIYOR")
                }
                delay(2500L)
            }
            delay(2500L)''',"duo recover from RPC and signaling failure")
src=one(src,
'''    suspend fun disconnect() {
        running=false;generation++
        forceMute()''',
'''    suspend fun disconnect() {
        running=false;generation++
        unregisterNetworkRecovery()
        forceMute()''',"duo disconnect unregister")
duo.write_text(src,encoding="utf-8")

src=mesh.read_text(encoding="utf-8")
src=one(src,'''import android.content.pm.PackageManager''',
'''import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import kotlinx.coroutines.CancellationException
import java.util.concurrent.atomic.AtomicBoolean''',"mesh imports")
src=one(src,
'''    private var epoch=0''',
'''    private var epoch=0
    private val networkReset=AtomicBoolean(false)
    @Volatile private var currentNetwork:Network?=null
    private var networkCallback:ConnectivityManager.NetworkCallback?=null

    private fun registerNetworkRecovery() {
        if(networkCallback!=null)return
        val cm=context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val callback=object:ConnectivityManager.NetworkCallback(){
            override fun onAvailable(network:Network){
                val previous=currentNetwork
                currentNetwork=network
                if(previous!=null && previous!=network){
                    forceMute()
                    networkReset.set(true)
                }
            }
            override fun onLost(network:Network){
                if(currentNetwork==network){
                    currentNetwork=null
                    forceMute()
                    networkReset.set(true)
                }
            }
            override fun onCapabilitiesChanged(network:Network,caps:NetworkCapabilities){
                if(currentNetwork==network && !caps.hasCapability(
                        NetworkCapabilities.NET_CAPABILITY_VALIDATED)){
                    forceMute()
                    networkReset.set(true)
                }
            }
        }
        cm.registerDefaultNetworkCallback(callback)
        networkCallback=callback
    }
    private fun unregisterNetworkRecovery(){
        val cb=networkCallback?:return
        networkCallback=null
        runCatching{
            (context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager)
                .unregisterNetworkCallback(cb)
        }
        currentNetwork=null
        networkReset.set(false)
    }''',"mesh callback state")
src=one(src,
'''            running=true
            watchJob=scope.launch{watch(thisEpoch)}''',
'''            running=true
            runCatching{registerNetworkRecovery()}
            watchJob=scope.launch{watch(thisEpoch)}''',"mesh register while radio on")
src=one(src,
'''        while(running && scope.isActive && epoch==generation) {
            try {
                val res=presence("beat")''',
'''        while(running && scope.isActive && epoch==generation) {
            try {
                if(networkReset.getAndSet(false)) {
                    destroyAllLinks()
                    LiveChannelUiState.status("CONNECTING")
                    LiveChannelUiState.connectionProblem("P2P_AG_YENILENIYOR")
                }
                val res=presence("beat")''',"mesh reset stale ICE on handoff")
src=one(src,
'''            } catch(e:Exception){
                LiveChannelUiState.connectionProblem(
                    "P2P_ESLESME_"+e.javaClass.simpleName.take(20))
            }
            delay(2500L)''',
'''            } catch(e:CancellationException){
                throw e
            } catch(e:Exception){
                forceMute()
                destroyAllLinks()
                LiveChannelUiState.status("CONNECTING")
                LiveChannelUiState.connectionProblem("P2P_AG_YENIDEN_BAGLANIYOR")
            }
            delay(2500L)''',"mesh reconnect on presence/signaling loss")
src=one(src,
'''    suspend fun disconnect(){
        running=false;admitted=false;epoch++
        forceMute()''',
'''    suspend fun disconnect(){
        running=false;admitted=false;epoch++
        unregisterNetworkRecovery()
        forceMute()''',"mesh unregister")
mesh.write_text(src,encoding="utf-8")

m=manifest.read_text(encoding="utf-8")
if 'android.permission.ACCESS_NETWORK_STATE' not in m:
 m=one(m,'<application',
     '<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />\\n    <application',
     "network state permission")
 manifest.write_text(m,encoding="utf-8")

# Assert foreground service stays active even after task is removed and its
# sticky restart guard remains. Do not attempt prohibited boot mic starts.
sv=service.read_text(encoding="utf-8")
for item in ('return START_STICKY','override fun onTaskRemoved',
             'android:stopWithTask="false"' if False else 'startAsForeground',
             'VideoCallMonitor.start(applicationContext)',
             'ACTION_PTT_UP','ptt.forceMute()'):
 if item not in sv: raise RuntimeError("Protected foreground radio missing "+item)
for item in ('android:stopWithTask="false"',
             'android:foregroundServiceType="microphone"'):
 assert item in m,item

for fp in (duo,mesh):
 data=fp.read_text(encoding="utf-8")
 for token in ('registerDefaultNetworkCallback','unregisterNetworkCallback',
               'networkReset.getAndSet(false)','forceMute()','presence("beat")'):
  assert token in data,fp.name+" missing "+token
assert 'applicationId = "com.melehat.telsiz"' in Path("app/build.gradle.kts").read_text()
print("MELEHAT_1375_FOREGROUND_RADIO_AUTORECONNECT_NETWORK_HANDOFF_READY")
