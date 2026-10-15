package com.chronocol.blurry.engine

import android.content.res.AssetManager
import org.opencv.core.Mat
import org.opencv.core.MatOfByte
import org.opencv.core.Size
import org.opencv.imgproc.Imgproc
import org.opencv.objdetect.FaceDetectorYN

/** YuNet through OpenCV's FaceDetectorYN, with the parameters of detect.py. */
class Detector(model: ByteArray, val confidence: Double, nms: Double, topK: Int) {
    companion object {
        /** At the most sensitive level: the others filter its scores (Review.imagePlan). */
        fun create(assets: AssetManager, levels: Levels, level: String = levels.mostSensitive): Detector =
            Detector(Model.loadVerified(assets), levels.get(level).confidence, levels.yunetNms, levels.yunetTopk)
    }

    private val net = FaceDetectorYN.create(
        "onnx",
        MatOfByte(*Model.verified(model)),
        MatOfByte(),
        Size(320.0, 320.0),
        confidence.toFloat(),
        nms.toFloat(),
        topK,
    )
    private var size: Pair<Int, Int>? = null

    /** Faces in an RGB 8-bit image, as the engine converts it for detect.py. */
    fun detectRGB(rgb: Mat): List<Box> {
        val bgr = Mat()
        Imgproc.cvtColor(rgb, bgr, Imgproc.COLOR_RGB2BGR)
        return detect(bgr).also { bgr.release() }
    }

    /** Faces in a BGR 8-bit image, clipped to the image. */
    fun detect(bgr: Mat): List<Box> {
        val w = bgr.cols()
        val h = bgr.rows()
        if (size != w to h) {
            net.inputSize = Size(w.toDouble(), h.toDouble())
            size = w to h
        }
        val faces = Mat()
        net.detect(bgr, faces)
        val boxes = ArrayList<Box>()
        val row = FloatArray(faces.cols())
        for (i in 0 until faces.rows()) {
            faces.get(i, 0, row)
            // int() in Python truncates toward zero, as toInt() does.
            var x = row[0].toInt()
            var y = row[1].toInt()
            var bw = row[2].toInt()
            var bh = row[3].toInt()
            // YuNet can return boxes that go past the frame edges.
            x = maxOf(0, x)
            y = maxOf(0, y)
            bw = minOf(w - x, bw)
            bh = minOf(h - y, bh)
            if (bw > 0 && bh > 0) boxes += Box(x, y, bw, bh, row[row.size - 1].toDouble())
        }
        faces.release()
        return boxes
    }
}
