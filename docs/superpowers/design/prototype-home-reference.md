# DressMe prototype: Home screen reference

Source: the team's interactive prototype (Design canvas "DressMe app prototype", 390 x 844 phone frame, 5 tabs: Home,
Dress, Buy, Add, Wardrobe). A REFERENCE for look and layout only. All names, dates, weather and pieces in it are sample
data: never copy them into the app; the app shows the user's real data. The tokens are in `dressme-prototype-tokens.json`
next to this file; the full prototype markup (`dressme-prototype.dc.html`) was handed over with the step-H brief.

## Type

- Display family: `"Bricolage Grotesque", "Figtree", system-ui, sans-serif`
- Body family: `"Figtree", system-ui, sans-serif`
- Google Fonts: `https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500..800&family=Figtree:wght@400..700&display=swap`
- Neither font has Arabic glyphs: Arabic needs its own family in the stack.

## Home screen, top to bottom

1. **Header**: a soft context line (date and weather, 14/20 medium, `ink-soft`), then the greeting as the one display
   headline (40/42, 700, -0.03em). On the right, a 48 px round `ink` avatar button with the user's initial that opens
   profile and settings.
2. **Today's pick** (hero, the whole card is one button to Dress): `tint-sage` card, radius 32, padding 20. Top row: a
   white pill "Today's pick" and a caption "Safe · high confidence". Middle: an overlapping collage of the outfit's
   cut-out photos with a soft drop shadow. Bottom row: title 24/28 display, one reason in `ink-soft`, and a 48 px round
   `ink` arrow button. Too few pieces for an outfit: a "Start here / Add your first clothes" card instead (same tint
   and radius) with one black pill button.
3. **Two big action tiles** (2-column grid, gap 12, height 156, radius 28, padding 16): "Should I buy it?" on an `ink`
   fill with white text, and "Add clothes" on `surface`. Each has a 44 px round icon disc at the top and a title plus
   one-line subtitle at the bottom.
4. **Ask the stylist** (one row, `tint-lilac`, radius 28): title and subtitle on the left, a 44 px round `surface` icon
   button on the right.
5. **Your wardrobe · N items**: a heading row with an underlined "See all" link, then a horizontal strip of piece tiles
   (92 x 116, radius 20, `surface`, photo contained), scrolling edge to edge with the 20 px gutter kept.
6. **Gap card** (`tint-peach`, radius 28, padding 20): a small caption "Gap in your wardrobe", a 24 px title, one
   sentence, and a `surface` pill button that opens Should I buy it?
7. Screen padding: 64 px top, 20 px sides, 128 px bottom (clears the floating tab bar). Sections 28 px apart.

## Tab bar

A floating pill: 20 px from the sides and 24 px from the bottom, 64 px high, `surface`, radius 999, `shadow-float`,
padding 8. Each tab is a 48 px pill. The active tab is filled `ink` with `on-ink` text and shows its icon plus label;
the others show the icon only (with an `aria-label`).

## Motion and global rules

- Pressable things scale to 0.97 on press (160 ms). A screen rises 14 px and fades in on open (320 ms). Bottom sheets
  slide up. All motion is off under `prefers-reduced-motion`.
- Only the tab bar and bottom sheets cast a shadow. Cards are flat colour on the `ground`.
- Garment cut-outs use `object-fit: contain` with a soft drop shadow, on a light `photo` tile.
- Icons are thin stroke icons (1.75 px, round caps), never emoji.
- Focus ring: 2 px `accent` outline, offset 2 px.
