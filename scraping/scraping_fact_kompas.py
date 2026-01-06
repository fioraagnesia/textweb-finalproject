import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from requests.exceptions import RequestException

# === CONFIGURATIONS ===
BASE_URL = "https://indeks.kompas.com"
LIST_PAGE_URL = f"{BASE_URL}/?page="
# Set the total number of articles you want to process
MAX_LIMIT = 1000 # scraping raw data
# MAX_LIMIT = 200  # scraping test data
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': BASE_URL 
}

# --- LINK HARVESTING FUNCTION (Index Page) ---
def get_all_links_url(max_limit):
    """
    Collects article links from the Kompas.com index pages using pagination.
    """
    all_links = set()
    page_counter = 1
    LINK_SELECTOR = 'a[href*="/read/"]'     # Link selector for Kompas.com

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
    # CSS Selectors (Kompas Article Page)
    TITLE_SELECTOR = 'h1.read__title' 
    CATEGORY_SELECTOR = 'li.breadcrumb__item a, div.breadcrum-new li a' 
    DATE_SOURCE_CONTAINER_SELECTOR = 'div.read__time'
    ARTICLE_SELECTOR = 'div.read__content' 

    try:
        response = requests.get(article_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        # Metadata defaults 
        title, category, source, publication_date, narasi_text = 'N/A', 'N/A', 'N/A', 'N/A', 'N/A'
        
        # -- Extract Metadata --
        # 1. Title
        title_element = soup.select_one(TITLE_SELECTOR)
        if title_element:
             title = title_element.get_text(strip=True)
        
        # 2. Category (last item in breadcrumb)
        category_element = soup.select(CATEGORY_SELECTOR)
        if category_element:
            category = category_element[-1].get_text(strip=True)
        
        # 3. Date and Source 
        date_source_container = soup.select_one(DATE_SOURCE_CONTAINER_SELECTOR)
        if date_source_container:
            date_source_text = date_source_container.get_text(separator=' ', strip=True)
            
            # Ex: "Kompas.com, 4 Desember 2025, 18:00 WIB"
            # Separate the data by comma
            parts = date_source_text.split(',')
            if len(parts) >= 2:
                # First part: source (result: "Kompas.com")
                source = parts[0].strip()
                # Second part: date (result: "4 Desember 2025")
                publication_date = parts[1].strip()
        
        # 4. Full Text (Narasi)
        article_wrapper = soup.select_one(ARTICLE_SELECTOR)     # main container for the article

        if article_wrapper:
            paragraphs = article_wrapper.find_all('p')
            cleaned_paragraphs = []
            
            # Looping to get all the paragraphs
            for p in paragraphs:
                text_content = p.get_text(strip=True)
                # Filter out ads and non-content text
                if text_content and len(text_content) > 10 and 'ADVERTISEMENT' not in text_content.upper():
                    cleaned_paragraphs.append(text_content)

            # Join all paragraphs
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


# --- Save Raw Data ---
if final_scraped_data:
    df = pd.DataFrame(final_scraped_data)
    df.to_csv('news_kompascom.csv', index=False, encoding='utf-8-sig')
    print(f"\nSuccess! Scraped a total of {len(final_scraped_data)} full articles and saved to news_kompascom.csv")
else:
    print("\nNo full article content was scraped in the end.")

# --- Save Test Data ---
# if final_scraped_data:
#     df = pd.DataFrame(final_scraped_data)
#     df.to_csv('test_news_kompascom.csv', index=False, encoding='utf-8-sig')
#     print(f"\nSuccess! Scraped a total of {len(final_scraped_data)} full articles and saved to news_kompascom.csv")
# else:
#     print("\nNo full article content was scraped in the end.")