package com.mehmetdem.crownfall.campaign

import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RadialGradient
import android.graphics.Shader
import kotlin.math.cos
import kotlin.math.sin

object CampaignArt {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val outline = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }

    fun drawOcean(canvas: Canvas, width: Int, height: Int, time: Float) {
        paint.shader = LinearGradient(
            0f,
            0f,
            width.toFloat(),
            height.toFloat(),
            intArrayOf(Color.rgb(20, 55, 80), Color.rgb(31, 82, 108), Color.rgb(15, 44, 69)),
            null,
            Shader.TileMode.CLAMP
        )
        canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), paint)
        paint.shader = null
        paint.style = Paint.Style.STROKE
        paint.strokeWidth = 1.4f
        paint.color = Color.argb(45, 210, 235, 245)
        val shift = (time * 11f) % 70f
        var y = -70f + shift
        while (y < height + 70f) {
            val path = Path()
            path.moveTo(-20f, y)
            var x = -20f
            while (x < width + 80f) {
                path.quadTo(x + 34f, y - 8f, x + 68f, y)
                x += 68f
            }
            canvas.drawPath(path, paint)
            y += 70f
        }
        paint.style = Paint.Style.FILL
    }

    fun drawProvinceTexture(canvas: Canvas, path: Path, terrain: TerrainType, alpha: Int = 34) {
        canvas.save()
        canvas.clipPath(path)
        paint.color = when (terrain) {
            TerrainType.PLAINS -> Color.argb(alpha, 232, 226, 152)
            TerrainType.FOREST -> Color.argb(alpha + 20, 20, 70, 32)
            TerrainType.HILLS -> Color.argb(alpha + 8, 82, 57, 35)
            TerrainType.DESERT -> Color.argb(alpha + 28, 245, 211, 118)
            TerrainType.STEPPE -> Color.argb(alpha + 12, 171, 153, 75)
            TerrainType.TUNDRA -> Color.argb(alpha + 28, 205, 228, 235)
            TerrainType.COAST -> Color.argb(alpha + 8, 69, 155, 181)
            TerrainType.MOUNTAIN -> Color.argb(alpha + 20, 55, 55, 58)
        }
        canvas.drawPath(path, paint)

        outline.strokeWidth = 2f
        outline.color = Color.argb(28, 255, 255, 255)
        val bounds = android.graphics.RectF()
        path.computeBounds(bounds, true)
        var y = bounds.top - 30f
        while (y < bounds.bottom + 30f) {
            canvas.drawLine(bounds.left - 30f, y, bounds.right + 30f, y + 42f, outline)
            y += 36f
        }
        canvas.restore()
    }

    fun drawCapital(canvas: Canvas, x: Float, y: Float, scale: Float, nationColor: Int) {
        paint.shader = RadialGradient(x, y, 32f * scale, Color.argb(150, 255, 223, 120), Color.TRANSPARENT, Shader.TileMode.CLAMP)
        canvas.drawCircle(x, y, 36f * scale, paint)
        paint.shader = null

        paint.color = Color.rgb(55, 58, 63)
        canvas.drawRoundRect(x - 21f * scale, y - 8f * scale, x + 21f * scale, y + 18f * scale, 3f * scale, 3f * scale, paint)
        paint.color = Color.rgb(90, 94, 100)
        for (offset in listOf(-18f, -6f, 6f, 18f)) {
            canvas.drawRect(x + offset * scale - 3f * scale, y - 17f * scale, x + offset * scale + 3f * scale, y - 5f * scale, paint)
        }
        paint.color = nationColor
        val roof = Path().apply {
            moveTo(x - 18f * scale, y - 7f * scale)
            lineTo(x, y - 28f * scale)
            lineTo(x + 18f * scale, y - 7f * scale)
            close()
        }
        canvas.drawPath(roof, paint)
        paint.color = Color.rgb(34, 28, 24)
        canvas.drawRoundRect(x - 5f * scale, y + 3f * scale, x + 5f * scale, y + 18f * scale, 2f, 2f, paint)
        outline.color = Color.argb(220, 15, 18, 20)
        outline.strokeWidth = 2f * scale
        canvas.drawRoundRect(x - 21f * scale, y - 8f * scale, x + 21f * scale, y + 18f * scale, 3f, 3f, outline)
    }

    fun drawStructures(canvas: Canvas, province: ProvinceState, x: Float, y: Float, scale: Float) {
        var slot = 0
        if (province.farmLevel > 0) {
            drawFarm(canvas, x - 34f * scale, y + 30f * scale, scale, province.farmLevel)
            slot++
        }
        if (province.mineLevel > 0) {
            drawMine(canvas, x + 34f * scale, y + 30f * scale, scale, province.mineLevel)
            slot++
        }
        if (province.barracksLevel > 0) {
            drawBarracks(canvas, x - 37f * scale, y - 31f * scale, scale, province.barracksLevel)
            slot++
        }
        if (province.fortressLevel > 0 && !province.capital) {
            drawFortress(canvas, x + 37f * scale, y - 31f * scale, scale, province.fortressLevel)
        }
    }

    fun drawMinionPack(canvas: Canvas, x: Float, y: Float, count: Int, scale: Float, nationColor: Int) {
        val shown = count.coerceIn(1, 9)
        for (index in 0 until shown) {
            val row = index / 3
            val column = index % 3
            val px = x + (column - 1) * 11f * scale + row * 2f
            val py = y + row * 9f * scale
            drawMinion(canvas, px, py, scale, nationColor, index % 3)
        }
    }

    fun drawMarchingArmy(canvas: Canvas, x: Float, y: Float, troops: Int, scale: Float, nationColor: Int) {
        paint.shader = RadialGradient(x, y, 28f * scale, Color.argb(115, 255, 220, 110), Color.TRANSPARENT, Shader.TileMode.CLAMP)
        canvas.drawCircle(x, y, 30f * scale, paint)
        paint.shader = null
        drawMinionPack(canvas, x, y - 8f * scale, (troops / 12).coerceIn(3, 9), scale * 1.08f, nationColor)
        paint.color = Color.rgb(46, 37, 29)
        canvas.drawRoundRect(x - 22f * scale, y + 19f * scale, x + 22f * scale, y + 27f * scale, 4f, 4f, paint)
        paint.color = Color.rgb(234, 210, 142)
        val ratio = (troops / 120f).coerceIn(0.1f, 1f)
        canvas.drawRoundRect(x - 20f * scale, y + 21f * scale, x - 20f * scale + 40f * scale * ratio, y + 25f * scale, 2f, 2f, paint)
    }

    private fun drawMinion(canvas: Canvas, x: Float, y: Float, scale: Float, nationColor: Int, variant: Int) {
        paint.color = Color.argb(105, 0, 0, 0)
        canvas.drawOval(x - 5f * scale, y + 8f * scale, x + 5f * scale, y + 12f * scale, paint)
        paint.color = nationColor
        canvas.drawRoundRect(x - 5f * scale, y, x + 5f * scale, y + 10f * scale, 3f, 3f, paint)
        paint.color = Color.rgb(226, 190, 145)
        canvas.drawCircle(x, y - 3f * scale, 4.3f * scale, paint)
        paint.color = when (variant) {
            0 -> Color.rgb(90, 93, 101)
            1 -> Color.rgb(103, 69, 38)
            else -> Color.rgb(70, 58, 50)
        }
        canvas.drawArc(x - 4.5f * scale, y - 7.5f * scale, x + 4.5f * scale, y + 1f * scale, 180f, 180f, true, paint)
        outline.color = Color.argb(190, 20, 20, 22)
        outline.strokeWidth = 1f * scale
        canvas.drawLine(x + 5f * scale, y + 1f * scale, x + 10f * scale, y - 5f * scale, outline)
    }

    private fun drawFarm(canvas: Canvas, x: Float, y: Float, scale: Float, level: Int) {
        paint.color = Color.rgb(176, 127, 54)
        canvas.drawRoundRect(x - 11f * scale, y - 7f * scale, x + 11f * scale, y + 8f * scale, 2f, 2f, paint)
        paint.color = Color.rgb(122, 62, 41)
        val roof = Path().apply {
            moveTo(x - 14f * scale, y - 6f * scale)
            lineTo(x, y - 17f * scale)
            lineTo(x + 14f * scale, y - 6f * scale)
            close()
        }
        canvas.drawPath(roof, paint)
        paint.color = Color.rgb(239, 200, 76)
        repeat(level.coerceAtMost(4)) { index ->
            canvas.drawLine(x - 12f * scale + index * 7f * scale, y + 10f * scale, x - 10f * scale + index * 7f * scale, y + 19f * scale, paint)
        }
    }

    private fun drawMine(canvas: Canvas, x: Float, y: Float, scale: Float, level: Int) {
        paint.color = Color.rgb(80, 80, 86)
        canvas.drawCircle(x, y, 14f * scale, paint)
        paint.color = Color.rgb(38, 34, 31)
        canvas.drawArc(x - 10f * scale, y - 8f * scale, x + 10f * scale, y + 14f * scale, 180f, 180f, true, paint)
        paint.color = Color.rgb(227, 181, 60)
        repeat(level.coerceAtMost(4)) { index ->
            canvas.drawCircle(x - 7f * scale + index * 5f * scale, y + 10f * scale, 2.4f * scale, paint)
        }
    }

    private fun drawBarracks(canvas: Canvas, x: Float, y: Float, scale: Float, level: Int) {
        paint.color = Color.rgb(98, 68, 46)
        canvas.drawRoundRect(x - 13f * scale, y - 9f * scale, x + 13f * scale, y + 10f * scale, 2f, 2f, paint)
        paint.color = Color.rgb(63, 60, 58)
        canvas.drawRect(x - 3f * scale, y - 4f * scale, x + 3f * scale, y + 10f * scale, paint)
        outline.color = Color.rgb(220, 220, 215)
        outline.strokeWidth = 2f * scale
        canvas.drawLine(x - 10f * scale, y - 15f * scale, x + 10f * scale, y + 3f * scale, outline)
        canvas.drawLine(x + 10f * scale, y - 15f * scale, x - 10f * scale, y + 3f * scale, outline)
        if (level > 2) {
            paint.color = Color.rgb(190, 45, 45)
            canvas.drawCircle(x, y - 15f * scale, 3f * scale, paint)
        }
    }

    private fun drawFortress(canvas: Canvas, x: Float, y: Float, scale: Float, level: Int) {
        paint.color = Color.rgb(75, 78, 84)
        canvas.drawRoundRect(x - 14f * scale, y - 9f * scale, x + 14f * scale, y + 12f * scale, 2f, 2f, paint)
        repeat(3) { index ->
            canvas.drawRect(x - 14f * scale + index * 10f * scale, y - 15f * scale, x - 8f * scale + index * 10f * scale, y - 7f * scale, paint)
        }
        outline.color = Color.rgb(35, 36, 39)
        outline.strokeWidth = (1.2f + level * 0.35f) * scale
        canvas.drawRoundRect(x - 14f * scale, y - 9f * scale, x + 14f * scale, y + 12f * scale, 2f, 2f, outline)
    }
}
