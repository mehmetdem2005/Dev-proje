package com.mehmetdem.crownfall.campaign

import android.graphics.Color
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin

object WorldDefinition {
    const val WORLD_WIDTH = 2500f
    const val WORLD_HEIGHT = 1320f
    private const val HEX_RADIUS = 102f

    private data class Cell(
        val q: Int,
        val r: Int,
        val name: String,
        val owner: Int,
        val terrain: TerrainType,
        val capital: Boolean = false
    )

    fun createNations(): MutableList<NationState> = mutableListOf(
        NationState(0, "Anadolu Tacı", "AN", Color.rgb(45, 132, 220), 520, 340, 180),
        NationState(1, "Nordgard", "NO", Color.rgb(63, 110, 178), 470, 300, 220),
        NationState(2, "Albion Birliği", "AL", Color.rgb(160, 72, 184), 490, 320, 170),
        NationState(3, "Franka Krallığı", "FR", Color.rgb(205, 67, 76), 510, 340, 190),
        NationState(4, "İberya Ligi", "IB", Color.rgb(230, 138, 49), 480, 350, 150),
        NationState(5, "Sahra Sultanlığı", "SA", Color.rgb(213, 173, 61), 500, 420, 120),
        NationState(6, "Nil Hanedanı", "NI", Color.rgb(42, 157, 132), 520, 390, 150),
        NationState(7, "Bozkır Kağanlığı", "BO", Color.rgb(132, 91, 57), 470, 300, 250),
        NationState(8, "Boreal Birliği", "BR", Color.rgb(89, 152, 165), 460, 280, 230),
        NationState(9, "Yeşim İmparatorluğu", "YE", Color.rgb(62, 153, 82), 540, 360, 210),
        NationState(10, "Yamato Şogunluğu", "YA", Color.rgb(189, 56, 92), 500, 330, 220),
        NationState(11, "And Dağları Konfederasyonu", "AD", Color.rgb(121, 101, 184), 490, 360, 180)
    )

    fun createProvinces(): MutableList<ProvinceState> {
        val cells = listOf(
            Cell(0, 1, "Buz Körfezi", 8, TerrainType.TUNDRA),
            Cell(1, 1, "Kuzey Ormanları", 8, TerrainType.FOREST, true),
            Cell(0, 2, "Batı Gölleri", 8, TerrainType.FOREST),
            Cell(1, 2, "Demir Ovası", 8, TerrainType.PLAINS),
            Cell(0, 4, "And Kuzeyi", 11, TerrainType.MOUNTAIN),
            Cell(1, 4, "Amazon Kapısı", 11, TerrainType.FOREST, true),
            Cell(0, 5, "Gümüş Sırt", 11, TerrainType.MOUNTAIN),
            Cell(1, 5, "Güney Yağmurları", 11, TerrainType.FOREST),
            Cell(2, 5, "Pampa", 11, TerrainType.PLAINS),

            Cell(4, 1, "Nord Fiyordu", 1, TerrainType.COAST),
            Cell(5, 1, "Nord Başkenti", 1, TerrainType.TUNDRA, true),
            Cell(6, 1, "Kuzey Madenleri", 1, TerrainType.HILLS),
            Cell(3, 2, "Albion Adası", 2, TerrainType.COAST, true),
            Cell(4, 2, "Frank Batısı", 3, TerrainType.PLAINS),
            Cell(5, 2, "Frank Başkenti", 3, TerrainType.PLAINS, true),
            Cell(6, 2, "Frank Doğusu", 3, TerrainType.FOREST),
            Cell(3, 3, "İber Batısı", 4, TerrainType.HILLS),
            Cell(4, 3, "İber Başkenti", 4, TerrainType.PLAINS, true),
            Cell(5, 3, "Akdeniz Kapısı", 4, TerrainType.COAST),

            Cell(6, 3, "Bosphoros", 0, TerrainType.COAST, true),
            Cell(7, 3, "Anadolu", 0, TerrainType.HILLS),
            Cell(7, 2, "Karadeniz", 0, TerrainType.COAST),
            Cell(8, 3, "Doğu Geçidi", 0, TerrainType.MOUNTAIN),

            Cell(4, 4, "Sahra Batısı", 5, TerrainType.DESERT),
            Cell(5, 4, "Sahra Başkenti", 5, TerrainType.DESERT, true),
            Cell(4, 5, "Altın Kumlar", 5, TerrainType.DESERT),
            Cell(5, 5, "Tuz Denizi", 5, TerrainType.DESERT),
            Cell(6, 4, "Nil Deltası", 6, TerrainType.COAST, true),
            Cell(6, 5, "Nil Vadisi", 6, TerrainType.PLAINS),
            Cell(7, 5, "Kızıl Yayla", 6, TerrainType.HILLS),

            Cell(8, 1, "Boreal Tundrası", 8, TerrainType.TUNDRA),
            Cell(8, 2, "Bozkır Batısı", 7, TerrainType.STEPPE),
            Cell(9, 2, "Kağanlık Merkezi", 7, TerrainType.STEPPE, true),
            Cell(9, 3, "Atlı Ova", 7, TerrainType.STEPPE),
            Cell(10, 2, "Yeşim Batısı", 9, TerrainType.HILLS),
            Cell(10, 3, "Yeşim Başkenti", 9, TerrainType.PLAINS, true),
            Cell(11, 3, "İpek Havzası", 9, TerrainType.PLAINS),
            Cell(11, 2, "Kuzey Seddi", 9, TerrainType.MOUNTAIN),
            Cell(12, 3, "Yamato Kuzeyi", 10, TerrainType.COAST),
            Cell(12, 4, "Yamato Başkenti", 10, TerrainType.COAST, true),
            Cell(11, 4, "Güney Limanları", 10, TerrainType.COAST)
        )

        val provinces = cells.mapIndexed { index, cell ->
            val center = centerFor(cell.q, cell.r)
            ProvinceState(
                id = index,
                name = cell.name,
                center = center,
                polygon = hexPolygon(center),
                terrain = cell.terrain,
                ownerId = cell.owner,
                capital = cell.capital,
                population = if (cell.capital) 145 else 85,
                garrison = if (cell.capital) 48 else 24,
                militia = if (cell.capital) 18 else 9,
                development = if (cell.capital) 2 else 1,
                fortressLevel = if (cell.capital) 1 else 0,
                farmLevel = if (cell.terrain in setOf(TerrainType.PLAINS, TerrainType.COAST)) 1 else 0,
                mineLevel = if (cell.terrain in setOf(TerrainType.HILLS, TerrainType.MOUNTAIN)) 1 else 0
            )
        }.toMutableList()

        for (a in cells.indices) {
            for (b in a + 1 until cells.size) {
                if (areHexNeighbors(cells[a], cells[b])) {
                    provinces[a].neighbors += b
                    provinces[b].neighbors += a
                }
            }
        }
        return provinces
    }

    private fun centerFor(q: Int, r: Int): Vec2 {
        val x = 165f + q * HEX_RADIUS * 1.72f
        val y = 145f + r * HEX_RADIUS * 1.48f + if (q % 2 == 0) 0f else HEX_RADIUS * 0.74f
        return Vec2(x, y)
    }

    private fun hexPolygon(center: Vec2): List<Vec2> = List(6) { index ->
        val angle = Math.toRadians((60.0 * index) - 30.0)
        Vec2(
            center.x + cos(angle).toFloat() * HEX_RADIUS,
            center.y + sin(angle).toFloat() * HEX_RADIUS
        )
    }

    private fun areHexNeighbors(a: Cell, b: Cell): Boolean {
        val dq = abs(a.q - b.q)
        val dr = abs(a.r - b.r)
        if (dq == 0 && dr == 1) return true
        if (dq != 1) return false
        return if (a.q % 2 == 0) {
            b.r == a.r || b.r == a.r - 1
        } else {
            b.r == a.r || b.r == a.r + 1
        }
    }
}
