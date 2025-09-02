import asyncio
from playwright.async_api import async_playwright

class BrowserHandler:
    def __init__(self, headless: bool = True, stealth: bool = True, DEBUG: bool = False):
        self.playwright = None
        self.browser = None
        self.context = None
        self.headless = headless
        self.original_headless = headless
        self.stealth = stealth
        self.DEBUG = DEBUG

    async def start(self) -> None:
        """
        Purpose: Open a browser with stealth and block heavy resources
        """
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context()

        # Block heavy resources like images, stylesheets, fonts
        await self.context.route("**/*", self._block_heavy_resources)

    async def stop(self) -> None:
        """
        Purpose: Close browser and clean up resources
        """
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def get_page(self):
        """
        Purpose: Return new browser page with optional stealth
        """
        if not self.context:
            raise RuntimeError("Browser context not started.")
        page = await self.context.new_page()
        if self.stealth:
            await self._apply_stealth(page)
        return page

    async def get_page_content(self, url: str, timeout: int = 30000, allow_retry: bool = True) -> str | None:
        """
        Purpose: Open link and return full HTML content. Retry in non-headless mode if needed.
        """
        page = await self.get_page()
        try:
            await page.goto(url, timeout=timeout)

            try:
                await page.wait_for_selector("a[href]", timeout=timeout)
            except Exception:
                await asyncio.sleep(5)

            content = await page.content()

            # Retry if content is empty or suspiciously short
            if not content.strip() or "<a" not in content:
                raise ValueError("Empty or non-functional page content")

            return content

        except Exception as e:
            if self.DEBUG:
                print(f"[DEBUG][BROWSER][ERROR] get_page_content failed (headless={self.headless}): {e}")

            # Retry logic: only retry once, in non-headless mode
            if self.headless and allow_retry:
                if self.DEBUG:
                    print(f"[DEBUG][BROWSER] Retrying with headless=False")
                await self.stop()
                self.headless = False
                await self.start()
                return await self.get_page_content(url, timeout=timeout, allow_retry=False)

            return None

        finally:
            await page.close()

    async def reset_headless(self):
        if self.headless != self.original_headless:
            if self.DEBUG:
                print(f"[DEBUG][BROWSER] Resetting headless from {self.headless} to {self.original_headless}")
            await self.stop()
            self.headless = self.original_headless
            await self.start()

    async def _block_heavy_resources(self, route, request):
        """
        Purpose: Block unnecessary resources like images and fonts
        """
        if request.resource_type in ["image", "stylesheet", "font"]:
            await route.abort()
        else:
            await route.continue_()

    async def _apply_stealth(self, page):
        """
        Purpose: Inject stealth JS to mask automation
        """
        await page.add_init_script("""() => {
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });

            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Intel Inc.';
                if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                return getParameter.call(this, parameter);
            };
        }""")
