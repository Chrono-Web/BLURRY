package com.chronocol.blurry.engine

import android.graphics.Bitmap
import android.graphics.ColorSpace
import org.opencv.android.Utils
import org.opencv.core.Core
import org.opencv.core.Mat
import org.opencv.imgproc.Imgproc
import java.io.ByteArrayOutputStream

/**
 * Clean writing as image_io.encode: the pixels only. Bitmap.compress encodes,
 * then Containers keeps only what is needed to show the image (see there why).
 */
object ImageOut {
    class EncodeError(message: String) : Exception(message)

    fun encode(rgb: Mat, alpha: Mat?, format: OutFormat): ByteArray {
        val withAlpha = alpha != null && format == OutFormat.PNG
        val rgba = Mat()
        if (withAlpha) {
            val planes = ArrayList<Mat>()
            Core.split(rgb, planes)
            Core.merge(planes + alpha!!, rgba)
            planes.forEach { it.release() }
        } else {
            Imgproc.cvtColor(rgb, rgba, Imgproc.COLOR_RGB2RGBA)
        }
        val bitmap = Bitmap.createBitmap(
            rgb.cols(), rgb.rows(), Bitmap.Config.ARGB_8888, withAlpha, ColorSpace.get(ColorSpace.Named.SRGB),
        )
        // Straight alpha, as the Python engine writes it: the colour under a
        // transparent pixel is kept, not multiplied away.
        if (withAlpha) bitmap.isPremultiplied = false
        Utils.matToBitmap(rgba, bitmap, false)
        rgba.release()

        val out = ByteArrayOutputStream()
        val ok = when (format) {
            OutFormat.JPEG -> bitmap.compress(Bitmap.CompressFormat.JPEG, 95, out)
            OutFormat.PNG -> bitmap.compress(Bitmap.CompressFormat.PNG, 100, out)
        }
        bitmap.recycle()
        if (!ok) throw EncodeError("cannot encode ${format.id}")
        val encoded = out.toByteArray()
        val clean = when (format) {
            OutFormat.JPEG -> Containers.cleanJPEG(encoded)
            OutFormat.PNG -> Containers.cleanPNG(encoded)
        }
        if (!Containers.isClean(clean)) throw EncodeError("the output still holds metadata")
        return clean
    }
}
