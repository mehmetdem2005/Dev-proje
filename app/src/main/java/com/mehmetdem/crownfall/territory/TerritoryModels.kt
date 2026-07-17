package com.mehmetdem.crownfall.territory

import com.mehmetdem.crownfall.campaign.TerrainType
import com.mehmetdem.crownfall.campaign.Vec2

data class CountryTerritoryState(
    val id: Int,
    val name: String,
    val shortName: String,
    val paletteColor: Int,
    val capitalProvinceId: Int,
    var treasury: Int,
    var populationReserve: Int,
    var militaryReserve: Int,
    var technologyLevel: Int = 1,
    var alive: Boolean = true
)

data class StrategicProvinceState(
    val id: Int,
    val name: String,
    val polygon: List<Vec2>,
    val center: Vec2,
    val neighbors: MutableSet<Int>,
    val terrain: TerrainType,
    val isCity: Boolean = false,
    val isCapital: Boolean = false,
    val isPort: Boolean = false,
    val resourceYield: Int = 0,
    var sovereignCountryId: Int,
    var controllerCountryId: Int,
    var population: Int,
    var economy: Int,
    var morale: Float,
    var supply: Float,
    var fortification: Float,
    var stationedPower: Float,
    var captureAttackerId: Int? = null,
    var captureProgress: Float = 0f
)

data class AttackOrderState(
    val id: Long,
    val attackerCountryId: Int,
    val sourceProvinceId: Int,
    val targetProvinceId: Int,
    val committedPercentage: Float,
    val committedPower: Float,
    val issuedAtTick: Long,
    var progress: Float = 0f,
    var state: AttackOrderStatus = AttackOrderStatus.MARCHING
)

enum class AttackOrderStatus {
    MARCHING,
    CONTESTING,
    CAPTURED,
    REPELLED,
    CANCELLED
}

data class TerritorySimulationSnapshot(
    val tick: Long,
    val provinces: List<ProvinceRenderState>,
    val armies: List<ArmyRenderState>
)

data class ProvinceRenderState(
    val id: Int,
    val controllerCountryId: Int,
    val captureAttackerId: Int?,
    val captureProgress: Float,
    val stationedPower: Float,
    val morale: Float
)

data class ArmyRenderState(
    val id: Long,
    val ownerCountryId: Int,
    val source: Vec2,
    val target: Vec2,
    val routeProgress: Float,
    val representedPower: Float,
    val status: AttackOrderStatus
)
