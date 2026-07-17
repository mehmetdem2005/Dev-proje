package com.mehmetdem.crownfall

import android.content.Context
import android.graphics.*
import android.view.MotionEvent
import android.view.SurfaceHolder
import android.view.SurfaceView
import kotlin.math.*
import kotlin.random.Random

class GameView(context: Context) : SurfaceView(context), SurfaceHolder.Callback, Runnable {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD) }
    private var running = false
    private var loopThread: Thread? = null
    private var lastNs = 0L
    private val worldSize = 4200f
    private var camX = 2100f
    private var camY = 2100f
    private var zoom = 0.72f
    private var joyId = -1
    private var joyBaseX = 150f
    private var joyBaseY = 650f
    private var joyX = 0f
    private var joyY = 0f
    private var gameOver = false
    private var victory = false
    private var selectedBuild = ""
    private val teams = Array(4) { Team(it) }
    private val units = mutableListOf<UnitEntity>()
    private val buildings = mutableListOf<Building>()
    private val gold = mutableListOf<GoldPile>()
    private val buttons = mutableListOf<ActionButton>()
    private val rng = Random(7319)

    init {
        holder.addCallback(this)
        isFocusable = true
        teams[0].apply { color = Color.rgb(55, 145, 235); gold = 650; cap = 18; leaderX = 800f; leaderY = 2100f }
        teams[1].apply { color = Color.rgb(215, 68, 60); gold = 500; cap = 18; leaderX = 3400f; leaderY = 750f }
        teams[2].apply { color = Color.rgb(154, 81, 210); gold = 500; cap = 18; leaderX = 3400f; leaderY = 3400f }
        teams[3].apply { color = Color.rgb(230, 150, 40); gold = 500; cap = 18; leaderX = 2100f; leaderY = 500f }
        for (t in teams) {
            buildings += Building(t.id, "KEEP", t.leaderX, t.leaderY, 1500f, 140f)
            repeat(5) { spawnUnit(t.id, if (it == 4) "ARCHER" else "SWORD") }
        }
        repeat(110) {
            gold += GoldPile(rng.nextFloat() * (worldSize - 240f) + 120f, rng.nextFloat() * (worldSize - 240f) + 120f, rng.nextInt(28, 65))
        }
    }

    override fun surfaceCreated(holder: SurfaceHolder) {
        running = true
        lastNs = System.nanoTime()
        loopThread = Thread(this, "CrownfallGameLoop").also { it.start() }
    }

    override fun surfaceDestroyed(holder: SurfaceHolder) {
        running = false
        loopThread?.join(700)
    }

    override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) = Unit

    override fun run() {
        while (running) {
            val now = System.nanoTime()
            val dt = ((now - lastNs) / 1_000_000_000f).coerceIn(0f, 0.034f)
            lastNs = now
            updateGame(dt)
            drawGame()
            Thread.sleep(8)
        }
    }

    private fun updateGame(dt: Float) {
        if (gameOver) return
        val player = teams[0]
        val speed = 360f
        player.leaderX = (player.leaderX + joyX * speed * dt).coerceIn(60f, worldSize - 60f)
        player.leaderY = (player.leaderY + joyY * speed * dt).coerceIn(60f, worldSize - 60f)
        camX += (player.leaderX - camX) * min(1f, dt * 4.8f)
        camY += (player.leaderY - camY) * min(1f, dt * 4.8f)

        val gi = gold.iterator()
        while (gi.hasNext()) {
            val g = gi.next()
            if (dist(player.leaderX, player.leaderY, g.x, g.y) < 78f) {
                player.gold += g.value
                gi.remove()
            }
        }

        for (b in buildings) {
            if (b.hp <= 0f) continue
            if (b.kind == "MINE") {
                b.timer += dt
                if (b.timer >= 2.5f) { teams[b.team].gold += 12; b.timer = 0f }
            }
            if (b.kind == "TOWER") {
                b.timer -= dt
                if (b.timer <= 0f) {
                    val target = units.asSequence().filter { it.alive && it.team != b.team }
                        .minByOrNull { dist(it.x, it.y, b.x, b.y) }
                    if (target != null && dist(target.x, target.y, b.x, b.y) < 480f) {
                        target.hp -= 32f
                        b.timer = 0.65f
                    }
                }
            }
        }

        for (t in 1..3) updateBot(teams[t], dt)
        updateUnits(dt)
        units.removeAll { !it.alive }
        buildings.removeAll { it.hp <= 0f }

        for (t in teams) {
            if (t.keepAlive && buildings.none { it.team == t.id && it.kind == "KEEP" }) t.keepAlive = false
        }
        if (!teams[0].keepAlive) { gameOver = true; victory = false }
        if ((1..3).none { teams[it].keepAlive }) { gameOver = true; victory = true }
    }

    private fun updateBot(t: Team, dt: Float) {
        if (!t.keepAlive) return
        t.aiTimer -= dt
        val enemyKeep = buildings.filter { it.team != t.id && it.kind == "KEEP" }.minByOrNull { dist(t.leaderX, t.leaderY, it.x, it.y) }
        if (enemyKeep != null) {
            val dx = enemyKeep.x - t.leaderX
            val dy = enemyKeep.y - t.leaderY
            val d = hypot(dx, dy).coerceAtLeast(1f)
            val aggression = if (units.count { it.team == t.id } >= 9) 1f else 0.22f
            t.leaderX = (t.leaderX + dx / d * 135f * aggression * dt).coerceIn(50f, worldSize - 50f)
            t.leaderY = (t.leaderY + dy / d * 135f * aggression * dt).coerceIn(50f, worldSize - 50f)
        }
        val nearGold = gold.minByOrNull { dist(t.leaderX, t.leaderY, it.x, it.y) }
        if (nearGold != null && t.gold < 250) {
            val dx = nearGold.x - t.leaderX; val dy = nearGold.y - t.leaderY; val d = hypot(dx,dy).coerceAtLeast(1f)
            t.leaderX += dx/d*150f*dt; t.leaderY += dy/d*150f*dt
            if (d < 75f) { t.gold += nearGold.value; gold.remove(nearGold) }
        }
        if (t.aiTimer <= 0f) {
            t.aiTimer = rng.nextFloat() * 1.4f + 0.7f
            when {
                t.population < t.cap && t.gold >= 90 -> {
                    val kind = if (t.gold >= 240 && rng.nextFloat() > .72f) "KNIGHT" else if (rng.nextBoolean()) "ARCHER" else "SWORD"
                    val cost = unitCost(kind)
                    if (t.gold >= cost) { t.gold -= cost; spawnUnit(t.id, kind) }
                }
                t.gold >= 320 && buildings.count { it.team == t.id && it.kind == "MINE" } < 2 -> build(t.id, "MINE", t.leaderX + rng.nextInt(-180,180), t.leaderY + rng.nextInt(-180,180))
                t.gold >= 280 && buildings.count { it.team == t.id && it.kind == "TOWER" } < 3 -> build(t.id, "TOWER", t.leaderX + rng.nextInt(-220,220), t.leaderY + rng.nextInt(-220,220))
                t.population >= t.cap - 2 && t.gold >= 220 -> build(t.id, "HOUSE", t.leaderX + rng.nextInt(-180,180), t.leaderY + rng.nextInt(-180,180))
            }
        }
    }

    private fun updateUnits(dt: Float) {
        for ((index, u) in units.withIndex()) {
            if (!u.alive) continue
            u.cooldown -= dt
            val leader = teams[u.team]
            val enemyUnit = units.asSequence().filter { it.alive && it.team != u.team && dist(it.x,it.y,u.x,u.y) < u.sight }
                .minByOrNull { dist(it.x,it.y,u.x,u.y) }
            val enemyBuilding = buildings.asSequence().filter { it.hp > 0 && it.team != u.team && dist(it.x,it.y,u.x,u.y) < u.sight }
                .minByOrNull { dist(it.x,it.y,u.x,u.y) }
            val tx: Float; val ty: Float; val targetRadius: Float
            if (enemyUnit != null) { tx = enemyUnit.x; ty = enemyUnit.y; targetRadius = 20f }
            else if (enemyBuilding != null) { tx = enemyBuilding.x; ty = enemyBuilding.y; targetRadius = enemyBuilding.radius }
            else {
                val slot = index % 22
                val ring = 72f + (slot / 8) * 48f
                val angle = (slot % 8) / 8f * (Math.PI * 2).toFloat()
                tx = leader.leaderX + cos(angle) * ring
                ty = leader.leaderY + sin(angle) * ring
                targetRadius = 0f
            }
            val dx = tx-u.x; val dy=ty-u.y; val d=hypot(dx,dy).coerceAtLeast(1f)
            if ((enemyUnit != null || enemyBuilding != null) && d <= u.range + targetRadius) {
                if (u.cooldown <= 0f) {
                    if (enemyUnit != null) enemyUnit.hp -= u.damage else enemyBuilding?.let { it.hp -= u.damage }
                    u.cooldown = u.attackDelay
                }
            } else {
                u.x += dx/d*u.speed*dt; u.y += dy/d*u.speed*dt
            }
            if (u.hp <= 0f) { u.alive = false; teams[u.team].population = max(0, teams[u.team].population-1) }
        }
    }

    private fun spawnUnit(team: Int, kind: String) {
        val t = teams[team]
        if (t.population >= t.cap) return
        val a = rng.nextFloat() * 6.283f
        val u = when(kind) {
            "ARCHER" -> UnitEntity(team,kind,t.leaderX+cos(a)*80f,t.leaderY+sin(a)*80f,82f,82f,18f,260f,320f,1.05f)
            "KNIGHT" -> UnitEntity(team,kind,t.leaderX+cos(a)*80f,t.leaderY+sin(a)*80f,170f,170f,34f,65f,205f,.72f)
            "MAGE" -> UnitEntity(team,kind,t.leaderX+cos(a)*80f,t.leaderY+sin(a)*80f,95f,95f,38f,300f,300f,1.3f)
            "DRAGON" -> UnitEntity(team,kind,t.leaderX+cos(a)*80f,t.leaderY+sin(a)*80f,420f,420f,68f,360f,270f,1.45f)
            else -> UnitEntity(team,"SWORD",t.leaderX+cos(a)*80f,t.leaderY+sin(a)*80f,115f,115f,25f,55f,230f,.68f)
        }
        units += u; t.population++
    }

    private fun unitCost(kind: String) = when(kind) { "ARCHER"->110; "KNIGHT"->240; "MAGE"->320; "DRAGON"->900; else->90 }

    private fun build(team:Int, kind:String, x:Float, y:Float) {
        val t=teams[team]
        val cost=when(kind){"HOUSE"->220;"MINE"->320;"TOWER"->280;else->0}
        if(t.gold<cost)return
        t.gold-=cost
        val b=when(kind){
            "HOUSE"->Building(team,kind,x,y,480f,68f)
            "MINE"->Building(team,kind,x,y,620f,72f)
            else->Building(team,"TOWER",x,y,700f,62f)
        }
        buildings+=b
        if(kind=="HOUSE")t.cap+=10
    }

    private fun drawGame() {
        val c = holder.lockCanvas() ?: return
        try {
            c.drawColor(Color.rgb(78,122,70))
            drawTerrain(c)
            for (g in gold) drawGold(c,g)
            for (b in buildings) drawBuilding(c,b)
            for (u in units) drawUnit(c,u)
            drawLeader(c,teams[0])
            for (i in 1..3) if(teams[i].keepAlive) drawLeader(c,teams[i])
            drawHud(c)
        } finally { holder.unlockCanvasAndPost(c) }
    }

    private fun drawTerrain(c:Canvas) {
        paint.style=Paint.Style.FILL
        paint.color=Color.rgb(68,109,61)
        val grid=260f
        var x=floor((camX-width/(2*zoom))/grid)*grid
        while(x<camX+width/(2*zoom)){ var y=floor((camY-height/(2*zoom))/grid)*grid; while(y<camY+height/(2*zoom)){
            if(((x/grid).toInt()+(y/grid).toInt())%2==0)c.drawRect(sx(x),sy(y),sx(x+grid),sy(y+grid),paint); y+=grid};x+=grid}
        paint.color=Color.rgb(43,88,122)
        val riverX=worldSize*.53f
        c.drawRect(sx(riverX-90),sy(0f),sx(riverX+90),sy(worldSize),paint)
        paint.color=Color.rgb(126,103,69)
        c.drawRect(sx(riverX-120),sy(1940f),sx(riverX+120),sy(2260f),paint)
    }

    private fun drawGold(c:Canvas,g:GoldPile){ val x=sx(g.x);val y=sy(g.y); if(!visible(x,y,30f))return; paint.color=Color.rgb(249,199,52);c.drawCircle(x,y,12f*zoom,paint);paint.color=Color.rgb(255,231,115);c.drawCircle(x-4*zoom,y-4*zoom,4*zoom,paint)}

    private fun drawLeader(c:Canvas,t:Team){val x=sx(t.leaderX);val y=sy(t.leaderY);if(!visible(x,y,70f))return;paint.color=t.color;c.drawCircle(x,y,28f*zoom,paint);paint.style=Paint.Style.STROKE;paint.strokeWidth=5f;paint.color=Color.WHITE;c.drawCircle(x,y,32f*zoom,paint);paint.style=Paint.Style.FILL}

    private fun drawUnit(c:Canvas,u:UnitEntity){ val x=sx(u.x);val y=sy(u.y);if(!visible(x,y,40f))return;paint.color=teams[u.team].color; val r=if(u.kind=="DRAGON")24f else if(u.kind=="KNIGHT")17f else 13f;c.drawCircle(x,y,r*zoom,paint);paint.color=Color.rgb(25,25,25);paint.style=Paint.Style.STROKE;paint.strokeWidth=2f;c.drawCircle(x,y,r*zoom,paint);paint.style=Paint.Style.FILL;drawBar(c,x-17*zoom,y-24*zoom,34*zoom,4*zoom,u.hp/u.maxHp)}

    private fun drawBuilding(c:Canvas,b:Building){ val x=sx(b.x);val y=sy(b.y);if(!visible(x,y,b.radius*zoom))return;paint.color=teams[b.team].color;val r=b.radius*zoom;when(b.kind){"KEEP"->c.drawRect(x-r,y-r,x+r,y+r,paint);"TOWER"->c.drawCircle(x,y,r,paint);"HOUSE"->{c.drawRect(x-r,y-r*.55f,x+r,y+r,paint);val p=Path();p.moveTo(x-r,y-r*.55f);p.lineTo(x,y-r*1.35f);p.lineTo(x+r,y-r*.55f);p.close();paint.color=Color.rgb(82,52,35);c.drawPath(p,paint)}else->{paint.color=Color.rgb(86,88,92);c.drawCircle(x,y,r,paint);paint.color=teams[b.team].color;c.drawCircle(x,y,r*.45f,paint)}};drawBar(c,x-r,y-r-10f,r*2,6f,b.hp/b.maxHp)}

    private fun drawBar(c:Canvas,x:Float,y:Float,w:Float,h:Float,v:Float){paint.color=Color.rgb(35,25,25);c.drawRect(x,y,x+w,y+h,paint);paint.color=Color.rgb(72,220,93);c.drawRect(x+1,y+1,x+1+(w-2)*v.coerceIn(0f,1f),y+h-1,paint)}

    private fun drawHud(c:Canvas){
        buttons.clear()
        paint.color=Color.argb(200,20,25,20);c.drawRoundRect(18f,16f,390f,104f,18f,18f,paint)
        val p=teams[0]; drawText(c,"ALTIN  ${p.gold}",38f,52f,25f,Color.rgb(255,210,62));drawText(c,"ORDU  ${p.population}/${p.cap}",38f,86f,23f,Color.WHITE)
        drawMinimap(c)
        joyBaseY=height-135f
        paint.color=Color.argb(90,255,255,255);c.drawCircle(joyBaseX,joyBaseY,88f,paint);paint.color=Color.argb(170,255,255,255);c.drawCircle(joyBaseX+joyX*54f,joyBaseY+joyY*54f,40f,paint)
        val labels=listOf("KILIÇ\n90" to "SWORD","OKÇU\n110" to "ARCHER","ŞÖVALYE\n240" to "KNIGHT","BÜYÜCÜ\n320" to "MAGE","EV\n220" to "HOUSE","MADEN\n320" to "MINE","KULE\n280" to "TOWER")
        val bw=108f;val gap=10f;val startX=width-(bw+gap)*4-20f
        labels.forEachIndexed{i,pair->val row=i/4;val col=i%4;val x=startX+col*(bw+gap);val y=height-160f+row*78f; val rect=RectF(x,y,x+bw,y+68f);buttons+=ActionButton(rect,pair.second);paint.color=if(selectedBuild==pair.second)Color.rgb(184,137,48) else Color.argb(220,28,35,29);c.drawRoundRect(rect,13f,13f,paint);drawCentered(c,pair.first,x+bw/2,y+26f,17f,Color.WHITE)}
        val minus=RectF(width-150f,20f,width-90f,78f);val plus=RectF(width-78f,20f,width-18f,78f);buttons+=ActionButton(minus,"ZOOM_OUT");buttons+=ActionButton(plus,"ZOOM_IN");paint.color=Color.argb(220,25,30,25);c.drawRoundRect(minus,12f,12f,paint);c.drawRoundRect(plus,12f,12f,paint);drawCentered(c,"−",minus.centerX(),56f,34f,Color.WHITE);drawCentered(c,"+",plus.centerX(),56f,32f,Color.WHITE)
        if(gameOver){paint.color=Color.argb(220,10,14,10);c.drawRect(0f,0f,width.toFloat(),height.toFloat(),paint);drawCentered(c,if(victory)"ZAFER" else "KRALLIĞIN YIKILDI",width/2f,height/2f-20f,52f,if(victory)Color.rgb(255,214,70) else Color.rgb(240,80,75));drawCentered(c,"Yeniden başlatmak için dokun",width/2f,height/2f+42f,24f,Color.WHITE)}
    }

    private fun drawMinimap(c:Canvas){val size=150f;val left=410f;val top=18f;paint.color=Color.argb(190,16,20,16);c.drawRoundRect(left,top,left+size,top+size*.58f,10f,10f,paint);for(t in teams){if(!t.keepAlive)continue;paint.color=t.color;c.drawCircle(left+t.leaderX/worldSize*size,top+t.leaderY/worldSize*(size*.58f),5f,paint)}}

    override fun onTouchEvent(e:MotionEvent):Boolean{
        if(gameOver && e.actionMasked==MotionEvent.ACTION_DOWN){restart();return true}
        when(e.actionMasked){
            MotionEvent.ACTION_DOWN,MotionEvent.ACTION_POINTER_DOWN->{val i=e.actionIndex;val x=e.getX(i);val y=e.getY(i);val id=e.getPointerId(i);val button=buttons.firstOrNull{it.rect.contains(x,y)};if(button!=null){activate(button.action);return true};if(x<width*.42f){joyId=id;joyBaseX=x;joyBaseY=y;updateJoy(x,y)}}
            MotionEvent.ACTION_MOVE->{if(joyId>=0){val i=e.findPointerIndex(joyId);if(i>=0)updateJoy(e.getX(i),e.getY(i))}}
            MotionEvent.ACTION_UP,MotionEvent.ACTION_POINTER_UP,MotionEvent.ACTION_CANCEL->{val id=e.getPointerId(e.actionIndex);if(id==joyId){joyId=-1;joyX=0f;joyY=0f}}
        };return true
    }

    private fun updateJoy(x:Float,y:Float){val dx=x-joyBaseX;val dy=y-joyBaseY;val d=hypot(dx,dy);if(d<1f){joyX=0f;joyY=0f}else{val m=min(1f,d/82f);joyX=dx/d*m;joyY=dy/d*m}}

    private fun activate(a:String){val p=teams[0];when(a){"ZOOM_IN"->zoom=(zoom+0.12f).coerceAtMost(1.35f);"ZOOM_OUT"->zoom=(zoom-0.12f).coerceAtLeast(.42f);"HOUSE","MINE","TOWER"->{selectedBuild=a;build(0,a,p.leaderX+cos(System.nanoTime().toFloat())*105f,p.leaderY+sin(System.nanoTime().toFloat())*105f);selectedBuild=""};else->{val cost=unitCost(a);if(p.gold>=cost&&p.population<p.cap){p.gold-=cost;spawnUnit(0,a)}}}}

    private fun restart(){units.clear();buildings.clear();gold.clear();gameOver=false;victory=false;teams.forEachIndexed{i,t->t.gold=if(i==0)650 else 500;t.cap=18;t.population=0;t.keepAlive=true;t.aiTimer=1f};val pos=arrayOf(800f to 2100f,3400f to 750f,3400f to 3400f,2100f to 500f);teams.forEachIndexed{i,t->t.leaderX=pos[i].first;t.leaderY=pos[i].second;buildings+=Building(i,"KEEP",t.leaderX,t.leaderY,1500f,140f);repeat(5){spawnUnit(i,if(it==4)"ARCHER" else "SWORD")}};repeat(110){gold+=GoldPile(rng.nextFloat()*(worldSize-240)+120,rng.nextFloat()*(worldSize-240)+120,rng.nextInt(28,65))}}

    private fun sx(x:Float)=(x-camX)*zoom+width/2f
    private fun sy(y:Float)=(y-camY)*zoom+height/2f
    private fun visible(x:Float,y:Float,r:Float)=x>-r&&x<width+r&&y>-r&&y<height+r
    private fun dist(x1:Float,y1:Float,x2:Float,y2:Float)=hypot(x2-x1,y2-y1)
    private fun drawText(c:Canvas,s:String,x:Float,y:Float,size:Float,color:Int){textPaint.textSize=size;textPaint.color=color;c.drawText(s,x,y,textPaint)}
    private fun drawCentered(c:Canvas,s:String,x:Float,y:Float,size:Float,color:Int){textPaint.textSize=size;textPaint.color=color;textPaint.textAlign=Paint.Align.CENTER;s.split("\n").forEachIndexed{i,line->c.drawText(line,x,y+i*(size+2),textPaint)};textPaint.textAlign=Paint.Align.LEFT}

    data class Team(val id:Int,var color:Int=Color.WHITE,var gold:Int=0,var cap:Int=0,var population:Int=0,var leaderX:Float=0f,var leaderY:Float=0f,var aiTimer:Float=1f,var keepAlive:Boolean=true)
    data class UnitEntity(val team:Int,val kind:String,var x:Float,var y:Float,var hp:Float,val maxHp:Float,val damage:Float,val range:Float,val speed:Float,val attackDelay:Float,val sight:Float=520f,var cooldown:Float=0f,var alive:Boolean=true)
    data class Building(val team:Int,val kind:String,val x:Float,val y:Float,var hp:Float,val radius:Float,val maxHp:Float=hp,var timer:Float=0f)
    data class GoldPile(val x:Float,val y:Float,val value:Int)
    data class ActionButton(val rect:RectF,val action:String)
}
