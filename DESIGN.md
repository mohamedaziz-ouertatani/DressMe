---
name: DressMe
description: An AI fashion assistant for second-hand shoppers, printed as tickets and validated like a fare.
colors:
  stock: "#E6F0EA"
  stock-deep: "#D3E2D8"
  paper: "#F5F9F6"
  ink: "#1E2E8E"
  ink-soft: "#3A4796"
  carbon: "#14161A"
  carbon-soft: "#3B4440"
  perf: "#9AA7A1"
  stamp: "#C8234F"
  stamp-deep: "#A51A40"
typography:
  display:
    fontFamily: "Readex Pro Variable, Readex Pro, system-ui, sans-serif"
    fontSize: "32px"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.015em"
  headline:
    fontFamily: "Readex Pro Variable, Readex Pro, system-ui, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.25
  title:
    fontFamily: "Readex Pro Variable, Readex Pro, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.25
  body:
    fontFamily: "Readex Pro Variable, Readex Pro, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.625
  label:
    fontFamily: "Readex Pro Variable, Readex Pro, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    letterSpacing: "0.06em"
  second-line:
    fontFamily: "Readex Pro Variable, Readex Pro, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.25
  serial:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: "11px"
    fontWeight: 500
    letterSpacing: "0.08em"
    fontFeature: "tnum"
rounded:
  none: "0px"
  punch: "9999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "40px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.none}"
    padding: "0 16px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.ink-soft}"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0 16px"
    height: "44px"
  button-secondary-hover:
    backgroundColor: "{colors.stock}"
  button-quiet:
    textColor: "{colors.ink}"
    height: "44px"
  chip:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.carbon}"
    rounded: "{rounded.none}"
    padding: "0 12px"
    height: "36px"
  chip-selected:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.none}"
    padding: "0 12px"
    height: "36px"
  ticket:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.carbon}"
    rounded: "{rounded.none}"
  text-field:
    textColor: "{colors.carbon}"
    rounded: "{rounded.none}"
    height: "44px"
  item-photo:
    backgroundColor: "#FFFFFF"
    size: "96px"
  tab-scan:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    size: "68px"
  tab-scan-active:
    backgroundColor: "{colors.stamp}"
    textColor: "{colors.paper}"
---

# Design System: DressMe

## Overview

**Creative North Star: "Ticket & Recharge-Card Stock"**

Every garment is a printed ticket and every verdict is validated like a fare. The ground is guilloché security stock: a pale mint card with a faint ultramarine wave tile printed over it (an authored vector, 240 x 96 px, 0.5 px strokes at 0.08 opacity, from `frontend/scripts/make-guilloche.mjs`). Pieces of content sit on it as paper tickets with square corners, perforated tear-off stubs, mono serials, and a second print line in the other script. The magenta rubber stamp is the single loud mark. It lands when the app has a verdict, and nowhere else.

The density is ticket-office practical. On the phone, tickets stack full width with tight 8 px gaps. Thumb-reach navigation sits in a stub bar at the bottom. On desktop, a rail of ticket stubs runs down the inline-start edge and content can split into a main column and a 300 px aside. The admin area uses the same world, denser and quieter. State is shown with line form wherever possible, not with colour: dashed means the model guessed, solid means a person confirmed.

The world rejects the resale-marketplace default of white rounded cards and floating pills.

**Key Characteristics:**
- Guilloché mint stock ground; paper tickets on top with zero radius.
- Perforated stubs with punched notches carry dates, serials and position counts.
- Ultramarine security-print ink for every action and data mark.
- One reserved magenta for the validation stamp and the active-page punch.
- Dashed = model-guessed, solid = confirmed.
- Every label prints bilingually: UI language plus a second line in the other script.
- Photos are on white plates at one fixed scale, on a shared baseline.

## Colors

The palette is cool security print: a mint card stock, ultramarine ink, near-black carbon, a grey perforation hairline, and one validation magenta held in reserve.

### Primary
- **Security-Print Ultramarine** (ink): primary buttons, secondary outlines, quiet links, selected chips, focus rings, text selection, caret, field-guess dashes, and stamps in their secondary (ink) tone. This is the colour of anything you can act on.
- **Faded Ultramarine** (ink-soft): primary button hover, serials, second print lines, mono field status, and the single bar hue of every admin chart (validated against the ticket surface; chart hover goes to full ink).

### Secondary
- **Validation Magenta** (stamp): the active verdict stamp (BUY / THINK / SKIP), Today's score stamp, and the active-page punch (desktop nav stub dot, phone tab dot, the Scan slot when active). That is the complete list.
- **Pressed Magenta** (stamp-deep): inline validation text and the invalid-field underline. It is never used as a fill.

### Neutral
- **Guilloché Mint Stock** (stock): the page ground under the guilloché tile; the net ground reads #E3EDE7. It is also the colour of punched holes and perforation notches, because they show the ground through the paper.
- **Deep Stock** (stock-deep): the desktop nav rail (at 60%), chart troughs, and skeleton shimmer.
- **Ticket Paper** (paper): the face of every ticket, unselected chips, secondary buttons, error notes, and the phone tab bar.
- **Carbon** (carbon): body and title text, the confirmed-field underline, error note borders, chart baselines, and tooltips.
- **Soft Carbon** (carbon-soft): labels, hints, metadata and inactive nav.
- **Perforation Grey** (perf): perforations, input hairlines, unselected chip edges, scrollbars, and disabled states.

### Named Rules
**The Reserved Magenta Rule.** Magenta appears only on the active verdict stamp, Today's score stamp, and the active-page punch. Secondary and decorative stamps use the ink tone, and a decorative stamp is aria-hidden. If a new screen wants magenta for anything else, it is wrong.

**The Ink Is Action Rule.** Anything tappable, selected, focused or charted is ultramarine. Carbon is for reading and never for an action.

## Typography

**Display Font:** Readex Pro Variable (with Readex Pro, system-ui)
**Body Font:** Readex Pro Variable (one face for Latin and Arabic)
**Label/Mono Font:** JetBrains Mono 500

**Character:** One humanist face covers both scripts, so a Latin line and its Arabic second line read as one print run. The mono is the ticket machine. It prints serials, dates and numbers, and nothing else.

### Hierarchy
- **Display** (600, 22px phone / 24px from 420px / 32px desktop, 1.25, -0.015em): the page title on the header ticket's face. Each page has one.
- **Headline** (600, 18–20px, 1.25): section headings and the scanned item's name.
- **Title** (600, 16px, 1.25): item names on outfit tickets and ticket section headings.
- **Body** (400, 14–16px, 1.625 for paragraphs, max 52ch): hints, reasons, empty-state copy. Inputs use 16px.
- **Label** (500, 12px, 0.06em, uppercase): field-row labels and fieldset legends only. Chips and buttons use 13px and 15px in sentence case.
- **Second line** (400, 12px, ink-soft): the other-script print line under a label.
- **Serial** (JetBrains Mono 500, 11–12px, 0.08em, tabular): serials (`№ 4F2A19`), dates (`03.10.2026`), position counts (`01/04`), confidence, and chart numbers. Always `dir="ltr"`.

### Named Rules
**The One Face Rule.** Readex Pro is the only typeface. Do not add a display face, and do not let the system font stand in as one.

**The Mono Is Data Rule.** JetBrains Mono prints serials, dates and numeric data. Never use it for prose, labels or headings.

**The Bilingual Print Rule.** Every vocabulary label prints in the UI language with a second line in the other script: Arabic under Latin, English under Arabic.

## Layout

Pages are centred in a 1080px column with 16px gutters on phones and 40px on desktop (lg, 1024px). The bottom padding (128px) clears the phone tab bar. Every page opens with its header ticket and a 20px gap. When a page has an aside, from lg up it splits into a fluid main column and a 300px aside with a 32px gap. Focused tasks (Scan) narrow to 640px. Tickets in a list stack with 8px gaps. Inside a ticket the padding is 8–16px, and empty and hero tickets use 20–24px. The dominant rhythm is 8 / 12 / 16. Chip rows scroll sideways on phones without a scrollbar and wrap on desktop. The layout is built on logical properties throughout, so the stub, the stamp offset and the nav rail mirror in Arabic. Directional icons flip in RTL, and serials and the stamp ring stay LTR.

**The Shared Baseline Rule.** Item photos sit on a white plate at one fixed size per context (96px on outfit strips, 72px compact, 132px on the scan ticket). The image is contained and bottom-aligned, so pieces compare like registered plates.

## Elevation & Depth

Depth is paper on card stock: a two-layer shadow, a tight carbon contact line plus a soft ultramarine-tinted drop. Tickets carry the resting shadow. Interactive tickets (nav stubs, completion rows) lift on hover. The Scan tab sits permanently lifted. Holes are the inverse of elevation. Punched notches and chip holes are filled with the stock colour, and the chip hole adds an inset shadow, so the ground seems to show through the paper.

### Shadow Vocabulary
- **Ticket** (`box-shadow: 0 1px 1px rgb(20 22 26 / 0.06), 0 6px 14px -6px rgb(30 46 142 / 0.22)`): the resting state for every ticket.
- **Lift** (`box-shadow: 0 2px 2px rgb(20 22 26 / 0.08), 0 14px 28px -10px rgb(30 46 142 / 0.32)`): hover on interactive tickets, and the Scan slot.
- **Punch** (`box-shadow: inset 0 1px 1.5px rgb(20 22 26 / 0.6)`): the hole in a selected chip.

### Named Rules
**The Paper On Stock Rule.** Only paper casts a shadow. Ground, rails, inputs and chips stay flat.

## Shapes

Every rectangle is square-cornered: tickets, buttons, chips, inputs, the tab bar, tooltips. The only circles are physical: the rubber stamp, the punched holes and notches (14px notches top and bottom of every perforation, 10px chip holes), the active-page punch dots, colour swatches, and the picked-item marker. Perforations are 1.5px dashed perf hairlines. A vertical perforation separates a ticket from its stub, which sits on the inline-end side. A horizontal one tears the phone tab bar from the page. Admin chart columns get a 4px rounded top so the marks read as data, not as tickets.

**The Square Ticket Rule.** Zero radius on every rectangle. A rounded card or pill breaks the world.

## Components

### Buttons
Square ticket-office buttons, 44px minimum height, 15px medium.
- **Shape:** square (0px).
- **Primary:** ink fill, paper text, 16px horizontal padding; hover goes to ink-soft; press nudges down 1px; disabled is perf.
- **Secondary:** paper face with a 1.5px ink outline and ink text; hover fills with stock.
- **Quiet:** ink text with a solid 1px underline (4px offset) that thickens to 2px on hover. It has no box.
- **Focus:** a 2px ink outline at a 2px offset, global.
- **Busy:** a spinning loader icon, with the button disabled and aria-busy set.

### Chips
Fare-zone chips, 36px tall, 13px, square.
- **Unselected:** paper face, 1.5px perf edge, carbon text, medium weight; hover darkens the edge to ink.
- **Selected:** solid ink fill, paper text, semibold, and a punched hole (a 10px stock-colour circle with the punch inset shadow) at the inline start. Set with aria-pressed.

### Tickets / Containers
- **Corner Style:** square (0px).
- **Background:** paper on the stock ground.
- **Shadow Strategy:** Ticket at rest and Lift on hover when interactive (see Elevation).
- **Border:** none. Stubs are separated by a vertical perforation with punched notches.
- **Internal Padding:** 8px on item strips, 12–16px on sections, 20–24px on empty states.
- **Stub:** the tear-off end on the inline-end side. It carries a mono date, a serial, or a position count (`01/04`).

### Header Ticket
Every page header is a ticket. The title sits on the face. A perforated stub carries the mono date and, optionally, a serial. The outfit serial is a 6-character FNV-1a hash of the outfit's item ids, so it never equals one piece's own serial (the last six characters of its id).

### Inputs / Fields
- **Text fields:** transparent, with a solid 1.5px perf hairline underneath. The hairline turns ink on focus, so there is no outline ring. The label is 13px soft carbon above. The value text is 16px.
- **Error:** the underline and the message both turn stamp-deep (12px). Page-level errors are an Error Note: a paper box with a solid 1.5px carbon border, an icon, the message, and a quiet Retry.
- **Ticket-face inputs:** the chat composer and the admin search are paper tickets with the global ink focus ring.
- **Field rows:** a 12px uppercase label column, then the value on a line. A dashed ink line means the model guessed it, with a mono "guessed NN%". A solid carbon line means the user confirmed it, with a mono "confirmed". Tapping opens the choices as chips right below.
- **Admin unsaved edits:** a mono ink marker, "edited · was X", under the changed value.

### Navigation
- **Desktop rail** (236px, stock-deep at 60%, perf edge): a column of ticket stubs, each one 48px tall with an icon and a 15px label on the face and a blank 44px perforated stub. The current page is ink, semibold and full paper, and it carries a magenta punch in its stub. Other pages are paper at 70% in soft carbon and lift on hover. The wordmark, profile, admin and log out sit outside the stubs.
- **Phone tab bar:** a paper bar torn along a dashed perf line at the bottom, with five slots at 11px. The active slot is ink with a small magenta punch dot above. Scan is the big centre slot (68px square, ink, lifted, raised 24px). It turns magenta when active.

### Validation Stamp (signature)
A round rubber stamp in SVG: a 3.5px outer ring, two hairline rings, the ring text running around the edge (always ltr), and a big centre word or number in uppercase 700. A turbulence filter gives it uneven rubber edges. It is rotated about -9 to -11°. When it lands it presses in over 260ms (scale 1.4 → 0.95 → 1, blur 3px → 0, eased with cubic-bezier(0.16, 1, 0.3, 1)). Under reduced motion it fades instead. Tone is magenta only for the active verdict and Today's score. Compact outfit strips and decorative uses (like the login mark) are ink, and decorative stamps are aria-hidden.

### Outfit Strip
An outfit is a vertical strip of item tickets. Each ticket has a photo on its plate, the name, the second line, a colour swatch, and a serial. The stub counts the position (`02/04`). The score stamp overlaps the top inline-end corner. Reasons follow as a list with short perf dashes as bullets.

### Admin Charts
Plain SVG, a single ink-soft hue (hover is ink), and thin columns with 2px gaps on a carbon baseline. Axis numbers are mono. Each chart has a carbon tooltip on hover and focus, and a "Show as a table" disclosure with exact values.

### Loading
Skeletons are a stock-deep → stock shimmer (1.4s linear). The shimmer stops under reduced motion.

## Do's and Don'ts

### Do:
- **Do** put every piece of content on a square paper ticket over the guilloché stock (#E3EDE7 net ground).
- **Do** give every page a header ticket: the title on the face, and a perforated stub with the mono date and an optional serial.
- **Do** use a dashed line only for a model-guessed field or a real perforation. Confirmed fields, inputs, links and borders are solid.
- **Do** keep magenta to the active verdict stamp, Today's score stamp, and the active-page punch. Use tone="ink" for any other stamp.
- **Do** mark a selected chip with a solid ink fill and a punched stock-colour hole.
- **Do** print a second line in the other script under every vocabulary label, and use logical properties so stubs and stamps mirror in Arabic.
- **Do** show photos on a white plate at the context's fixed size, bottom-aligned.
- **Do** give every admin chart a single ink-soft hue, a hover/focus tooltip, and a table view.
- **Do** keep JetBrains Mono for serials, dates and numbers, always LTR and tabular.

### Don't:
- **Don't** round a rectangle or use a pill. The only circles are stamps, holes, punch dots and swatches.
- **Don't** use a dashed border as decoration, as an input style, or for an error. Dashed means "the model guessed this".
- **Don't** use magenta for selection, badges, hover, links, or a decorative stamp.
- **Don't** add a second typeface or use mono for prose.
- **Don't** use colour alone to say guessed vs confirmed. The line form carries it.
- **Don't** cast shadows from anything but paper tickets (and the lifted Scan slot).
