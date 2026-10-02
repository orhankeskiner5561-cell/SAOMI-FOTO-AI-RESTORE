package com.saomi.fotoairestore

import android.content.Context
import android.graphics.*
import androidx.compose.runtime.*
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider

class RestoreViewModel(private val context: Context) : ViewModel() {
    var originalBitmap by mutableStateOf<Bitmap?>(null); private set
    var resultBitmap by mutableStateOf<Bitmap?>(null); private set
    var previewBitmap by mutableStateOf<Bitmap?>(null); private set
    var originalPreview by mutableStateOf<Bitmap?>(null); private set
    var resultPreview by mutableStateOf<Bitmap?>(null); private set

    var preserveOriginal by mutableStateOf(true)
    var faceProtectEnabled by mutableStateOf(true)
    var scratchRepairEnabled by mutableStateOf(true)
    var cleanEnabled by mutableStateOf(true)
    var colorEnabled by mutableStateOf(true)
    var scale by mutableIntStateOf(4)

    var isBusy by mutableStateOf(false); private set
    var aiReady by mutableStateOf(false); private set
    var progress by mutableFloatStateOf(0f); private set
    var status by mutableStateOf("Fotoğraf seçin.")

    private val ai = RealSrEngine(context)

    init {
        Thread {
            aiReady = ai.prepare()
            status = if (aiReady) "AI motoru hazır." else "AI motoru bulunamadı; temel restorasyon kullanılacak."
        }.start()
    }

    fun setImage(bitmap: Bitmap) {
        originalBitmap = bitmap
        resultBitmap = null
        originalPreview = makePreview(bitmap)
        resultPreview = null
        previewBitmap = originalPreview
        status = "Fotoğraf hazır. İşlem henüz yapılmadı."
        progress = 0f
    }

    fun showBefore() { previewBitmap = originalPreview }
    fun showAfter() { previewBitmap = resultPreview ?: originalPreview }

    fun process() {
        val src = originalBitmap ?: return
        if (isBusy) return

        isBusy = true
        progress = 0.02f
        status = "Restorasyon başladı..."

        Thread {
            try {
                val faces = if (faceProtectEnabled) {
                    status = "Yüz bölgeleri korunmak için tespit ediliyor..."
                    FaceProtector.detect(src)
                } else emptyList()

                var working = src.copy(Bitmap.Config.ARGB_8888, true)
                progress = 0.10f

                if (scratchRepairEnabled) {
                    status = "Çizik ve noktasal hasarlar onarılıyor..."
                    working = ScratchRepair.repair(
                        working,
                        strength = if (preserveOriginal) 1 else 2
                    )
                    progress = 0.28f
                }

                if (cleanEnabled) {
                    status = "Kir ve kumlanma yumuşatılıyor..."
                    working = edgeAwareDenoise(working, if (preserveOriginal) 1 else 2)
                    progress = 0.42f
                }

                if (colorEnabled) {
                    status = "Solmuş renkler dengeleniyor..."
                    working = restoreColor(working, preserveOriginal)
                    progress = 0.52f
                }

                if (scale == 4 && aiReady) {
                    val tile = MemoryPlanner.chooseTileSize(context, working.width, working.height)
                    status = "Real-ESRGAN 4× çalışıyor • tile=$tile"
                    val aiOut = ai.upscale(working, 4, tile)
                    working = aiOut ?: Bitmap.createScaledBitmap(
                        working, working.width * 4, working.height * 4, true
                    )
                    progress = 0.86f
                } else if (scale == 2) {
                    status = "2× büyütme uygulanıyor..."
                    working = Bitmap.createScaledBitmap(
                        working, working.width * 2, working.height * 2, true
                    )
                    progress = 0.76f
                }

                status = "Son netlik ayarı..."
                working = gentleSharpen(working, if (preserveOriginal) 0.18f else 0.30f)

                if (faceProtectEnabled && faces.isNotEmpty()) {
                    status = "Yüz kimliği korunuyor..."
                    working = FaceProtector.blendOriginalFaces(
                        original = src,
                        restored = working,
                        faces = faces,
                        alpha = if (preserveOriginal) 0.72f else 0.52f
                    )
                }

                progress = 1f
                resultBitmap = working
                resultPreview = makePreview(working)
                previewBitmap = resultPreview
                status = buildString {
                    append("Restorasyon tamamlandı.")
                    if (faces.isNotEmpty()) append(" ${faces.size} yüz korundu.")
                }
            } catch (e: Throwable) {
                status = "Hata: ${e.message ?: e.javaClass.simpleName}"
            } finally {
                isBusy = false
            }
        }.start()
    }

    private fun makePreview(src: Bitmap, maxSide: Int = 1400): Bitmap {
        val maxDim = maxOf(src.width, src.height)
        if (maxDim <= maxSide) return src
        val ratio = maxSide.toFloat() / maxDim.toFloat()
        val w = (src.width * ratio).toInt().coerceAtLeast(1)
        val h = (src.height * ratio).toInt().coerceAtLeast(1)
        return Bitmap.createScaledBitmap(src, w, h, true)
    }

    private fun edgeAwareDenoise(src: Bitmap, passes: Int): Bitmap {
        var cur = src
        repeat(passes) {
            val w = cur.width; val h = cur.height
            val input = IntArray(w*h); val out = input.copyOf()
            cur.getPixels(input,0,w,0,0,w,h)
            for (y in 1 until h-1) for (x in 1 until w-1) {
                val center = input[y*w+x]
                val cr=(center shr 16) and 255; val cg=(center shr 8) and 255; val cb=center and 255
                var rs=0; var gs=0; var bs=0; var ws=0
                for (dy in -1..1) for (dx in -1..1) {
                    val c=input[(y+dy)*w+(x+dx)]
                    val r=(c shr 16) and 255; val g=(c shr 8) and 255; val b=c and 255
                    val diff = kotlin.math.abs(r-cr)+kotlin.math.abs(g-cg)+kotlin.math.abs(b-cb)
                    val weight = if (diff < 55) 3 else if (diff < 100) 1 else 0
                    rs += r*weight; gs += g*weight; bs += b*weight; ws += weight
                }
                if (ws>0) {
                    val a=(center ushr 24) and 255
                    out[y*w+x]=(a shl 24) or ((rs/ws) shl 16) or ((gs/ws) shl 8) or (bs/ws)
                }
            }
            cur = Bitmap.createBitmap(out,w,h,Bitmap.Config.ARGB_8888)
        }
        return cur
    }

    private fun restoreColor(src: Bitmap, subtle: Boolean): Bitmap {
        val w=src.width; val h=src.height; val px=IntArray(w*h)
        src.getPixels(px,0,w,0,0,w,h)
        val sat = if (subtle) 1.035f else 1.09f
        val contrast = if (subtle) 1.02f else 1.055f
        for (i in px.indices) {
            val c=px[i]; val a=(c ushr 24) and 255
            var r=(c shr 16) and 255; var g=(c shr 8) and 255; var b=c and 255
            val avg=(r+g+b)/3f
            r=(avg+(r-avg)*sat).toInt(); g=(avg+(g-avg)*sat).toInt(); b=(avg+(b-avg)*sat).toInt()
            r=((r-128)*contrast+128).toInt().coerceIn(0,255)
            g=((g-128)*contrast+128).toInt().coerceIn(0,255)
            b=((b-128)*contrast+128).toInt().coerceIn(0,255)
            px[i]=(a shl 24) or (r shl 16) or (g shl 8) or b
        }
        return Bitmap.createBitmap(px,w,h,Bitmap.Config.ARGB_8888)
    }

    private fun gentleSharpen(src: Bitmap, amount: Float): Bitmap {
        val blur = edgeAwareDenoise(src, 1)
        val w=src.width; val h=src.height
        val a=IntArray(w*h); val b=IntArray(w*h); val out=IntArray(w*h)
        src.getPixels(a,0,w,0,0,w,h); blur.getPixels(b,0,w,0,0,w,h)
        for (i in out.indices) {
            val ca=a[i]; val cb=b[i]
            val alpha=(ca ushr 24) and 255
            fun ch(shift:Int):Int {
                val x=(ca shr shift) and 255
                val y=(cb shr shift) and 255
                return (x + (x-y)*amount).toInt().coerceIn(0,255)
            }
            out[i]=(alpha shl 24) or (ch(16) shl 16) or (ch(8) shl 8) or ch(0)
        }
        return Bitmap.createBitmap(out,w,h,Bitmap.Config.ARGB_8888)
    }

    companion object {
        fun factory(context: Context) = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T =
                RestoreViewModel(context.applicationContext) as T
        }
    }
}
