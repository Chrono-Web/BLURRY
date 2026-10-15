package com.chronocol.blurry.engine

import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/** PIANO_BLURRY 6a, as BlurryKit's test (d) and the R3/R5/R6 rules on images. */
@RunWith(AndroidJUnit4::class)
class ImageTest {
    init {
        Reference.levels // loads OpenCV
    }

    /** Reading the extra files (orientation, colour profiles, alpha, refusals) gives what image_io.load gives. */
    @Test
    fun readingLikeEngine() {
        val extra = Reference.extra()
        assertTrue(extra.isNotEmpty())
        for ((name, ref) in extra) {
            val bytes = Reference.bytes("extra/$name")
            val ext = name.substringAfterLast('.')
            if (ref.has("error")) {
                val e = assertThrows(name, InputError::class.java) { ImageIn.load(bytes, ext) }
                assertEquals(name, ref.getString("error"), e.message)
                continue
            }
            val loaded = ImageIn.load(bytes, ext)
            assertEquals(name, ref.getInt("width"), loaded.width)
            assertEquals(name, ref.getInt("height"), loaded.height)
            assertEquals(name, ref.getString("out_format"), loaded.outFormat.id)
            assertEquals(name, ref.getBoolean("has_alpha"), loaded.alpha != null)
            assertEquals(name, Reference.strings(ref.getJSONArray("metadata_found")), loaded.metadataFound)

            val engine = Reference.load(ref.getString("decoded"))
            val a = loaded.alpha
            val b = engine.alpha
            val d = if (a != null && b != null) {
                assertEquals("$name: alpha", 0, Pixels.diff(a, b).count)
                // Under transparent pixels the colour is invisible and may differ.
                val opaque = org.opencv.core.Mat()
                org.opencv.core.Core.compare(a, org.opencv.core.Scalar(255.0), opaque, org.opencv.core.Core.CMP_EQ)
                Pixels.diff(loaded.rgb, engine.rgb, opaque)
            } else {
                Pixels.diff(loaded.rgb, engine.rgb)
            }
            assertTrue("$name: Δ mean ${d.mean}", d.mean <= Pixels.DECODER_NOISE)
            Log.i("BlurryImage", "%s: pixels Δ mean %.2f max %d".format(name, d.mean, d.max))
            loaded.release()
            engine.release()
        }
    }

    /**
     * R3: written files hold the pixels and nothing else, checked by our own
     * parser. They are also left in the app's external files folder, where
     * scripts/android/test-engine.sh pulls them and runs exiftool.
     */
    @Test
    fun outputsHoldNoMetadata() {
        val outDir = File(InstrumentationRegistry.getInstrumentation().targetContext.getExternalFilesDir(null), "outputs")
        outDir.deleteRecursively()
        outDir.mkdirs()
        for (src in listOf("extra/poisoned.jpg", "extra/alpha_text.png", "sts125_gps.heic")) {
            val loaded = ImageIn.load(Reference.bytes(src), src.substringAfterLast('.'))
            val data = ImageOut.encode(loaded.rgb, loaded.alpha, loaded.outFormat)
            assertTrue(src, Containers.isClean(data))
            val name = src.substringAfterLast('/').substringBeforeLast('.')
            File(outDir, "$name.${loaded.outFormat.ext}").writeBytes(data)

            val back = ImageIn.load(data, loaded.outFormat.ext)
            assertEquals(src, emptyList<String>(), back.metadataFound)
            assertEquals(loaded.width, back.width)
            assertEquals(loaded.height, back.height)
            if (loaded.alpha != null) {
                assertEquals("alpha survives in PNG", 0, Pixels.diff(loaded.alpha!!, back.alpha!!).count)
            } else {
                assertNull(back.alpha)
            }
            assertTrue(src, Pixels.diff(back.rgb, loaded.rgb).mean <= 3.0)
            loaded.release()
            back.release()
        }
    }

    /** The allowlist filter on a file full of metadata. */
    @Test
    fun cleanJPEGDropsEveryAppSegment() {
        val bytes = Reference.bytes("extra/poisoned.jpg")
        assertFalse(Containers.isClean(bytes))
        val clean = Containers.cleanJPEG(bytes)
        assertTrue(Containers.isClean(clean))
        assertEquals(emptySet<String>(), Containers.jpegMetadata(clean).names)
        ImageIn.load(clean, "jpg").release()
    }

    @Test
    fun cleanPNGDropsAncillaryChunks() {
        val bytes = Reference.bytes("extra/alpha_text.png")
        assertEquals(setOf("text_chunks"), Containers.pngMetadata(bytes).names)
        val clean = Containers.cleanPNG(bytes)
        assertTrue(Containers.isClean(clean))
        assertEquals(listOf("IHDR", "IEND"), Containers.pngChunks(clean).map { it.type }.filter { it != "IDAT" })
    }

    /** R5: the bundled model has the pinned hash, and any change is refused. */
    @Test
    fun modelHash() {
        val data = Model.loadVerified(Reference.engineAssets)
        val changed = data.copyOf()
        changed[changed.size / 2] = (changed[changed.size / 2].toInt() xor 1).toByte()
        assertThrows(Model.IntegrityError::class.java) { Model.verified(changed) }
    }

    @Test
    fun refusals() {
        val e1 = assertThrows(InputError::class.java) { ImageIn.load("x".toByteArray(), "gif") }
        assertEquals("unsupported image type (accepted: JPEG, PNG, WebP, HEIC)", e1.message)
        val e2 = assertThrows(InputError::class.java) { ImageIn.load(ByteArray(0), "jpg") }
        assertEquals("empty file", e2.message)
    }

    /** Covered areas of a transparent image become opaque, as redact.py. */
    @Test
    fun coverMakesAlphaOpaque() {
        val loaded = Reference.load("extra/alpha_text.png")
        val alpha = loaded.alpha!!
        Redact.apply(loaded.rgb, listOf(Box(0, 0, 40, 40)), CoverMode.SOLID, 0.0, 4, alpha)
        assertEquals(255.0, org.opencv.core.Core.minMaxLoc(alpha.submat(0, 40, 0, 40)).minVal, 0.0)
        loaded.release()
    }
}
