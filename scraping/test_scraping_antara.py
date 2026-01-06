import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from requests.exceptions import RequestException

# === CONFIGURATIONS ===
BASE_URL = "https://www.antaranews.com"
LIST_PAGE_URL = f"{BASE_URL}/terkini/"
# Set the total number of articles you want to process
MAX_LIMIT = 200  # scraping test data
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': BASE_URL 
}

# --- LINK HARVESTING FUNCTION (Index Page) ---
def get_all_links_url(max_limit):
    """
    Collects article links from the Antara News index pages using pagination.
    """
    all_links = set()
    page_counter = 1
    LINK_SELECTOR = 'a[href*="/berita/"]'     # Link selector for antaranews

    # Looping each page until the total links has reached the max_limit
    while len(all_links) < max_limit:
        page_url = f"{LIST_PAGE_URL}{page_counter}"
        print(f"\n--- Collecting links from Page {page_counter} (Collected: {len(all_links)}/{max_limit}) ---")
        
        time.sleep(5.0)

        try:
            response = requests.get(page_url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            links_before_update = len(all_links)
            link_elements = soup.select(LINK_SELECTOR)
            
            for link_tag in link_elements:
                if len(all_links) >= max_limit:
                    break

                relative_url = link_tag.get('href')
                
                # Filter and add valid absolute URL
                if relative_url and relative_url.startswith('https://'):
                    all_links.add(relative_url)

            links_added = len(all_links) - links_before_update

            # Stop Condition: If no new unique links are found
            if links_added == 0 and page_counter > 1:
                print("No new unique links found. Stopping index scraping.")
                break

            if len(all_links) >= max_limit:
                break

            # Move to the next page
            page_counter += 1

        except RequestException as e:
            print(f"Failed to load page {page_url}. Error: {e}. Stopping.")
            break

    return list(all_links)


# --- DATA EXTRACTION FUNCTION (Scrape Article Detail) ---
def scrape_full_article(article_url):
    """Fetches a single article and extracts the full content using requests."""
    # CSS Selectors (Antara News Article Page)
    TITLE_SELECTOR = 'h1' 
    SOURCE_CATEGORY_SELECTOR = 'ul.breadcrumbs li.breadcrumbs__item a' 
    DATE_SELECTOR = 'div.wrap__article-detail-info span'
    ARTICLE_SELECTOR = 'div.post-content, div.post-content.clearfix, div.content-text'

    try:
        response = requests.get(article_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        # Metadata defaults
        title, category, source, publication_date, narasi_text= 'N/A', 'N/A', 'N/A', 'N/A', 'N/A'

        # --- Extract Metadata ---
        # 1. Title
        title_element = soup.select_one(TITLE_SELECTOR)
        if title_element:
             title = title_element.get_text(strip=True)
        
        # 2. Category (last item in breadcrumb)
        category_element = soup.select(SOURCE_CATEGORY_SELECTOR)
        if category_element:
            category = category_element[-2].get_text(strip=True)
        
        # 3. Source
        source_element = soup.select(SOURCE_CATEGORY_SELECTOR)
        if source_element:
            source = source_element[0].get_text(strip=True)

        # 4. Date 
        date_container = soup.select_one(DATE_SELECTOR)

        if date_container:
            date_text = date_container.get_text(separator=' ', strip=True)
            
            # Ex: "Kamis, 4 Desember 2025 18:00 WIB"
            # Separate the data by comma
            parts = date_text.split(',')
            if len(parts) >= 2:
                # Second part: date (result: "4 Desember 2025 18:00 WIB")
                full_date = parts[1].strip()
                # To get the date only (without time)
                publication_date = re.sub(r'\s*\d{1,2}[:.]\d{2}\s*(WIB|WITA|WIT)?', '', full_date).strip()
        
    
        # 5. Full Text (Narasi & Penjelasan)
        article_wrapper = soup.select_one(ARTICLE_SELECTOR)     # main container for the article

        if article_wrapper:
            paragraphs = article_wrapper.find_all('p')
            cleaned_narasi = []
           
            for p in paragraphs:
                text_content = p.get_text(strip=True)

                if text_content and len(text_content) > 10 and 'IKLAN' not in text_content.upper() and 'Baca juga:' not in text_content:
                        cleaned_narasi.append(text_content)
            
            # Join all paragraphs
                narasi_text = '\n\n'.join(cleaned_narasi)

        return {
            'title': title,
            'source': source,
            'date': publication_date,
            'category': category,
            'narasi': narasi_text,
            'url': article_url,
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


# --- Save Test Data ---
if final_scraped_data:
    df = pd.DataFrame(final_scraped_data)
    df.to_csv('test_news_antaranews.csv', index=False, encoding='utf-8-sig')
    print(f"\nSuccess! Scraped a total of {len(final_scraped_data)} full articles and saved to test_news_antaranews.csv")
else:
    print("\nNo full article content was scraped in the end.")