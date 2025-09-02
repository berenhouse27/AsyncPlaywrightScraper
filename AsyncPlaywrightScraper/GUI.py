import tkinter as tk
from tkinter import ttk
import webbrowser
import asyncio
import threading

from ScraperHandler import ScraperHandler

class ScraperGUI:
    def __init__(self, whitelist: list[str] = None, blacklist: list[str] = None,
                 headless: bool = True, stealth: bool = True, DEBUG: bool = True):

        self.scraper: ScraperHandler = ScraperHandler(whitelist_keywords=whitelist, blacklist_keywords=blacklist,
                                                      headless = headless, stealth = stealth, DEBUG = DEBUG)
        self.all_results: dict = {}

        self.root = None
        self.dropdown_var = None
        self.input_area = None
        self.search_entries = []
        self.tab_control = None
        self.canvas = None
        self.scrollable_frame = None
        self.search_button = None
        self.top_frame = None

    def update_input_fields(self, selection):
        # Clear previous widgets
        for widget in self.input_area.winfo_children():
            widget.destroy()
        self.search_entries.clear()

        if selection == "company":
            tk.Label(self.input_area, text="Company:").grid(row=0, column=0, padx=5, pady=5)
            entry = tk.Entry(self.input_area)
            entry.grid(row=0, column=1, padx=5, pady=5)
            entry.bind("<Return>", lambda event: self.perform_search())
            self.search_entries.append(entry)

        elif selection == "company + keyword":
            tk.Label(self.input_area, text="Company:").grid(row=0, column=0, padx=5, pady=5)
            entry1 = tk.Entry(self.input_area)
            entry1.grid(row=0, column=1, padx=5, pady=5)

            tk.Label(self.input_area, text="Search Terms:").grid(row=1, column=0, padx=5, pady=5)
            entry2 = tk.Entry(self.input_area)
            entry2.grid(row=1, column=1, padx=5, pady=5)

            # Enter key behavior
            entry1.bind("<Return>", lambda event: entry2.focus_set())
            entry2.bind("<Return>", lambda event: self.perform_search())

            self.search_entries.extend([entry1, entry2])

        self.update_tabs()  # Update tabs when inputs change

    def update_tabs(self):
        # Clear previous tabs
        for tab in self.tab_control.tabs():
            self.tab_control.forget(tab)

        # Create new tabs
        self.tab_news = ttk.Frame(self.tab_control)
        self.tab_company = ttk.Frame(self.tab_control)

        self.tab_control.add(self.tab_news, text="News")
        self.tab_control.add(self.tab_company, text="Company Page")

        self.clear_tab(self.tab_news)
        self.clear_tab(self.tab_company)

    def clear_tab(self, tab) -> None:
        for widget in tab.winfo_children():
            widget.destroy()

    def perform_search(self) -> None:
        # Disable the search button to prevent simultaneous searches
        self.search_button.config(state="disabled", text="Searching...")

        # Run the async search in a separate thread
        search_thread = threading.Thread(target=self._run_async_search)
        search_thread.daemon = True  # Thread will die when main program dies
        search_thread.start()

    def _run_async_search(self):
        update_gui: bool = False
        try:
            company = self.search_entries[0].get()
            search_terms = [
                term.strip()
                for entry in self.search_entries[1:]
                for term in entry.get().split(",")
                if term.strip()
            ]

            self.scraper.retrieve_company(company)
            self.scraper.retrieve_search_terms(search_terms)

            news = self.scraper.run_news_scrape()

            # Create new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            homepage, found_links = None, []

            try:
                if self.dropdown_var.get() == "company":
                    # Only find homepage, no full scrape
                    homepage = self.scraper.find_homepage()

                elif self.dropdown_var.get() == "company + keyword":
                    async def run_scrape():
                        return await self.scraper.run_company_scrape()
                    result = loop.run_until_complete(run_scrape())
                    if result:
                        homepage, found_links = result
                update_gui = True

            finally:
                self.all_results = {
                    "news": news,
                    "homepage": homepage,
                    "found_links": found_links
                }
                loop.close()
                if update_gui:
                    self.root.after(0, self._update_gui_with_results)

        except Exception as e:
            print(f"Search error: {e}")
            self.root.after(0, self._search_error, str(e))

    def _update_gui_with_results(self):
        self.search_button.config(state="normal", text="Search")
        self.update_tabs()
        self.display_results()

    def _search_error(self, error_msg):
        self.search_button.config(state="normal", text="Search")
        self.clear_tab(self.tab_news)
        self.clear_tab(self.tab_company)
        tk.Label(self.tab_news, text=f"Search failed: {error_msg}", font=("Arial", 10), pady=10, fg="red").pack()

    def display_results(self):
        self.clear_tab(self.tab_news)
        self.clear_tab(self.tab_company)
        self.display_news_results(self.tab_news)
        self.display_company_results(self.tab_company)

    def display_news_results(self, tab):
        # Create a scrollable frame for news results
        scrollable_frame = tab

        # Display news results
        news_data = self.all_results.get("news", [])
        if not news_data:
            tk.Label(scrollable_frame, text="No news results found.",
                     font=("Arial", 10), pady=10).pack()
            return

        for i, news_item in enumerate(news_data):
            # Create frame for each news item
            news_frame = tk.Frame(scrollable_frame, relief="solid", bd=1, padx=10, pady=10)
            news_frame.pack(fill="x", padx=5, pady=5)

            # Title (clickable link)
            title_link = tk.Label(news_frame, text=news_item.get("title", "No title"),
                                  font=("Arial", 12, "bold"), fg="blue", cursor="hand2",
                                  wraplength=450, justify="left")
            title_link.pack(anchor="w")
            title_link.bind("<Button-1>", lambda e, url=news_item.get("link", ""): self.create_clickable_link(url))

            # Snippet
            snippet = news_item.get("snippet", "No snippet available")
            snippet_label = tk.Label(news_frame, text=snippet, font=("Arial", 10),
                                     wraplength=450, justify="left")
            snippet_label.pack(anchor="w", pady=(5, 0))

            # URL (smaller text)
            url_label = tk.Label(news_frame, text=news_item.get("link", ""),
                                 font=("Arial", 8), fg="gray", wraplength=450, justify="left")
            url_label.pack(anchor="w", pady=(2, 0))

    def display_company_results(self, tab):
        scrollable_frame = tab

        homepage = self.all_results.get("homepage", "")
        found_links = self.all_results.get("found_links", [])

        if not homepage and not found_links:
            tk.Label(scrollable_frame, text="No company page results found.",
                     font=("Arial", 10), pady=10).pack()
            return

        # Display homepage
        if homepage:
            homepage_frame = tk.Frame(scrollable_frame, relief="solid", bd=2, padx=10, pady=10)
            homepage_frame.pack(fill="x", padx=5, pady=5)

            tk.Label(homepage_frame, text="Company Homepage:",
                     font=("Arial", 14, "bold")).pack(anchor="w")

            homepage_link = tk.Label(homepage_frame, text=homepage, font=("Arial", 11),
                                     fg="blue", cursor="hand2", wraplength=450, justify="left")
            homepage_link.pack(anchor="w", pady=(5, 0))
            homepage_link.bind("<Button-1>", lambda e, url=homepage: self.create_clickable_link(url))

        # Display sublinks
        if found_links:
            tk.Label(scrollable_frame, text="Found Sublinks:",
                     font=("Arial", 14, "bold")).pack(anchor="w", pady=(15, 5))

            sorted_links = sorted(found_links, key=lambda x: len(x.matched_terms), reverse=True)

            for link_data in sorted_links:
                sublink = getattr(link_data, "url", "")
                anchor_text = getattr(link_data, "text", "").strip()
                keywords = getattr(link_data, "matched_terms", [])

                link_frame = tk.Frame(scrollable_frame, relief="solid", bd=1, padx=10, pady=8)
                link_frame.pack(fill="x", padx=5, pady=3)

                if anchor_text:
                    anchor_label = tk.Label(link_frame, text=anchor_text, font=("Arial", 10, "italic"),
                                            wraplength=450, justify="left", fg="gray25")
                    anchor_label.pack(anchor="w", pady=(0, 3))

                # Clickable link
                link_label = tk.Label(link_frame, text=sublink, font=("Arial", 10, "bold"),
                                      fg="blue", cursor="hand2", wraplength=450, justify="left")
                link_label.pack(anchor="w")
                link_label.bind("<Button-1>", lambda e, url=sublink: self.create_clickable_link(url))

                # Matched search terms
                if keywords:
                    if isinstance(keywords, list):
                        keywords_text = ", ".join(keywords)
                    else:
                        keywords_text = str(keywords)

                    keywords_label = tk.Label(link_frame, text=f"Search Terms: {keywords_text}",
                                              font=("Arial", 9), fg="darkgreen")
                    keywords_label.pack(anchor="w", pady=(2, 0))

    def create_clickable_link(self, url):
        if url:
            webbrowser.open(url)

    def on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def create_GUI(self):
        # Root window
        self.root = tk.Tk()
        self.root.title("Fixed Header Search GUI")
        self.root.geometry("500x400")

        # Fixed top frame
        self.top_frame = tk.Frame(self.root)
        self.top_frame.pack(side="top", fill="x")

        # Dropdown
        self.dropdown_var = tk.StringVar()
        dropdown = ttk.Combobox(self.top_frame, textvariable=self.dropdown_var, state="readonly")
        dropdown['values'] = ['company', 'company + keyword']
        dropdown.current(0)
        dropdown.grid(row=0, column=0, padx=5, pady=10)

        # Input area (inside top frame to keep fixed)
        self.input_area = tk.Frame(self.top_frame)
        self.input_area.grid(row=0, column=1, padx=5)

        # Search button
        self.search_button = tk.Button(self.top_frame, text="Search", command=self.perform_search)
        self.search_button.grid(row=0, column=2, padx=5)

        # Scrollable content area with tabs
        self.canvas = tk.Canvas(self.root)
        scrollbar = tk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)

        self.scrollable_frame = tk.Frame(self.canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mousewheel scrolling
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)

        # Create tab_control
        self.tab_control = ttk.Notebook(self.scrollable_frame)
        self.tab_control.pack(fill="both", expand=True)

        # Initialize input fields
        self.update_input_fields('company')

        # Bind dropdown selection change
        dropdown.bind('<<ComboboxSelected>>', lambda event: self.update_input_fields(self.dropdown_var.get()))

        # Start the GUI
        self.root.mainloop()


async def main():
    app = ScraperGUI(headless = True, stealth = True, DEBUG=True)
    app.create_GUI()


if __name__ == "__main__":
    asyncio.run(main())