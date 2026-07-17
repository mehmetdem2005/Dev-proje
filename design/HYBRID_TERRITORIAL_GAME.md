# Crownfall — Hybrid Territorial Strategy

## Correct product direction

The game is a native Android 2D/3D hybrid strategy title.

- The strategic map is a flat 2D political world map with irregular country and province polygons.
- Territory ownership, borders, roads, cities, resources and front lines belong to the 2D strategic layer.
- Commanders, army formations, siege units, important buildings, projectiles and combat effects are real 3D actors rendered above the map.
- Expansion uses a fast percentage-based territorial conquest loop: the player commits part of available population/army power, pushes through adjacent territory, reinforces borders and balances growth against aggression.
- The authoritative simulation is province/cell based. 3D actors visualize armies but do not determine the simulation outcome through animation collisions.

## Explicit removals from the current build

The current hex-grid presentation and Canvas-drawn soldier packs are temporary and must be removed from the production path.

- Remove regular hex provinces.
- Remove 2D army icon packs.
- Remove whole-map free-roaming Lordz.io movement.
- Do not use one collider per province.
- Do not use pixel colors as authoritative territory state.

## Target hierarchy

```text
HybridGameRoot
├── SimulationHost
│   ├── FixedTickScheduler
│   ├── WorldMapDatabase
│   ├── CountrySystem
│   ├── ProvinceGraph
│   ├── TerritoryExpansionSystem
│   ├── EconomyPopulationSystem
│   ├── ArmyCommandSystem
│   ├── BattleResolutionSystem
│   ├── SupplyAndFrontlineSystem
│   ├── BotStrategySystem
│   └── SaveReplaySystem
├── StrategicMapLayer2D
│   ├── TerrainAtlas
│   ├── CountryFillRenderer
│   ├── ProvinceBorderRenderer
│   ├── RoadAndCityRenderer
│   ├── FrontlineRenderer
│   ├── ProvinceIdPickingBuffer
│   └── SelectionOverlay
├── WorldActorLayer3D
│   ├── HybridCameraRig
│   ├── ArmyFormationPool
│   ├── CommanderPool
│   ├── SiegeUnitPool
│   ├── BuildingPool
│   ├── ProjectilePool
│   └── CombatVfxPool
├── InputRouter
│   ├── PanZoomController
│   ├── ProvinceSelectionController
│   ├── AttackPercentageController
│   └── ArmyCommandController
└── HudLayer
    ├── CountryStatusBar
    ├── ProvinceInspector
    ├── ArmyInspector
    ├── AttackPowerSlider
    ├── DiplomacyPanel
    ├── Minimap
    └── EventFeed
```

## World data model

```text
Country
- id
- name
- palette index
- capital province id
- treasury
- population reserve
- military reserve
- technology
- diplomacy state

Province
- id
- country id
- controller id
- irregular polygon
- neighboring province ids
- terrain type
- city/resource/port flags
- population
- economy
- morale
- supply
- fortification
- stationed army power

AttackOrder
- source province id
- target province id
- committed percentage
- committed power
- progress
- supply state
- result seed
```

The province graph is authoritative. The colored map, border mesh and 3D formations are generated from simulation snapshots. This keeps save files deterministic and allows an authoritative multiplayer server later.

## Territory conquest

1. The player taps an owned province or country region.
2. Adjacent hostile or neutral regions become valid targets.
3. The player chooses the percentage of available power to commit.
4. An attack order creates a moving front and one or more 3D formation visuals.
5. The fixed-tick simulation resolves movement, supply, terrain, morale and defense.
6. Ownership changes only after the capture threshold is reached.
7. Borders and country fill update only in dirty map regions.

## 2D/3D rendering contract

The map and actors share one camera transform but remain separate render domains.

- Map coordinates use a stable world-space coordinate system.
- Province polygons render on the Z=0 plane.
- Roads, borders and selection overlays use small ordered depth offsets.
- 3D actors are anchored to province centers, roads or interpolated attack routes.
- One 3D formation represents a simulation stack, not one soldier per population unit.
- Selected formations use full models and animation. Distant formations use low-detail pooled meshes.

## Production mobile limits

- Native Android only; no browser runtime.
- Landscape orientation.
- OpenGL ES 3.0 compatible render path.
- Fixed simulation tick independent from frame rate.
- Maximum visible full-detail formations controlled by device tier.
- Batched province rendering and dirty-region border rebuilds.
- ID-buffer or spatial index picking instead of hundreds of Android views or physics bodies.
- Object pools for all 3D actors and effects.

## First production milestone

- Replace the hex world with an irregular political-map dataset.
- Add country/province ownership and adjacency data.
- Add percentage-based attack orders.
- Split the current combined Canvas class into simulation, 2D map renderer, 3D actor renderer and HUD/input modules.
- Render infantry, cavalry and siege formations as real 3D low-poly actors above attack routes.
- Preserve the current economy, AI, victory and Android build pipeline while replacing only the wrong presentation and conquest model.
