// One small fetch wrapper for every API call. The log-in token lives in
// localStorage; a 401 anywhere logs the user out (see AuthProvider).
import type {
  AdminSource, AdminUser, BuyAdvice, Category, ChatTurn, Completion, Formula, Insights, Item, ItemPatch,
  Listing, ListingFilters, ListingPage, ListingPatch, ModelQuality, ReviewListing, SellForm, Occasion, Outfit, Season, Similar, Stats, User,
  ChatAttachment,
} from './types'

const BASE = '/api'
const TOKEN_KEY = 'dressme.token'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* private mode: the session lasts until the tab closes */
  }
}

let onUnauthorized: () => void = () => {}
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn
}

/** FastAPI errors are {detail: string} or {detail: [{msg}]} (validation). */
function errorText(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown })?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg).replace(/^Value error, /, '')
  return fallback
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  let res: Response
  try {
    res = await fetch(BASE + path, { ...init, headers })
  } catch {
    throw new ApiError(0, 'offline')
  }
  if (res.status === 204) return undefined as T
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    if (res.status === 401 && token) onUnauthorized()
    throw new ApiError(res.status, errorText(body, res.statusText))
  }
  return body as T
}

const json = (method: string, data: unknown): RequestInit => ({ method, body: JSON.stringify(data) })

function photoForm(file: Blob): FormData {
  const form = new FormData()
  form.append('photo', file, 'photo.jpg')
  return form
}

/** Protected images are fetched with the Authorization header (never a token in
 *  the URL, which would leak into logs and history) and shown from a blob URL.
 *  Each path is downloaded once per session. */
const imageCache = new Map<string, Promise<string>>()
export function loadImage(path: string): Promise<string> {
  let p = imageCache.get(path)
  if (!p) {
    p = (async () => {
      const token = getToken()
      const res = await fetch(BASE + path, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      if (!res.ok) throw new ApiError(res.status, res.statusText)
      return URL.createObjectURL(await res.blob())
    })()
    p.catch(() => imageCache.delete(path))   // a failed load can be retried later
    imageCache.set(path, p)
  }
  return p
}

export const api = {
  register: (email: string, password: string, name: string) =>
    request<{ token: string; user: User }>('/auth/register', json('POST', { email, password, name })),
  login: (email: string, password: string) =>
    request<{ token: string; user: User }>('/auth/login', json('POST', { email, password })),
  me: () => request<User>('/me'),
  updateMe: (patch: Partial<Pick<User, 'name' | 'min_coverage' | 'language'>>) =>
    request<User>('/me', json('PUT', patch)),

  items: () => request<Item[]>('/items'),
  item: (id: string) => request<Item>(`/items/${id}`),
  addItem: (file: Blob) => request<Item>('/items', { method: 'POST', body: photoForm(file) }),
  updateItem: (id: string, patch: ItemPatch) => request<Item>(`/items/${id}`, json('PATCH', patch)),
  deleteItem: (id: string) => request<void>(`/items/${id}`, { method: 'DELETE' }),

  insights: () => request<Insights>('/insights'),

  analyze: (file: Blob) => request<Item>('/analyze', { method: 'POST', body: photoForm(file) }),
  buyAdvice: (candidateId: string, corrections?: ItemPatch) =>
    request<BuyAdvice>('/buy-advice', json('POST', { candidate_id: candidateId, corrections })),

  suggest: (opts: { season?: Season; occasion?: Occasion; n?: number }) => {
    const q = new URLSearchParams()
    if (opts.season) q.set('season', opts.season)
    if (opts.occasion) q.set('occasion', opts.occasion)
    q.set('n', String(opts.n ?? 5))
    return request<Outfit[]>(`/outfits/suggest?${q}`)
  },
  outfitLimits: () => request<{ max_items: Record<Category, number> }>('/outfits/limits'),
  score: (itemIds: string[]) => request<Outfit>('/outfits/score', json('POST', { item_ids: itemIds })),
  feedback: (itemIds: string[], rating: 1 | -1) =>
    request<{ item_ids: string[]; rating: 1 | -1 }>('/outfits/feedback', json('POST', { item_ids: itemIds, rating })),
  complete: (itemIds: string[], k = 5) =>
    request<Completion[]>('/outfits/complete', json('POST', { item_ids: itemIds, k })),
  similar: (ref: { itemId?: string; candidateId?: string }, k = 6) => {
    const q = new URLSearchParams({ k: String(k) })
    if (ref.itemId) q.set('item_id', ref.itemId)
    if (ref.candidateId) q.set('candidate_id', ref.candidateId)
    return request<Similar>(`/similar?${q}`)
  },

  listings: (f: ListingFilters = {}) => {
    const q = new URLSearchParams()
    for (const [k, v] of Object.entries(f)) if (v !== undefined && v !== '') q.set(k, String(v))
    return request<ListingPage>(`/listings?${q}`)
  },
  listingSources: () => request<{ source_id: string; brands: string[]; count: number }[]>('/listings/sources'),
  myListings: () => request<Listing[]>('/listings/mine'),
  sell: (file: Blob, f: SellForm) => {
    const form = photoForm(file)
    for (const [k, v] of Object.entries(f)) form.append(k, String(v))
    return request<Listing>('/listings/sell', { method: 'POST', body: form })
  },
  updateListing: (id: string, patch: ListingPatch) => request<Listing>(`/listings/${id}`, json('PATCH', patch)),
  deleteListing: (id: string) => request<void>(`/listings/${id}`, { method: 'DELETE' }),
  listing: (id: string) => request<Listing>(`/listings/${id}`),
  /** "Should I buy this?" on a listing: it becomes a candidate, then use buyAdvice. */
  listingCandidate: (id: string) => request<Item>(`/listings/${id}/candidate`, { method: 'POST' }),

  chat: (message: string) =>
    request<{ reply: string; tools_used: string[]; attachments: ChatAttachment[] }>('/chat', json('POST', { message })),
  chatHistory: () => request<ChatTurn[]>('/chat/history'),
  clearChat: () => request<void>('/chat/history', { method: 'DELETE' }),

  admin: {
    stats: (days = 30) => request<Stats>(`/admin/stats?days=${days}`),
    quality: () => request<ModelQuality>('/admin/model-quality'),
    users: (q = '', page = 1) =>
      request<{ total: number; page: number; size: number; users: AdminUser[] }>(
        `/admin/users?${new URLSearchParams({ q, page: String(page) })}`),
    updateUser: (id: string, patch: { disabled?: boolean; role?: 'user' | 'admin' }) =>
      request<AdminUser>(`/admin/users/${id}`, json('PATCH', patch)),
    deleteUser: (id: string) => request<void>(`/admin/users/${id}`, { method: 'DELETE' }),
    formula: () => request<Formula>('/admin/formula'),
    saveFormula: (values: Record<string, number>) => request<Formula>('/admin/formula', json('PUT', { values })),
    sources: () => request<{ sources: AdminSource[]; file: string }>('/admin/sources'),
    reviewQueue: (status = 'pending') =>
      request<{ total: number; listings: ReviewListing[] }>(`/admin/listings?status=${status}`),
    review: (id: string, status: 'active' | 'rejected', note = '') =>
      request<Listing>(`/admin/listings/${id}`, json('PATCH', { status, note })),
  },
}
