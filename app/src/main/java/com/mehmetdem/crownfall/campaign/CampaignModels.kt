package com.mehmetdem.crownfall.campaign

enum class TerrainType {
    PLAINS,
    FOREST,
    HILLS,
    DESERT,
    STEPPE,
    TUNDRA,
    COAST,
    MOUNTAIN
}

enum class StructureType {
    FARM,
    MINE,
    BARRACKS,
    FORTRESS
}

data class Vec2(val x: Float, val y: Float)

data class NationState(
    val id: Int,
    val name: String,
    val shortName: String,
    val color: Int,
    var treasury: Int,
    var food: Int,
    var iron: Int,
    var attackLevel: Int = 1,
    var defenseLevel: Int = 1,
    var aiCooldown: Float = 1f,
    var alive: Boolean = true
)

data class ProvinceState(
    val id: Int,
    val name: String,
    val center: Vec2,
    val polygon: List<Vec2>,
    val terrain: TerrainType,
    val neighbors: MutableSet<Int> = linkedSetOf(),
    var ownerId: Int,
    var capital: Boolean = false,
    var population: Int = 80,
    var garrison: Int = 24,
    var militia: Int = 10,
    var development: Int = 1,
    var farmLevel: Int = 0,
    var mineLevel: Int = 0,
    var barracksLevel: Int = 0,
    var fortressLevel: Int = 0,
    var unrest: Float = 0f
)

data class ArmyGroup(
    val id: Long,
    val ownerId: Int,
    val sourceProvinceId: Int,
    val targetProvinceId: Int,
    val troops: Int,
    var progress: Float = 0f,
    val travelSeconds: Float,
    var alive: Boolean = true
)

data class CampaignEvent(
    val text: String,
    val nationId: Int,
    var remainingSeconds: Float = 7f
)

data class CampaignSnapshot(
    val totalProvinces: Int,
    val playerProvinces: Int,
    val playerArmy: Int,
    val leadingNationId: Int,
    val leadingNationProvinces: Int
)
