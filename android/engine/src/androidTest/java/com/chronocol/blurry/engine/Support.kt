package com.chronocol.blurry.engine

import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.opencv.android.OpenCVLoader
import org.opencv.core.Core
import org.opencv.core.Mat
import kotlin.math.abs

/** What the Python engine did, written by scripts/coreml/riferimento.py into build/parity. */
object Reference {
    init {
        check(OpenCVLoader.initLocal()) { "OpenCV did not load" }
    }

    private val instrumentation = InstrumentationRegistry.getInstrumentation()

    /** The test APK's assets: build/parity and tests/fixtures/public. */
    val assets = instrumentation.context.assets

    /** The engine's own assets: model and levels. */
    val engineAssets = instrumentation.targetContext.assets

    val levels: Levels by lazy { Levels.load(engineAssets) }
    val detector: Detector by lazy { Detector.create(engineAssets, levels) }

    private val json: JSONObject by lazy {
        JSONObject(assets.open("reference.json").use { String(it.readBytes()) })
    }

    private fun section(name: String): List<Pair<String, JSONObject>> {
        val s = json.getJSONObject(name)
        return s.keys().asSequence().sorted().map { it to s.getJSONObject(it) }.toList()
    }

    fun fixtures() = section("fixtures")
    fun extra() = section("extra")

    fun bytes(path: String): ByteArray = assets.open(path).use { it.readBytes() }

    /** A file of build/parity, read by the engine. */
    fun load(path: String): LoadedImage = ImageIn.load(bytes(path), path.substringAfterLast('.'))

    /** [[x, y, w, h, score]] -> boxes. */
    fun boxes(arr: JSONArray): List<Box> = (0 until arr.length()).map { arr.getJSONArray(it) }.map {
        Box(it.getInt(0), it.getInt(1), it.getInt(2), it.getInt(3), if (it.isNull(4)) null else it.getDouble(4))
    }

    fun flags(arr: JSONArray): List<Flag> = (0 until arr.length()).map { arr.getJSONObject(it) }.map {
        fun opt(k: String) = if (it.has(k)) it.getInt(k) else null
        Flag(Flag.Kind.of(it.getString("kind")), opt("frame"), opt("track"), opt("box"))
    }

    fun strings(arr: JSONArray): List<String> = (0 until arr.length()).map { arr.getString(it) }
}

object Pixels {
    /**
     * Mean difference allowed between two decoders (Android's and Pillow's),
     * as in BlurryKit. A wrong orientation, profile or channel order gives tens of levels.
     */
    const val DECODER_NOISE = 3.0

    class Diff(val mean: Double, val max: Int, val count: Int)

    /** Mean and max absolute difference over all bytes (optionally where `mask` is 255). */
    fun diff(a: Mat, b: Mat, mask: Mat? = null): Diff {
        assertEquals(a.size(), b.size())
        val d = Mat()
        Core.absdiff(a, b, d)
        val flat = d.reshape(1, d.rows())
        val m = if (mask != null) {
            val mask3 = Mat()
            Core.merge(listOf(mask, mask, mask), mask3)
            mask3.reshape(1, mask3.rows())
        } else null
        val mean = if (m != null) Core.mean(flat, m).`val`[0] else Core.mean(flat).`val`[0]
        val max = if (m != null) Core.minMaxLoc(flat, m).maxVal else Core.minMaxLoc(flat).maxVal
        val count = Core.countNonZero(flat)
        return Diff(mean, max.toInt(), count)
    }
}

/** Greedy IoU matching, as scripts/coreml/compare.py. */
class Match(val missing: List<Box>, val extra: List<Box>, val minIoU: Double)

fun match(ref: List<Box>, got: List<Box>): Match {
    val used = HashSet<Int>()
    val missing = ArrayList<Box>()
    var minIoU = 1.0
    for (r in ref) {
        var best = 0.0
        var bi = -1
        got.forEachIndexed { i, g ->
            if (i in used) return@forEachIndexed
            val v = r.iou(g)
            if (v > best) {
                best = v
                bi = i
            }
        }
        if (bi < 0 || best < 0.5) {
            missing += r
            continue
        }
        used += bi
        minIoU = minOf(minIoU, best)
    }
    return Match(missing, got.filterIndexed { i, _ -> i !in used }, minIoU)
}

/** Identical boxes and identical scores: the same OpenCV runs the same model. */
fun assertSame(got: List<Box>, ref: List<Box>, what: String) {
    assertEquals("$what: number of faces", ref.size, got.size)
    for ((g, r) in got.zip(ref)) {
        assertEquals(what, listOf(r.x, r.y, r.w, r.h), listOf(g.x, g.y, g.w, g.h))
        assertTrue("$what: score ${g.score} vs ${r.score}", abs((g.score ?: -1.0) - (r.score ?: -1.0)) == 0.0)
    }
}
