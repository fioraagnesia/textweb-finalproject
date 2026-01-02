import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests

# === CONFIGURATIONS ===
BASE_URL = "https://www.tempo.co"
LIST_PAGE_URL = f"{BASE_URL}/indeks?category=contentCategory&content_category=berita&page="
MAX_LIMIT = 2500 # Set the total number of articles you want to process
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': BASE_URL 
}

session = requests.Session()
retry = Retry(
    total=10,
    backoff_factor=2,
    status_forcelist=[500, 502, 503, 504, 429]
)
adapter = HTTPAdapter(max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)


# --- LINK HARVESTING FUNCTION (Index Page) ---
def get_all_links_url(max_limit):
    """
    Collects article links from the Tempo.co index pages using pagination.
    """
    all_links = set()
    page_counter = 1
    LINK_SELECTOR = 'figure.contents a'     # Link selector for Tempo.co

    # Looping each page until the total links has reached the max_limit 
    while len(all_links) < max_limit:
        page_url = f"{LIST_PAGE_URL}{page_counter}"
        print(f"\n--- Collecting links from Page {page_counter} (Collected: {len(all_links)}/{max_limit}) ---")
        time.sleep(5.0)

        try:
            response = session.get(page_url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            links_before_update = len(all_links)
            link_elements = soup.select(LINK_SELECTOR)
            
            for link_tag in link_elements:
                if len(all_links) >= max_limit:
                    break

                relative_url = link_tag.get('href')
                
                # # Filter and add valid absolute URL (/read/...)
                if relative_url and relative_url.startswith('/'):
                    absolute_url = urljoin(BASE_URL, relative_url)
                    all_links.add(absolute_url)

            links_added = len(all_links) - links_before_update

             # Stop Condition: If no new unique links are found
            if links_added == 0 and page_counter > 1:
                print("No new unique links found. Stopping index scraping.")
                break

            if len(all_links) >= max_limit:
                break

            # Move to the next page
            page_counter += 1

        except requests.exceptions.RequestException as e:
            print(f"Failed to load page {page_url}. Error: {e}. Stopping.")
            break

    return list(all_links)


# --- DATA EXTRACTION FUNCTION (Scrape Article Detail) ---
def scrape_full_article(article_url):
    """Fetches a single article and extracts the full content using requests."""
    # CSS Selectors (Tempo Article Page)
    TITLE_SELECTOR = 'h1' 
    CATEGORY_SELECTOR = 'div.flex span.text-sm.font-medium.text-primary-main' 
    DATE_SELECTOR = 'p.text-neutral-900.text-sm' 
    ARTICLE_SELECTOR = 'div#content-wrapper, div[data-innity-container="article"]' # Selector for the main article body

    try:
        response = session.get(article_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        # Metadata defaults
        title, category, source, publication_date, narasi_text = 'N/A', 'N/A', 'tempo.co', 'N/A', 'N/A'

        # --- Extract Metadata ---
        # 1. Title
        title_element = soup.select_one(TITLE_SELECTOR)
        if title_element:
             title = title_element.get_text(strip=True)
        
        # 2. Category (last item in breadcrumb)
        category_element = soup.select(CATEGORY_SELECTOR)
        if category_element:
            category = category_element[-1].get_text(strip=True)
        
        # 3. Date
        date_container = soup.select_one(DATE_SELECTOR)
        if date_container:
            date_text = date_container.get_text(separator=' ', strip=True)
            
            # Ex: "4 Desember 2025 | 18.00 WIB"
            # Separate by '|'
            parts = date_text.split('|')
            if len(parts) >= 2:
                # First part: date (result: "4 Desember 2025")
                publication_date = parts[0].strip() 

        # 4. Full Text (Narasi)
        all_article_wrappers = soup.select(ARTICLE_SELECTOR)     # main container for the article
        cleaned_paragraphs = []
        
        if all_article_wrappers:
            # Loop every container found
            for wrapper in all_article_wrappers:
                # Find all <p> tags inside the wrapper
                paragraphs = wrapper.find_all('p') 
                # Looping to get all the paragraphs
                for p in paragraphs:
                    text_content = p.get_text(strip=True)

                    # Filter the contents
                    if 'Pilihan Editor:' in text_content:
                      break
                    if text_content and len(text_content) > 30 and 'ADVERTISEMENT' not in text_content.upper():
                        cleaned_paragraphs.append(text_content)

            # Join all paragraphs from all wrappers
            narasi_text = '\n\n'.join(cleaned_paragraphs)

        return {
            'title': title,
            'source': source,
            'date': publication_date,
            'category': category,
            'narasi': narasi_text,
            'url': article_url,
            'status': 'fact',
        }

    except requests.exceptions.RequestException as e:
        print(f"Error fetching article {article_url}: {e}")
        return None
    except Exception as e:
        print(f"General error processing article {article_url}: {e}")
        return None


# === MAIN EXECUTION ===
final_scraped_data = []

print(f"--- Stage 1: Collecting Links based on Data Limit ({MAX_LIMIT} Links) ---")
all_article_links_list = get_all_links_url(MAX_LIMIT)
print(f"\nCollected a total of {len(all_article_links_list)} unique article links.")

print("--- Stage 2: Scraping Full Content for Each Article ---")
# Loop through collected links
for i, link in enumerate(all_article_links_list):
    if i >= MAX_LIMIT:
        break 

    print(f"Scraping article {i+1}/{min(MAX_LIMIT, len(all_article_links_list))}: {link}")
    article_data = scrape_full_article(link)

    if article_data:
        final_scraped_data.append(article_data)

    time.sleep(5.0)


# --- Save Data ---
if final_scraped_data:
    df = pd.DataFrame(final_scraped_data)
    df.to_csv('news_tempo.csv', index=False, encoding='utf-8-sig')
    print(f"\nSuccess! Scraped a total of {len(final_scraped_data)} full articles and saved to news_tempo.csv")
else:
    print("\nNo full article content was scraped in the end.")