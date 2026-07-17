package com.mehmetdem.crownfall

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.DashPathEffect
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.util.Log
import android.view.MotionEvent
import android.view.SurfaceHolder
import android.view.SurfaceView
import com.mehmetdem.crownfall.campaign.ArmyGroup
import com.mehmetdem.crownfall.campaign.CampaignArt
import com.mehmetdem.crownfall.campaign.CampaignSimulation
import com.mehmetdem.crownfall.campaign.ProvinceState
import com.mehmetdem.crownfall.campaign.Vec2
import com.mehmetdem.crownfall.campaign.WorldDefinition
import java.util.concurrent.ConcurrentLinkedQueue
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min

class WorldConquestView(context: Context) : SurfaceView(context), SurfaceHolder.Callback, Runnable {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val outline = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeJoin = Paint.Join.ROUND
        strokeCap = Paint.Cap.ROUND
    }
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        typeface = android.graphics.Typeface.create(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD)
    }

    @Volatile private var running = false
    private var gameThread: Thread? = null
    private var lastFrameNs = 0L
    private val frameBudgetNs = 16_666_667L

    private var simulation = CampaignSimulation()
    private var selectedProvinceId: Int? = null
    private var targetProvinceId: Int? = null

    @Volatile private var cameraX = WorldDefinition.WORLD_WIDTH * 0.52f
    @Volatile private var cameraY = WorldDefinition.WORLD_HEIGHT * 0.5f
    @Volatile private var zoom = 0.52f

    @Volatile private var primaryPointerId = -1
    @Volatile private var secondaryPointerId = -1
    @Volatile private var lastTouchX = 0f
    @Volatile private var lastTouchY = 0f
    @Volatile private var touchDownX = 0f
    @Volatile private var touchDownY = 0f
    @Volatile private var dragged = false
    @Volatile private var previousPinchDistance = 0f

    private val commands = ConcurrentLinkedQueue<WorldCommand>()
    @Volatile private var buttonSnapshot: List<ActionButton> = emptyList()

    init {
        holder.addCallback(this)
        isFocusable = true
        isFocusableInTouchMode = true
        keepScreenOn = true
    }

    override fun surfaceCreated(surfaceHolder: SurfaceHolder) {
        if (running) return
        fitWorldToScreen()
        running = true
        lastFrameNs = System.nanoTime()
        gameThread = Thread(this, "CrownfallWorldConquest").also { it.start() }
    }

    override fun surfaceChanged(surfaceHolder: SurfaceHolder, format: Int, width: Int, height: Int) {
        if (width > 0 && height > 0) fitWorldToScreen()
    }

    override fun surfaceDestroyed(surfaceHolder: SurfaceHolder) {
        running = false
        gameThread?.interrupt()
        try {
            gameThread?.join(1000)
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
        }
        gameThread = null
    }

    override fun run() {
        while (running) {
            val frameStart = System.nanoTime()
            try {
                val dt = ((frameStart - lastFrameNs) / 1_000_000_000f).coerceIn(0f, 0.05f)
                lastFrameNs = frameStart
                drainCommands()
                simulation.update(dt)
                clampCamera()
                drawFrame()
            } catch (error: Throwable) {
                Log.e(TAG, "World campaign loop stopped", error)
                drawFailure(error)
                running = false
                break
            }

            val remaining = frameBudgetNs - (System.nanoTime() - frameStart)
            if (remaining > 1_000_000L) {
                try {
                    Thread.sleep(remaining / 1_000_000L)
                } catch (_: InterruptedException) {
                    if (!running) break
                }
            }
        }
    }

    private fun drainCommands() {
        while (true) {
            when (val command = commands.poll() ?: break) {
                is WorldCommand.Tap -> handleMapTap(command.x, command.y)
                is WorldCommand.Action -> handleAction(command.name)
                is WorldCommand.Pan -> {
                    cameraX -= command.dx / zoom
                    cameraY -= command.dy / zoom
                }
                is WorldCommand.Zoom -> {
                    val before = screenToWorld(command.focusX, command.focusY)
                    zoom = (zoom * command.factor).coerceIn(0.34f, 1.42f)
                    val after = screenToWorld(command.focusX, command.focusY)
                    cameraX += before.x - after.x
                    cameraY += before.y - after.y
                }
                WorldCommand.Restart -> restartCampaign()
            }
        }
    }

    private fun handleMapTap(screenX: Float, screenY: Float) {
        if (simulation.winnerNationId != null) {
            restartCampaign()
            return
        }
        val worldPoint = screenToWorld(screenX, screenY)
        val tapped = simulation.provinces.firstOrNull { pointInPolygon(worldPoint, it.polygon) } ?: return
        val current = selectedProvinceId?.let { simulation.provinces.getOrNull(it) }

        if (tapped.ownerId == PLAYER_NATION_ID) {
            selectedProvinceId = tapped.id
            targetProvinceId = null
            return
        }

        if (current != null && current.ownerId == PLAYER_NATION_ID && tapped.id in current.neighbors) {
            targetProvinceId = tapped.id
        } else {
            selectedProvinceId = tapped.id
            targetProvinceId = null
        }
    }

    private fun handleAction(action: String) {
        when (action) {
            "RECRUIT" -> {
                val selected = selectedProvinceId ?: return
                if (simulation.provinces[selected].ownerId == PLAYER_NATION_ID) simulation.recruit(selected, 18)
            }
            "UPGRADE" -> {
                val selected = selectedProvinceId ?: return
                if (simulation.provinces[selected].ownerId == PLAYER_NATION_ID) simulation.upgradeProvince(selected)
            }
            "INVADE" -> {
                val source = selectedProvinceId ?: return
                val target = targetProvinceId ?: return
                if (simulation.provinces[source].ownerId == PLAYER_NATION_ID) {
                    if (simulation.moveOrInvade(source, target)) targetProvinceId = null
                }
            }
            "AUTO" -> simulation.autoPlayer = !simulation.autoPlayer
            "SPEED" -> simulation.timeScale = when (simulation.timeScale) {
                1f -> 2f
                2f -> 4f
                else -> 1f
            }
            "CENTER" -> centerOnPlayer()
            "RESTART" -> restartCampaign()
        }
    }

    private fun restartCampaign() {
        simulation = CampaignSimulation()
        selectedProvinceId = null
        targetProvinceId = null
        cameraX = WorldDefinition.WORLD_WIDTH * 0.52f
        cameraY = WorldDefinition.WORLD_HEIGHT * 0.5f
        fitWorldToScreen()
    }

    private fun drawFrame() {
        if (!holder.surface.isValid) return
        val canvas = holder.lockCanvas() ?: return
        try {
            CampaignArt.drawOcean(canvas, width, height, simulation.elapsedSeconds)
            drawWorldBoundary(canvas)
            drawArmyRoutes(canvas)
            for (province in simulation.provinces) drawProvince(canvas, province)
            for (army in simulation.armies) drawArmy(canvas, army)
            drawHud(canvas)
        } finally {
            if (holder.surface.isValid) holder.unlockCanvasAndPost(canvas)
        }
    }

    private fun drawWorldBoundary(canvas: Canvas) {
        paint.color = Color.argb(70, 0, 0, 0)
        canvas.drawRoundRect(
            sx(35f),
            sy(40f),
            sx(WorldDefinition.WORLD_WIDTH - 35f),
            sy(WorldDefinition.WORLD_HEIGHT - 40f),
            24f,
            24f,
            paint
        )
    }

    private fun drawProvince(canvas: Canvas, province: ProvinceState) {
        val path = provinceScreenPath(province)
        val nation = simulation.nations[province.ownerId]

        outline.style = Paint.Style.STROKE
        outline.strokeWidth = max(2.4f, 7f * zoom)
        outline.color = Color.argb(235, 18, 24, 28)
        canvas.drawPath(path, outline)

        paint.style = Paint.Style.FILL
        paint.color = shaded(nation.color, if (province.unrest > 1f) 0.72f else 0.9f)
        canvas.drawPath(path, paint)
        CampaignArt.drawProvinceTexture(canvas, path, province.terrain)

        outline.strokeWidth = max(1.2f, 2f * zoom)
        outline.color = Color.argb(150, 245, 235, 205)
        canvas.drawPath(path, outline)

        if (province.id == selectedProvinceId) {
            outline.strokeWidth = max(3f, 7f * zoom)
            outline.color = Color.rgb(255, 224, 91)
            canvas.drawPath(path, outline)
        }
        if (province.id == targetProvinceId) {
            outline.strokeWidth = max(3f, 7f * zoom)
            outline.pathEffect = DashPathEffect(floatArrayOf(16f, 10f), 0f)
            outline.color = Color.rgb(255, 77, 70)
            canvas.drawPath(path, outline)
            outline.pathEffect = null
        }

        val cx = sx(province.center.x)
        val cy = sy(province.center.y)
        if (!visible(cx, cy, 150f)) return

        if (province.capital) CampaignArt.drawCapital(canvas, cx, cy - 18f * zoom, zoom.coerceAtLeast(0.45f), nation.color)
        if (zoom > 0.46f) {
            CampaignArt.drawStructures(canvas, province, cx, cy, zoom.coerceAtMost(1f))
            val troopIcons = (province.garrison / 12).coerceIn(1, 9)
            CampaignArt.drawMinionPack(canvas, cx, cy + 20f * zoom, troopIcons, zoom.coerceIn(0.5f, 1f), nation.color)
        }

        drawCentered(canvas, province.name, cx, cy - 54f * zoom, (13f * zoom).coerceIn(10f, 18f), Color.WHITE)
        drawCentered(
            canvas,
            "${province.garrison} asker",
            cx,
            cy + 61f * zoom,
            (11f * zoom).coerceIn(9f, 15f),
            Color.rgb(240, 231, 199)
        )
    }

    private fun drawArmyRoutes(canvas: Canvas) {
        outline.style = Paint.Style.STROKE
        outline.strokeWidth = max(1.8f, 3f * zoom)
        outline.pathEffect = DashPathEffect(floatArrayOf(13f, 10f), simulation.elapsedSeconds * 18f)
        for (army in simulation.armies) {
            val source = simulation.provinces[army.sourceProvinceId].center
            val target = simulation.provinces[army.targetProvinceId].center
            outline.color = Color.argb(175, 255, 225, 145)
            canvas.drawLine(sx(source.x), sy(source.y), sx(target.x), sy(target.y), outline)
        }
        outline.pathEffect = null
    }

    private fun drawArmy(canvas: Canvas, army: ArmyGroup) {
        val source = simulation.provinces[army.sourceProvinceId].center
        val target = simulation.provinces[army.targetProvinceId].center
        val eased = smoothStep(army.progress.coerceIn(0f, 1f))
        val x = lerp(source.x, target.x, eased)
        val y = lerp(source.y, target.y, eased)
        val nationColor = simulation.nations[army.ownerId].color
        CampaignArt.drawMarchingArmy(canvas, sx(x), sy(y), army.troops, zoom.coerceIn(0.52f, 1f), nationColor)
    }

    private fun drawHud(canvas: Canvas) {
        val player = simulation.nations[PLAYER_NATION_ID]
        val snapshot = simulation.snapshot(PLAYER_NATION_ID)
        paint.color = Color.argb(225, 11, 18, 24)
        canvas.drawRoundRect(16f, 14f, min(width - 16f, 760f), 100f, 18f, 18f, paint)
        drawText(canvas, "CROWNFALL  •  DÜNYA HÂKİMİYETİ", 34f, 44f, 23f, Color.rgb(255, 221, 105))
        drawText(canvas, "ALTIN ${player.treasury}   YİYECEK ${player.food}   DEMİR ${player.iron}", 34f, 72f, 18f, Color.WHITE)
        drawText(canvas, "TOPRAK ${snapshot.playerProvinces}/${snapshot.totalProvinces}   ORDU ${snapshot.playerArmy}", 34f, 94f, 16f, Color.rgb(198, 216, 226))

        drawLeaderboard(canvas)
        drawEventLog(canvas)
        drawSelectionPanel(canvas)
        drawActionBar(canvas)

        simulation.winnerNationId?.let { winnerId ->
            paint.color = Color.argb(224, 7, 10, 13)
            canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), paint)
            val won = winnerId == PLAYER_NATION_ID
            drawCentered(
                canvas,
                if (won) "DÜNYA SENİN" else "DÜNYA ${simulation.nations[winnerId].name.uppercase()} EGEMENLİĞİNDE",
                width / 2f,
                height / 2f - 20f,
                42f,
                if (won) Color.rgb(255, 218, 82) else Color.rgb(238, 98, 91)
            )
            drawCentered(canvas, "Yeniden başlatmak için dokun", width / 2f, height / 2f + 42f, 22f, Color.WHITE)
        }
    }

    private fun drawLeaderboard(canvas: Canvas) {
        val sorted = simulation.nations.filter { it.alive }.sortedByDescending { simulation.provinceCount(it.id) }.take(4)
        val left = width - 245f
        paint.color = Color.argb(215, 11, 18, 24)
        canvas.drawRoundRect(left, 14f, width - 16f, 136f, 16f, 16f, paint)
        drawText(canvas, "GÜÇ SIRALAMASI", left + 16f, 40f, 17f, Color.rgb(255, 221, 105))
        sorted.forEachIndexed { index, nation ->
            paint.color = nation.color
            canvas.drawCircle(left + 18f, 60f + index * 19f, 5f, paint)
            drawText(
                canvas,
                "${index + 1}. ${nation.shortName}  ${simulation.provinceCount(nation.id)} bölge",
                left + 31f,
                65f + index * 19f,
                14f,
                Color.WHITE
            )
        }
    }

    private fun drawEventLog(canvas: Canvas) {
        if (simulation.events.isEmpty()) return
        val panelWidth = min(460f, width * 0.42f)
        val left = width - panelWidth - 16f
        val top = 152f
        paint.color = Color.argb(180, 11, 18, 24)
        canvas.drawRoundRect(left, top, width - 16f, top + 34f + simulation.events.size * 24f, 14f, 14f, paint)
        drawText(canvas, "CEPHE RAPORU", left + 16f, top + 24f, 15f, Color.rgb(255, 221, 105))
        simulation.events.asReversed().forEachIndexed { index, event ->
            val nationColor = simulation.nations.getOrNull(event.nationId)?.color ?: Color.WHITE
            paint.color = nationColor
            canvas.drawCircle(left + 18f, top + 45f + index * 24f, 4f, paint)
            drawText(canvas, event.text, left + 30f, top + 50f + index * 24f, 13f, Color.WHITE)
        }
    }

    private fun drawSelectionPanel(canvas: Canvas) {
        val selected = selectedProvinceId?.let { simulation.provinces.getOrNull(it) } ?: return
        val nation = simulation.nations[selected.ownerId]
        val panel = RectF(18f, height - 178f, min(width * 0.46f, 540f), height - 18f)
        paint.color = Color.argb(228, 11, 18, 24)
        canvas.drawRoundRect(panel, 18f, 18f, paint)
        paint.color = nation.color
        canvas.drawRoundRect(panel.left, panel.top, panel.left + 9f, panel.bottom, 5f, 5f, paint)
        drawText(canvas, selected.name.uppercase(), panel.left + 24f, panel.top + 32f, 22f, Color.WHITE)
        drawText(canvas, nation.name, panel.left + 24f, panel.top + 57f, 16f, nation.color)
        drawText(canvas, "Nüfus ${selected.population}   Garnizon ${selected.garrison}   Milis ${selected.militia}", panel.left + 24f, panel.top + 84f, 15f, Color.rgb(218, 224, 228))
        drawText(canvas, "Gelişim ${selected.development}   Kale ${selected.fortressLevel}   Kışla ${selected.barracksLevel}", panel.left + 24f, panel.top + 108f, 15f, Color.rgb(218, 224, 228))
        val target = targetProvinceId?.let { simulation.provinces.getOrNull(it) }
        if (target != null) {
            drawText(canvas, "HEDEF: ${target.name} • Savunma ${target.garrison + target.militia}", panel.left + 24f, panel.top + 139f, 16f, Color.rgb(255, 108, 91))
        } else {
            drawText(canvas, "Komşu düşman bölgesine dokunarak hedef seç.", panel.left + 24f, panel.top + 139f, 14f, Color.rgb(181, 195, 204))
        }
    }

    private fun drawActionBar(canvas: Canvas) {
        val actions = listOf(
            Triple("ASKER\nTOPLA", "RECRUIT", Color.rgb(52, 126, 196)),
            Triple("BÖLGEYİ\nGELİŞTİR", "UPGRADE", Color.rgb(77, 148, 89)),
            Triple("İSTİLA\nBAŞLAT", "INVADE", Color.rgb(190, 64, 59)),
            Triple(if (simulation.autoPlayer) "OTOMATİK\nAÇIK" else "OTOMATİK\nKAPALI", "AUTO", Color.rgb(132, 79, 169)),
            Triple("HIZ\n${simulation.timeScale.toInt()}x", "SPEED", Color.rgb(183, 125, 43)),
            Triple("MERKEZE\nDÖN", "CENTER", Color.rgb(62, 95, 117))
        )
        val buttonWidth = min(126f, (width - 36f) / actions.size - 8f)
        val gap = 8f
        val total = actions.size * buttonWidth + (actions.size - 1) * gap
        val startX = width - total - 18f
        val y = height - 92f
        val buttons = ArrayList<ActionButton>(actions.size)
        actions.forEachIndexed { index, item ->
            val x = startX + index * (buttonWidth + gap)
            val rect = RectF(x, y, x + buttonWidth, height - 18f)
            buttons += ActionButton(rect, item.second)
            val enabled = actionEnabled(item.second)
            paint.color = if (enabled) item.third else shaded(item.third, 0.38f)
            canvas.drawRoundRect(rect, 15f, 15f, paint)
            outline.strokeWidth = 1.5f
            outline.color = Color.argb(150, 255, 255, 255)
            canvas.drawRoundRect(rect, 15f, 15f, outline)
            drawCentered(canvas, item.first, rect.centerX(), rect.top + 28f, 15f, if (enabled) Color.WHITE else Color.LTGRAY)
        }
        buttonSnapshot = buttons
    }

    private fun actionEnabled(action: String): Boolean {
        val selected = selectedProvinceId?.let { simulation.provinces.getOrNull(it) }
        return when (action) {
            "RECRUIT", "UPGRADE" -> selected?.ownerId == PLAYER_NATION_ID
            "INVADE" -> selected?.ownerId == PLAYER_NATION_ID && targetProvinceId != null
            else -> true
        }
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                val index = event.actionIndex
                val x = event.getX(index)
                val y = event.getY(index)
                val button = buttonSnapshot.firstOrNull { it.rect.contains(x, y) }
                if (button != null) {
                    commands.offer(WorldCommand.Action(button.action))
                    performClick()
                    return true
                }
                primaryPointerId = event.getPointerId(index)
                lastTouchX = x
                lastTouchY = y
                touchDownX = x
                touchDownY = y
                dragged = false
            }
            MotionEvent.ACTION_POINTER_DOWN -> {
                if (secondaryPointerId < 0) {
                    secondaryPointerId = event.getPointerId(event.actionIndex)
                    previousPinchDistance = currentPinchDistance(event)
                }
            }
            MotionEvent.ACTION_MOVE -> {
                if (secondaryPointerId >= 0) {
                    val distance = currentPinchDistance(event)
                    if (distance > 1f && previousPinchDistance > 1f) {
                        val factor = (distance / previousPinchDistance).coerceIn(0.82f, 1.22f)
                        commands.offer(WorldCommand.Zoom(factor, event.getX(0), event.getY(0)))
                        dragged = true
                    }
                    previousPinchDistance = distance
                } else {
                    val index = event.findPointerIndex(primaryPointerId)
                    if (index >= 0) {
                        val x = event.getX(index)
                        val y = event.getY(index)
                        val dx = x - lastTouchX
                        val dy = y - lastTouchY
                        if (hypot(x - touchDownX, y - touchDownY) > 12f) dragged = true
                        commands.offer(WorldCommand.Pan(dx, dy))
                        lastTouchX = x
                        lastTouchY = y
                    }
                }
            }
            MotionEvent.ACTION_POINTER_UP -> {
                val released = event.getPointerId(event.actionIndex)
                if (released == secondaryPointerId) secondaryPointerId = -1
                if (released == primaryPointerId) {
                    primaryPointerId = secondaryPointerId
                    secondaryPointerId = -1
                }
                previousPinchDistance = 0f
            }
            MotionEvent.ACTION_UP -> {
                if (!dragged) commands.offer(WorldCommand.Tap(event.x, event.y))
                primaryPointerId = -1
                secondaryPointerId = -1
                previousPinchDistance = 0f
                performClick()
            }
            MotionEvent.ACTION_CANCEL -> {
                primaryPointerId = -1
                secondaryPointerId = -1
                previousPinchDistance = 0f
            }
        }
        return true
    }

    override fun performClick(): Boolean {
        super.performClick()
        return true
    }

    private fun currentPinchDistance(event: MotionEvent): Float {
        if (event.pointerCount < 2) return 0f
        return hypot(event.getX(1) - event.getX(0), event.getY(1) - event.getY(0))
    }

    private fun centerOnPlayer() {
        val capital = simulation.provinces.firstOrNull { it.ownerId == PLAYER_NATION_ID && it.capital }
            ?: simulation.provinces.firstOrNull { it.ownerId == PLAYER_NATION_ID }
            ?: return
        cameraX = capital.center.x
        cameraY = capital.center.y
        zoom = max(zoom, 0.72f)
    }

    private fun fitWorldToScreen() {
        if (width <= 0 || height <= 0) return
        val horizontal = width / WorldDefinition.WORLD_WIDTH
        val vertical = height / WorldDefinition.WORLD_HEIGHT
        zoom = min(horizontal, vertical).coerceIn(0.34f, 0.72f)
        cameraX = WorldDefinition.WORLD_WIDTH * 0.5f
        cameraY = WorldDefinition.WORLD_HEIGHT * 0.5f
    }

    private fun clampCamera() {
        val halfWidth = width / (2f * zoom)
        val halfHeight = height / (2f * zoom)
        cameraX = cameraX.coerceIn(-halfWidth * 0.15f, WorldDefinition.WORLD_WIDTH + halfWidth * 0.15f)
        cameraY = cameraY.coerceIn(-halfHeight * 0.15f, WorldDefinition.WORLD_HEIGHT + halfHeight * 0.15f)
    }

    private fun provinceScreenPath(province: ProvinceState): Path = Path().apply {
        province.polygon.forEachIndexed { index, point ->
            if (index == 0) moveTo(sx(point.x), sy(point.y)) else lineTo(sx(point.x), sy(point.y))
        }
        close()
    }

    private fun pointInPolygon(point: Vec2, polygon: List<Vec2>): Boolean {
        var inside = false
        var previous = polygon.last()
        for (current in polygon) {
            val crosses = (current.y > point.y) != (previous.y > point.y) &&
                point.x < (previous.x - current.x) * (point.y - current.y) /
                ((previous.y - current.y).takeIf { kotlin.math.abs(it) > 0.0001f } ?: 0.0001f) + current.x
            if (crosses) inside = !inside
            previous = current
        }
        return inside
    }

    private fun screenToWorld(x: Float, y: Float): Vec2 = Vec2(
        (x - width / 2f) / zoom + cameraX,
        (y - height / 2f) / zoom + cameraY
    )

    private fun sx(worldX: Float): Float = (worldX - cameraX) * zoom + width / 2f
    private fun sy(worldY: Float): Float = (worldY - cameraY) * zoom + height / 2f
    private fun visible(x: Float, y: Float, radius: Float): Boolean = x > -radius && x < width + radius && y > -radius && y < height + radius

    private fun drawText(canvas: Canvas, text: String, x: Float, y: Float, size: Float, color: Int) {
        textPaint.textAlign = Paint.Align.LEFT
        textPaint.textSize = size
        textPaint.color = color
        canvas.drawText(text, x, y, textPaint)
    }

    private fun drawCentered(canvas: Canvas, text: String, x: Float, y: Float, size: Float, color: Int) {
        textPaint.textAlign = Paint.Align.CENTER
        textPaint.textSize = size
        textPaint.color = color
        text.split("\n").forEachIndexed { index, line ->
            canvas.drawText(line, x, y + index * (size + 2f), textPaint)
        }
        textPaint.textAlign = Paint.Align.LEFT
    }

    private fun shaded(color: Int, factor: Float): Int = Color.rgb(
        (Color.red(color) * factor).toInt().coerceIn(0, 255),
        (Color.green(color) * factor).toInt().coerceIn(0, 255),
        (Color.blue(color) * factor).toInt().coerceIn(0, 255)
    )

    private fun lerp(a: Float, b: Float, t: Float): Float = a + (b - a) * t
    private fun smoothStep(t: Float): Float = t * t * (3f - 2f * t)

    private fun drawFailure(error: Throwable) {
        try {
            if (!holder.surface.isValid) return
            val canvas = holder.lockCanvas() ?: return
            try {
                canvas.drawColor(Color.rgb(13, 18, 22))
                drawCentered(canvas, "KAMPANYA GÜVENLİ MODDA DURDU", width / 2f, height / 2f, 26f, Color.WHITE)
                drawCentered(canvas, error.javaClass.simpleName, width / 2f, height / 2f + 38f, 18f, Color.LTGRAY)
            } finally {
                if (holder.surface.isValid) holder.unlockCanvasAndPost(canvas)
            }
        } catch (ignored: Throwable) {
            Log.e(TAG, "Unable to draw failure screen", ignored)
        }
    }

    private data class ActionButton(val rect: RectF, val action: String)

    private sealed interface WorldCommand {
        data class Tap(val x: Float, val y: Float) : WorldCommand
        data class Action(val name: String) : WorldCommand
        data class Pan(val dx: Float, val dy: Float) : WorldCommand
        data class Zoom(val factor: Float, val focusX: Float, val focusY: Float) : WorldCommand
        data object Restart : WorldCommand
    }

    companion object {
        private const val TAG = "CrownfallWorldView"
        private const val PLAYER_NATION_ID = 0
    }
}
