package com.mehmetdem.crownfall.territory

import java.util.concurrent.atomic.AtomicReference

/**
 * Runs authoritative conquest at a stable tick rate while the renderer consumes
 * the latest immutable snapshot at the device frame rate.
 */
class FixedTickTerritoryHost(
    private val expansionSystem: TerritoryExpansionSystem,
    private val ticksPerSecond: Int = 10
) {
    private val latestSnapshot = AtomicReference(expansionSystem.snapshot())
    private var accumulatorSeconds = 0f

    fun update(realDeltaSeconds: Float) {
        accumulatorSeconds += realDeltaSeconds.coerceIn(0f, 0.1f)
        val tickDuration = 1f / ticksPerSecond.coerceAtLeast(1)
        var safetyCounter = 0

        while (accumulatorSeconds >= tickDuration && safetyCounter < MAX_CATCH_UP_TICKS) {
            expansionSystem.advanceOneTick()
            accumulatorSeconds -= tickDuration
            safetyCounter += 1
        }

        if (safetyCounter > 0) latestSnapshot.set(expansionSystem.snapshot())
        if (safetyCounter == MAX_CATCH_UP_TICKS) accumulatorSeconds = 0f
    }

    fun latest(): TerritorySimulationSnapshot = latestSnapshot.get()

    private companion object {
        const val MAX_CATCH_UP_TICKS = 5
    }
}
