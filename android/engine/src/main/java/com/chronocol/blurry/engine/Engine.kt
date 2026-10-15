package com.chronocol.blurry.engine

/** What the user chose, as engine.Settings. */
data class Settings(
    val level: String,
    val mode: CoverMode,
    val padding: Double,
    /** False = metadata cleanup only (--no-faces). */
    val faces: Boolean = true,
) {
    fun validate(levels: Levels) {
        levels.get(level)
        require(padding in 0.0..2.0) { "padding must be between 0 and 2" }
    }

    companion object {
        fun defaults(levels: Levels) = Settings(levels.defaultLevel, levels.defaultMode, levels.defaultPadding)
    }
}

class ImageJob(val loaded: LoadedImage, val plan: ImagePlan)

/**
 * The two phases of engine.py for images: analyze gives a plan in memory,
 * render applies it and returns the clean file's bytes. Nothing touches the disk.
 */
object Engine {
    /** With `settings.faces`, `detector` must be the most sensitive one. */
    fun analyzeImage(data: ByteArray, fileExtension: String, settings: Settings, detector: Detector?, levels: Levels): ImageJob {
        val loaded = ImageIn.load(data, fileExtension)
        val plan = ImagePlan(loaded.width, loaded.height, facesExpected = settings.faces)
        if (settings.faces) {
            requireNotNull(detector) { "a detector is required to cover faces" }
            plan.boxes += detector.detectRGB(loaded.rgb)
            plan.flags = Review.imageFlags(plan, detector.confidence, levels)
        }
        return ImageJob(loaded, plan)
    }

    /** The plan at the chosen level: the boxes whose score reaches it, plus manual ones. */
    fun planAt(job: ImageJob, settings: Settings, levels: Levels): ImagePlan =
        Review.imagePlan(job.plan, levels.get(settings.level).confidence, levels)

    fun renderImage(job: ImageJob, plan: ImagePlan, settings: Settings, levels: Levels): ByteArray {
        val rgb = ImageIn.copyOf(job.loaded.rgb)
        val alpha = job.loaded.alpha?.let { ImageIn.copyOf(it) }
        try {
            Redact.apply(rgb, plan.boxes, settings.mode, settings.padding, levels.get(settings.level).blocks, alpha)
            return ImageOut.encode(rgb, alpha, job.loaded.outFormat)
        } finally {
            rgb.release()
            alpha?.release()
        }
    }
}
