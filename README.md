# Property Re-listing automation using Playwright

## Commands

```bash
pip install -e .

playwright install
```

run the CLI tool with the following command:

```bash
relister relist \
  --source zoopla \
  --destination zoopla \
  --url "https://www.zoopla.co.uk/to-rent/details/12345678/"

relister relist \
  --source zoopla \
  --destination zoopla \
  --url "https://www.zoopla.co.uk/to-rent/details/12345678/" \
  --publish

relister relist \
  --source zoopla \
  --destination zoopla \
  --url "LISTING_URL"

```

## Image Manager UI

Install the desktop dependency first:

```bash
pip install -r requirements.txt
```

Then launch the image manager from the repo root:

```bash
python image_manager/src/main.py
```

The UI lets you pick a folder, reorder thumbnails by dragging, and save the current order to `instructions.txt` in that folder.
