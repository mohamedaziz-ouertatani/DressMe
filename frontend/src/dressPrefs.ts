import type { WeatherCondition } from './api/types'
import type { StringKey } from './i18n/strings'

// What the Dress page remembers in this browser, shared with Home so both make the SAME GET /outfits/today call
// (same chip, same position, shuffle 0) and show the same outfits on the same day.

export const CHIP_KEY = 'dressme.dressChip'              // the last chip used
export const PLACE_KEY = 'dressme.weatherPlace'          // the position the user shared, rounded to ~10 km
export const DEFAULT_CHIP = 'everyday'
export type Place = { lat: number; lon: number }

/** The word for the weather of the day (Dress's context line, Home's header). */
export const CONDITION_KEY: Record<WeatherCondition, StringKey> = {
  clear: 'weatherClear', cloudy: 'weatherCloudy', fog: 'weatherFog', rain: 'weatherRainy', snow: 'weatherSnow', storm: 'weatherStorm',
}

export function remembered(key: string): string | null {
  try { return localStorage.getItem(key) } catch { return null }       // private mode: nothing is remembered
}

export function remember(key: string, value: string) {
  try { localStorage.setItem(key, value) } catch { /* the next visit starts from the default */ }
}

export function savedPlace(): Place | null {
  try {
    const place = JSON.parse(remembered(PLACE_KEY) ?? 'null')
    return typeof place?.lat === 'number' && typeof place?.lon === 'number' ? place : null
  } catch {
    return null
  }
}

/** The chip Dress opens on: the last one used, else everyday. */
export function startChip(): string {
  return remembered(CHIP_KEY) ?? DEFAULT_CHIP
}
