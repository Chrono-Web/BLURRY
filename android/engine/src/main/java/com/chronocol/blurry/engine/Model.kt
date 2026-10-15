package com.chronocol.blurry.engine

import android.content.res.AssetManager
import java.security.MessageDigest

/** YuNet, the same ONNX file as the Python engine (src/blurry_opsec/model). */
object Model {
    const val FILENAME = "face_detection_yunet_2023mar.onnx"
    const val SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"

    class IntegrityError(message: String) : RuntimeException(message)

    /** The model bytes, checked before use: no fallback detector (R5). */
    fun loadVerified(assets: AssetManager): ByteArray {
        val data = try {
            assets.open(FILENAME).use { it.readBytes() }
        } catch (e: java.io.IOException) {
            throw IntegrityError("the face detection model is missing; reinstall Blurry")
        }
        return verified(data)
    }

    fun verified(data: ByteArray): ByteArray {
        val digest = MessageDigest.getInstance("SHA-256").digest(data)
            .joinToString("") { "%02x".format(it) }
        if (digest != SHA256) {
            throw IntegrityError(
                "the face detection model does not match the expected SHA-256; " +
                    "reinstall Blurry from a verified download",
            )
        }
        return data
    }
}
