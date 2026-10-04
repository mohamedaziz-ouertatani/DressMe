import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AdminFormula, AdminLayout, AdminModeration, AdminOverview, AdminQuality, AdminSources, AdminUsers } from './admin/AdminPages'
import { AuthProvider, useAuth } from './auth'
import { I18nProvider } from './i18n'
import { AuthPage } from './pages/AuthPage'
import { LandingPage } from './pages/LandingPage'
import { BuildPage } from './pages/BuildPage'
import { ChatPage } from './pages/ChatPage'
import { InsightsPage } from './pages/InsightsPage'
import { ProfilePage } from './pages/ProfilePage'
import { ScanPage } from './pages/ScanPage'
import { ListingPage, ShopPage } from './pages/ShopPage'
import { SellPage } from './pages/SellPage'
import { SimilarPage } from './pages/SimilarPage'
import { TodayPage } from './pages/TodayPage'
import { TryOnPage } from './pages/TryOnPage'
import { ItemPage, WardrobePage } from './pages/WardrobePage'
import { AppShell, Wordmark } from './shell'
import { ErrorNote } from './ui/states'
import { ApiError } from './api/client'

function Gate({ children, admin = false }: { children: ReactNode; admin?: boolean }) {
  const { user, ready, unreachable, retry } = useAuth()
  if (unreachable) return <Unreachable onRetry={retry} />
  if (!ready) {
    return (
      <div className="grid min-h-dvh place-items-center" aria-busy="true">
        <Wordmark />
      </div>
    )
  }
  if (!user) return <Navigate to="/welcome" replace />
  if (admin && user.role !== 'admin') return <Navigate to="/" replace />
  return <>{children}</>
}

function Unreachable({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="mx-auto flex min-h-dvh max-w-[440px] flex-col justify-center gap-6 px-4">
      <Wordmark />
      <ErrorNote error={new ApiError(0, '')} onRetry={onRetry} />
    </div>
  )
}

function GuestOnly({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth()
  if (ready && user) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <I18nProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/welcome" element={<GuestOnly><LandingPage /></GuestOnly>} />
            <Route path="/login" element={<GuestOnly><AuthPage mode="login" /></GuestOnly>} />
            <Route path="/signup" element={<GuestOnly><AuthPage mode="signup" /></GuestOnly>} />
            <Route element={<Gate><AppShell /></Gate>}>
              <Route index element={<TodayPage />} />
              <Route path="scan" element={<ScanPage />} />
              <Route path="wardrobe" element={<WardrobePage />} />
              <Route path="wardrobe/:id" element={<ItemPage />} />
              <Route path="insights" element={<InsightsPage />} />
              <Route path="build" element={<BuildPage />} />
              <Route path="tryon" element={<TryOnPage />} />
              <Route path="chat" element={<ChatPage />} />
              <Route path="similar" element={<SimilarPage />} />
              <Route path="shop" element={<ShopPage />} />
              <Route path="shop/:id" element={<ListingPage />} />
              <Route path="sell" element={<SellPage />} />
              <Route path="me" element={<ProfilePage />} />
            </Route>
            <Route path="/admin" element={<Gate admin><AdminLayout /></Gate>}>
              <Route index element={<AdminOverview />} />
              <Route path="quality" element={<AdminQuality />} />
              <Route path="users" element={<AdminUsers />} />
              <Route path="formula" element={<AdminFormula />} />
              <Route path="sources" element={<AdminSources />} />
              <Route path="moderation" element={<AdminModeration />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </I18nProvider>
  )
}
