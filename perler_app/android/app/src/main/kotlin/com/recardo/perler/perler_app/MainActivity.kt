package com.recardo.perler.perler_app

import android.content.ContentValues
import android.media.MediaScannerConnection
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File
import java.io.FileOutputStream

class MainActivity : FlutterActivity() {
    private val channelName = "perler_app/export"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "savePng" -> {
                        val bytes = call.argument<ByteArray>("bytes")
                        val name = call.argument<String>("name") ?: "pattern.png"
                        if (bytes == null) {
                            result.error("no_bytes", "PNG 字节为空", null)
                            return@setMethodCallHandler
                        }
                        try {
                            val rel = savePng(bytes, name)
                            result.success(rel)
                        } catch (e: Exception) {
                            result.error("save_failed", e.message, null)
                        }
                    }
                    else -> result.notImplemented()
                }
            }
    }

    /** 保存到相册「Pictures/拼豆图纸」，返回展示用路径。 */
    private fun savePng(bytes: ByteArray, name: String): String {
        val folder = "拼豆图纸"
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            // Android 10+：MediaStore 直接写入公共相册，无需任何权限
            val values = ContentValues().apply {
                put(MediaStore.Images.Media.DISPLAY_NAME, name)
                put(MediaStore.Images.Media.MIME_TYPE, "image/png")
                put(
                    MediaStore.Images.Media.RELATIVE_PATH,
                    "${Environment.DIRECTORY_PICTURES}/$folder"
                )
                put(MediaStore.Images.Media.IS_PENDING, 1)
            }
            val resolver = contentResolver
            val uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
                ?: throw IllegalStateException("无法创建媒体条目")
            resolver.openOutputStream(uri)?.use { it.write(bytes) }
                ?: throw IllegalStateException("无法打开输出流")
            values.clear()
            values.put(MediaStore.Images.Media.IS_PENDING, 0)
            resolver.update(uri, values, null, null)
            "相册 › Pictures/$folder/$name"
        } else {
            // Android 9 及以下：写公共 Pictures 目录并触发媒体扫描
            val dir = File(
                Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PICTURES),
                folder
            )
            if (!dir.exists()) dir.mkdirs()
            val file = File(dir, name)
            FileOutputStream(file).use { it.write(bytes) }
            MediaScannerConnection.scanFile(
                this, arrayOf(file.absolutePath), arrayOf("image/png"), null
            )
            "Pictures/$folder/$name"
        }
    }
}
