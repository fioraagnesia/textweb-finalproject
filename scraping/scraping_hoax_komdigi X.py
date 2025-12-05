import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
import time
import re
# --- REQUIRED IMPORTS FOR INTERACTION ---
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# --- CONFIGURATION ---
BASE_URL = "https://www.komdigi.go.id"
# The list page URL. You can iterate through pages by changing the URL pattern.
LIST_PAGE_URL = f"{BASE_URL}/berita/berita-hoaks"
MAX_LIMIT = 15 # Set this to the number of list pages you want to process

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://www.komdigi.go.id/berita/berita-hoaks' # PENTING: Menyamar seolah-olah berasal dari halaman list
}

def extract_content_only(article_wrapper):
    """
    Mengambil teks hanya dari tag <p> dan membersihkan iklan yang tersembunyi.
    """
    full_text_parts = []
    
    if article_wrapper:
        # ⚠️ Hapus semua script/style/img sebelum mengambil teks
        for tag in article_wrapper.find_all(['script', 'style', 'noscript', 'img']):
            tag.decompose()
            
        paragraphs = article_wrapper.find_all('p')
        
        for p in paragraphs:
            text_content = p.get_text(strip=True)
            
            # Filter ketat untuk menghilangkan teks iklan/non-konten
            if text_content and 'ADVERTISEMENT' not in text_content.upper() and 'GPT_INLINE' not in text_content.upper():
                full_text_parts.append(text_content)
        
        return '\n\n'.join(full_text_parts)
    return 'N/A'


# --- 1. FUNCTIONS FOR DATA EXTRACTION ---
def scrape_full_article(article_url):
    """Fetches a single article and extracts the full content using requests."""
    
    # --- CSS Selectors for an INDIVIDUAL Article Page ---
    # ⚠️ These are common guesses. Adjust these if they don't work.
    TITLE_SELECTOR = 'h3'

    CATEGORY_SELECTOR = 'div.berita-detail-meta a' # Must be verified
    DATE_SELECTOR = 'span.text-body-l'    # Must be verified
    SOURCE_SELECTOR = 'a span'   # Must be verified

    # The main text is often in a specific container class (like 'entry-content' or 'post-content')
    ARTICLE_SELECTOR = 'div.custom-body' 
    # ARTICLE_HEADING_SELECTOR = 'strong'
    

    try:
        # 1. Fetch the full article page
        response = requests.get(article_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # 1. Extract Metadata 
        # Title
        title_element = soup.select_one(TITLE_SELECTOR)
        title = title_element.get_text(strip=True) if title_element else 'N/A'
        # Category
        category_element = soup.select_one(CATEGORY_SELECTOR)
        category = category_element.get_text(strip=True) if category_element else 'N/A'
        # Date
        date_element = soup.select_one(DATE_SELECTOR)
            # Uses the machine-readable 'datetime' attribute if present, otherwise falls back to visible text.
        publication_date = date_element.get('datetime') if date_element and date_element.get('datetime') else (date_element.get_text(strip=True) if date_element else 'N/A')
        # Source
        source_element = soup.select_one(SOURCE_SELECTOR)
        source = source_element.get_text(strip=True) if source_element else 'N/A'
        

        # 2. Sectional Extraction Logic (FIXED)
        # FULL TEXT
        narasi_text = 'N/A'
        article_wrapper = soup.select_one(ARTICLE_SELECTOR)

        if article_wrapper:
            # Cari semua tag <p> di dalam kontainer utama
            paragraphs = article_wrapper.find_all('p')

            cleaned_paragraphs = []
            for p in paragraphs:
                # Membersihkan teks dari iklan inline/placeholders (ADVERTISEMENT)
                text_content = p.get_text(strip=True)

                # Filter ketat untuk menghilangkan teks non-konten
                if text_content not in text_content.upper():
                    cleaned_paragraphs.append(text_content)

            # Menggabungkan semua paragraf dengan pemisah baris ganda (\n\n)
            narasi_text = '\n\n'.join(cleaned_paragraphs)


        return {
            'title': title,
            'source': source,
            'date': publication_date,
            'category': category,
            'narasi': narasi_text,      # <-- New Column
            'url': article_url,
            'status': 'hoax',
        }

    except requests.exceptions.RequestException as e:
        print(f"Error fetching article {article_url}: {e}")
        return None

# --- 2. LINK HARVESTING WITH INTERACTION (Selenium) ---
def get_all_links_with_interaction(base_url, max_limit):
    all_links = set()
    page_counter = 1
    
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    with webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options) as driver:
        
        driver.get(LIST_PAGE_URL) 
        
        while len(all_links) < max_limit: 
            print(f"\n--- Mengumpulkan tautan dari Halaman {page_counter} (Terkumpul: {len(all_links)}/{max_limit}) ---")
            
            # A. Scrape Konten Halaman Saat Ini
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            links_before_update = len(all_links)
            
            # ⚠️ SELECTOR LINK BARU UNTUK KOMDIGI (Mengambil semua tautan dari daftar artikel) ⚠️
            link_elements = soup.select('div.list-artikel a[href*="/berita/"]') 

            for link_tag in link_elements:
                if len(all_links) >= max_limit: 
                    break 
                    
                relative_url = link_tag.get('href')
                
                # Filter agar hanya link detail yang panjang
                if relative_url and '/berita/' in relative_url and len(relative_url) > 30 and not relative_url.endswith('/'): 
                    absolute_url = urljoin(base_url, relative_url)
                    all_links.add(absolute_url)
            
            links_added = len(all_links) - links_before_update
            
            # B. Kondisi Berhenti
            if len(all_links) >= max_limit:
                break 
            
            if links_added == 0 and page_counter > 1:
                print("Tidak ada tautan unik baru ditemukan. Berhenti scraping.")
                break 

            # C. KLIK TOMBOL PAGINATION (Next/Selanjutnya)
            try:
                # ⚠️ PERBAIKAN SELECTOR BUTTON NEXT (Targetkan button chevron-right) ⚠️
                # Kita mencari button yang berisi icon panah ke kanan
                next_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[.//*[@class='chevron-right_icon']]"))
                )
                
                next_button.click() # Klik langsung tanpa execute_script
                print(f"Berhasil mengklik tombol 'Next'.")
                
                page_counter += 1
                time.sleep(5.0) 

            except (NoSuchElementException, TimeoutException):
                print(f"Tombol navigasi 'Next' tidak ditemukan. Selesai.")
                break
            
            except Exception as e:
                print(f"Error saat mengklik 'Next': {e}. Selesai.")
                break

    return list(all_links)


# --- 3. MAIN EXECUTION ---

all_article_links = set()
final_scraped_data = []

print(f"--- Stage 1: Collecting Links from {MAX_LIMIT} List Pages ---")


# Replace the loop with the new Selenium function
all_article_links_list = get_all_links_with_interaction(BASE_URL, MAX_LIMIT)

print(f"\nCollected a total of {len(all_article_links_list)} unique article links.")
print("--- Stage 2: Scraping Full Content for Each Article ---")

# Loop through every collected link to scrape the full article content
for i, link in enumerate(all_article_links_list):
    if i >= MAX_LIMIT: 
        break 
        
    print(f"Scraping article {i+1}/{len(all_article_links_list)}: {link}")
    
    article_data = scrape_full_article(link)

    if article_data:
        # LOGIKA FILTERING JUDUL
        title = article_data['title'].upper().strip() 
        
        if title.startswith('FOTO:') or title.startswith('VIDEO:') or title.startswith('INFOGRAFIS:'):
            print(f"    ➡️ Skipping: Judul dimulai dengan FOTO:, VIDEO:, atau INFOGRAFIS: ({article_data['title']})")
            continue 
        
        final_scraped_data.append(article_data)
        
    # Apply polite delay between article requests
    time.sleep(5.0)

# --- 3. SAVE DATA ---
if final_scraped_data:
    df = pd.DataFrame(final_scraped_data)
    df.to_csv('news_komdigihoax.csv', index=False, encoding='utf-8-sig')
    print(f"\nSuccess! Scraped a total of {len(final_scraped_data)} full articles and saved to news_komdigihoax.csv")
else:
    print("\nNo full article content was scraped in the end.")