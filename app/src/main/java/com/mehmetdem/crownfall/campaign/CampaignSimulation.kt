package com.mehmetdem.crownfall.campaign

import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt
import kotlin.random.Random

class CampaignSimulation(seed: Int = 20260717) {
    val nations: MutableList<NationState> = WorldDefinition.createNations()
    val provinces: MutableList<ProvinceState> = WorldDefinition.createProvinces()
    val armies: MutableList<ArmyGroup> = mutableListOf()
    val events: MutableList<CampaignEvent> = mutableListOf()

    var elapsedSeconds: Float = 0f
        private set
    var timeScale: Float = 1f
    var autoPlayer: Boolean = false
    var winnerNationId: Int? = null
        private set

    private val random = Random(seed)
    private var economyAccumulator = 0f
    private var nextArmyId = 1L

    fun update(realDt: Float) {
        if (winnerNationId != null) return
        val dt = realDt.coerceIn(0f, 0.05f) * timeScale
        elapsedSeconds += dt
        economyAccumulator += dt

        while (economyAccumulator >= 1f) {
            economyAccumulator -= 1f
            updateEconomy()
        }

        updateArmies(dt)
        updateEvents(dt)
        updateNations(dt)
        evaluateWinner()
    }

    fun recruit(provinceId: Int, amount: Int = 16): Boolean {
        val province = provinces.getOrNull(provinceId) ?: return false
        val nation = nations[province.ownerId]
        val barracksDiscount = province.barracksLevel * 3
        val goldCost = max(20, 54 - barracksDiscount)
        val foodCost = max(8, 22 - province.farmLevel * 2)
        val ironCost = max(3, 9 - province.mineLevel)
        if (nation.treasury < goldCost || nation.food < foodCost || nation.iron < ironCost) return false
        if (province.population < amount + 20) return false

        nation.treasury -= goldCost
        nation.food -= foodCost
        nation.iron -= ironCost
        province.population -= amount / 2
        province.garrison += amount + province.barracksLevel * 2
        addEvent("${province.name} bölgesinde ${amount} asker toplandı.", nation.id)
        return true
    }

    fun upgradeProvince(provinceId: Int): Boolean {
        val province = provinces.getOrNull(provinceId) ?: return false
        val nation = nations[province.ownerId]
        val developmentCost = 95 + province.development * 45
        if (nation.treasury < developmentCost || nation.food < 35) return false

        nation.treasury -= developmentCost
        nation.food -= 35
        province.development += 1
        when (province.development % 4) {
            0 -> province.fortressLevel = min(4, province.fortressLevel + 1)
            1 -> province.farmLevel = min(4, province.farmLevel + 1)
            2 -> province.mineLevel = min(4, province.mineLevel + 1)
            else -> province.barracksLevel = min(4, province.barracksLevel + 1)
        }
        province.population += 14
        addEvent("${province.name} gelişim seviyesi ${province.development} oldu.", nation.id)
        return true
    }

    fun launchArmy(sourceProvinceId: Int, targetProvinceId: Int, fraction: Float = 0.62f): Boolean {
        val source = provinces.getOrNull(sourceProvinceId) ?: return false
        val target = provinces.getOrNull(targetProvinceId) ?: return false
        if (targetProvinceId !in source.neighbors) return false
        if (source.garrison < 18) return false

        val troopCount = max(10, (source.garrison * fraction.coerceIn(0.25f, 0.82f)).toInt())
        source.garrison -= troopCount
        val dx = target.center.x - source.center.x
        val dy = target.center.y - source.center.y
        val distance = sqrt(dx * dx + dy * dy)
        val travelSeconds = (distance / 125f).coerceIn(1.4f, 4.8f)
        armies += ArmyGroup(
            id = nextArmyId++,
            ownerId = source.ownerId,
            sourceProvinceId = source.id,
            targetProvinceId = target.id,
            troops = troopCount,
            travelSeconds = travelSeconds
        )
        addEvent(
            "${nations[source.ownerId].shortName}: ${source.name} → ${target.name} (${troopCount})",
            source.ownerId
        )
        return true
    }

    fun moveOrInvade(sourceProvinceId: Int, targetProvinceId: Int): Boolean =
        launchArmy(sourceProvinceId, targetProvinceId, if (provinces[targetProvinceId].ownerId == provinces[sourceProvinceId].ownerId) 0.5f else 0.68f)

    fun totalArmy(nationId: Int): Int {
        val stationed = provinces.asSequence().filter { it.ownerId == nationId }.sumOf { it.garrison }
        val marching = armies.asSequence().filter { it.ownerId == nationId && it.alive }.sumOf { it.troops }
        return stationed + marching
    }

    fun provinceCount(nationId: Int): Int = provinces.count { it.ownerId == nationId }

    fun snapshot(playerNationId: Int = 0): CampaignSnapshot {
        val lead = nations.maxByOrNull { provinceCount(it.id) } ?: nations.first()
        return CampaignSnapshot(
            totalProvinces = provinces.size,
            playerProvinces = provinceCount(playerNationId),
            playerArmy = totalArmy(playerNationId),
            leadingNationId = lead.id,
            leadingNationProvinces = provinceCount(lead.id)
        )
    }

    private fun updateEconomy() {
        for (province in provinces) {
            val nation = nations[province.ownerId]
            val terrainFood = when (province.terrain) {
                TerrainType.PLAINS, TerrainType.COAST -> 3
                TerrainType.FOREST -> 2
                TerrainType.DESERT, TerrainType.TUNDRA -> 0
                else -> 1
            }
            val terrainIron = when (province.terrain) {
                TerrainType.HILLS, TerrainType.MOUNTAIN -> 3
                TerrainType.STEPPE -> 2
                else -> 1
            }
            nation.treasury += 2 + province.development + province.mineLevel * 2
            nation.food += terrainFood + province.farmLevel * 3
            nation.iron += terrainIron + province.mineLevel * 2

            val growth = max(0, 1 + province.farmLevel - province.unrest.toInt())
            province.population = min(320, province.population + growth)
            province.militia = min(60, province.militia + if (province.population > 120) 1 else 0)
            province.unrest = max(0f, province.unrest - 0.035f)
        }
    }

    private fun updateArmies(dt: Float) {
        val iterator = armies.iterator()
        while (iterator.hasNext()) {
            val army = iterator.next()
            if (!army.alive) {
                iterator.remove()
                continue
            }
            army.progress += dt / army.travelSeconds
            if (army.progress >= 1f) {
                resolveArrival(army)
                army.alive = false
                iterator.remove()
            }
        }
    }

    private fun resolveArrival(army: ArmyGroup) {
        val target = provinces[army.targetProvinceId]
        if (target.ownerId == army.ownerId) {
            target.garrison += army.troops
            return
        }

        val attackerNation = nations[army.ownerId]
        val defenderNation = nations[target.ownerId]
        val terrainDefense = when (target.terrain) {
            TerrainType.MOUNTAIN -> 1.34f
            TerrainType.HILLS, TerrainType.FOREST -> 1.18f
            TerrainType.DESERT, TerrainType.STEPPE -> 0.94f
            else -> 1f
        }
        val attackPower = army.troops * (1f + attackerNation.attackLevel * 0.08f) * random.nextDouble(0.88, 1.14).toFloat()
        val defensiveTroops = target.garrison + target.militia
        val defensePower = defensiveTroops *
            (1f + defenderNation.defenseLevel * 0.07f + target.fortressLevel * 0.16f) *
            terrainDefense * random.nextDouble(0.9, 1.12).toFloat()

        if (attackPower > defensePower) {
            val oldOwner = target.ownerId
            val survivalRatio = ((attackPower - defensePower) / max(attackPower, 1f)).coerceIn(0.18f, 0.72f)
            target.ownerId = army.ownerId
            target.garrison = max(8, (army.troops * survivalRatio).toInt())
            target.militia = max(3, target.militia / 3)
            target.unrest = 3.5f
            target.capital = target.capital && provinceCount(oldOwner) == 0
            addEvent("${target.name}, ${attackerNation.name} tarafından işgal edildi.", army.ownerId)
            if (provinceCount(oldOwner) == 0) {
                nations[oldOwner].alive = false
                addEvent("${nations[oldOwner].name} haritadan silindi.", army.ownerId)
            }
        } else {
            val lossRatio = (attackPower / max(defensePower, 1f)).coerceIn(0.15f, 0.82f)
            val losses = max(4, (defensiveTroops * lossRatio * 0.55f).toInt())
            target.garrison = max(3, target.garrison - losses)
            target.militia = max(0, target.militia - losses / 3)
            addEvent("${target.name} saldırıyı püskürttü.", target.ownerId)
        }
    }

    private fun updateNations(dt: Float) {
        for (nation in nations) {
            if (!nation.alive) continue
            if (nation.id == 0 && !autoPlayer) continue
            nation.aiCooldown -= dt
            if (nation.aiCooldown > 0f) continue
            nation.aiCooldown = random.nextDouble(1.25, 2.85).toFloat()
            runAiTurn(nation)
        }
    }

    private fun runAiTurn(nation: NationState) {
        val owned = provinces.filter { it.ownerId == nation.id }
        if (owned.isEmpty()) {
            nation.alive = false
            return
        }

        val weakest = owned.minByOrNull { it.garrison + it.fortressLevel * 15 }
        if (weakest != null && weakest.garrison < 42 && nation.treasury >= 45) {
            recruit(weakest.id, if (nation.treasury > 420) 22 else 16)
            return
        }

        val border = owned.filter { province -> province.neighbors.any { provinces[it].ownerId != nation.id } }
        val attackSource = border
            .filter { it.garrison >= 34 }
            .maxByOrNull { it.garrison + it.barracksLevel * 8 }
        if (attackSource != null) {
            val target = attackSource.neighbors
                .map { provinces[it] }
                .filter { it.ownerId != nation.id }
                .minByOrNull { it.garrison + it.militia + it.fortressLevel * 20 }
            if (target != null && attackSource.garrison > target.garrison * 0.72f + 12) {
                launchArmy(attackSource.id, target.id, random.nextDouble(0.54, 0.76).toFloat())
                return
            }
        }

        val upgradeTarget = owned.minByOrNull { it.development }
        if (upgradeTarget != null && nation.treasury > 180) {
            upgradeProvince(upgradeTarget.id)
            return
        }

        val reinforceTarget = border.minByOrNull { it.garrison }
        val reserve = owned.filter { it.id != reinforceTarget?.id && it.garrison > 46 }.maxByOrNull { it.garrison }
        if (reinforceTarget != null && reserve != null && reinforceTarget.id in reserve.neighbors) {
            launchArmy(reserve.id, reinforceTarget.id, 0.42f)
        }
    }

    private fun updateEvents(dt: Float) {
        events.forEach { it.remainingSeconds -= dt }
        events.removeAll { it.remainingSeconds <= 0f }
        while (events.size > 6) events.removeAt(0)
    }

    private fun evaluateWinner() {
        val aliveOwners = provinces.map { it.ownerId }.distinct()
        if (aliveOwners.size == 1) {
            winnerNationId = aliveOwners.first()
            addEvent("${nations[aliveOwners.first()].name} dünya hâkimiyetini kurdu.", aliveOwners.first())
        }
    }

    private fun addEvent(text: String, nationId: Int) {
        events += CampaignEvent(text, nationId)
    }
}
