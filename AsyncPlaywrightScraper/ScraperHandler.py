import asyncio
from HomepageScraper import HomepageScraper, CrawlResult
from NewsScraper import NewsScraper

class ScraperHandler:
    brave_api_key = "<insert API key>"
    def __init__(self, whitelist_keywords: list[str] = None, blacklist_keywords: list[str] = None,
                 max_depth: int = 3, headless: bool = True, stealth: bool = True, DEBUG = False):

        self.homepage_scraper = HomepageScraper(api_key = self.brave_api_key, search_terms = [], whitelist_keywords = whitelist_keywords, blacklist_keywords = blacklist_keywords,
                                                max_depth = max_depth, headless = headless, stealth = stealth, DEBUG = DEBUG)
        self.news_scraper = NewsScraper(DEBUG = DEBUG)

        self.company = None
        self.search_terms = None

        self.DEBUG = DEBUG

    def retrieve_company(self, company: str) -> None:
        if self.DEBUG:
            print(f'[DEBUG][GUI] Company: {company}')
        self.company = company

    def retrieve_search_terms(self, search_terms: list[str]) -> None:
        if self.DEBUG:
            print(f'[DEBUG][GUI] Search Terms: {search_terms}')
        self.search_terms = search_terms

    def run_news_scrape(self) -> list[dict]:
        if self.DEBUG:
            print(f'\n[DEBUG][GUI] BEGINNING NEWS SCRAPE')
        news = self.news_scraper.perform_search(self.company, self.search_terms)
        if self.DEBUG:
            print(f'[DEBUG][GUI] News: {news}')
        return news

    def find_homepage(self) -> str:
        if self.DEBUG:
            print(f'\n[DEBUG][GUI] FINDING HOMEPAGE')
        homepage: str = self.homepage_scraper.find_company_homepage(self.company)
        return homepage

    async def run_company_scrape(self) -> tuple[str,list[CrawlResult]] | None:
        if self.DEBUG:
            print(f'\n[DEBUG][GUI] BEGINNING HOMEPAGE SCRAPE')
        self.homepage_scraper.reset_search_values()
        homepage: str = self.homepage_scraper.find_company_homepage(self.company)
        await self.homepage_scraper.browser_handler.start()
        if homepage:
            self.homepage_scraper.update_search_terms(self.search_terms)
            await self.homepage_scraper.crawl()
            results = self.homepage_scraper.results
            await self.homepage_scraper.browser_handler.stop()
            return homepage, results
        else:
            await self.homepage_scraper.browser_handler.stop()
            return None

async def main():
    handler = ScraperHandler(DEBUG = True)
    company = 'United Aluminum'
    search_terms = ['tolling']
    handler.retrieve_company(company)
    handler.retrieve_search_terms(search_terms)

    handler.run_news_scrape()

    await handler.run_company_scrape()

if __name__ == '__main__':
    asyncio.run(main())