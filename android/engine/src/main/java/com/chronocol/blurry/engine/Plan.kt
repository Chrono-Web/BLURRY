package com.chronocol.blurry.engine

/** A rectangle in display-oriented image coordinates (before padding), as plan.Box. */
data class Box(
    val x: Int,
    val y: Int,
    val w: Int,
    val h: Int,
    val score: Double? = null, // null for manual boxes
    val source: Source = Source.AUTO,
) {
    enum class Source { AUTO, MANUAL }

    val longSide: Int get() = maxOf(w, h)

    fun iou(other: Box): Double {
        val ix = maxOf(0, minOf(x + w, other.x + other.w) - maxOf(x, other.x))
        val iy = maxOf(0, minOf(y + h, other.y + other.h) - maxOf(y, other.y))
        val inter = ix * iy
        val union = w * h + other.w * other.h - inter
        return if (union > 0) inter.toDouble() / union else 0.0
    }

    fun union(other: Box): Box {
        val x0 = minOf(x, other.x)
        val y0 = minOf(y, other.y)
        val x1 = maxOf(x + w, other.x + other.w)
        val y1 = maxOf(y + h, other.y + other.h)
        return Box(x0, y0, x1 - x0, y1 - y0, null, source)
    }
}

/** A review flag, as plan.Flag. */
data class Flag(val kind: Kind, val frame: Int? = null, val track: Int? = null, val box: Int? = null) {
    enum class Kind(val id: String) {
        NO_FACES("no_faces"),
        NEAR_THRESHOLD("near_threshold"),
        SMALL_FACE("small_face"),
        TRACK_GAP("track_gap");

        companion object {
            fun of(id: String) = entries.first { it.id == id }
        }
    }
}

/** What will be covered in an image. Lives in memory only, never on disk. */
data class ImagePlan(
    val width: Int,
    val height: Int,
    val boxes: MutableList<Box> = mutableListOf(),
    var flags: List<Flag> = emptyList(),
    val facesExpected: Boolean = true,
) {
    fun addBox(box: Box) {
        boxes += Box(box.x, box.y, box.w, box.h, null, Box.Source.MANUAL)
    }

    fun removeBox(index: Int) {
        boxes.removeAt(index)
    }
}

/** The rules of engine.py that do not touch files. */
object Review {
    /** engine.image_flags. */
    fun imageFlags(plan: ImagePlan, confidence: Double, levels: Levels): List<Flag> {
        val flags = ArrayList<Flag>()
        plan.boxes.forEachIndexed { i, box ->
            if (box.score != null && box.score < confidence + levels.nearThresholdMargin) {
                flags += Flag(Flag.Kind.NEAR_THRESHOLD, box = i)
            }
            if (box.longSide < levels.smallFacePx) flags += Flag(Flag.Kind.SMALL_FACE, box = i)
        }
        if (plan.facesExpected && plan.boxes.isEmpty()) flags += Flag(Flag.Kind.NO_FACES)
        return flags
    }

    /** Manual boxes have no score and always count. */
    fun reaches(box: Box, confidence: Double): Boolean = box.score?.let { it >= confidence } ?: true

    /**
     * engine.image_plan_at: the plan a less sensitive level would give, from a
     * detection at the most sensitive one (YuNet applies the threshold before NMS).
     */
    fun imagePlan(plan: ImagePlan, confidence: Double, levels: Levels): ImagePlan {
        val out = ImagePlan(
            plan.width, plan.height,
            plan.boxes.filter { reaches(it, confidence) }.toMutableList(),
            facesExpected = plan.facesExpected,
        )
        if (plan.facesExpected) out.flags = imageFlags(out, confidence, levels)
        return out
    }
}
