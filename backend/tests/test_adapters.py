import pytest

from app.browser.mock import MockBrowserAdapter
from app.platforms.mock import MockPlatformAdapter


@pytest.mark.anyio
async def test_mock_adapters_expose_protocol_operations() -> None:
    browser = MockBrowserAdapter([{"title": "Visible"}])
    await browser.open("https://example.test")
    assert browser.current_url == "https://example.test"
    assert await browser.extract_visible_content() == [{"title": "Visible"}]

    platform = MockPlatformAdapter([{"url": "https://example.test/item"}])
    assert await platform.search("example", 1) == [{"url": "https://example.test/item"}]
    await platform.open_content("https://example.test/item")
    assert platform.opened_url == "https://example.test/item"
