package com.chronocol.blurry.engine

/**
 * The structure of JPEG, PNG, WebP and HEIF files, at the level of segments,
 * chunks and boxes: what metadata an input carries, and an allowlist filter
 * for outputs. Ported from BlurryKit's Containers.swift.
 *
 * Bitmap.compress writes an sRGB ICC profile into every JPEG, and sRGB/sBIT
 * chunks into every PNG (phase 6.0). Nothing personal, but R3 means the file
 * holds only what we chose: outputs keep only the segments and chunks needed
 * to show the pixels, and `isClean` checks it again before anything is written.
 */
object Containers {
    class ContainerError(message: String) : Exception(message)

    private fun u8(d: ByteArray, i: Int) = d[i].toInt() and 0xFF
    private fun be16(d: ByteArray, i: Int) = (u8(d, i) shl 8) or u8(d, i + 1)
    private fun be32(d: ByteArray, i: Int) = (be16(d, i).toLong() shl 16) or be16(d, i + 2).toLong()
    private fun le32(d: ByteArray, i: Int) =
        u8(d, i).toLong() or (u8(d, i + 1).toLong() shl 8) or (u8(d, i + 2).toLong() shl 16) or (u8(d, i + 3).toLong() shl 24)
    private fun ascii(d: ByteArray, from: Int, to: Int) = String(d, from, to - from, Charsets.ISO_8859_1)
    private fun startsWith(d: ByteArray, at: Int, end: Int, prefix: String): Boolean {
        val p = prefix.toByteArray(Charsets.ISO_8859_1)
        if (at + p.size > end) return false
        for (k in p.indices) if (d[at + k] != p[k]) return false
        return true
    }

    // JPEG

    /** A segment: [start, end) with the marker, payload after the length field. */
    class Segment(val marker: Int, val start: Int, val end: Int, val payloadStart: Int, val payloadEnd: Int)

    fun isJPEG(d: ByteArray) = d.size >= 3 && u8(d, 0) == 0xFF && u8(d, 1) == 0xD8 && u8(d, 2) == 0xFF

    fun jpegSegments(d: ByteArray): List<Segment> {
        if (!isJPEG(d)) throw ContainerError("not a JPEG")
        val segs = arrayListOf(Segment(0xD8, 0, 2, 2, 2))
        var i = 2
        while (i < d.size) {
            if (u8(d, i) != 0xFF) throw ContainerError("JPEG: expected a marker")
            val start = i
            while (i < d.size && u8(d, i) == 0xFF) i++ // fill bytes
            if (i >= d.size) break
            val m = u8(d, i)
            i++
            if (m == 0xD9) {
                segs += Segment(m, start, i, i, i)
                return segs
            }
            if (m in 0xD0..0xD7 || m == 0x01) {
                segs += Segment(m, start, i, i, i)
                continue
            }
            if (i + 2 > d.size) throw ContainerError("JPEG: truncated")
            val len = be16(d, i)
            if (len < 2 || i + len > d.size) throw ContainerError("JPEG: bad length")
            var end = i + len
            val payloadStart = i + 2
            val payloadEnd = end
            if (m == 0xDA) {
                // Entropy-coded data runs to the next marker that is not a
                // stuffed byte (FF 00) or a restart marker.
                while (end + 1 < d.size) {
                    val next = u8(d, end + 1)
                    if (u8(d, end) == 0xFF && next != 0 && next !in 0xD0..0xD7) break
                    end++
                }
                if (end + 1 >= d.size) end = d.size
            }
            segs += Segment(m, start, end, payloadStart, payloadEnd)
            i = end
        }
        throw ContainerError("JPEG: no end of image")
    }

    /** Markers needed to decode the image: SOI, EOI, tables, frame and scan headers. */
    private fun jpegNeeded(m: Int): Boolean = when (m) {
        0xD8, 0xD9, 0xDB, 0xC4, 0xCC, 0xDD, 0xDA, 0x01, in 0xD0..0xD7 -> true
        in 0xC0..0xCF -> m != 0xC8 // SOFn (C4 DHT, CC DAC above; C8 is reserved)
        else -> false
    }

    private fun isJFIF(d: ByteArray, s: Segment) = s.marker == 0xE0 && startsWith(d, s.payloadStart, s.payloadEnd, "JFIF\u0000")

    /**
     * Keep what decodes the image and the JFIF header; drop APPn and COM.
     * Any other marker is unexpected in a file the encoder just wrote: refuse.
     */
    fun cleanJPEG(d: ByteArray): ByteArray {
        val out = java.io.ByteArrayOutputStream(d.size)
        for (s in jpegSegments(d)) {
            when {
                jpegNeeded(s.marker) || isJFIF(d, s) -> out.write(d, s.start, s.end - s.start)
                s.marker in 0xE0..0xEF || s.marker == 0xFE -> Unit
                else -> throw ContainerError("JPEG: unexpected marker %02X".format(s.marker))
            }
        }
        return out.toByteArray()
    }

    // PNG

    class Chunk(val type: String, val start: Int, val end: Int, val dataStart: Int, val dataEnd: Int)

    private val pngSignature = byteArrayOf(0x89.toByte(), 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A)

    fun isPNG(d: ByteArray) = d.size >= 8 && (0 until 8).all { d[it] == pngSignature[it] }

    fun pngChunks(d: ByteArray): List<Chunk> {
        if (!isPNG(d)) throw ContainerError("not a PNG")
        val chunks = ArrayList<Chunk>()
        var i = 8
        while (i + 12 <= d.size) {
            val len = be32(d, i)
            if (len < 0 || i + 12 + len > d.size) throw ContainerError("PNG: bad length")
            val n = len.toInt()
            val type = ascii(d, i + 4, i + 8)
            chunks += Chunk(type, i, i + 12 + n, i + 8, i + 8 + n)
            i += 12 + n
            if (type == "IEND") return chunks
        }
        throw ContainerError("PNG: no IEND")
    }

    private val pngKept = setOf("IHDR", "PLTE", "tRNS", "IDAT", "IEND")

    /**
     * Keep the critical chunks and transparency; drop every other ancillary
     * chunk (text, eXIf, iCCP, sRGB, sBIT, gAMA, pHYs, tIME...). An unknown
     * critical chunk is unexpected: refuse.
     */
    fun cleanPNG(d: ByteArray): ByteArray {
        val out = java.io.ByteArrayOutputStream(d.size)
        out.write(pngSignature)
        for (c in pngChunks(d)) {
            when {
                c.type in pngKept -> out.write(d, c.start, c.end - c.start)
                !c.type[0].isLowerCase() -> throw ContainerError("PNG: unexpected critical chunk ${c.type}")
            }
        }
        return out.toByteArray()
    }

    /** Whether a PNG is animated (APNG): an acTL chunk. */
    fun pngIsAnimated(d: ByteArray): Boolean =
        runCatching { pngChunks(d).any { it.type == "acTL" } }.getOrDefault(false)

    /** The final check before writing: only allowed segments or chunks remain. */
    fun isClean(d: ByteArray): Boolean {
        if (isJPEG(d)) {
            val segs = runCatching { jpegSegments(d) }.getOrNull() ?: return false
            return segs.all { jpegNeeded(it.marker) || isJFIF(d, it) }
        }
        if (isPNG(d)) {
            val chunks = runCatching { pngChunks(d) }.getOrNull() ?: return false
            return chunks.all { it.type in pngKept }
        }
        return false
    }

    // EXIF (TIFF structure)

    /** What a TIFF-structured EXIF block holds, as Pillow's getexif reads it. */
    class Exif(val orientation: Int?, val hasGps: Boolean, val hasThumbnailIFD: Boolean)

    /** Reads IFD0 (orientation, GPS pointer), the GPS IFD and IFD1. Accepts an "Exif\0\0" prefix. */
    fun exif(d: ByteArray, from: Int, to: Int): Exif? {
        var s = from
        if (startsWith(d, s, to, "Exif\u0000\u0000")) s += 6
        if (to - s < 8) return null
        val little = u8(d, s) == 0x49 && u8(d, s + 1) == 0x49
        if (!little && !(u8(d, s) == 0x4D && u8(d, s + 1) == 0x4D)) return null
        fun u16(off: Long): Int? {
            val i = s + off
            if (off < 0 || i + 2 > to) return null
            val a = u8(d, i.toInt())
            val b = u8(d, i.toInt() + 1)
            return if (little) a or (b shl 8) else (a shl 8) or b
        }
        fun u32(off: Long): Long? {
            val a = u16(off) ?: return null
            val b = u16(off + 2) ?: return null
            return if (little) a.toLong() or (b.toLong() shl 16) else (a.toLong() shl 16) or b.toLong()
        }
        val ifd0 = u32(4) ?: return null
        val n0 = u16(ifd0) ?: return null
        var orientation: Int? = null
        var gpsIfd: Long? = null
        for (k in 0 until n0) {
            val e = ifd0 + 2 + 12L * k
            when (u16(e)) {
                0x0112 -> orientation = u16(e + 8)
                0x8825 -> gpsIfd = u32(e + 8)
            }
        }
        val hasGps = gpsIfd?.let { (u16(it) ?: 0) > 0 } ?: false
        val ifd1 = u32(ifd0 + 2 + 12L * n0)
        val hasThumb = ifd1 != null && ifd1 != 0L && (u16(ifd1) ?: 0) > 0
        return Exif(orientation, hasGps, hasThumb)
    }

    /** Metadata found in an input, with the names of image_io._metadata_found. */
    class Found(val names: Set<String>, val orientation: Int)

    private fun withExif(found: MutableSet<String>, ex: Exif?): Int {
        found += "exif"
        if (ex == null) return 1
        if (ex.hasGps) found += "gps"
        if (ex.hasThumbnailIFD) found += "exif_thumbnail"
        val o = ex.orientation ?: 1
        if (o != 1) found += "orientation"
        return o
    }

    fun jpegMetadata(d: ByteArray): Found {
        val found = HashSet<String>()
        var orientation = 1
        val segs = runCatching { jpegSegments(d) }.getOrNull() ?: return Found(found, 1)
        for (s in segs) {
            val p = s.payloadStart
            val e = s.payloadEnd
            when {
                s.marker == 0xE1 && startsWith(d, p, e, "Exif\u0000") ->
                    orientation = withExif(found, exif(d, p, e))
                s.marker == 0xE1 && startsWith(d, p, e, "http://ns.adobe.com/xap/1.0/\u0000") -> found += "xmp"
                s.marker == 0xED -> found += "iptc"
                s.marker == 0xE2 && startsWith(d, p, e, "ICC_PROFILE\u0000") -> found += "icc_profile"
                s.marker == 0xFE -> found += "comment"
            }
        }
        return Found(found, orientation)
    }

    fun pngMetadata(d: ByteArray): Found {
        val found = HashSet<String>()
        var orientation = 1
        val chunks = runCatching { pngChunks(d) }.getOrNull() ?: return Found(found, 1)
        for (c in chunks) {
            when (c.type) {
                "eXIf" -> orientation = withExif(found, exif(d, c.dataStart, c.dataEnd))
                "iCCP" -> found += "icc_profile"
                "tEXt", "zTXt", "iTXt" -> {
                    found += "text_chunks"
                    if (startsWith(d, c.dataStart, c.dataEnd, "XML:com.adobe.xmp\u0000")) found += "xmp"
                }
            }
        }
        return Found(found, orientation)
    }

    fun isWebP(d: ByteArray) = d.size >= 12 && ascii(d, 0, 4) == "RIFF" && ascii(d, 8, 12) == "WEBP"

    /** RIFF chunks of a WebP file: fourcc, data start, data end. */
    private fun webpChunks(d: ByteArray): List<Triple<String, Int, Int>> {
        val out = ArrayList<Triple<String, Int, Int>>()
        if (!isWebP(d)) return out
        var i = 12
        while (i + 8 <= d.size) {
            val len = le32(d, i + 4)
            val start = i + 8
            val end = minOf(d.size.toLong(), start + len).toInt()
            out += Triple(ascii(d, i, i + 4), start, end)
            i = (start + len + (len and 1)).coerceAtMost(Int.MAX_VALUE.toLong()).toInt()
        }
        return out
    }

    fun webpIsAnimated(d: ByteArray): Boolean = webpChunks(d).any { (cc, s, e) ->
        cc == "ANIM" || (cc == "VP8X" && e > s && (u8(d, s) and 0x02) != 0)
    }

    fun webpMetadata(d: ByteArray): Found {
        val found = HashSet<String>()
        var orientation = 1
        for ((cc, s, e) in webpChunks(d)) {
            when (cc) {
                "EXIF" -> orientation = withExif(found, exif(d, s, e))
                "XMP " -> found += "xmp"
                "ICCP" -> found += "icc_profile"
            }
        }
        return Found(found, orientation)
    }

    // HEIF (ISO BMFF)

    class BMFFBox(val type: String, val bodyStart: Int, val bodyEnd: Int)

    fun bmffBoxes(d: ByteArray, from: Int, to: Int): List<BMFFBox> {
        val boxes = ArrayList<BMFFBox>()
        var i = from
        while (i + 8 <= to) {
            var size = be32(d, i)
            val type = ascii(d, i + 4, i + 8)
            var header = 8
            if (size == 1L) {
                if (i + 16 > to) break
                size = (be32(d, i + 8) shl 32) or be32(d, i + 12)
                header = 16
            } else if (size == 0L) {
                size = (to - i).toLong()
            }
            if (size < header || i + size > to) break
            boxes += BMFFBox(type, i + header, (i + size).toInt())
            i = (i + size).toInt()
        }
        return boxes
    }

    fun isHEIF(d: ByteArray): Boolean {
        if (d.size < 12 || ascii(d, 4, 8) != "ftyp") return false
        val brands = setOf("heic", "heix", "heim", "heis", "hevc", "hevx", "mif1", "msf1", "avif")
        val ftyp = bmffBoxes(d, 0, d.size).firstOrNull() ?: return false
        if (ascii(d, ftyp.bodyStart, ftyp.bodyStart + 4) in brands) return true
        var i = ftyp.bodyStart + 8
        while (i + 4 <= ftyp.bodyEnd) {
            if (ascii(d, i, i + 4) in brands) return true
            i += 4
        }
        return false
    }

    private fun cString(d: ByteArray, at: Int, end: Int): Pair<String, Int> {
        var i = at
        while (i < end && d[i] != 0.toByte()) i++
        return ascii(d, at, i) to i + 1
    }

    /** URNs of auxiliary images that hold depth (what libheif counts as a depth image). */
    private val depthURNs = setOf("urn:mpeg:hevc:2015:auxid:2", "urn:mpeg:mpegB:cicp:systems:auxiliary:depth")

    /**
     * Exif and XMP items, colour profiles, thumbnails and depth images in the
     * meta box. GPS comes from the Exif item, read by the caller.
     */
    fun heifMetadata(d: ByteArray): Found {
        val found = HashSet<String>()
        val meta = bmffBoxes(d, 0, d.size).firstOrNull { it.type == "meta" }
        if (meta == null || meta.bodyEnd - meta.bodyStart <= 4) return Found(found, 1)
        for (box in bmffBoxes(d, meta.bodyStart + 4, meta.bodyEnd)) { // FullBox
            when (box.type) {
                "iinf" -> {
                    if (box.bodyEnd - box.bodyStart <= 6) continue
                    val version = u8(d, box.bodyStart)
                    val first = box.bodyStart + 4 + if (version == 0) 2 else 4
                    for (infe in bmffBoxes(d, first, box.bodyEnd)) {
                        if (infe.type != "infe") continue
                        val v = u8(d, infe.bodyStart)
                        if (v < 2) continue
                        var i = infe.bodyStart + 4 + (if (v == 2) 2 else 4) + 2
                        if (i + 4 > infe.bodyEnd) continue
                        val itemType = ascii(d, i, i + 4)
                        i += 4
                        i = cString(d, i, infe.bodyEnd).second // item name
                        if (itemType == "Exif") found += "exif"
                        if (itemType == "mime" && cString(d, i, infe.bodyEnd).first == "application/rdf+xml") {
                            found += "xmp"
                        }
                    }
                }
                "iprp" -> for (ipco in bmffBoxes(d, box.bodyStart, box.bodyEnd)) {
                    if (ipco.type != "ipco") continue
                    for (p in bmffBoxes(d, ipco.bodyStart, ipco.bodyEnd)) {
                        if (p.type == "colr" && p.bodyEnd - p.bodyStart >= 4) {
                            val kind = ascii(d, p.bodyStart, p.bodyStart + 4)
                            if (kind == "prof" || kind == "rICC") found += "icc_profile"
                        }
                        if (p.type == "auxC" && p.bodyEnd - p.bodyStart > 4) {
                            if (cString(d, p.bodyStart + 4, p.bodyEnd).first in depthURNs) found += "depth_map"
                        }
                    }
                }
                "iref" -> if (bmffBoxes(d, box.bodyStart + 4, box.bodyEnd).any { it.type == "thmb" }) {
                    found += "embedded_thumbnails"
                }
            }
        }
        return Found(found, 1)
    }
}
