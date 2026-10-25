import { Link } from 'react-router-dom'
import { MessageCircle } from 'lucide-react'
import { useI18n } from '../i18n'
import { Page } from '../shell'
import { Empty } from '../ui/states'

/** The Assistant while it is rebuilt: step 3a removed the old chat, and the new Ask flow and assistant arrive in steps
 *  3b to 3h. Until then this page says so and points to the screens that work. */
export function AssistantPage() {
  const { t } = useI18n()
  return (
    <Page title={t('navAssistant')} look="soft" kicker={t('assistantKicker')}>
      {/* TODO(step 3f): the new assistant's conversation goes here */}
      <Empty
        icon={MessageCircle}
        title={t('assistantTitle')}
        body={t('assistantBody')}
        action={
          <Link to="/dress" className="press inline-flex min-h-button items-center justify-center rounded-pill bg-pill px-6 text-[16px] font-semibold text-pill-text">
            {t('assistantGo')}
          </Link>
        }
      />
    </Page>
  )
}
