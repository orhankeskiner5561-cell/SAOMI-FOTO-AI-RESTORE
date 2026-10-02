package com.saomi.fotoairestore

import android.content.ContentValues
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.provider.MediaStore
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.compose.setContent
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import java.io.OutputStream

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                val vm: RestoreViewModel = viewModel(factory = RestoreViewModel.factory(applicationContext))
                AppScreen(
                    vm = vm,
                    loadBitmap = { uri -> contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it) } },
                    saveBitmap = { bmp -> saveBitmap(bmp) }
                )
            }
        }
    }

    private fun saveBitmap(bitmap: Bitmap): String {
        val name = "SAOMI_AI_${System.currentTimeMillis()}.png"
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, name)
            put(MediaStore.Images.Media.MIME_TYPE, "image/png")
            put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/SaomiFotoAIRestore")
        }
        val uri = contentResolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
            ?: return "Kaydetme başarısız."
        contentResolver.openOutputStream(uri)?.use { out: OutputStream ->
            bitmap.compress(Bitmap.CompressFormat.PNG, 100, out)
        }
        return "Kaydedildi: Pictures/SaomiFotoAIRestore/$name"
    }
}

@Composable
private fun CompareCard(title: String, bitmap: Bitmap?, emptyText: String, modifier: Modifier = Modifier) {
    Card(modifier = modifier) {
        Column(Modifier.fillMaxWidth().padding(8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(title, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(6.dp))
            Box(
                Modifier.fillMaxWidth().height(260.dp).background(MaterialTheme.colorScheme.surfaceVariant),
                contentAlignment = Alignment.Center
            ) {
                if (bitmap != null) {
                    Image(
                        bitmap = bitmap.asImageBitmap(),
                        contentDescription = title,
                        modifier = Modifier.fillMaxSize(),
                        contentScale = ContentScale.Fit
                    )
                } else {
                    Text(emptyText, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}

@Composable
private fun AppScreen(
    vm: RestoreViewModel,
    loadBitmap: (Uri) -> Bitmap?,
    saveBitmap: (Bitmap) -> String
) {
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        uri?.let { loadBitmap(it)?.let(vm::setImage) }
    }

    Scaffold(
        topBar = {
            Surface(shadowElevation = 2.dp) {
                Column(Modifier.fillMaxWidth().padding(16.dp)) {
                    Text("ŞAOMİ FOTO AI RESTORE", style = MaterialTheme.typography.titleLarge)
                    Text("V0.4 • Öncesi / Sonrası • Yerel AI", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    ) { pad ->
        Column(
            Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            AssistChip(
                onClick = {},
                label = { Text(if (vm.aiReady) "AI motoru hazır" else "AI motoru hazırlanıyor / bulunamadı") }
            )

            Button(onClick = { picker.launch("image/*") }, modifier = Modifier.fillMaxWidth()) {
                Text("Fotoğraf Seç")
            }

            if (vm.originalBitmap != null) {
                Text("Karşılaştırma", style = MaterialTheme.typography.titleMedium)
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    CompareCard("ÖNCESİ", vm.originalPreview, "Fotoğraf seçin", Modifier.weight(1f))
                    CompareCard("SONRASI", vm.resultPreview, "İşlemden sonra burada görünecek", Modifier.weight(1f))
                }

                val done = vm.resultBitmap != null && !vm.isBusy
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    tonalElevation = 2.dp,
                    shape = MaterialTheme.shapes.medium
                ) {
                    Text(
                        if (vm.isBusy) "⏳ İşlem devam ediyor..." else if (done) "✓ İşlem yapıldı. Sonuç sağ tarafta." else "Henüz işlem yapılmadı.",
                        modifier = Modifier.padding(12.dp),
                        fontWeight = FontWeight.SemiBold
                    )
                }

                Text("Restorasyon", style = MaterialTheme.typography.titleMedium)

                FilterChip(
                    selected = vm.preserveOriginal,
                    onClick = { vm.preserveOriginal = !vm.preserveOriginal },
                    label = { Text("Orijinalliği Koru") }
                )
                FilterChip(
                    selected = vm.faceProtectEnabled,
                    onClick = { vm.faceProtectEnabled = !vm.faceProtectEnabled },
                    label = { Text("Yüzleri Değiştirme / Kimliği Koru") }
                )
                FilterChip(
                    selected = vm.scratchRepairEnabled,
                    onClick = { vm.scratchRepairEnabled = !vm.scratchRepairEnabled },
                    label = { Text("Uzun Çizik / Toz Onarımı") }
                )
                FilterChip(
                    selected = vm.cleanEnabled,
                    onClick = { vm.cleanEnabled = !vm.cleanEnabled },
                    label = { Text("Kir / Kumlanma Temizleme") }
                )
                FilterChip(
                    selected = vm.colorEnabled,
                    onClick = { vm.colorEnabled = !vm.colorEnabled },
                    label = { Text("Renkleri canlandır") }
                )

                Text("AI büyütme")
                SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                    SegmentedButton(
                        selected = vm.scale == 1,
                        onClick = { vm.scale = 1 },
                        shape = SegmentedButtonDefaults.itemShape(0, 3)
                    ) { Text("1×") }
                    SegmentedButton(
                        selected = vm.scale == 2,
                        onClick = { vm.scale = 2 },
                        shape = SegmentedButtonDefaults.itemShape(1, 3)
                    ) { Text("2×") }
                    SegmentedButton(
                        selected = vm.scale == 4,
                        onClick = { vm.scale = 4 },
                        shape = SegmentedButtonDefaults.itemShape(2, 3)
                    ) { Text("4× AI") }
                }

                Button(
                    onClick = { vm.process() },
                    enabled = !vm.isBusy,
                    modifier = Modifier.fillMaxWidth()
                ) { Text(if (vm.isBusy) "İşleniyor..." else "Temizle + Netleştir") }

                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(
                        onClick = { vm.showBefore() },
                        enabled = !vm.isBusy,
                        modifier = Modifier.weight(1f)
                    ) { Text("Öncesi") }
                    OutlinedButton(
                        onClick = { vm.showAfter() },
                        enabled = !vm.isBusy && vm.resultBitmap != null,
                        modifier = Modifier.weight(1f)
                    ) { Text("Sonrası") }
                }

                vm.previewBitmap?.let { preview ->
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(8.dp)) {
                            Text("Büyük Önizleme", fontWeight = FontWeight.Bold)
                            Spacer(Modifier.height(6.dp))
                            Image(
                                bitmap = preview.asImageBitmap(),
                                contentDescription = "Büyük önizleme",
                                modifier = Modifier.fillMaxWidth().heightIn(min = 300.dp, max = 520.dp),
                                contentScale = ContentScale.Fit
                            )
                        }
                    }
                }

                vm.resultBitmap?.let { result ->
                    Button(
                        onClick = { vm.status = saveBitmap(result) },
                        enabled = !vm.isBusy,
                        modifier = Modifier.fillMaxWidth()
                    ) { Text("Kaydet") }
                }

                LinearProgressIndicator(
                    progress = { vm.progress },
                    modifier = Modifier.fillMaxWidth()
                )
                Text(vm.status, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
