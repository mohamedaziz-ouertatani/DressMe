import { ArrowUpRight, Check, ScanLine, Shirt, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useI18n } from '../i18n'
import { LanguageSwitch } from './AuthPage'
import { Wordmark } from '../shell'
import { Stamp } from '../ui/Stamp'

function PreviewTicket() {
  return (
    <div className="ticket relative mx-auto w-full max-w-[430px] rotate-[1.5deg] p-4 shadow-[var(--shadow-lift)] sm:p-6">
      <div className="mb-5 flex items-start justify-between border-b border-dashed border-perf pb-4">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-soft">DressMe / scan</p>
          <h2 className="mt-1 text-[22px] font-semibold leading-tight text-carbon">Should I buy this?</h2>
        </div>
        <ScanLine className="size-6 text-ink" aria-hidden />
      </div>
      <div className="grid grid-cols-[112px_1fr] gap-4 sm:grid-cols-[132px_1fr]">
        <div className="grid aspect-[3/4] place-items-center bg-white">
          <Shirt className="size-16 text-ink-soft" strokeWidth={1.2} aria-hidden />
        </div>
        <div className="flex flex-col justify-between">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.08em] text-ink-soft">Read from photo</p>
            <p className="mt-2 text-[17px] font-semibold text-carbon">Overshirt</p>
            <p className="mt-1 text-[13px] text-carbon-soft">Olive · casual · mid-season</p>
          </div>
          <div className="border-t border-dashed border-perf pt-3">
            <p className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-soft">Verdict</p>
            <p className="mt-1 text-[24px] font-semibold text-stamp">THINK</p>
            <p className="text-[12px] leading-snug text-carbon-soft">Works with 3 pieces you own. Similar top already in your wardrobe.</p>
          </div>
        </div>
      </div>
      <div className="mt-5 flex items-center justify-between border-t border-dashed border-perf pt-3 font-mono text-[10px] uppercase tracking-[0.08em] text-ink-soft">
        <span>Private wardrobe check</span>
        <span dir="ltr">№ 04A2</span>
      </div>
      <Stamp big="DM" ring="DRESSME · CHECK · DRESSME · CHECK ·" size={72} angle={-10} label="" tone="ink" />
    </div>
  )
}

export function LandingPage() {
  const { t } = useI18n()
  const steps = [
    { icon: ScanLine, text: t('landingStepOne') },
    { icon: Sparkles, text: t('landingStepTwo') },
    { icon: Check, text: t('landingStepThree') },
  ]
  return (
    <div className="min-h-dvh overflow-hidden px-4 pb-12 pt-[max(16px,env(safe-area-inset-top))] sm:px-6 lg:px-10">
      <header className="mx-auto flex w-full max-w-[1180px] items-center justify-between">
        <Wordmark />
        <div className="flex items-center gap-2 sm:gap-5">
          <LanguageSwitch />
          <Link to="/login" className="hidden min-h-9 items-center px-2 text-[13px] font-medium text-ink underline decoration-1 underline-offset-4 hover:decoration-2 sm:inline-flex">
            {t('landingLogin')}
          </Link>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1180px]">
        <section className="grid items-center gap-12 pb-20 pt-16 sm:pt-24 lg:grid-cols-[minmax(0,1fr)_minmax(360px,0.85fr)] lg:gap-20 lg:pb-28 lg:pt-28">
          <div className="max-w-[650px]">
            <h1 className="max-w-[10ch] text-[clamp(3.25rem,8vw,6.5rem)] font-semibold leading-[0.98] tracking-[-0.045em] text-carbon">{t('landingTitle')}</h1>
            <p className="mt-7 max-w-[46ch] text-[18px] leading-relaxed text-carbon-soft sm:text-[20px]">{t('landingBody')}</p>
            <div className="mt-8 flex flex-col items-start gap-4 sm:flex-row sm:items-center">
              <Link to="/signup" className="group inline-flex min-h-12 items-center gap-3 bg-ink px-5 text-[15px] font-semibold text-paper shadow-[var(--shadow-ticket)] transition-[background-color,box-shadow,transform] duration-150 hover:bg-ink-soft hover:shadow-[var(--shadow-lift)] active:translate-y-px">
                {t('landingCta')} <ArrowUpRight className="size-4 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" aria-hidden />
              </Link>
              <Link to="/login" className="inline-flex min-h-11 items-center px-1 text-[14px] font-medium text-ink underline decoration-1 underline-offset-4 hover:decoration-2 sm:hidden">
                {t('landingLogin')}
              </Link>
            </div>
            <p className="mt-7 flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.08em] text-ink-soft">
              <Check className="size-4 text-stamp" aria-hidden /> {t('landingProof')}
            </p>
          </div>
          <div className="relative px-2 sm:px-8 lg:px-0">
            <div className="absolute -inset-5 -z-10 rotate-[-5deg] border border-ink/15 bg-stock-deep/45" aria-hidden />
            <PreviewTicket />
          </div>
        </section>

        <section className="border-t border-dashed border-perf py-10 lg:py-14">
          <div className="grid gap-8 md:grid-cols-3 md:gap-0">
            {steps.map(({ icon: Icon, text }, index) => (
              <div key={text} className={`flex items-start gap-4 ${index > 0 ? 'md:border-s border-perf md:ps-8' : ''}`}>
                <span className="grid size-10 shrink-0 place-items-center bg-paper text-ink shadow-[var(--shadow-ticket)]">
                  <Icon className="size-5" aria-hidden />
                </span>
                <p className="max-w-[22ch] pt-1 text-[16px] font-semibold leading-snug text-carbon">{text}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  )
}
