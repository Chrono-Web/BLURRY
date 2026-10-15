package com.chronocol.blurry.engine

import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/** PIANO_BLURRY 6a: the Android engine against the Python engine, as BlurryKit's (a)-(c). */
@RunWith(AndroidJUnit4::class)
class ParityTest {
    private val levels = Reference.levels

    /** (a) On the pixels the engine decoded: identical boxes and scores, identical plans and flags at every level. */
    @Test
    fun detectionIdenticalOnEnginePixels() {
        val fixtures = Reference.fixtures()
        assertTrue(fixtures.isNotEmpty())
        for ((name, ref) in fixtures) {
            val img = Reference.load(ref.getString("decoded"))
            val boxes = Reference.detector.detectRGB(img.rgb)
            assertSame(boxes, Reference.boxes(ref.getJSONArray("boxes")), name)
            val plan = ImagePlan(img.width, img.height, boxes.toMutableList())
            for (level in levels.levels) {
                val at = Review.imagePlan(plan, level.confidence, levels)
                val refPlan = ref.getJSONObject("plans").getJSONObject(level.name)
                assertSame(at.boxes, Reference.boxes(refPlan.getJSONArray("boxes")), "$name ${level.name}")
                assertEquals("$name ${level.name}", Reference.flags(refPlan.getJSONArray("flags")), at.flags)
            }
            img.release()
        }
    }

    /**
     * (b) From the original file, read by Android instead of Pillow: format,
     * metadata found, pixels within decoder noise, the same faces with IoU >= 0.9.
     */
    @Test
    fun endToEndFromOriginalFile() {
        for ((name, ref) in Reference.fixtures()) {
            val job = Engine.analyzeImage(
                Reference.bytes(name), name.substringAfterLast('.'),
                Settings.defaults(levels).copy(level = levels.mostSensitive), Reference.detector, levels,
            )
            val loaded = job.loaded
            assertEquals(name, ref.getInt("width"), loaded.width)
            assertEquals(name, ref.getInt("height"), loaded.height)
            assertEquals(name, ref.getString("out_format"), loaded.outFormat.id)
            assertEquals(name, Reference.strings(ref.getJSONArray("metadata_found")), loaded.metadataFound)

            val engine = Reference.load(ref.getString("decoded"))
            val d = Pixels.diff(loaded.rgb, engine.rgb)
            assertTrue("$name: decoded pixels differ by ${d.mean} on average", d.mean <= Pixels.DECODER_NOISE)

            val m = match(Reference.boxes(ref.getJSONArray("boxes")), job.plan.boxes)
            assertTrue("$name: missing ${m.missing}, extra ${m.extra}", m.missing.isEmpty() && m.extra.isEmpty())
            assertTrue("$name: min IoU ${m.minIoU}", m.minIoU >= 0.9)
            Log.i("BlurryParity", "%s: pixels Δ mean %.2f max %d, min IoU %.3f".format(name, d.mean, d.max, m.minIoU))
            engine.release()
            loaded.release()
        }
    }

    /** (c) On the same pixels and boxes, both cover modes identical to the byte to redact.py. */
    @Test
    fun redactionIdenticalToEngine() {
        for ((name, ref) in Reference.fixtures()) {
            val boxes = Reference.boxes(ref.getJSONArray("boxes"))
            val renders = ref.getJSONObject("renders")
            for (mode in CoverMode.entries) {
                val img = Reference.load(ref.getString("decoded"))
                Redact.apply(img.rgb, boxes, mode, ref.getDouble("padding"), ref.getInt("blocks"))
                val expected = Reference.load(renders.getString(mode.id))
                val d = Pixels.diff(img.rgb, expected.rgb)
                assertEquals("$name ${mode.id}: bytes that differ", 0, d.count)
                img.release()
                expected.release()
            }
        }
    }
}
