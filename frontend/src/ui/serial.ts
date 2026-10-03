/** Short serial from an id, printed like a ticket number: № 4F2A19 */
export function serialOf(id: string): string {
  return id.slice(-6).toUpperCase()
}

/** Serial of a set of items (an outfit): a short hash of all their ids, so it
 *  never equals one piece's own serial. */
export function groupSerial(ids: string[]): string {
  let h = 0x811c9dc5                       // FNV-1a
  for (const ch of ids.join('|')) {
    h ^= ch.charCodeAt(0)
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return h.toString(16).toUpperCase().padStart(8, '0').slice(-6)
}
