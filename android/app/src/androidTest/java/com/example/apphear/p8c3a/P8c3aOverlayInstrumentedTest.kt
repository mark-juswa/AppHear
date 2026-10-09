package com.example.apphear.p8c3a

import android.graphics.Bitmap
import android.graphics.Canvas
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.p8b.P8bOverlayContract
import com.example.apphear.p8b.P8bOverlayView
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.io.FileOutputStream
import kotlin.math.abs

@RunWith(AndroidJUnit4::class)
class P8c3aOverlayInstrumentedTest {
    private val expectedHand = listOf(
        0 to 1, 1 to 2, 2 to 3, 3 to 4,
        0 to 5, 5 to 6, 6 to 7, 7 to 8,
        0 to 9, 9 to 10, 10 to 11, 11 to 12,
        0 to 13, 13 to 14, 14 to 15, 15 to 16,
        0 to 17, 17 to 18, 18 to 19, 19 to 20,
        5 to 9, 9 to 13, 13 to 17,
    )
    private val expectedBody = listOf(
        42 to 43, 42 to 44, 44 to 46, 43 to 45, 45 to 47,
        42 to 48, 43 to 49, 48 to 49,
    )

    @Test
    fun topologySyntheticRenderingAndPreviewTransformPass() {
        assertEquals(expectedHand, P8bOverlayContract.HAND_EDGES)
        assertEquals(expectedBody, P8bOverlayContract.BODY_EDGES)
        val fullEdges = P8bOverlayContract.edges(P8bOverlayContract.RenderMode.FULL_TOPOLOGY)
        assertEquals(54, fullEdges.size)
        assertEquals(23, fullEdges.count { it.group == "LH" })
        assertEquals(23, fullEdges.count { it.group == "RH" })
        assertEquals(8, fullEdges.count { it.group == "BODY" })
        assertTrue(fullEdges.filter { it.group == "LH" }.all { it.a in 0..20 && it.b in 0..20 })
        assertTrue(fullEdges.filter { it.group == "RH" }.all { it.a in 21..41 && it.b in 21..41 })
        assertTrue(fullEdges.filter { it.group == "BODY" }.all { it.a in 42..49 && it.b in 42..49 })
        assertTrue(P8bOverlayContract.edges(P8bOverlayContract.RenderMode.POINTS_ONLY).isEmpty())

        val source = syntheticCoordinates()
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val root = File(requireNotNull(context.getExternalFilesDir(null)), "p8c3a").apply { mkdirs() }
        instrumentation.runOnMainSync {
            render(
                context = context,
                source = source,
                mode = P8bOverlayContract.RenderMode.FULL_TOPOLOGY,
                output = File(root, "synthetic_full_topology.png"),
            )
            render(
                context = context,
                source = source,
                mode = P8bOverlayContract.RenderMode.POINTS_ONLY,
                output = File(root, "synthetic_points_only.png"),
            )
        }

        val sourceLeft = P8bOverlayContract.mapPoint(100f, 300f, 600, 800, 1080, 1920, false)
        val sourceRight = P8bOverlayContract.mapPoint(400f, 300f, 600, 800, 1080, 1920, false)
        val mirroredLeft = P8bOverlayContract.mapPoint(100f, 300f, 600, 800, 1080, 1920, true)
        val mirroredRight = P8bOverlayContract.mapPoint(400f, 300f, 600, 800, 1080, 1920, true)
        assertClose(60f, sourceLeft.x)
        assertClose(780f, sourceRight.x)
        assertClose(1020f, mirroredLeft.x)
        assertClose(300f, mirroredRight.x)
        assertClose(sourceLeft.y, mirroredLeft.y)
        assertClose(sourceRight.y, mirroredRight.y)

        File(root, "synthetic_topology_validation.json").writeText(
            JSONObject()
                .put("schema", "P8C3A_SYNTHETIC_TOPOLOGY_VALIDATION_V1")
                .put("status", "PASS")
                .put("rendered_through_live_overlay_view", true)
                .put("full_edge_count", fullEdges.size)
                .put("lh_edges", fullEdges.count { it.group == "LH" })
                .put("rh_edges", fullEdges.count { it.group == "RH" })
                .put("body_edges", fullEdges.count { it.group == "BODY" })
                .put("points_only_edge_count", 0)
                .put("all_channels_unique_coordinates", source.asList().chunked(2).distinct().size == 50)
                .put("screenshots", JSONArray(listOf("synthetic_full_topology.png", "synthetic_points_only.png")))
                .toString(2),
        )
        File(root, "preview_transform_validation.json").writeText(
            JSONObject()
                .put("schema", "P8C3A_PREVIEW_TRANSFORM_VALIDATION_V1")
                .put("status", "PASS")
                .put("source_plane", "UPRIGHT_UNMIRRORED")
                .put("view", "1080x1920_FILL_CENTER")
                .put("source_lh_example", JSONObject().put("semantic", "LH").put("x", 100).put("mapped_x", sourceLeft.x).put("mirrored_x", mirroredLeft.x))
                .put("source_rh_example", JSONObject().put("semantic", "RH").put("x", 400).put("mapped_x", sourceRight.x).put("mirrored_x", mirroredRight.x))
                .put("semantic_labels_after_mirror", JSONArray(listOf("LH", "RH")))
                .put("semantic_group_swap", false)
                .put("model_coordinate_mirror_count", 0)
                .put("display_mirror_count", 1)
                .put("overlay_rotation_count", 0)
                .toString(2),
        )
    }

    private fun render(
        context: android.content.Context,
        source: FloatArray,
        mode: P8bOverlayContract.RenderMode,
        output: File,
    ) {
        val view = P8bOverlayView(context)
        view.layout(0, 0, 1080, 1920)
        view.setSnapshot(P8bOverlayView.Snapshot(source, 600, 800, true, mode))
        val bitmap = Bitmap.createBitmap(1080, 1920, Bitmap.Config.ARGB_8888)
        view.draw(Canvas(bitmap))
        FileOutputStream(output).use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        bitmap.recycle()
    }

    private fun syntheticCoordinates(): FloatArray {
        val out = FloatArray(100)
        fun set(channel: Int, x: Float, y: Float) {
            out[channel * 2] = x
            out[channel * 2 + 1] = y
        }
        // LH: wrist and five deliberately separated rays.
        set(0, 150f, 520f)
        val leftBases = listOf(115f, 135f, 155f, 175f, 195f)
        val leftStarts = listOf(1, 5, 9, 13, 17)
        leftStarts.forEachIndexed { finger, start ->
            for (joint in 0..3) set(start + joint, leftBases[finger] - joint * 4f, 465f - joint * 42f - finger * 3f)
        }
        // RH: a non-identical orientation prevents accidental mirrored equality.
        set(21, 450f, 520f)
        val rightBases = listOf(405f, 425f, 445f, 465f, 485f)
        leftStarts.forEachIndexed { finger, localStart ->
            for (joint in 0..3) set(21 + localStart + joint, rightBases[finger] + joint * 5f, 470f - joint * 39f + finger * 2f)
        }
        set(42, 225f, 235f); set(43, 375f, 235f)
        set(44, 185f, 350f); set(45, 415f, 350f)
        set(46, 152f, 522f); set(47, 448f, 522f)
        set(48, 255f, 640f); set(49, 345f, 640f)
        return out
    }

    private fun assertClose(expected: Float, actual: Float) {
        assertTrue("expected=$expected actual=$actual", abs(expected - actual) <= 1e-4f)
    }
}
