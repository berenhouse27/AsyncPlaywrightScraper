import re
import asyncio
from urllib.parse import urlparse, urljoin, unquote, urlunparse
from rapidfuzz import fuzz
from bs4 import BeautifulSoup
import requests
from dataclasses import dataclass
import tldextract
from BrowserHandler import BrowserHandler
from requests.adapters import HTTPAdapter, Retry


@dataclass
class CrawlResult:
    url: str
    text: str
    matched_terms: list[str]


def normalize_url(url: str) -> str | None:
    """
    Purpose: normalize URL
    Input:
        - url = url to normalize
    Output:
        - normalized URL
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None
    netloc = parsed.netloc.lower().lstrip("www.")
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme, netloc, path, '', '', ''))


def strip_common_path(source_url: str, target_url: str) -> str:
    """
    Purpose: Strip common path from link for processing
    Input:
        - source_url = URL to base stripping off of
        - target_url = URL to be stripped
    Output:
        - Stripped URL
    """
    source_parsed = urlparse(source_url)
    target_parsed = urlparse(target_url)

    if source_parsed.netloc != target_parsed.netloc:
        return target_url

    source_parts = [p for p in source_parsed.path.strip('/').split('/') if p]
    target_parts = [p for p in target_parsed.path.strip('/').split('/') if p]

    common_length = 0
    for s_part, t_part in zip(source_parts, target_parts):
        if s_part == t_part:
            common_length += 1
        else:
            break

    unique_parts = target_parts[common_length:]
    unique_path = '/'.join(unique_parts)

    rest = ''
    if target_parsed.query:
        rest += '?' + target_parsed.query
    if target_parsed.fragment:
        rest += '#' + target_parsed.fragment

    return unique_path + rest


class HomepageScraper:
    default_whitelist = [
        r'news(room)?',
        r'insight(s)?',
        r'article(s)?',
        r'press(-release)?s?',
        r'media(center)?',
        r'announcements?',
        r'investor(s)?(-)?( )?relations'
        r'updates?',
        r'blog(s)?',
        r'company[-_]?news',
        r'industry[-_]?news',
        r'bulletin(s)?',
        r'journalist(s)?'
    ]
    default_blacklist = [
        r'contact$', r'careers?$', r'jobs?$', r'support$', r'help$', r'faq$',
        r'privacy$', r'terms$', r'legal$', r'cookies?$', r'sitemap$', r'search$',
        r'login$', r'register$', r'account$', r'profile$', r'cart$', r'checkout$',
        r'author(/[^/]+)?$',
        r'date/\d{4}/?$',
        r".(html|htm|php|asp|pdf|doc|docx|txt|ppt|pptx|rtf|jpg|jpeg|webp|png|gif)$",
        r'https?://(www\.)?facebook\.com/[^/?#\s]+',
        r'https?://(www\.)?instagram\.com/[^/?#\s]+',
        r'https?://(www\.)?linkedin\.com/(in|company)/[^/?#\s]+',
        r'https?://(www\.)?twitter\.com/[^/?#\s]+',
        r'https?://(www\.)?youtube\.com/(c|channel|user)/[^/?#\s]+',
        r'https?://(www\.)?tiktok\.com/@[^/?#\s]+',
        r'https?://(www\.)?X\.com/[^/?#\s]+',
    ]
    def __init__(self, api_key: str, search_terms: list[str], whitelist_keywords: list[str] = None, blacklist_keywords: list[str] = None,
                 max_depth: int = 3, headless: bool = True, stealth: bool = True, DEBUG: bool = False):
        self.api_key = api_key
        self.DEBUG = DEBUG
        self.max_depth = max_depth
        self.header = {"Accept": "application/json", "X-Subscription-Token": api_key}
        self.brave_url = "https://api.search.brave.com/res/v1/web/search"

        self.browser_handler = BrowserHandler(headless = headless, stealth = stealth, DEBUG = DEBUG)

        self.company_homepage = None

        whitelist_keywords = whitelist_keywords or self.default_whitelist
        blacklist_keywords = blacklist_keywords or self.default_blacklist
        self.whitelist_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in whitelist_keywords]
        self.blacklist_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in blacklist_keywords]

        self.search_terms: list[str] = search_terms
        self.results: list[CrawlResult] = []
        self.seen_links: set[str] = set()
        self.processed_links: set[str] = set()

    def update_search_terms(self, search_terms: list[str]) -> None:
        self.search_terms = search_terms

    def reset_search_values(self) -> None:
        self.company_homepage = None
        self.search_terms = []
        self.results = []
        self.seen_links = set()
        self.processed_links = set()

    def find_company_homepage(self, company: str) -> str | None:
        """
        Purpose: Find company's homepage
        Input:
            - company = Company name
        Output:
            - Company homepage
        Effect: Updates self.company_homepage
        """
        def generate_brave_api_parameters(company_name: str) -> dict[str, str | int]:
            """
            Purpose: Create parameters to connect to Brave API
            """
            query = f"{company_name} official website"
            if self.DEBUG:
                print(f"[DEBUG][HOMEPAGE] Query: {query}")
            return {"q": query, "count": 5, "source": "web"}

        def fuzzy_match(string1: str, string2: str, threshold: int = 45) -> bool:
            """
            Purpose: Match strings using fuzzy matching
            """
            return fuzz.ratio(string1.lower(), string2.lower()) >= threshold

        parameters = generate_brave_api_parameters(company)
        session = requests.Session()
        session.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=0.5)))
        response = session.get(self.brave_url, headers=self.header, params=parameters)

        if response.status_code != 200:
            return None

        results = response.json().get("web", {}).get("results", [])
        company_domain = company.lower()

        for result in results:
            link = result.get("url", "")
            result_domain = tldextract.extract(urlparse(link).netloc).domain.lower()
            if fuzzy_match(company_domain, result_domain):
                self.company_homepage = link
                if self.DEBUG:
                    print(f"[DEBUG][HOMEPAGE] Matched domain: {link}")
                break
        if self.company_homepage:
            return self.company_homepage
        else:
            if self.DEBUG:
                print(f'[DEBUG][HOMEPAGE] No homepage found')
            return None

    async def _scrape_for_links(self, start_url: str = None) -> tuple[str, dict[str, str]] | None:
        """
        Purpose: scrape a designated page for all possible links and their anchor text
        Input:
            - start_url = URL to start scraping from
        Output:
            - Tuple containing starting url and a dict with links and their anchor text
        Effect: Adds any found links to self.seen_links
        """
        start_url = start_url or self.company_homepage
        if not start_url:
            print("Set Company Homepage First")
            return None

        content = await self.browser_handler.get_page_content(start_url)
        if not content:
            return None

        soup = BeautifulSoup(content, "lxml")
        found_links: dict[str, str] = {}

        # 1) Find links having standard anchor (<a>) tags with href attribute
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            anchor_text = tag.get_text(separator=" ").strip()
            full_url = urljoin(start_url, unquote(href))
            parsed = urlparse(full_url)
            if parsed.scheme not in {"http", "https"}:
                continue

            normalized_url = normalize_url(full_url)
            if normalized_url and normalized_url not in self.seen_links:
                found_links[normalized_url] = anchor_text
                self.seen_links.add(normalized_url)

        # 2) Find JavaScript-driven links via onclick attributes
        onclick_elements = soup.find_all(attrs={"onclick": True})
        onclick_pattern = re.compile(r"location\.href\s*=\s*['\"](.*?)['\"]", re.IGNORECASE)
        for el in onclick_elements:
            onclick = el["onclick"]
            match = onclick_pattern.search(onclick)
            if match:
                full_url = urljoin(start_url, match.group(1).strip())
                normalized_url = normalize_url(full_url)
                if normalized_url and normalized_url not in self.seen_links:
                    found_links[normalized_url] = ""  # No anchor text
                    self.seen_links.add(normalized_url)

        # 3) Find links embedded in custom data attributes (data-url, data-href)
        for attr in ("data-url", "data-href"):
            data_elements = soup.find_all(attrs={attr: True})
            for el in data_elements:
                data_url = el[attr].strip()
                full_url = urljoin(start_url, data_url)
                normalized_url = normalize_url(full_url)
                if normalized_url and normalized_url not in self.seen_links:
                    found_links[normalized_url] = ""  # No anchor text
                    self.seen_links.add(normalized_url)

        # 4) Find meta refresh redirect links
        meta_refresh = soup.find("meta", attrs={"http-equiv": "refresh"})
        if meta_refresh:
            content_attr = meta_refresh.get("content", "")
            match = re.search(r"url=(.+)", content_attr, re.IGNORECASE)
            if match:
                full_url = urljoin(start_url, match.group(1).strip())
                normalized_url = normalize_url(full_url)
                if normalized_url and normalized_url not in self.seen_links:
                    found_links[normalized_url] = ""  # No anchor text
                    self.seen_links.add(normalized_url)

        if self.DEBUG:
            print(f"[DEBUG][HOMEPAGE] Collected {len(found_links)} links from: {start_url}")

        return start_url, found_links

    def _process_links(self, links: tuple[str, dict[str, str]]) -> tuple[list[str], list[CrawlResult]]:
        """
        Purpose: Process each link and evaluate whether it is relevant or contains search terms.
        Input:
            - links = (source_url, {normalized_url: anchor_text})
        Output:
            - relevant_links = links that match whitelist/blacklist rules
            - result_links = CrawlResult objects where anchor or path matches search terms
        Effect: Adds any processed links to self.processed_links
        """
        def is_article(path: str) -> bool:
            """
            Purpose: determine if path is likely to be an article
            """
            parsed = urlparse(path)
            path = parsed.path.lower().strip("/") or path.lower().strip("/")
            if not path:
                return False
            # Check for overly long slug [ ex) https://news.lenovo.com/long-article-title-with-many-hyphens ]
            slug = path.split("/")[-1]
            parts = slug.split("-")
            if len(parts) >= 4 and sum(len(p) for p in parts) > 30:
                return True
            # Check for common date formats
            if re.search(r'/\d{4}([/-])?\d{2}(([/-])?\d{2})?([/-])?', f"/{path}/"):  # /yyyy/mm/dd OR /yyyy-mm-dd OR /yyyymmdd
                return True
            if re.search(r'/\d{2}([/-])?\d{2}(([/-])?\d{4})?([/-])?', f"/{path}/"):  # /dd/mm/yyyy OR /dd-mm-yyyy OR /ddmmyyyy
                return True
            # Check for a UUID pattern
            if re.search(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', path):
                return True

            return False

        def is_relevant(path: str) -> bool:
            """
            Purpose: determine if path is likely to be a relevant link
            """
            path_lower = path.lower()
            article_check = is_article(path_lower)
            has_whitelist_match = any(pattern.search(path_lower) for pattern in (self.whitelist_patterns or []))
            has_blacklist_match = any(pattern.search(path_lower) for pattern in (self.blacklist_patterns or []))

            # If there is a whitelist match AND no blacklist match AND it's not an article, return True
            return has_whitelist_match and not has_blacklist_match and not article_check

        def is_result(text: str) -> list[str] | None:
            """
            Purpose: determine if path is likely to be a result
            """
            matches = [term for term in self.search_terms if term.lower() in text.lower()]
            return matches if matches else None

        source = links[0]
        links_to_process = links[1]
        relevant_links: list[str] = []
        result_links: list[CrawlResult] = []

        for link, anchor_text in links_to_process.items():
            if link in self.processed_links:
                continue
            self.processed_links.add(link) # Add any processed links to list to avoid re-processing unnecessarily

            stripped_link = strip_common_path(source, link)
            if not stripped_link:
                continue

            relevant = is_relevant(stripped_link)
            matched_terms = is_result(stripped_link + " " + anchor_text)

            if relevant:
                relevant_links.append(link)
            if matched_terms:
                result_links.append(CrawlResult(
                    url = link,
                    text = anchor_text,
                    matched_terms = matched_terms
                ))

            if self.DEBUG:
                print(f'[DEBUG][HOMEPAGE] Processed link: {stripped_link}')
                print(f"                  Relevant: {relevant}")
                print(f"                  Matched Terms: {matched_terms}")

        return relevant_links, result_links


    async def crawl(self, max_tabs: int = 10) -> None:
        """
        Purpose: Run scrape_for_links and process_links to continuously crawl multiple pages
        Inputs:
            - max_tabs = max number of concurrent tabs able to be opened by Playwright
        Effect: Add results to self.results
        """
        semaphore = asyncio.Semaphore(max_tabs)
        queue: list[tuple[str, int]] = [(self.company_homepage, 0)]
        iterations = 1

        async def scrape_and_process(link: str, depth: int):
            """
            Purpose: asynchronously scrape and process a link
            """
            async with semaphore:
                links_to_process = await self._scrape_for_links(link)
                if not links_to_process:
                    return []

                relevant_links, result_links = self._process_links(links_to_process)
                self.results.extend(result_links)

                # Return new links to crawl with incremented depth
                return [(rl, depth + 1) for rl in relevant_links if depth + 1 <= self.max_depth]

        if self.DEBUG:
            print(f"[DEBUG][HOMEPAGE][BEGIN] Beginning Crawl")

        while queue:
            if self.DEBUG:
                print(f"[DEBUG][HOMEPAGE][CRAWL #{iterations}][BEGIN]")

            # Launch concurrent scraping tasks
            tasks = [scrape_and_process(link, depth) for link, depth in queue]
            relevant_links = await asyncio.gather(*tasks)

            # Combine results into singular list and add all relevant links to queue
            queue = [link for sublist in relevant_links for link in sublist]

            if self.DEBUG:
                print(f"[DEBUG][HOMEPAGE][CRAWL #{iterations}] Links Still In Queue: {len(queue)}")
                print(f"                            Total Results Found: {len(self.results)}")
                print(f"[DEBUG][HOMEPAGE][CRAWL #{iterations}][END]")
            iterations += 1

        await self.browser_handler.reset_headless()

        if self.DEBUG:
            print(f"[DEBUG][HOMEPAGE][END] Crawl Completed:")
            print(f"                       {len(self.seen_links)} Links Seen")
            print(f"                       {len(self.processed_links)} Links Processed")
            print(f"                       {len(self.results)} Results Found")

async def main() -> None:

    BRAVE_API_KEY = "BSAKe9yRx_jPam-h0rz1YvotUkSjIDY"
    COMPANY = "air liquide"
    SEARCH_TERMS = ['second quarter']

    DEBUG_MODE = True

    scraper = HomepageScraper(BRAVE_API_KEY, SEARCH_TERMS,
                              max_depth=3, headless = True, DEBUG=DEBUG_MODE)

    await scraper.browser_handler.start()

    homepage = scraper.find_company_homepage(COMPANY)

    if homepage:
        await scraper.crawl()
        print(scraper.results)

    await scraper.browser_handler.stop()


if __name__ == "__main__":
    asyncio.run(main())

