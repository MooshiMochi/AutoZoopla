import asyncio
from playwright.async_api import async_playwright
from dotenv import load_dotenv
import os

load_dotenv()


DASHBOARD_URL = "https://pro.zoopla.co.uk/portal/dashboard?viewId=195132"
LOGIN_URL = "https://pro.zoopla.co.uk/login/"


async def is_authenticated(page) -> bool:
    await page.goto(
        DASHBOARD_URL,
        wait_until="domcontentloaded",
    )

    # Check something only logged-in users can see.
    username_input = page.locator("input#username")

    try:
        await username_input.wait_for(
            state="visible",
            timeout=5_000,
        )
        print("Not logged in.")
        return False
    except TimeoutError:
        print("Logged in.")
        return True


async def login(page, dry_run: bool = False) -> None:
    email_input = page.locator("input#username")
    password_input = page.locator("input#password")

    submit_button = page.get_by_role("button", name="Sign in")

    await email_input.press_sequentially(os.getenv("ZOOPLA_SOURCE_USERNAME", ""))
    await page.wait_for_timeout(200)  # Wait for 0.2 seconds before typing the password
    await password_input.press_sequentially(os.getenv("ZOOPLA_SOURCE_PASSWORD", ""))
    await page.wait_for_timeout(
        200
    )  # Wait for 0.2 seconds before clicking the submit button

    if dry_run:
        print("Dry run complete. The form has been filled but not submitted.")
        return

    await submit_button.click()


async def main():
    p = await async_playwright().start()

    browser = await p.firefox.launch(headless=False, slow_mo=100)
    context = await browser.new_context(storage_state="data/browser_states/zoopla.json")

    page = await context.new_page()
    await page.goto(DASHBOARD_URL, wait_until="domcontentloaded")

    if await is_authenticated(page):
        print("Already logged in.")
    else:
        await login(page, dry_run=True)

    await page.pause()
    await context.storage_state(path="data/browser_states/zoopla.json")
    await browser.close()
    await p.stop()


if __name__ == "__main__":
    asyncio.run(main())
