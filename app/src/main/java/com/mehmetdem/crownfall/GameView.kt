package com.mehmetdem.crownfall

import android.content.Context
import android.graphics.*
import android.util.Log
import android.view.MotionEvent
import android.view.SurfaceHolder
import android.view.SurfaceView
import java.util.concurrent.ConcurrentLinkedQueue
import kotlin.math.*
import kotlin.random.Random

class GameView(context: Context) : SurfaceView(context), SurfaceHolder.Callback, Runnable {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
    }

    @Volatile private var running = false
    private var loopThread: Thread? = null
    private var lastNs = 0L
    private val targetFrameNs = 16_666_667L

    private val worldSize = 4200f
    private var camX = 2100f
    private var camY = 2100f
    private var zoom = 0.72f

    @Volatile private var joyId = -1
    @Volatile private var joyBaseX = 150f
    @Volatile private var joyBaseY = 650f
    @Volatile private var joyX = 0f
    @Volatile private var joyY = 0f
    @Volatile private var gameOver = false

    private var victory = false
    private var selectedBuild = ""
    private val teams = Array(4) { Team(it) }
    private val units = mutableListOf<UnitEntity>()
    private val buildings = mutableListOf<Building>()
    private val gold = mutableListOf<GoldPile>()
    private val inputCommands = ConcurrentLinkedQueue<String>()
    @Volatile private var buttonSnapshot: List<ActionButton> = emptyList()
    private val rng = Random(7319)

    init {
        holder.addCallback(this)
        isFocusable = true
        isFocusableInTouchMode = true
        keepScreenOn = true

        teams[0].apply { color = Color.rgb(55, 145, 235); gold = 650; cap = 18; leaderX = 800f; leaderY = 2100f }
        teams[1].apply { color = Color.rgb(215, 68, 60); gold = 500; cap = 18; leaderX = 3400f; leaderY = 750f }
        teams[2].apply { color = Color.rgb(154, 81, 210); gold = 500; cap = 18; leaderX = 3400f; leaderY = 3400f }
        teams[3].apply { color = Color.rgb(230, 150, 40); gold = 500; cap = 18; leaderX = 2100f; leaderY = 500f }

        for (team in teams) {
            buildings += Building(team.id, "KEEP", team.leaderX, team.leaderY, 1500f, 140f)
            repeat(5) { spawnUnit(team.id, if (it == 4) "ARCHER" else "SWORD") }
        }
        repeat(110) {
            gold += GoldPile(
                rng.nextFloat() * (worldSize - 240f) + 120f,
                rng.nextFloat() * (worldSize - 240f) + 120f,
                rng.nextInt(28, 65)
            )
        }
    }

    override fun surfaceCreated(surfaceHolder: SurfaceHolder) {
        if (running) return
        running = true
        lastNs = System.nanoTime()
        loopThread = Thread(this, "CrownfallGameLoop").also { it.start() }
    }

    override fun surfaceDestroyed(surfaceHolder: SurfaceHolder) {
        running = false
        loopThread?.interrupt()
        try {
            loopThread?.join(1000)
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
        }
        loopThread = null
    }

    override fun surfaceChanged(surfaceHolder: SurfaceHolder, format: Int, width: Int, height: Int) {
        if (joyId < 0) {
            joyBaseX = 150f
            joyBaseY = height - 135f
        }
    }

    override fun run() {
        while (running) {
            val frameStart = System.nanoTime()
            try {
                val dt = ((frameStart - lastNs) / 1_000_000_000f).coerceIn(0f, 0.034f)
                lastNs = frameStart
                updateGame(dt)
                drawGame()
            } catch (error: Throwable) {
                Log.e(TAG, "Game loop stopped safely", error)
                drawFailureScreen(error)
                running = false
                break
            }

            val remainingNs = targetFrameNs - (System.nanoTime() - frameStart)
            if (remainingNs > 1_000_000L) {
                try {
                    Thread.sleep(remainingNs / 1_000_000L)
                } catch (_: InterruptedException) {
                    if (!running) break
                }
            }
        }
    }

    private fun updateGame(dt: Float) {
        drainInputCommands()
        if (gameOver) return

        val player = teams[0]
        val speed = 360f
        player.leaderX = (player.leaderX + joyX * speed * dt).coerceIn(60f, worldSize - 60f)
        player.leaderY = (player.leaderY + joyY * speed * dt).coerceIn(60f, worldSize - 60f)
        camX += (player.leaderX - camX) * min(1f, dt * 4.8f)
        camY += (player.leaderY - camY) * min(1f, dt * 4.8f)

        val goldIterator = gold.iterator()
        while (goldIterator.hasNext()) {
            val pile = goldIterator.next()
            if (dist(player.leaderX, player.leaderY, pile.x, pile.y) < 78f) {
                player.gold += pile.value
                goldIterator.remove()
            }
        }

        for (building in buildings) {
            if (building.hp <= 0f) continue
            if (building.kind == "MINE") {
                building.timer += dt
                if (building.timer >= 2.5f) {
                    teams[building.team].gold += 12
                    building.timer = 0f
                }
            }
            if (building.kind == "TOWER") {
                building.timer -= dt
                if (building.timer <= 0f) {
                    val target = units.asSequence()
                        .filter { it.alive && it.team != building.team }
                        .minByOrNull { dist(it.x, it.y, building.x, building.y) }
                    if (target != null && dist(target.x, target.y, building.x, building.y) < 480f) {
                        target.hp -= 32f
                        building.timer = 0.65f
                    }
                }
            }
        }

        for (teamId in 1..3) updateBot(teams[teamId], dt)
        updateUnits(dt)
        units.removeAll { !it.alive }
        buildings.removeAll { it.hp <= 0f }

        for (team in teams) {
            if (team.keepAlive && buildings.none { it.team == team.id && it.kind == "KEEP" }) {
                team.keepAlive = false
            }
        }
        if (!teams[0].keepAlive) {
            gameOver = true
            victory = false
        }
        if ((1..3).none { teams[it].keepAlive }) {
            gameOver = true
            victory = true
        }
    }

    private fun drainInputCommands() {
        while (true) {
            val command = inputCommands.poll() ?: break
            if (command == "RESTART") restart() else activate(command)
        }
    }

    private fun updateBot(team: Team, dt: Float) {
        if (!team.keepAlive) return
        team.aiTimer -= dt

        val enemyKeep = buildings
            .filter { it.team != team.id && it.kind == "KEEP" }
            .minByOrNull { dist(team.leaderX, team.leaderY, it.x, it.y) }

        if (enemyKeep != null) {
            val dx = enemyKeep.x - team.leaderX
            val dy = enemyKeep.y - team.leaderY
            val distance = hypot(dx, dy).coerceAtLeast(1f)
            val aggression = if (units.count { it.team == team.id } >= 9) 1f else 0.22f
            team.leaderX = (team.leaderX + dx / distance * 135f * aggression * dt).coerceIn(50f, worldSize - 50f)
            team.leaderY = (team.leaderY + dy / distance * 135f * aggression * dt).coerceIn(50f, worldSize - 50f)
        }

        val nearGold = gold.minByOrNull { dist(team.leaderX, team.leaderY, it.x, it.y) }
        if (nearGold != null && team.gold < 250) {
            val dx = nearGold.x - team.leaderX
            val dy = nearGold.y - team.leaderY
            val distance = hypot(dx, dy).coerceAtLeast(1f)
            team.leaderX += dx / distance * 150f * dt
            team.leaderY += dy / distance * 150f * dt
            if (distance < 75f) {
                team.gold += nearGold.value
                gold.remove(nearGold)
            }
        }

        if (team.aiTimer <= 0f) {
            team.aiTimer = rng.nextFloat() * 1.4f + 0.7f
            when {
                team.population < team.cap && team.gold >= 90 -> {
                    val kind = if (team.gold >= 240 && rng.nextFloat() > 0.72f) {
                        "KNIGHT"
                    } else if (rng.nextBoolean()) {
                        "ARCHER"
                    } else {
                        "SWORD"
                    }
                    val cost = unitCost(kind)
                    if (team.gold >= cost) {
                        team.gold -= cost
                        spawnUnit(team.id, kind)
                    }
                }
                team.gold >= 320 && buildings.count { it.team == team.id && it.kind == "MINE" } < 2 -> {
                    build(team.id, "MINE", team.leaderX + rng.nextInt(-180, 180), team.leaderY + rng.nextInt(-180, 180))
                }
                team.gold >= 280 && buildings.count { it.team == team.id && it.kind == "TOWER" } < 3 -> {
                    build(team.id, "TOWER", team.leaderX + rng.nextInt(-220, 220), team.leaderY + rng.nextInt(-220, 220))
                }
                team.population >= team.cap - 2 && team.gold >= 220 -> {
                    build(team.id, "HOUSE", team.leaderX + rng.nextInt(-180, 180), team.leaderY + rng.nextInt(-180, 180))
                }
            }
        }
    }

    private fun updateUnits(dt: Float) {
        for ((index, unit) in units.withIndex()) {
            if (!unit.alive) continue
            unit.cooldown -= dt
            val leader = teams[unit.team]
            val enemyUnit = units.asSequence()
                .filter { it.alive && it.team != unit.team && dist(it.x, it.y, unit.x, unit.y) < unit.sight }
                .minByOrNull { dist(it.x, it.y, unit.x, unit.y) }
            val enemyBuilding = buildings.asSequence()
                .filter { it.hp > 0 && it.team != unit.team && dist(it.x, it.y, unit.x, unit.y) < unit.sight }
                .minByOrNull { dist(it.x, it.y, unit.x, unit.y) }

            val targetX: Float
            val targetY: Float
            val targetRadius: Float
            if (enemyUnit != null) {
                targetX = enemyUnit.x
                targetY = enemyUnit.y
                targetRadius = 20f
            } else if (enemyBuilding != null) {
                targetX = enemyBuilding.x
                targetY = enemyBuilding.y
                targetRadius = enemyBuilding.radius
            } else {
                val slot = index % 22
                val ring = 72f + (slot / 8) * 48f
                val angle = (slot % 8) / 8f * (Math.PI * 2).toFloat()
                targetX = leader.leaderX + cos(angle) * ring
                targetY = leader.leaderY + sin(angle) * ring
                targetRadius = 0f
            }

            val dx = targetX - unit.x
            val dy = targetY - unit.y
            val distance = hypot(dx, dy).coerceAtLeast(1f)
            if ((enemyUnit != null || enemyBuilding != null) && distance <= unit.range + targetRadius) {
                if (unit.cooldown <= 0f) {
                    if (enemyUnit != null) enemyUnit.hp -= unit.damage else enemyBuilding?.let { it.hp -= unit.damage }
                    unit.cooldown = unit.attackDelay
                }
            } else {
                unit.x += dx / distance * unit.speed * dt
                unit.y += dy / distance * unit.speed * dt
            }

            if (unit.hp <= 0f) {
                unit.alive = false
                teams[unit.team].population = max(0, teams[unit.team].population - 1)
            }
        }
    }

    private fun spawnUnit(teamId: Int, kind: String) {
        val team = teams[teamId]
        if (team.population >= team.cap) return
        val angle = rng.nextFloat() * 6.283f
        val unit = when (kind) {
            "ARCHER" -> UnitEntity(teamId, kind, team.leaderX + cos(angle) * 80f, team.leaderY + sin(angle) * 80f, 82f, 82f, 18f, 260f, 320f, 1.05f)
            "KNIGHT" -> UnitEntity(teamId, kind, team.leaderX + cos(angle) * 80f, team.leaderY + sin(angle) * 80f, 170f, 170f, 34f, 65f, 205f, 0.72f)
            "MAGE" -> UnitEntity(teamId, kind, team.leaderX + cos(angle) * 80f, team.leaderY + sin(angle) * 80f, 95f, 95f, 38f, 300f, 300f, 1.3f)
            "DRAGON" -> UnitEntity(teamId, kind, team.leaderX + cos(angle) * 80f, team.leaderY + sin(angle) * 80f, 420f, 420f, 68f, 360f, 270f, 1.45f)
            else -> UnitEntity(teamId, "SWORD", team.leaderX + cos(angle) * 80f, team.leaderY + sin(angle) * 80f, 115f, 115f, 25f, 55f, 230f, 0.68f)
        }
        units += unit
        team.population++
    }

    private fun unitCost(kind: String): Int = when (kind) {
        "ARCHER" -> 110
        "KNIGHT" -> 240
        "MAGE" -> 320
        "DRAGON" -> 900
        else -> 90
    }

    private fun build(teamId: Int, kind: String, x: Float, y: Float) {
        val team = teams[teamId]
        val cost = when (kind) {
            "HOUSE" -> 220
            "MINE" -> 320
            "TOWER" -> 280
            else -> 0
        }
        if (team.gold < cost) return
        team.gold -= cost
        val building = when (kind) {
            "HOUSE" -> Building(teamId, kind, x, y, 480f, 68f)
            "MINE" -> Building(teamId, kind, x, y, 620f, 72f)
            else -> Building(teamId, "TOWER", x, y, 700f, 62f)
        }
        buildings += building
        if (kind == "HOUSE") team.cap += 10
    }

    private fun drawGame() {
        if (!holder.surface.isValid) return
        val canvas = holder.lockCanvas() ?: return
        try {
            canvas.drawColor(Color.rgb(78, 122, 70))
            drawTerrain(canvas)
            for (pile in gold) drawGold(canvas, pile)
            for (building in buildings) drawBuilding(canvas, building)
            for (unit in units) drawUnit(canvas, unit)
            drawLeader(canvas, teams[0])
            for (teamId in 1..3) if (teams[teamId].keepAlive) drawLeader(canvas, teams[teamId])
            drawHud(canvas)
        } finally {
            if (holder.surface.isValid) holder.unlockCanvasAndPost(canvas)
        }
    }

    private fun drawFailureScreen(error: Throwable) {
        try {
            if (!holder.surface.isValid) return
            val canvas = holder.lockCanvas() ?: return
            try {
                canvas.drawColor(Color.rgb(20, 24, 20))
                drawCentered(canvas, "OYUN GÜVENLİ MODDA DURDURULDU", width / 2f, height / 2f - 20f, 28f, Color.WHITE)
                drawCentered(canvas, error.javaClass.simpleName, width / 2f, height / 2f + 28f, 20f, Color.LTGRAY)
            } finally {
                if (holder.surface.isValid) holder.unlockCanvasAndPost(canvas)
            }
        } catch (ignored: Throwable) {
            Log.e(TAG, "Unable to draw recovery screen", ignored)
        }
    }

    private fun drawTerrain(canvas: Canvas) {
        paint.style = Paint.Style.FILL
        paint.color = Color.rgb(68, 109, 61)
        val grid = 260f
        var x = floor((camX - width / (2 * zoom)) / grid) * grid
        while (x < camX + width / (2 * zoom)) {
            var y = floor((camY - height / (2 * zoom)) / grid) * grid
            while (y < camY + height / (2 * zoom)) {
                if (((x / grid).toInt() + (y / grid).toInt()) % 2 == 0) {
                    canvas.drawRect(sx(x), sy(y), sx(x + grid), sy(y + grid), paint)
                }
                y += grid
            }
            x += grid
        }
        paint.color = Color.rgb(43, 88, 122)
        val riverX = worldSize * 0.53f
        canvas.drawRect(sx(riverX - 90), sy(0f), sx(riverX + 90), sy(worldSize), paint)
        paint.color = Color.rgb(126, 103, 69)
        canvas.drawRect(sx(riverX - 120), sy(1940f), sx(riverX + 120), sy(2260f), paint)
    }

    private fun drawGold(canvas: Canvas, pile: GoldPile) {
        val x = sx(pile.x)
        val y = sy(pile.y)
        if (!visible(x, y, 30f)) return
        paint.color = Color.rgb(249, 199, 52)
        canvas.drawCircle(x, y, 12f * zoom, paint)
        paint.color = Color.rgb(255, 231, 115)
        canvas.drawCircle(x - 4 * zoom, y - 4 * zoom, 4 * zoom, paint)
    }

    private fun drawLeader(canvas: Canvas, team: Team) {
        val x = sx(team.leaderX)
        val y = sy(team.leaderY)
        if (!visible(x, y, 70f)) return
        paint.color = team.color
        canvas.drawCircle(x, y, 28f * zoom, paint)
        paint.style = Paint.Style.STROKE
        paint.strokeWidth = 5f
        paint.color = Color.WHITE
        canvas.drawCircle(x, y, 32f * zoom, paint)
        paint.style = Paint.Style.FILL
    }

    private fun drawUnit(canvas: Canvas, unit: UnitEntity) {
        val x = sx(unit.x)
        val y = sy(unit.y)
        if (!visible(x, y, 40f)) return
        paint.color = teams[unit.team].color
        val radius = if (unit.kind == "DRAGON") 24f else if (unit.kind == "KNIGHT") 17f else 13f
        canvas.drawCircle(x, y, radius * zoom, paint)
        paint.color = Color.rgb(25, 25, 25)
        paint.style = Paint.Style.STROKE
        paint.strokeWidth = 2f
        canvas.drawCircle(x, y, radius * zoom, paint)
        paint.style = Paint.Style.FILL
        drawBar(canvas, x - 17 * zoom, y - 24 * zoom, 34 * zoom, 4 * zoom, unit.hp / unit.maxHp)
    }

    private fun drawBuilding(canvas: Canvas, building: Building) {
        val x = sx(building.x)
        val y = sy(building.y)
        if (!visible(x, y, building.radius * zoom)) return
        paint.color = teams[building.team].color
        val radius = building.radius * zoom
        when (building.kind) {
            "KEEP" -> canvas.drawRect(x - radius, y - radius, x + radius, y + radius, paint)
            "TOWER" -> canvas.drawCircle(x, y, radius, paint)
            "HOUSE" -> {
                canvas.drawRect(x - radius, y - radius * 0.55f, x + radius, y + radius, paint)
                val roof = Path().apply {
                    moveTo(x - radius, y - radius * 0.55f)
                    lineTo(x, y - radius * 1.35f)
                    lineTo(x + radius, y - radius * 0.55f)
                    close()
                }
                paint.color = Color.rgb(82, 52, 35)
                canvas.drawPath(roof, paint)
            }
            else -> {
                paint.color = Color.rgb(86, 88, 92)
                canvas.drawCircle(x, y, radius, paint)
                paint.color = teams[building.team].color
                canvas.drawCircle(x, y, radius * 0.45f, paint)
            }
        }
        drawBar(canvas, x - radius, y - radius - 10f, radius * 2, 6f, building.hp / building.maxHp)
    }

    private fun drawBar(canvas: Canvas, x: Float, y: Float, width: Float, height: Float, value: Float) {
        paint.color = Color.rgb(35, 25, 25)
        canvas.drawRect(x, y, x + width, y + height, paint)
        paint.color = Color.rgb(72, 220, 93)
        canvas.drawRect(x + 1, y + 1, x + 1 + (width - 2) * value.coerceIn(0f, 1f), y + height - 1, paint)
    }

    private fun drawHud(canvas: Canvas) {
        val nextButtons = ArrayList<ActionButton>(9)
        paint.color = Color.argb(200, 20, 25, 20)
        canvas.drawRoundRect(18f, 16f, 390f, 104f, 18f, 18f, paint)
        val player = teams[0]
        drawText(canvas, "ALTIN  ${player.gold}", 38f, 52f, 25f, Color.rgb(255, 210, 62))
        drawText(canvas, "ORDU  ${player.population}/${player.cap}", 38f, 86f, 23f, Color.WHITE)
        drawMinimap(canvas)

        if (joyId < 0) {
            joyBaseX = 150f
            joyBaseY = height - 135f
        }
        paint.color = Color.argb(90, 255, 255, 255)
        canvas.drawCircle(joyBaseX, joyBaseY, 88f, paint)
        paint.color = Color.argb(170, 255, 255, 255)
        canvas.drawCircle(joyBaseX + joyX * 54f, joyBaseY + joyY * 54f, 40f, paint)

        val labels = listOf(
            "KILIÇ\n90" to "SWORD",
            "OKÇU\n110" to "ARCHER",
            "ŞÖVALYE\n240" to "KNIGHT",
            "BÜYÜCÜ\n320" to "MAGE",
            "EV\n220" to "HOUSE",
            "MADEN\n320" to "MINE",
            "KULE\n280" to "TOWER"
        )
        val buttonWidth = 108f
        val gap = 10f
        val startX = width - (buttonWidth + gap) * 4 - 20f
        labels.forEachIndexed { index, pair ->
            val row = index / 4
            val column = index % 4
            val x = startX + column * (buttonWidth + gap)
            val y = height - 160f + row * 78f
            val rect = RectF(x, y, x + buttonWidth, y + 68f)
            nextButtons += ActionButton(rect, pair.second)
            paint.color = if (selectedBuild == pair.second) Color.rgb(184, 137, 48) else Color.argb(220, 28, 35, 29)
            canvas.drawRoundRect(rect, 13f, 13f, paint)
            drawCentered(canvas, pair.first, x + buttonWidth / 2, y + 26f, 17f, Color.WHITE)
        }

        val minus = RectF(width - 150f, 20f, width - 90f, 78f)
        val plus = RectF(width - 78f, 20f, width - 18f, 78f)
        nextButtons += ActionButton(minus, "ZOOM_OUT")
        nextButtons += ActionButton(plus, "ZOOM_IN")
        paint.color = Color.argb(220, 25, 30, 25)
        canvas.drawRoundRect(minus, 12f, 12f, paint)
        canvas.drawRoundRect(plus, 12f, 12f, paint)
        drawCentered(canvas, "−", minus.centerX(), 56f, 34f, Color.WHITE)
        drawCentered(canvas, "+", plus.centerX(), 56f, 32f, Color.WHITE)
        buttonSnapshot = nextButtons

        if (gameOver) {
            paint.color = Color.argb(220, 10, 14, 10)
            canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), paint)
            drawCentered(
                canvas,
                if (victory) "ZAFER" else "KRALLIĞIN YIKILDI",
                width / 2f,
                height / 2f - 20f,
                52f,
                if (victory) Color.rgb(255, 214, 70) else Color.rgb(240, 80, 75)
            )
            drawCentered(canvas, "Yeniden başlatmak için dokun", width / 2f, height / 2f + 42f, 24f, Color.WHITE)
        }
    }

    private fun drawMinimap(canvas: Canvas) {
        val size = 150f
        val left = 410f
        val top = 18f
        paint.color = Color.argb(190, 16, 20, 16)
        canvas.drawRoundRect(left, top, left + size, top + size * 0.58f, 10f, 10f, paint)
        for (team in teams) {
            if (!team.keepAlive) continue
            paint.color = team.color
            canvas.drawCircle(
                left + team.leaderX / worldSize * size,
                top + team.leaderY / worldSize * (size * 0.58f),
                5f,
                paint
            )
        }
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        if (gameOver && event.actionMasked == MotionEvent.ACTION_DOWN) {
            inputCommands.offer("RESTART")
            performClick()
            return true
        }

        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN, MotionEvent.ACTION_POINTER_DOWN -> {
                val index = event.actionIndex
                val x = event.getX(index)
                val y = event.getY(index)
                val pointerId = event.getPointerId(index)
                val button = buttonSnapshot.firstOrNull { it.rect.contains(x, y) }
                if (button != null) {
                    inputCommands.offer(button.action)
                    performClick()
                    return true
                }
                if (x < width * 0.42f) {
                    joyId = pointerId
                    joyBaseX = x
                    joyBaseY = y
                    updateJoy(x, y)
                }
            }
            MotionEvent.ACTION_MOVE -> {
                val activeId = joyId
                if (activeId >= 0) {
                    val index = event.findPointerIndex(activeId)
                    if (index >= 0) updateJoy(event.getX(index), event.getY(index))
                }
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_POINTER_UP -> {
                val pointerId = event.getPointerId(event.actionIndex)
                if (pointerId == joyId) resetJoystick()
                performClick()
            }
            MotionEvent.ACTION_CANCEL -> resetJoystick()
        }
        return true
    }

    override fun performClick(): Boolean {
        super.performClick()
        return true
    }

    private fun resetJoystick() {
        joyId = -1
        joyX = 0f
        joyY = 0f
    }

    private fun updateJoy(x: Float, y: Float) {
        val dx = x - joyBaseX
        val dy = y - joyBaseY
        val distance = hypot(dx, dy)
        if (distance < 1f) {
            joyX = 0f
            joyY = 0f
        } else {
            val magnitude = min(1f, distance / 82f)
            joyX = dx / distance * magnitude
            joyY = dy / distance * magnitude
        }
    }

    private fun activate(action: String) {
        val player = teams[0]
        when (action) {
            "ZOOM_IN" -> zoom = (zoom + 0.12f).coerceAtMost(1.35f)
            "ZOOM_OUT" -> zoom = (zoom - 0.12f).coerceAtLeast(0.42f)
            "HOUSE", "MINE", "TOWER" -> {
                selectedBuild = action
                val angle = rng.nextFloat() * (Math.PI * 2).toFloat()
                build(0, action, player.leaderX + cos(angle) * 105f, player.leaderY + sin(angle) * 105f)
                selectedBuild = ""
            }
            else -> {
                val cost = unitCost(action)
                if (player.gold >= cost && player.population < player.cap) {
                    player.gold -= cost
                    spawnUnit(0, action)
                }
            }
        }
    }

    private fun restart() {
        units.clear()
        buildings.clear()
        gold.clear()
        gameOver = false
        victory = false
        teams.forEachIndexed { index, team ->
            team.gold = if (index == 0) 650 else 500
            team.cap = 18
            team.population = 0
            team.keepAlive = true
            team.aiTimer = 1f
        }
        val positions = arrayOf(800f to 2100f, 3400f to 750f, 3400f to 3400f, 2100f to 500f)
        teams.forEachIndexed { index, team ->
            team.leaderX = positions[index].first
            team.leaderY = positions[index].second
            buildings += Building(index, "KEEP", team.leaderX, team.leaderY, 1500f, 140f)
            repeat(5) { spawnUnit(index, if (it == 4) "ARCHER" else "SWORD") }
        }
        repeat(110) {
            gold += GoldPile(
                rng.nextFloat() * (worldSize - 240f) + 120f,
                rng.nextFloat() * (worldSize - 240f) + 120f,
                rng.nextInt(28, 65)
            )
        }
    }

    private fun sx(x: Float) = (x - camX) * zoom + width / 2f
    private fun sy(y: Float) = (y - camY) * zoom + height / 2f
    private fun visible(x: Float, y: Float, radius: Float) = x > -radius && x < width + radius && y > -radius && y < height + radius
    private fun dist(x1: Float, y1: Float, x2: Float, y2: Float) = hypot(x2 - x1, y2 - y1)

    private fun drawText(canvas: Canvas, text: String, x: Float, y: Float, size: Float, color: Int) {
        textPaint.textSize = size
        textPaint.color = color
        canvas.drawText(text, x, y, textPaint)
    }

    private fun drawCentered(canvas: Canvas, text: String, x: Float, y: Float, size: Float, color: Int) {
        textPaint.textSize = size
        textPaint.color = color
        textPaint.textAlign = Paint.Align.CENTER
        text.split("\n").forEachIndexed { index, line ->
            canvas.drawText(line, x, y + index * (size + 2), textPaint)
        }
        textPaint.textAlign = Paint.Align.LEFT
    }

    data class Team(
        val id: Int,
        var color: Int = Color.WHITE,
        var gold: Int = 0,
        var cap: Int = 0,
        var population: Int = 0,
        var leaderX: Float = 0f,
        var leaderY: Float = 0f,
        var aiTimer: Float = 1f,
        var keepAlive: Boolean = true
    )

    data class UnitEntity(
        val team: Int,
        val kind: String,
        var x: Float,
        var y: Float,
        var hp: Float,
        val maxHp: Float,
        val damage: Float,
        val range: Float,
        val speed: Float,
        val attackDelay: Float,
        val sight: Float = 520f,
        var cooldown: Float = 0f,
        var alive: Boolean = true
    )

    data class Building(
        val team: Int,
        val kind: String,
        val x: Float,
        val y: Float,
        var hp: Float,
        val radius: Float,
        val maxHp: Float = hp,
        var timer: Float = 0f
    )

    data class GoldPile(val x: Float, val y: Float, val value: Int)
    data class ActionButton(val rect: RectF, val action: String)

    companion object {
        private const val TAG = "CrownfallGameView"
    }
}
