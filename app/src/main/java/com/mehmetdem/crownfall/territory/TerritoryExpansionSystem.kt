package com.mehmetdem.crownfall.territory

import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/**
 * Authoritative fixed-tick territory conquest.
 *
 * Rendering code may interpolate snapshots, but ownership and battle results are
 * decided only here. This prevents frame-rate dependent combat and keeps a future
 * multiplayer server deterministic.
 */
class TerritoryExpansionSystem(
    provinceStates: List<StrategicProvinceState>,
    private val ticksPerSecond: Int = 10
) {
    private val provincesById = provinceStates.associateBy { it.id }.toMutableMap()
    private val activeOrders = linkedMapOf<Long, AttackOrderState>()

    private var nextOrderId = 1L
    private var currentTick = 0L

    fun province(id: Int): StrategicProvinceState? = provincesById[id]

    fun issueAttack(
        attackerCountryId: Int,
        sourceProvinceId: Int,
        targetProvinceId: Int,
        committedPercentage: Float
    ): AttackOrderState? {
        val source = provincesById[sourceProvinceId] ?: return null
        val target = provincesById[targetProvinceId] ?: return null
        if (source.controllerCountryId != attackerCountryId) return null
        if (targetProvinceId !in source.neighbors) return null
        if (target.controllerCountryId == attackerCountryId) return null

        val percentage = committedPercentage.coerceIn(0.05f, 0.9f)
        val committedPower = source.stationedPower * percentage
        if (committedPower < MIN_ATTACK_POWER) return null

        source.stationedPower -= committedPower
        val order = AttackOrderState(
            id = nextOrderId++,
            attackerCountryId = attackerCountryId,
            sourceProvinceId = sourceProvinceId,
            targetProvinceId = targetProvinceId,
            committedPercentage = percentage,
            committedPower = committedPower,
            issuedAtTick = currentTick
        )
        activeOrders[order.id] = order
        return order
    }

    fun advanceOneTick() {
        currentTick += 1
        val completedOrderIds = mutableListOf<Long>()

        for (order in activeOrders.values) {
            val source = provincesById[order.sourceProvinceId]
            val target = provincesById[order.targetProvinceId]
            if (source == null || target == null) {
                order.state = AttackOrderStatus.CANCELLED
                completedOrderIds += order.id
                continue
            }

            if (source.controllerCountryId != order.attackerCountryId) {
                order.state = AttackOrderStatus.CANCELLED
                completedOrderIds += order.id
                continue
            }

            when (order.state) {
                AttackOrderStatus.MARCHING -> updateMarch(order, source, target)
                AttackOrderStatus.CONTESTING -> updateContest(order, target)
                AttackOrderStatus.CAPTURED,
                AttackOrderStatus.REPELLED,
                AttackOrderStatus.CANCELLED -> completedOrderIds += order.id
            }

            if (order.state == AttackOrderStatus.CAPTURED ||
                order.state == AttackOrderStatus.REPELLED ||
                order.state == AttackOrderStatus.CANCELLED
            ) {
                completedOrderIds += order.id
            }
        }

        completedOrderIds.distinct().forEach(activeOrders::remove)
        recoverControlledProvinces()
    }

    fun snapshot(): TerritorySimulationSnapshot {
        val provinceRenderStates = provincesById.values
            .sortedBy { it.id }
            .map {
                ProvinceRenderState(
                    id = it.id,
                    controllerCountryId = it.controllerCountryId,
                    captureAttackerId = it.captureAttackerId,
                    captureProgress = it.captureProgress,
                    stationedPower = it.stationedPower,
                    morale = it.morale
                )
            }

        val armyRenderStates = activeOrders.values.mapNotNull { order ->
            val source = provincesById[order.sourceProvinceId] ?: return@mapNotNull null
            val target = provincesById[order.targetProvinceId] ?: return@mapNotNull null
            ArmyRenderState(
                id = order.id,
                ownerCountryId = order.attackerCountryId,
                source = source.center,
                target = target.center,
                routeProgress = order.progress.coerceIn(0f, 1f),
                representedPower = order.committedPower,
                status = order.state
            )
        }

        return TerritorySimulationSnapshot(
            tick = currentTick,
            provinces = provinceRenderStates,
            armies = armyRenderStates
        )
    }

    private fun updateMarch(
        order: AttackOrderState,
        source: StrategicProvinceState,
        target: StrategicProvinceState
    ) {
        val distance = distance(source.center.x, source.center.y, target.center.x, target.center.y)
        val terrainSpeed = when (target.terrain.name) {
            "MOUNTAIN" -> 0.6f
            "HILLS", "FOREST" -> 0.78f
            "DESERT", "TUNDRA" -> 0.72f
            else -> 1f
        }
        val routeTicks = max(6f, distance / 18f / terrainSpeed)
        order.progress = min(1f, order.progress + 1f / routeTicks)

        if (order.progress >= 1f) {
            order.state = AttackOrderStatus.CONTESTING
            target.captureAttackerId = order.attackerCountryId
            target.captureProgress = max(target.captureProgress, 0.01f)
        }
    }

    private fun updateContest(order: AttackOrderState, target: StrategicProvinceState) {
        if (target.controllerCountryId == order.attackerCountryId) {
            target.stationedPower += order.committedPower * 0.75f
            order.state = AttackOrderStatus.CAPTURED
            return
        }

        val terrainDefense = when (target.terrain.name) {
            "MOUNTAIN" -> 1.35f
            "HILLS", "FOREST" -> 1.18f
            "DESERT", "STEPPE" -> 0.94f
            else -> 1f
        }
        val defenderPower = max(
            1f,
            target.stationedPower * terrainDefense *
                (1f + target.fortification * 0.12f) *
                (0.65f + target.morale.coerceIn(0f, 100f) / 100f)
        )
        val supplyModifier = 0.55f + target.supply.coerceIn(0f, 100f) / 220f
        val attackPressure = order.committedPower * supplyModifier
        val pressureRatio = attackPressure / defenderPower
        val captureDelta = ((pressureRatio - 0.55f) / ticksPerSecond).coerceIn(-0.08f, 0.12f)

        target.captureAttackerId = order.attackerCountryId
        target.captureProgress = (target.captureProgress + captureDelta).coerceIn(0f, 1f)
        target.stationedPower = max(0f, target.stationedPower - attackPressure * 0.008f)

        if (target.captureProgress >= 1f) {
            val previousController = target.controllerCountryId
            target.controllerCountryId = order.attackerCountryId
            target.captureAttackerId = null
            target.captureProgress = 0f
            target.morale = 28f
            target.supply = 38f
            target.stationedPower = max(4f, order.committedPower * 0.42f)
            order.state = AttackOrderStatus.CAPTURED

            if (previousController == target.sovereignCountryId) {
                target.sovereignCountryId = previousController
            }
        } else if (target.captureProgress <= 0f && pressureRatio < 0.72f) {
            target.captureAttackerId = null
            target.captureProgress = 0f
            order.state = AttackOrderStatus.REPELLED
        }
    }

    private fun recoverControlledProvinces() {
        for (province in provincesById.values) {
            if (province.captureAttackerId == null) {
                province.morale = min(100f, province.morale + 0.015f)
                province.supply = min(100f, province.supply + 0.025f)
                province.stationedPower = min(
                    province.population * 0.6f,
                    province.stationedPower + province.economy * 0.0007f
                )
            }
        }
    }

    private fun distance(x1: Float, y1: Float, x2: Float, y2: Float): Float {
        val dx = x2 - x1
        val dy = y2 - y1
        return sqrt(dx * dx + dy * dy)
    }

    private companion object {
        const val MIN_ATTACK_POWER = 5f
    }
}
