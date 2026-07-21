# AutoZoopla main app UI redesign — design

- **Date:** 2026-07-21
- **Status:** Approved (visual mockups signed off)
- **Scope:** Broader redesign, "refined evolution" direction. Styling and layout
  only — no relist/scrape/worker/image-ordering logic changes.

## Problem

The AutoZoopla desktop app (PySide6) has a decent underlying design language
(dark sidebar, light cards, badges) but suffers from accumulated rough edges,
confirmed by rendering the real windows offscreen at several sizes:

1. **Broken / squished on smaller windows.** When the "Action required" input
   prompt appears on a short window, the relist page overlaps itself — the
   config card's forced `minimumHeight` + the action bar + the splitter's
   hard-coded `[330, 220]` sizes exceed the available height, so the image
   status banner is clipped and the action bar paints over it. This is the same
   class of overlap bug [CHANGES.md](../../../CHANGES.md) has patched repeatedly.
2. **Old-looking bits.** Native, unstyled combo boxes whose drop-down arrow
   clips the rounded border; two competing stylesheets (`image_manager_app.py`'s
   `APP_STYLE` overlaps and disagrees with `main_window`'s inline sheet — e.g.
   title 18pt vs 21pt); a flat single-column form.
3. **Fragile responsiveness.** `resizeEvent` hard-codes magic breakpoints
   (760px / 1120px) and hides subtitles/hints, and the organiser toolbar uses a
   rigid `QGridLayout` that truncates its subtitle ("…into the corre") as the
   window narrows.

## Goals

- One source of truth for the visual system (tokens + QSS), shared by both the
  relist window and the embedded/standalone image organiser.
- Eliminate the overlap class of bugs structurally, not with more breakpoints.
- Modernise inputs (custom combos, retuned checkboxes) and restructure the
  relist form and organiser into clearer, reflowing layouts.
- Preserve all existing behaviour: validation, worker threads, settings
  persistence, prompt bridge, visibility tint, keyboard shortcuts.

## Non-goals

- No change to scraping/relisting/worker logic or the image-ordering engine
  (drag/drop, thumbnail loading, instructions.txt format).
- No new dependencies. No light/dark toggle (YAGNI for a single-user tool).
- Not adopting Zoopla's official branding/logo (third-party tool — stays
  neutral to avoid impersonation).

## Design

### Design tokens & theme module

New module `src/relister/gui/theme.py` owns the entire visual system:

- **Palette:** background `#f5f7fc`; sidebar `#0f172a` (hover `#1e293b`); card
  `#ffffff` / border `#e6eaf2`; text `#0f172a` / `#475569` / `#94a3b8`; accent
  indigo `#4f46e5` (hover `#4338ca`, soft `#eef2ff` / `#c7d2fe`); success/
  warning/danger tints; console `#0b1220`.
- **Type scale:** 12.5 / 13 / 13.5 / 15 / 24 px, one family (`"Segoe UI"`), one
  weight ramp. **Spacing:** 4/8/12/16/20 grid. **Radii:** inputs 10, cards 14.
- `build_stylesheet() -> str` returns the full QSS covering both surfaces
  (relist window + organiser selectors), replacing both existing stylesheets.
- Shared custom widgets live here so both surfaces use them:
  - `ChevronCombo(QComboBox)` — paints its own chevron; the native arrow is
    hidden via QSS (`::down-arrow { image: none; }`), so the rounded border can
    never be clipped.
  - `ModernCheckBox(QCheckBox)` — moved from `main_window.py`, retuned to the
    accent token.

`image_manager_app.py` deletes its local `APP_STYLE`. The embedded organiser is
already styled by the main window's sheet; the standalone `imager` entry point
imports the shared stylesheet lazily (guarded so image_manager still runs if
relister is somehow unavailable).

### Relist page restructure

The config card becomes labelled groups, each with a small-caps header and
label-above-field inputs, separated by hairline dividers:

- **Providers** — Source + Destination as `ChevronCombo`s, side by side (half
  width each), stacking vertically when narrow.
- **Listing** — Original listing URL (full width).
- **Images** — folder field + Browse + Organise (Organise = soft-accent
  button); Browse/Organise wrap below the field when narrow. Image-status
  banner sits directly beneath.
- **Options** — the three `ModernCheckBox`es.

Action bar (Start / Cancel / Clear output + progress + status) restyled with
tokens. All existing object names and signal wiring are preserved.

### Robust layout (kills the overlap bug)

Each page's content is wrapped in a `QScrollArea(widgetResizable=True)`:

- When the viewport is tall enough, the inner widget stretches to fill it, so
  the console card (Expanding, modest `minimumHeight`) grows — same "console
  fills the space" feel as today.
- When the viewport is too short (e.g. small window with the prompt open),
  a vertical scrollbar appears and **nothing overlaps**.

The console + prompt `QSplitter` and its forced sizes are removed. The prompt is
a card appended after the console; `_show_prompt` scrolls it into view via
`QScrollArea.ensureWidgetVisible` when it appears (preserving the existing
raise/focus/beep attention behaviour). The config card's forced
`minimumHeight` hack is removed.

### Responsive strategy

`resizeEvent`'s content-hiding is replaced by natural reflow:

- Subtitles use `setWordWrap(True)` and are never hidden.
- One gentle width breakpoint toggles the Providers row and the Browse/Organise
  row between side-by-side and stacked — it only *reflows*, never hides
  essential controls. Implemented by swapping which layout the fields sit in on
  resize.

### Organiser restructure

- Toolbar rebuilt from the rigid 4-column grid into a header row (title +
  wrapping subtitle stacked on the left, Choose folder / Save on the right) with
  the path chip below — no truncation.
- New **empty state**: a dashed card with a glyph, "No folder selected yet",
  guidance text, and a Choose folder CTA, shown until a folder is loaded. Fills
  the former dead space.
- Image cards restyled with tokens; the green "Visible" / grey "Hidden"
  visibility tint on each card's combo is preserved.

### Window sizing

Default nudged to ~1280×860 so the console is visible at rest; minimum lowered
(the scroll area makes small windows safe rather than something to forbid).

## Files changed

- **New:** `src/relister/gui/theme.py` (tokens, `build_stylesheet`,
  `ChevronCombo`, `ModernCheckBox`).
- `src/relister/gui/main_window.py` — rebuild `_build_relist_page`,
  `_apply_styles`, `resizeEvent`, prompt show/clear/sizing; import shared theme
  and widgets; drop the local `ModernCheckBox`.
- `src/image_manager/image_manager_app.py` — delete `APP_STYLE`; standalone
  `main()` uses the shared stylesheet; organiser toolbar → reflowing header;
  add empty state.

## Verification

No unit tests exist and layout is visual, so verification is:

1. A render harness (already built in scratchpad) that grabs both pages at
   default / narrow / prompt-open sizes and the organiser empty/populated states
   — inspect for overlap, truncation, clipping.
2. Import + short-lived launch smoke test of `autozoopla` and `imager` entry
   points (offscreen) to confirm nothing throws.

## Risks

- Reworking the prompt/console section touches attention-handling code; keep the
  raise/focus/beep/alert behaviour and the enable/disable of the prompt field.
- `image_manager` importing `relister.gui.theme` is a new cross-package link;
  keep it lazy + guarded so the organiser remains independently runnable.

## Post-review refinements (2026-07-21)

After the first build was reviewed, these decisions changed:

- **Providers no longer stack.** They stay side by side (two columns) at every
  width, including the minimum. The width-breakpoint reflow (`_apply_relist_reflow`,
  the `resizeEvent` override) is removed entirely — providers and the image
  field/buttons fit comfortably down to the minimum window width.
- **Prompt bar is pinned, not scrolled.** The input panel now lives in a
  container *below* the scroll area (`promptContainer` in `page_layout`), so the
  input box is always visible when the workflow asks for input and can never be
  scrolled off-screen. The earlier `ensureWidgetVisible` scroll-to is removed.
- **Popups are explicitly themed.** The global `* { color: … }` rule was leaving
  unstyled `QMessageBox`/`QMenu`/`QDialog` surfaces dark-on-dark under a dark-mode
  OS palette. Added explicit light backgrounds + dark text for dialogs and menus.
- **Compactness.** Input/button heights 40→34, page title 24→21, and card/page
  paddings and spacing tightened; default window 1220×820, minimum 880×600.

## Second refinement pass (2026-07-21)

- Removed the page title; the header is now just the description + a status
  badge with rounded (8px) corners.
- Form sections use an inline left tag (`_section_row`): the small-caps section
  name sits beside its field labels. Options is unlabelled; dividers removed.
- Image-folder status moved out of the form into a top banner that slides down
  (`_build_top_banner` / `_show_top_banner`, `maximumHeight` animation); neutral
  state shows nothing.
- The user-input area is now a permanent section below the console
  (`_build_input_section`), disabled by default and enabled with an accent glow
  (`QGraphicsDropShadowEffect` + `promptInput[active]` border) when input is
  requested. The pin-below-scroll container and the orange attention pulse are
  removed.
- Compacted sizes/paddings so the console and input section fit with no scroll;
  window minimum raised to 910×760, sidebar horizontal padding reduced.
