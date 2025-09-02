from html.parser import HTMLParser
import feedparser

class SnippetStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cleaned: list = []

    def handle_data(self, data) -> None:
        self.cleaned.append(data)

    def get_text(self) -> str:
        return ''.join(self.cleaned)


def strip_html_snippet(html_snippet: str) -> str:
    """
    Purpose: strip HTML of tags
    Input:
        - html_snippet = snippet from html
    Output:
        - Stripped html snippet
    """
    stripper = SnippetStripper()
    stripper.feed(html_snippet)
    return stripper.get_text().strip()


class NewsScraper:
    def __init__(self, DEBUG: bool = False):
        self.DEBUG: bool = DEBUG

    def _create_query(self, company: str, search_terms: list[str] = None) -> str:
        """
        Purpose: create query using company name and optionally include search_terms
        Inputs:
            - company = Company name
            - search_terms = Terms to search for
        Output:
            - search query
        """
        if search_terms is None:
            search_terms = []
        terms = [company] + search_terms
        query = " AND ".join(terms)
        if self.DEBUG:
            print(f"[DEBUG][NEWS] Query String: '{query}'")
        return query

    def _build_rss_url(self, company: str, search_terms: list[str] = None) -> str:
        """
        Purpose: create URL for Google News RSS
        Input:
            - company = Company name
            - search_terms = list of terms to search for
        Output:
            - RSS url
        """
        query = self._create_query(company, search_terms)
        rss_url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}"
        return rss_url

    def _parse_feed(self, feed, max_results: int) -> list[dict]:
        """
        Purpose: parse and clean results from RSS feed
        Inputs:
            - feed = Parsed RSS feed object
            - max_results = Max results to return
        Outputs:
            - List of dicts with title and link
        """
        results = []
        entries_to_parse = feed.entries[:max_results]
        if self.DEBUG:
            print(f"[DEBUG][NEWS] Parsing {len(entries_to_parse)} feed entries")
        for entry in entries_to_parse:
            html_summary = getattr(entry, 'summary', "")
            stripped_summary = strip_html_snippet(html_summary)
            results.append({
                "title": entry.title,
                "link": entry.link,
                "snippet": stripped_summary
            })
        return results

    def perform_search(self, company: str, search_terms: list[str], max_results: int = 10) -> list[dict]:
        """
        Purpose: perform search using company name and keywords provided
        Inputs:
            - company = Company name
            - search_terms = terms to search for
            - max_results = Max results to return
        Outputs:
            - List of dicts with title and link
        """
        if self.DEBUG:
            print(f"[DEBUG][NEWS] Starting search for company: '{company}' with keywords: {search_terms}")
        rss_url: str = self._build_rss_url(company, search_terms)
        feed = feedparser.parse(rss_url)
        results: list[dict] = self._parse_feed(feed, max_results)
        if self.DEBUG:
            print(f"[DEBUG][NEWS] Search complete. Found {len(results)} results.")
        return results

def main():
    COMPANY: str = 'midjourney'
    KEYWORDS: list[str] = ['AI', 'disney']
    company_news_scraper = NewsScraper(DEBUG = True)
    output = company_news_scraper.perform_search(COMPANY, KEYWORDS)
    print(type(output))


if __name__ == '__main__':
    main()