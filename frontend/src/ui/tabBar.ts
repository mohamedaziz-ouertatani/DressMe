import { createContext, useContext, useEffect } from 'react'

/** Lets a view hide the phone tab bar while it shows its own bar at the bottom (the verdict's Bought it / Left it,
 *  step H2). The shell provides the setter; `--tabbar-h` falls to 0 while the bar is hidden. */
export const TabBarContext = createContext<(hidden: boolean) => void>(() => {})

/** Hides the phone tab bar for as long as the calling component is on screen. */
export function useHideTabBar() {
  const setHidden = useContext(TabBarContext)
  useEffect(() => {
    setHidden(true)
    return () => setHidden(false)
  }, [setHidden])
}
