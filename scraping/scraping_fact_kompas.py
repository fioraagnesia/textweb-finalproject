import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
import time
import re
from requests.exceptions import RequestException
# Note: Selenium imports have been removed as they are unnecessary for Kompas.com

# --- CONFIGURATION ---
BASE_URL = "https://indeks.kompas.com"
LIST_PAGE_URL = f"{BASE_URL}/?page="
MAX_LIMIT = 1000 # Set the total number of articles you want to process

# Define standard browser User-Agent globally
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': BASE_URL 
}

# --- 1. FUNCTIONS FOR DATA EXTRACTION (Article Detail) ---
def scrape_full_article(article_url):
    """Fetches a single article and extracts the full content using requests."""

    # --- CORRECTED CSS Selectors for Kompas Article Page ---
    TITLE_SELECTOR = 'h1.read__title' 
    CATEGORY_SELECTOR = 'li.breadcrumb__item a, div.breadcrum-new li a' 
    DATE_SOURCE_CONTAINER_SELECTOR = 'div.read__time' 
    ARTICLE_SELECTOR = 'div.read__content' # Selector for the main article body

    try:
        response = requests.get(article_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Initialize return data with defaults
        title, category, source, publication_date, narasi_text = 'N/A', 'N/A', 'N/A', 'N/A', 'N/A'

        # --- Extract Metadata ---
        # Title
        title_element = soup.select_one(TITLE_SELECTOR)
        if title_element:
             title = title_element.get_text(strip=True)
        
        # Category (last item in breadcrumb)
        # --- Extract Category (Ambil elemen PALING BELAKANG / LAST ITEM) ---
        category_elements = soup.select(CATEGORY_SELECTOR)
        if category_elements:
            # Ambil elemen terakhir (indeks -1). Ini seringkali adalah Judul Artikel itu sendiri.
            category = category_elements[-1].get_text(strip=True)
        else:
            category = 'N/A error'
        
        # Date and Source Extraction
        date_source_container = soup.select_one(DATE_SOURCE_CONTAINER_SELECTOR)

        if date_source_container:
            # Mengambil teks secara keseluruhan dari kontainer tanggal/sumber.
            # Menggunakan separator ' ' untuk memastikan teks tidak menempel.
            full_text_metadata = date_source_container.get_text(separator=' ', strip=True)
            
            # Contoh: "Kompas.com, 4 Desember 2025, 18:00 WIB"
            
            # 1. Pisahkan berdasarkan koma (',')
            parts = full_text_metadata.split(',')
            
            if len(parts) >= 3:
                # Bagian pertama adalah Source
                source = parts[0].strip() # Hasil: "Kompas.com"
                
                # Gabungkan bagian Tanggal (parts[1]) dan Waktu (parts[2]) agar mudah diproses
                date_and_time = ','.join(parts[1:]).strip() # Hasil: "4 Desember 2025, 18:00 WIB"
                
                # Untuk mendapatkan hanya Tanggal:
                # Hapus bagian WIB dan Waktu yang tidak diperlukan
                publication_date = re.sub(r',\s*\d{2}:\d{2}\s*WIB', '', date_and_time, flags=re.I).strip()
                
            elif len(parts) == 2:
                # Kasus darurat jika formatnya lebih pendek (misal: "Kompas.com, 4 Desember 2025")
                source = parts[0].strip()
                publication_date = parts[1].strip()
            else:
                # Kasus gagal parsing
                source = 'N/A'
                publication_date = 'N/A'
        

        # --- FULL TEXT (Narasi) Extraction ---
        article_wrapper = soup.select_one(ARTICLE_SELECTOR)

        if article_wrapper:
            paragraphs = article_wrapper.find_all('p')
            cleaned_paragraphs = []
            
            for p in paragraphs:
                text_content = p.get_text(strip=True)
                
                # Filter out ads and non-content text
                if text_content and len(text_content) > 10 and 'ADVERTISEMENT' not in text_content.upper():
                    cleaned_paragraphs.append(text_content)

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

# --- 2. LINK HARVESTING (Index Page) ---
def get_all_links_via_url(max_limit):
    """
    Collects article links from the Kompas.com index pages using pagination.
    """
    all_links = set()
    page_counter = 1
    LINK_SELECTOR = 'a[href*="/read/"]'

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

            page_counter += 1

        except RequestException as e:
            print(f"Failed to load page {page_url}. Error: {e}. Stopping.")
            break

    return list(all_links)

# --- 3. MAIN EXECUTION ---

final_scraped_data = []

print(f"--- Stage 1: Collecting Links based on Data Limit ({MAX_LIMIT} Links) ---")
all_article_links_list = get_all_links_via_url(MAX_LIMIT)
print(f"\nCollected a total of {len(all_article_links_list)} unique article links.")
print("--- Stage 2: Scraping Full Content for Each Article ---")

# Loop through collected links
for i, link in enumerate(all_article_links_list):
    if i >= MAX_LIMIT:
        break 

    print(f"Scraping article {i+1}/{min(MAX_LIMIT, len(all_article_links_list))}: {link}")

    article_data = scrape_full_article(link)

    if article_data:
        # Title filtering logic (to skip FOTO/VIDEO articles)
        title = article_data['title'].upper().strip()

        if title.startswith('FOTO:') or title.startswith('VIDEO:') or title.startswith('INFOGRAFIS:'):
            print(f"      ➡️ Skipping: Title starts with FOTO/VIDEO/INFOGRAFIS: ({article_data['title']})")
            continue

        final_scraped_data.append(article_data)

    time.sleep(5.0)


# --- 4. SAVE DATA ---
if final_scraped_data:
    df = pd.DataFrame(final_scraped_data)
    # Ensure columns are in the requested order
    df.to_csv('news_kompascom.csv', index=False, encoding='utf-8-sig')
    print(f"\nSuccess! Scraped a total of {len(final_scraped_data)} full articles and saved to news_kompascom.csv")
else:
    print("\nNo full article content was scraped in the end.")