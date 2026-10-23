import { createContext, useContext } from 'react'

/** Which look the shared controls draw (step H). "ticket" = the app's original look (Admin, the Assistant);
 *  "soft" = the team prototype's look (Home and the polished user pages: `Page look="soft"`). Each shared
 *  control (Button, Chip, TextField, Empty, ErrorNote) reads it once, so a page never copies styles. */
export type Look = 'ticket' | 'soft'

export const LookContext = createContext<Look>('ticket')

export function useLook(): Look {
  return useContext(LookContext)
}
