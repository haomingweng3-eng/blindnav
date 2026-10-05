package com.blindnav.mobile.overlay

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.PointF
import android.util.AttributeSet
import android.view.View
import com.blindnav.mobile.guidance.GuidanceState
import com.blindnav.mobile.inference.FrameDetections
import com.blindnav.mobile.risk.RiskTrackSnapshot
import kotlin.math.max

/**
 * Camera preview overlay for the phone MVP.
 *
 * The overlay shows only confirmed route-relevant tracks and their observed
 * contact trail. It deliberately does not draw a guessed future line.
 */
class TrajectoryOverlayView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : View(context, attrs) {
    private var tracks: List<RiskTrackSnapshot> = emptyList()
    private var imageWidth = 1
    private var imageHeight = 1
    private var latestFrame = -1L
    private var guidanceState: GuidanceState? = null
    private val density = resources.displayMetrics.density
    private val boxPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE }
    private val trailPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.CYAN
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE
        style = Paint.Style.FILL
        typeface = android.graphics.Typeface.DEFAULT_BOLD
    }

    fun submit(
        frame: FrameDetections,
        observations: List<RiskTrackSnapshot>,
        guidanceState: GuidanceState? = null,
    ) {
            imageWidth = frame.frameWidth.coerceAtLeast(1)
            imageHeight = frame.frameHeight.coerceAtLeast(1)
            latestFrame = frame.sourceFrame
            tracks = observations
            this.guidanceState = guidanceState
            invalidate()
    }

    fun clearOverlay() {
        post {
            tracks = emptyList()
            guidanceState = null
            latestFrame = -1L
            invalidate()
        }
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (latestFrame < 0L) return
        val transform = transform()
        val textSize = 14f * density
        val stroke = max(3f * density, 3f)
        boxPaint.strokeWidth = stroke
        trailPaint.strokeWidth = max(4f * density, 4f)
        textPaint.textSize = textSize

        val legend = "CYAN trail  route-risk boxes only"
        canvas.drawText(legend, 14f * density, 24f * density, textPaint)

        for (track in tracks) {
            val contactY = track.roadHistory.lastOrNull()?.y ?: 0f
            val contactX = (track.box[0] + track.box[2]) / 2f
            val routeRelevant = contactY >= imageHeight * MIN_ROAD_CONTACT_Y &&
                contactX / imageWidth in ROUTE_LEFT..ROUTE_RIGHT
            // The phone is for route-risk feedback. Hide stable detections in
            // parking rows from the user-facing overlay; risk tracks remain
            // visible even while entering from outside the corridor.
            if (track.riskLevel == 0 && !routeRelevant) continue
            // Keep the display conservative even before the temporal risk
            // engine promotes a track: a close central target with a short
            // observed trail is shown as NOTICE, never as an apparently safe
            // green track. This is display-only and does not emit feedback.
            val closeCentralTrack = track.riskLevel == 0 && routeRelevant &&
                contactY >= imageHeight * CLOSE_CONTACT_Y &&
                track.roadHistory.size >= 2
            val uncertainRouteTrack = track.riskLevel == 0 && routeRelevant &&
                guidanceState == GuidanceState.UNKNOWN_SLOW_DOWN
            boxPaint.color = when {
                track.riskLevel >= 2 -> Color.RED
                track.riskLevel == 1 || closeCentralTrack || uncertainRouteTrack -> Color.rgb(255, 165, 0)
                else -> Color.GREEN
            }
            val displayRisk = when {
                track.riskLevel >= 2 -> " DANGER"
                track.riskLevel == 1 || closeCentralTrack -> " NOTICE"
                uncertainRouteTrack -> " SLOW DOWN"
                else -> " TRACK"
            }
            val box = track.box
            if (!validBox(box)) continue
            val leftTop = map(transform, box[0], box[1])
            val rightBottom = map(transform, box[2], box[3])
            canvas.drawRect(leftTop.x, leftTop.y, rightBottom.x, rightBottom.y, boxPaint)
            val label = track.className + " " + track.trackId + displayRisk
            canvas.drawText(label, leftTop.x, max(textSize + 4f, leftTop.y - 6f), boxPaint.asTextPaint())

            val points = track.roadHistory
            for (pair in points.zipWithNext()) {
                canvas.drawLine(
                    map(transform, pair.first.x, pair.first.y).x,
                    map(transform, pair.first.x, pair.first.y).y,
                    map(transform, pair.second.x, pair.second.y).x,
                    map(transform, pair.second.x, pair.second.y).y,
                    trailPaint,
                )
            }
        }
    }

    private fun transform(): Transform {
        val scale = max(width.toFloat() / imageWidth, height.toFloat() / imageHeight)
        return Transform(
            scale,
            (width - imageWidth * scale) / 2f,
            (height - imageHeight * scale) / 2f,
        )
    }

    private fun map(transform: Transform, x: Float, y: Float): PointF =
        PointF(x * transform.scale + transform.offsetX, y * transform.scale + transform.offsetY)

    private fun validBox(box: FloatArray): Boolean =
        box.size == 4 && box[2] > box[0] && box[3] > box[1]

    private fun Paint.asTextPaint(): Paint = Paint(this).apply {
        style = Paint.Style.FILL
        color = this@TrajectoryOverlayView.boxPaint.color
        textSize = this@TrajectoryOverlayView.textPaint.textSize
        typeface = android.graphics.Typeface.DEFAULT_BOLD
    }

    private data class Transform(val scale: Float, val offsetX: Float, val offsetY: Float)

    private companion object {
        const val MIN_ROAD_CONTACT_Y = 0.38f
        const val ROUTE_LEFT = 0.36f
        const val ROUTE_RIGHT = 0.64f
        const val CLOSE_CONTACT_Y = 0.72f
    }
}
