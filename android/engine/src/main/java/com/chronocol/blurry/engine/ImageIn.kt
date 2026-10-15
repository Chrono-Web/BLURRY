package com.chronocol.blurry.engine

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ColorSpace
import android.media.ExifInterface
import org.opencv.android.Utils
import org.opencv.core.Core
import org.opencv.core.Mat
import org.opencv.imgproc.Imgproc
import java.io.ByteArrayInputStream

/**
 * The input cannot be processed. Messages never contain paths, and are the
 * same as the Python engine's (files.InputError).
 */
class InputError(message: String) : Exception(message)

enum class OutFormat(val id: String, val ext: String) {
    JPEG("JPEG", "jpg"),
    PNG("PNG", "png"),
}

class LoadedImage(
    /** HxWx3 RGB, display orientation, sRGB. */
    val rgb: Mat,
    /** Only if some pixel is not opaque, and only for PNG output. */
    val alpha: Mat?,
    /** JPEG, PNG, WEBP, HEIF (Pillow's names). */
    val sourceFormat: String,
    val outFormat: OutFormat,
    /** Sorted, names as image_io._metadata_found. */
    val metadataFound: List<String>,
) {
    val width: Int get() = rgb.cols()
    val height: Int get() = rgb.rows()

    fun release() {
        rgb.release()
        alpha?.release()
    }
}

/**
 * Reading as image_io.load: EXIF orientation applied to the pixels, colour
 * profile converted to sRGB, everything in memory.
 */
object ImageIn {
    val extensions = setOf("jpg", "jpeg", "png", "webp", "heic", "heif")
    const val MAX_PIXELS = 120_000_000
    const val MAX_FILE_BYTES = 300 * 1024 * 1024

    private const val UNSUPPORTED_TYPE = "unsupported image type (accepted: JPEG, PNG, WebP, HEIC)"

    /** Bytes already in memory (from the photo picker, a shared file or a document). */
    fun load(data: ByteArray, fileExtension: String): LoadedImage {
        if (fileExtension.lowercase() !in extensions) throw InputError(UNSUPPORTED_TYPE)
        if (data.isEmpty()) throw InputError("empty file")
        if (data.size > MAX_FILE_BYTES) throw InputError("file too large (limit ${MAX_FILE_BYTES / (1024 * 1024)} MB)")

        val format = when {
            Containers.isJPEG(data) -> "JPEG"
            Containers.isPNG(data) -> "PNG"
            Containers.isWebP(data) -> "WEBP"
            Containers.isHEIF(data) -> "HEIF"
            data.size >= 4 && String(data, 0, 4, Charsets.ISO_8859_1) == "GIF8" -> throw InputError("GIF is not supported")
            else -> null
        }
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(data, 0, data.size, bounds)
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) throw InputError("not a readable image")
        if (format == null) throw InputError("unsupported image format (accepted: JPEG, PNG, WebP, HEIC)")
        if ((format == "PNG" && Containers.pngIsAnimated(data)) || (format == "WEBP" && Containers.webpIsAnimated(data))) {
            throw InputError("animated images are not supported")
        }
        if (bounds.outWidth.toLong() * bounds.outHeight > MAX_PIXELS) throw InputError("image too large")

        val found = metadataFound(data, format)
        val opts = BitmapFactory.Options().apply {
            inPreferredConfig = Bitmap.Config.ARGB_8888
            inPremultiplied = false
            inPreferredColorSpace = ColorSpace.get(ColorSpace.Named.SRGB)
        }
        val bitmap = try {
            BitmapFactory.decodeByteArray(data, 0, data.size, opts)
        } catch (e: OutOfMemoryError) {
            null
        } ?: throw InputError("image is damaged or too large")

        // HEIF rotation is applied by the decoder, as by pi-heif.
        val orientation = if (format == "HEIF") 1 else found.orientation
        var (rgb, alpha) = decode(bitmap, orientation)
        bitmap.recycle()
        val out = if (format == "PNG") OutFormat.PNG else OutFormat.JPEG
        if (out == OutFormat.JPEG && alpha != null) {
            flattenOnWhite(rgb, alpha)
            alpha.release()
            alpha = null
        }
        return LoadedImage(rgb, alpha, format, out, found.names.sorted())
    }

    /**
     * RGBA without premultiplication, in sRGB, then put in display orientation.
     * Alpha is kept only if some pixel is not fully opaque.
     */
    private fun decode(bitmap: Bitmap, orientation: Int): Pair<Mat, Mat?> {
        val rgba = Mat()
        Utils.bitmapToMat(bitmap, rgba, false)
        orient(rgba, orientation)
        val rgb = Mat()
        Imgproc.cvtColor(rgba, rgb, Imgproc.COLOR_RGBA2RGB)
        var alpha: Mat? = null
        if (bitmap.hasAlpha()) {
            val a = Mat()
            Core.extractChannel(rgba, a, 3)
            if (Core.minMaxLoc(a).minVal < 255.0) alpha = a else a.release()
        }
        rgba.release()
        return rgb to alpha
    }

    /** The stored pixels turned into display orientation (EXIF values 2 to 8). */
    fun orient(m: Mat, orientation: Int) {
        when (orientation) {
            2 -> Core.flip(m, m, 1)
            3 -> Core.rotate(m, m, Core.ROTATE_180)
            4 -> Core.flip(m, m, 0)
            5 -> Core.transpose(m, m)
            6 -> Core.rotate(m, m, Core.ROTATE_90_CLOCKWISE)
            7 -> {
                Core.transpose(m, m)
                Core.flip(m, m, -1)
            }
            8 -> Core.rotate(m, m, Core.ROTATE_90_COUNTERCLOCKWISE)
        }
    }

    /** JPEG has no transparency: flatten on white, like most viewers show it (float32, as Python). */
    private fun flattenOnWhite(rgb: Mat, alpha: Mat) {
        val n = rgb.rows() * rgb.cols()
        val px = ByteArray(n * 3)
        val a = ByteArray(n)
        rgb.get(0, 0, px)
        alpha.get(0, 0, a)
        for (i in 0 until n) {
            val f = (a[i].toInt() and 0xFF).toFloat() / 255f
            for (c in 0 until 3) {
                val v = (px[i * 3 + c].toInt() and 0xFF).toFloat() * f + 255f * (1f - f) + 0.5f
                px[i * 3 + c] = minOf(255, v.toInt()).toByte()
            }
        }
        rgb.put(0, 0, px)
    }

    /** The same names as image_io._metadata_found, read from the file's own structure. */
    private fun metadataFound(data: ByteArray, format: String): Containers.Found = when (format) {
        "JPEG" -> Containers.jpegMetadata(data)
        "PNG" -> Containers.pngMetadata(data)
        "WEBP" -> Containers.webpMetadata(data)
        else -> {
            // The Exif item of a HEIF is found through iloc: ExifInterface reads it.
            val f = Containers.heifMetadata(data)
            val names = f.names.toMutableSet()
            if ("exif" in names && heifHasGps(data)) names += "gps"
            Containers.Found(names, 1)
        }
    }

    private val gpsTags = listOf(
        ExifInterface.TAG_GPS_VERSION_ID, ExifInterface.TAG_GPS_LATITUDE, ExifInterface.TAG_GPS_LONGITUDE,
        ExifInterface.TAG_GPS_ALTITUDE, ExifInterface.TAG_GPS_TIMESTAMP, ExifInterface.TAG_GPS_DATESTAMP,
        ExifInterface.TAG_GPS_IMG_DIRECTION, ExifInterface.TAG_GPS_SPEED, ExifInterface.TAG_GPS_PROCESSING_METHOD,
        ExifInterface.TAG_GPS_AREA_INFORMATION, ExifInterface.TAG_GPS_MAP_DATUM,
    )

    private fun heifHasGps(data: ByteArray): Boolean = try {
        val exif = ExifInterface(ByteArrayInputStream(data))
        gpsTags.any { exif.getAttribute(it) != null }
    } catch (e: Exception) {
        false
    }

    /** Pixels as a new 8-bit Mat of the same shape (for tests and the app). */
    fun copyOf(m: Mat): Mat = Mat(m.rows(), m.cols(), m.type()).also { m.copyTo(it) }

}
