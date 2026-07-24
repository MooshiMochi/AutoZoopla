# Combined desktop app changes

## 0.1.1a — bug-fix pass

- **Browser no longer leaks between runs.** Cancelling a relist now always tears the
  browser context and browser down (even if the cancellation lands mid-teardown), and
  the login guard stops listening and cancels its tasks on close.
- **Doubled listing fields are auto-corrected.** After filling the create-listing form,
  the filled text fields (address + rent) are read back and re-filled until they match
  the source listing, fixing occasional doubling such as `ChurchillChurchill` before the
  listing is saved.
- **Dry run pauses in the app, not the browser inspector.** Instead of `page.pause()`
  (which opens the slow Chromium dev console on macOS), a dry run now waits for you to
  press Enter in the app's input panel.
- **Clearing the listing URL clears the image folder** too.
- **Saved image folders load reliably.** A stored path is normalised (whitespace, `~`,
  redundant separators) on load so it no longer spuriously warns that the folder is
  missing.
- **App icon.** Added an "AZ" monogram icon for the macOS bundle, Dock and window/taskbar.
- Window title and sidebar now show the version (`v0.1.1a`).

## Unified application

- Embedded the image ordering UI as `ImageOrderPage` inside the relister application.
- Added a modern sidebar for switching between **Relist property** and **Image organiser**.
- Added the `autozoopla` application command while retaining `relister-gui` and the standalone `imager` compatibility command.

## Image pre-handling

- Selecting an image directory immediately validates:
  - the folder exists and is readable;
  - supported images are present;
  - `instructions.txt` exists;
  - `instructions.txt` is not empty;
  - every listed image still exists and has a supported extension.
- The relist Start button remains disabled until the chosen image folder is ready.
- Missing or invalid instructions show an inline warning and offer to open the organiser or choose another folder.
- Saving an image order updates the relist image directory and returns to the relist page when the organiser was opened from that workflow.
- Saving is blocked when every image is marked Hidden.

## User-input attention

When the browser workflow requests input, the application now:

- switches back to the relist page;
- expands, highlights and pulses the input panel;
- changes the status badge to **ACTION NEEDED**;
- focuses the response field;
- restores and raises the application window;
- requests a taskbar/window alert;
- plays the system notification sound.

## Visual refresh

- Added a modern navigation shell, cards, status banners and badges.
- Improved spacing, typography, inputs, buttons, progress indicators and logs.
- Changed the log viewer to a high-contrast console-style panel.
- Applied a consistent design to the embedded image organiser.
## UI layout and checkbox fix

- Prevented the relist form from stretching and painting its controls over neighbouring rows.
- Assigned consistent heights to provider selectors, text fields and image action buttons.
- Added fixed-height form labels and top-aligned the form so it remains readable at different display scaling levels.
- Replaced platform-dependent checkbox indicators with consistently rendered checkboxes that remain visible when hovered, checked, focused or disabled.


## Compact-window layout fix

- Removed the duplicate configuration subtitle and tightened the relist-page spacing.
- Reduced form control heights slightly while preserving consistent row geometry.
- Enforced the configuration card's minimum layout height so Qt cannot compress rows until they overlap.
- Collapsed the user-input panel when no response is required; it now appears only when the workflow requests input.
- Added a compact mode that hides non-essential explanatory text and reduces outer margins in shorter windows.
- Allowed the log area to shrink before the relist form, keeping the configuration readable without maximising the window.

## UI redesign ("refined evolution")

Design doc: `docs/superpowers/specs/2026-07-21-main-app-ui-redesign-design.md`.

- Added a single shared theme module (`relister/gui/theme.py`): design tokens,
  one stylesheet and the custom widgets (`ChevronCombo`, `ModernCheckBox`).
  Deleted the duplicate `APP_STYLE` from the image organiser so both surfaces
  share one source of truth.
- Replaced native, clipping combo boxes with self-painted chevron combos.
- Restructured the relist form into labelled groups (Providers, Listing,
  Images, Options) with label-above-field inputs and side-by-side providers.
- Wrapped the relist page in a scroll area and removed the console/prompt
  splitter and the forced minimum-height hack. This structurally eliminates the
  prompt-panel overlap on short windows; the prompt now scrolls into view.
- Replaced the magic-breakpoint `resizeEvent` (which hid content) with layouts
  that reflow: provider and image-action rows stack when the window is narrow;
  subtitles wrap instead of being hidden or truncated.
- Rebuilt the organiser toolbar so its subtitle no longer truncates, and added
  an empty-state prompt with a call to action before a folder is chosen.

### Post-review refinements

- Source and destination providers now stay side by side at every width
  (removed the width-breakpoint reflow); tightened control heights, typography
  and spacing for a more compact layout.
- Pinned the user-input prompt bar below the scroll area so its input box is
  always visible when the workflow asks for input (previously it could be
  scrolled off-screen).
- Themed dialogs and menus explicitly (light surface, dark text) so message-box
  and menu text stays readable when the OS is in dark mode.

### Second review pass

- Removed the large "Relist a property" page title (the sidebar already names
  the section) and gave the status badge rounded corners consistent with the
  rest of the UI.
- Made each section tag (Providers / Listing / Images) sit inline to the left of
  its field(s); removed the Options heading and the section dividers.
- Replaced the persistent inline image-status message with a warning/success
  banner that slides down from the top of the page (nothing shown when no
  replacement folder is selected).
- Tightened control sizes, paddings and spacing so the full console and the
  input section are visible without scrolling at the default and minimum sizes.
- Reworked the user-input area into a permanent section below the program
  output: disabled by default, enabled with an accent (indigo) glow on the input
  box when the workflow asks for input.
- Reduced the sidebar's horizontal padding; set the window minimum to 910×760
  (≈30px wider than before) so the whole layout always fits without scrolling.
