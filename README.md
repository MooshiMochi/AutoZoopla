# AutoZoopla property relister

AutoZoopla is a Playwright-based property relisting tool with one combined desktop application for both relisting and image ordering.

## Install

```bash
pip install -e .
playwright install
```

## Launch the combined desktop app

```bash
autozoopla
```

The existing command remains available as an alias:

```bash
relister-gui
```

The desktop app contains two pages:

- **Relist property** configures and runs the source-to-destination relist workflow.
- **Image organiser** selects visible images, changes their upload order and writes `instructions.txt` into the image folder.

When an image directory is selected, the relist cannot start until the directory contains a valid, non-empty `instructions.txt`. Use **Organise** or **Open image organiser** to prepare that directory. Saving the order returns the folder to the relist page and marks it ready.

When Playwright needs a login code or other user response, the app returns to the relist page, highlights and pulses the input panel, focuses the response field, alerts the application window and plays the system notification sound.

## CLI

Dry run:

```bash
relister relist \
  --source zoopla \
  --destination zoopla \
  --url "https://pro.zoopla.co.uk/properties/listing/1234567"
```

Publish with an ordered image directory:

```bash
relister relist \
  --source zoopla \
  --destination zoopla \
  --url "https://pro.zoopla.co.uk/properties/listing/1234567" \
  --images "C:\\path\\to\\images" \
  --publish
```

The standalone `imager` command is retained for backwards compatibility, although the same organiser is now built into `autozoopla`.
