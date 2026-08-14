from __future__ import annotations

from typing import Any


class PlaywrightBrowserAdapter:
    """Thin public-page browser implementation; platform parsing stays outside this layer."""

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout_ms: int = 30_000,
        headers: dict[str, str] | None = None,
        cdp_endpoint: str | None = None,
    ) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.headers = headers or {}
        self.cdp_endpoint = cdp_endpoint
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._context: Any | None = None
        self._page: Any | None = None
        self._uses_existing_browser = False

    async def _ensure_page(self) -> Any:
        if self._page is None:
            try:
                from playwright.async_api import async_playwright
            except ImportError as error:  # pragma: no cover - depends on optional runtime install
                raise RuntimeError("Playwright is not installed; install backend dependencies and browser binaries") from error
            self._playwright = await async_playwright().start()
            if self.cdp_endpoint:
                try:
                    self._browser = await self._playwright.chromium.connect_over_cdp(self.cdp_endpoint, timeout=self.timeout_ms)
                except Exception as error:
                    await self._playwright.stop()
                    self._playwright = None
                    raise RuntimeError(
                        "Could not connect to the system browser. Start Chrome or Edge with remote debugging enabled, sign in there, then verify the local CDP endpoint."
                    ) from error
                if not self._browser.contexts:
                    await self._playwright.stop()
                    self._browser = self._playwright = None
                    raise RuntimeError("The system browser did not expose a usable browsing context")
                self._uses_existing_browser = True
                self._context = self._browser.contexts[0]
            else:
                self._browser = await self._playwright.chromium.launch(headless=self.headless)
                self._context = await self._browser.new_context(extra_http_headers=self.headers or None)
            self._page = await self._context.new_page()
            if self._uses_existing_browser and self.headers:
                # The page is created by this service, so configured headers do not alter the user's other tabs.
                await self._page.set_extra_http_headers(self.headers)
            self._page.set_default_timeout(self.timeout_ms)
        return self._page

    async def open(self, url: str) -> None:
        page = await self._ensure_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)

    async def scroll(self, amount: int) -> None:
        page = await self._ensure_page()
        await page.evaluate("window.scrollBy(0, arguments[0])", amount)

    async def extract_visible_content(
        self, item_selector: str | None = None, field_selectors: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        page = await self._ensure_page()
        selector = item_selector or "body"
        fields = field_selectors or {}
        for attempt in range(3):
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=self.timeout_ms)
                return await page.locator(selector).evaluate_all(
            """(elements, fields) => elements.map((element) => {
                const output = {text: (element.innerText || '').trim(), html: element.outerHTML};
                for (const [name, selector] of Object.entries(fields)) {
                  const target = selector === ':self' ? element : element.querySelector(selector);
                  if (!target) { output[name] = null; continue; }
                  if (name.endsWith('_url') || name === 'url' || name === 'content_link') output[name] = target.href || target.src || target.getAttribute('content') || target.textContent?.trim();
                  else if (name === 'image_urls' || name === 'image' || name === 'images') output[name] = [...element.querySelectorAll(selector)].map(item => item.src || item.href).filter(Boolean);
                  else if (name === 'cover') output[name] = target.src || target.href || target.getAttribute('content') || target.textContent?.trim();
                  else output[name] = (target.getAttribute('content') || target.textContent || '').trim();
                }
                output.url = output.url || element.querySelector('a[href]')?.href || null;
                output.image_urls = output.image_urls || [...element.querySelectorAll('img[src]')].map(item => item.src);
                return output;
            })""",
            fields,
                )
            except Exception as error:
                if "Execution context was destroyed" not in str(error) or attempt == 2:
                    raise
                await page.wait_for_timeout(300 * (attempt + 1))
        return []  # pragma: no cover - the retry loop either returns or raises

    async def screenshot(self) -> bytes:
        return await (await self._ensure_page()).screenshot(full_page=False)

    async def download_media(self, url: str) -> bytes:
        page = await self._ensure_page()
        response = await page.request.get(url, timeout=self.timeout_ms)
        if not response.ok:
            raise RuntimeError(f"Public media download failed with HTTP {response.status}")
        return await response.body()

    async def is_access_blocked(self, indicators: list[str]) -> bool:
        if not indicators:
            return False
        page = await self._ensure_page()
        body_text = (await page.locator("body").inner_text()).lower()
        return any(indicator.lower() in body_text for indicator in indicators)

    async def close(self) -> None:
        # CDP mode attaches to a user-owned browser.  Never close its context or browser;
        # only close the temporary page created for this collection operation.
        if self._uses_existing_browser:
            if self._page is not None:
                await self._page.close()
        else:
            if self._context is not None:
                await self._context.close()
            if self._browser is not None:
                await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        self._browser = self._context = self._page = self._playwright = None
        self._uses_existing_browser = False
