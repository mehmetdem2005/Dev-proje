package com.mehmetdem.crownfall.render

import com.mehmetdem.crownfall.campaign.Vec2
import com.mehmetdem.crownfall.territory.AttackOrderStatus
import com.mehmetdem.crownfall.territory.TerritorySimulationSnapshot

/**
 * Immutable frame data shared by the flat political map renderer and the 3D
 * formation renderer. Neither renderer may mutate authoritative simulation state.
 */
data class HybridRenderSnapshot(
    val simulationTick: Long,
    val provinceColors: List<ProvinceColorInstance>,
    val formations: List<Formation3DInstance>
) {
    companion object {
        fun from(
            simulation: TerritorySimulationSnapshot,
            provincePalette: (Int) -> Int
        ): HybridRenderSnapshot {
            val provinceInstances = simulation.provinces.map {
                ProvinceColorInstance(
                    provinceId = it.id,
                    baseColor = provincePalette(it.controllerCountryId),
                    contestedColor = it.captureAttackerId?.let(provincePalette),
                    contestAmount = it.captureProgress
                )
            }
            val formationInstances = simulation.armies.map {
                Formation3DInstance(
                    id = it.id,
                    ownerCountryId = it.ownerCountryId,
                    worldPosition = interpolate(it.source, it.target, it.routeProgress),
                    facingRadians = angle(it.source, it.target),
                    representedPower = it.representedPower,
                    lod = formationLod(it.representedPower),
                    animation = animationFor(it.status)
                )
            }
            return HybridRenderSnapshot(
                simulationTick = simulation.tick,
                provinceColors = provinceInstances,
                formations = formationInstances
            )
        }

        private fun interpolate(from: Vec2, to: Vec2, amount: Float): Vec2 = Vec2(
            x = from.x + (to.x - from.x) * amount.coerceIn(0f, 1f),
            y = from.y + (to.y - from.y) * amount.coerceIn(0f, 1f)
        )

        private fun angle(from: Vec2, to: Vec2): Float =
            kotlin.math.atan2(to.y - from.y, to.x - from.x)

        private fun formationLod(power: Float): FormationLod = when {
            power >= 120f -> FormationLod.LARGE
            power >= 45f -> FormationLod.MEDIUM
            else -> FormationLod.SMALL
        }

        private fun animationFor(status: AttackOrderStatus): FormationAnimation = when (status) {
            AttackOrderStatus.MARCHING -> FormationAnimation.MARCH
            AttackOrderStatus.CONTESTING -> FormationAnimation.ATTACK
            AttackOrderStatus.CAPTURED -> FormationAnimation.CELEBRATE
            AttackOrderStatus.REPELLED -> FormationAnimation.RETREAT
            AttackOrderStatus.CANCELLED -> FormationAnimation.DESPAWN
        }
    }
}

data class ProvinceColorInstance(
    val provinceId: Int,
    val baseColor: Int,
    val contestedColor: Int?,
    val contestAmount: Float
)

data class Formation3DInstance(
    val id: Long,
    val ownerCountryId: Int,
    val worldPosition: Vec2,
    val facingRadians: Float,
    val representedPower: Float,
    val lod: FormationLod,
    val animation: FormationAnimation
)

enum class FormationLod {
    SMALL,
    MEDIUM,
    LARGE
}

enum class FormationAnimation {
    MARCH,
    ATTACK,
    RETREAT,
    CELEBRATE,
    DESPAWN
}
