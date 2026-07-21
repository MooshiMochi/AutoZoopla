LOGIN_URL = "https://pro.zoopla.co.uk/login/"
CHECK_LOGIN_URL = "https://login.zoopla.co.uk/u/login"
DASHBOARD_URL = "https://pro.zoopla.co.uk/portal/dashboard?viewId=195132"

CREATE_LISTING_URL = "https://pro.zoopla.co.uk/properties/listing/?category=residential&listing_type=rent&return_url=%2Fproperties%2Fbrowse%2F%3Flisting_type%3Drent"
# CREATE_LISTING_URL = "file:///C:/Users/rchir/Downloads/ZooplaProCreateListing.html"
AGENT_LISTING_URL_FMT = "https://pro.zoopla.co.uk/properties/listing/{_id}"
CHANGE_BRANCH_URL = "https://pro.zoopla.co.uk/change-branch"


BRANCH_SELECTOR = "select#branch_id"
BRANCH_ID = "56042"


# Scraping selectors:

## Address:
LISTING_ADDR_POSTCODE = "input#postcode"
LISTING_ADDR_PROPERTY_NUMBER = "input#property_number"
LISTING_ADDR_STREET_NAME = "input#address"
LISTING_ADDR_TOWN = "input#town"

## Property Details:
LISTING_PROPERTY_TYPE = "select#property_type > option[selected]"

### checkboxes
LISTING_PROPERTY_CHECKBOXES = (
    "label.checkbox[for='retirement_home']",
    "label.checkbox[for='shared_occupancy']",
    "label.checkbox[for='short_let']",
    "label.checkbox[for='students_accepted']",
)

LISTING_PROPERTY_COUNCIL_TAX_BAND = "select#council_tax_band > option[selected]"
LISTING_PROPERTY_COUNCIL_TAX_EXEMPT = "input#council_tax_exempt"

## Price:
LISTING_PRICE_RENT = "input#price"
LISTING_RENT_FREQ = "select#rental_frequency > option[selected]"

# Images:
LISTING_IMAGE_UPLOAD_INPUT = "input.image_upload"

## Description:
LISTING_DESC_BEDROOMS = "select#num_bedrooms_sel > option[selected]"
LISTING_DESC_BATHROOMS = "select#num_bathrooms > option[selected]"
LISTING_DESC_RECEPTIONS = "select#num_recepts > option[selected]"
LISTING_DESC_FLOORS = "select#num_floors > option[selected]"

LISTING_DESC_FURNISHED = "select[name='furnished'] > option[selected]"
LISTING_DESC_AVAILABLE_FROM = "input#available_from"

LISTING_DESC_SUMMARY = "textarea#short_description"
LISTING_DESC_LONG_DESC = "textarea#long_description"

## Features:
LISTING_FEATURES_BILLS_INCLUDED = (
    'label:has(input[value="Bills Included"]) + div > label'
)
LISTING_FEATURES_OUTSIDE_SPACE = 'label:has(input[value="Outside space"]) + div > label'
LISTING_FEATURES_PARKING = 'label:has(input[value="Parking"]) + div > label'
LISTING_FEATURES_ACCESSIBILITY = 'label:has(input[value="Accessibility"]) + div > label'
LISTING_FEATURES_OTHER = (
    "fieldset#listing_features td:has(label.checkbox):last-child > label"
)
