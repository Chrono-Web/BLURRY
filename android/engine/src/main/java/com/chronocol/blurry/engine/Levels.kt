package com.chronocol.blurry.engine

import android.content.res.AssetManager
import org.json.JSONObject

/**
 * A detection level. The numbers come from src/blurry_opsec/levels.py, the
 * single source, through levels.json (scripts/coreml/levels_json.py).
 */
data class Level(
    val name: String,
    val confidence: Double,
    /** Pixelation strength: blocks on the long side of the face. */
    val blocks: Int,
    val label: Map<String, String>,
    val description: Map<String, String>,
)

class Levels(
    val levels: List<Level>,
    val defaultLevel: String,
    val mostSensitive: String,
    val defaultMode: CoverMode,
    val defaultPadding: Double,
    val yunetNms: Double,
    val yunetTopk: Int,
    val nearThresholdMargin: Double,
    val smallFacePx: Int,
) {
    class UnknownLevel(name: String) : IllegalArgumentException("unknown level '$name'")

    fun get(name: String): Level = levels.firstOrNull { it.name == name } ?: throw UnknownLevel(name)

    companion object {
        /** A missing or broken resource is a build error, not a runtime condition. */
        fun load(assets: AssetManager): Levels =
            parse(assets.open("levels.json").use { String(it.readBytes()) })

        fun parse(json: String): Levels {
            val o = JSONObject(json)
            fun strings(m: JSONObject) = m.keys().asSequence().associateWith { m.getString(it) }
            val arr = o.getJSONArray("levels")
            val levels = (0 until arr.length()).map { arr.getJSONObject(it) }.map {
                Level(
                    it.getString("name"), it.getDouble("confidence"), it.getInt("blocks"),
                    strings(it.getJSONObject("label")), strings(it.getJSONObject("description")),
                )
            }
            return Levels(
                levels,
                o.getString("default_level"),
                o.getString("most_sensitive"),
                CoverMode.of(o.getString("default_mode")),
                o.getDouble("default_padding"),
                o.getDouble("yunet_nms"),
                o.getInt("yunet_topk"),
                o.getDouble("near_threshold_margin"),
                o.getInt("small_face_px"),
            )
        }
    }
}

/** How a face is covered. */
enum class CoverMode(val id: String) {
    SOLID("solid"), // black box (default)
    PIXEL("pixel"); // pixelation with the level's blocks

    companion object {
        fun of(id: String) = entries.firstOrNull { it.id == id } ?: throw IllegalArgumentException("unknown mode '$id'")
    }
}
