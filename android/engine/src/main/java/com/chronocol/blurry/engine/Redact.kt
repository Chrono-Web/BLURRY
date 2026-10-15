package com.chronocol.blurry.engine

import org.opencv.core.Mat
import org.opencv.core.Rect
import org.opencv.core.Scalar
import org.opencv.core.Size
import org.opencv.imgproc.Imgproc

/** Cover regions: solid black or pixelation, as redact.py. */
object Redact {
    /** (x0, y0, x1, y1) grown by `padding` x long side on every side, clipped. */
    fun paddedRect(box: Box, padding: Double, width: Int, height: Int): IntArray {
        val pad = (box.longSide * padding).toInt()
        return intArrayOf(
            maxOf(0, box.x - pad),
            maxOf(0, box.y - pad),
            minOf(width, box.x + box.w + pad),
            minOf(height, box.y + box.h + pad),
        )
    }

    /** A fixed number of blocks on the long side; INTER_AREA down, INTER_NEAREST up. */
    fun pixelate(roi: Mat, blocks: Int) {
        val w = roi.cols()
        val h = roi.rows()
        // Python's round() rounds half to even; Math.rint does the same.
        val blockPx = maxOf(1, Math.rint(maxOf(w, h).toDouble() / maxOf(2, blocks)).toInt())
        val small = Mat()
        Imgproc.resize(
            roi, small,
            Size(maxOf(1, w / blockPx).toDouble(), maxOf(1, h / blockPx).toDouble()),
            0.0, 0.0, Imgproc.INTER_AREA,
        )
        val big = Mat()
        Imgproc.resize(small, big, Size(w.toDouble(), h.toDouble()), 0.0, 0.0, Imgproc.INTER_NEAREST)
        big.copyTo(roi)
        small.release()
        big.release()
    }

    /**
     * Cover `boxes` in place on an 8-bit image (any channel order). If an alpha
     * plane is given, covered areas become fully opaque, so that a transparent
     * region cannot hide the outline of a face.
     */
    fun apply(image: Mat, boxes: List<Box>, mode: CoverMode, padding: Double, blocks: Int, alpha: Mat? = null) {
        for (box in boxes) {
            val (x0, y0, x1, y1) = paddedRect(box, padding, image.cols(), image.rows()).toList()
            if (x1 <= x0 || y1 <= y0) continue
            val roi = image.submat(Rect(x0, y0, x1 - x0, y1 - y0))
            when (mode) {
                CoverMode.SOLID -> roi.setTo(Scalar.all(0.0))
                CoverMode.PIXEL -> pixelate(roi, blocks)
            }
            roi.release()
            if (alpha != null) {
                val a = alpha.submat(Rect(x0, y0, x1 - x0, y1 - y0))
                a.setTo(Scalar.all(255.0))
                a.release()
            }
        }
    }
}
