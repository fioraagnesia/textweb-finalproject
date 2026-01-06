import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from requests.exceptions import RequestException

# === CONFIGURATIONS ===
BASE_URL = "https://www.idntimes.com"
LIST_PAGE_URL = f"{BASE_URL}/index?category=all&page="
# Set the total number of articles you want to process
MAX_LIMIT = 250  # scraping test data
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': BASE_URL 
}

# --- LINK HARVESTING FUNCTION (Index Page) ---
def get_all_links_url(max_limit):
    """
    Collects article links from the IDN Times index pages using pagination.
    """
    all_links = set()
    page_counter = 1
    LINK_SELECTOR = 'div.css-1lir9g0 a[href*="/"]'     # Link selector for IDN Times

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
                link_title = link_tag.get('title-article') or link_tag.get_text()
                # Filter and add valid absolute URL
                if relative_url and relative_url.startswith('https://'):
                    is_not_quiz = link_title and '[QUIZ]' not in link_title.upper()     # Filter out quiz links
                    is_article = relative_url.count('/') > 3    # Filter out non-article links (e.g., category pages)
                    
                    if is_not_quiz and is_article:
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
    # CSS Selectors (IDN Times Article Page)
    TITLE_SELECTOR = 'h1.css-wst4gq' 
    CATEGORY_SELECTOR = 'div.css-jtkjmk span.css-13xae7l' 
    DATE_CONTAINER_SELECTOR = 'span.css-1i8asf5 time'
    ARTICLE_SELECTOR = 'div.css-oziss0' 

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
            category = category_element[-2].get_text(strip=True)
        
        # 3. Date 
        date_container = soup.select_one(DATE_CONTAINER_SELECTOR)
        if date_container:
            date_text = date_container.get_text(separator=' ', strip=True)
            
            # Ex: "06 Jan 2026, 14:00 WIB"
            # Separate the data by comma
            parts = date_text.split(',')
            if len(parts) >= 2:
                # First part: date (result: "06 Jan 2026")
                publication_date = parts[0].strip()
        
        # 4. Full Text (Narasi)
        article_wrapper = soup.select_one(ARTICLE_SELECTOR)     # main container for the article

        if article_wrapper:
            paragraphs = article_wrapper.find_all('p')
            cleaned_paragraphs = []
            
            # Looping to get all the paragraphs
            for p in paragraphs:
                text_content = p.get_text(strip=True)
                # Filter out ads and non-content text
                if text_content and len(text_content) > 10 and 'ADVERTISEMENT' not in text_content.upper() and 'Table of Content' not in text_content.upper():
                    cleaned_paragraphs.append(text_content)

            # Join all paragraphs
            narasi_text = '\n\n'.join(cleaned_paragraphs)

            if title == 'N/A' or not title or narasi_text == 'N/A' or len(narasi_text) < 100:
                return None

        return {
            'title': title,
            'source': 'IDN Times',
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
    df.to_csv('test_news_idntimes.csv', index=False, encoding='utf-8-sig')
    print(f"\nSuccess! Scraped a total of {len(final_scraped_data)} full articles and saved to test_news_idntimes.csv")
else:
    print("\nNo full article content was scraped in the end.")