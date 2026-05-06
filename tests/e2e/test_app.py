import pytest
from playwright.async_api import Page, expect

BASE_URL = "http://localhost:7860"


@pytest.mark.asyncio
async def test_app_loads(page: Page):
    await page.goto(BASE_URL)
    await expect(page).to_have_title("music-intel")


@pytest.mark.asyncio
async def test_settings_tab_visible(page: Page):
    await page.goto(BASE_URL)
    settings_tab = page.get_by_role("tab", name="Settings")
    await expect(settings_tab).to_be_visible()


@pytest.mark.asyncio
async def test_provider_dropdown_present(page: Page):
    await page.goto(BASE_URL)
    await page.get_by_role("tab", name="Settings").click()
    provider_dropdown = page.get_by_label("AI Provider")
    await expect(provider_dropdown).to_be_visible()


@pytest.mark.asyncio
async def test_analyze_tab_has_artist_input(page: Page):
    await page.goto(BASE_URL)
    await page.get_by_role("tab", name="Analyze").click()
    artist_input = page.get_by_placeholder("e.g. Radiohead")
    await expect(artist_input).to_be_visible()


@pytest.mark.asyncio
async def test_discover_tab_visible(page: Page):
    await page.goto(BASE_URL)
    discover_tab = page.get_by_role("tab", name="Discover")
    await expect(discover_tab).to_be_visible()


@pytest.mark.asyncio
async def test_source_checkboxes_present(page: Page):
    await page.goto(BASE_URL)
    await page.get_by_role("tab", name="Analyze").click()
    for source in ["Spotify", "MusicBrainz", "Last.fm", "Discogs"]:
        checkbox = page.get_by_label(source)
        await expect(checkbox).to_be_visible()


@pytest.mark.asyncio
async def test_export_buttons_present(page: Page):
    await page.goto(BASE_URL)
    await page.get_by_role("tab", name="Analyze").click()
    await expect(page.get_by_role("button", name="Export CSV")).to_be_visible()
    await expect(page.get_by_role("button", name="Export JSON")).to_be_visible()
