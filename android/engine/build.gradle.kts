plugins {
    alias(libs.plugins.android.library)
}

android {
    namespace = "com.chronocol.blurry.engine"
    compileSdk = 36

    defaultConfig {
        minSdk = 29
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        ndk { abiFilters += "arm64-v8a" }
    }

    sourceSets {
        // What the Python engine does (scripts/coreml/riferimento.py), and the originals it read.
        getByName("androidTest").assets.srcDirs("../../build/parity", "../../tests/fixtures/public")
    }

    androidResources {
        // The model must reach the app byte for byte (R5).
        noCompress += "onnx"
    }
}

// One home for each fact: the model and the levels come from where the Python
// engine and BlurryKit keep them, not copied into the repo. Only these files.
abstract class EngineAssets : DefaultTask() {
    @get:InputDirectory abstract val modelDir: DirectoryProperty
    @get:InputFile abstract val levels: RegularFileProperty
    @get:OutputDirectory abstract val outputDir: DirectoryProperty

    @TaskAction
    fun copy() {
        val out = outputDir.get().asFile
        out.deleteRecursively()
        out.mkdirs()
        val model = modelDir.get().asFile
        model.resolve("face_detection_yunet_2023mar.onnx").copyTo(out.resolve("face_detection_yunet_2023mar.onnx"))
        model.resolve("LICENSE").copyTo(out.resolve("YuNet-LICENSE"))
        levels.get().asFile.copyTo(out.resolve("levels.json"))
    }
}

val engineAssets = tasks.register<EngineAssets>("engineAssets") {
    modelDir.set(layout.projectDirectory.dir("../../src/blurry_opsec/model"))
    levels.set(layout.projectDirectory.file("../../ios/BlurryKit/Sources/BlurryKit/Resources/levels.json"))
}

androidComponents {
    onVariants { variant ->
        variant.sources.assets?.addGeneratedSourceDirectory(engineAssets, EngineAssets::outputDir)
    }
}

dependencies {
    implementation(libs.opencv)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.androidx.test.junit)
}
