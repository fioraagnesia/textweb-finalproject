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
BASE_URL = "https://turnbackhoax.id"
# The list page URL. You can iterate through pages by changing the URL pattern.
LIST_PAGE_URL = f"{BASE_URL}/articles?category=all&page="
PAGES_NUM = 500 # Set this to the number of list pages you want to process

def extract_content_between(start_element, stop_tag):
    content_list = []
    current_element = start_element.find_next_sibling()
    
    while current_element:
        if stop_tag and current_element.name == stop_tag:
            break
        
        # ⚠️ FIX: Abaikan tag yang tidak relevan (seperti script dan komentar)
        if current_element.name in ['script', 'style', 'header', 'footer', 'noscript']:
            current_element = current_element.find_next_sibling()
            continue

        # Ambil teks hanya dari paragraf atau div konten utama
        if current_element.name == 'p' or ('class' in current_element.attrs and 'quoted' in current_element['class']):
            content_list.append(current_element.get_text(strip=True))
        
        # Jika bukan p/div, dan bukan tag yang diabaikan, kita ambil teksnya saja 
        # (ini mungkin menangkap teks mentah tanpa tag)
        elif current_element.string and current_element.string.strip():
             content_list.append(current_element.string.strip())


        current_element = current_element.find_next_sibling()
    
    # Gunakan spasi tunggal untuk menggabungkan teks
    return ' '.join(content_list)


# --- 1. FUNCTIONS FOR DATA EXTRACTION ---
def scrape_full_article(article_url):
    """Fetches a single article and extracts the full content using requests."""
    
    # --- CSS Selectors for an INDIVIDUAL Article Page ---
    # ⚠️ These are common guesses. Adjust these if they don't work.
    TITLE_SELECTOR = 'h1'

    CATEGORY_SELECTOR = 'p span a' # Must be verified
    DATE_SELECTOR = 'time'    # Must be verified
    SOURCE_SELECTOR = 'p time + span'   # Must be verified

    # The main text is often in a specific container class (like 'entry-content' or 'post-content')
    ARTICLE_SELECTOR = 'section.article--main' 
    ARTICLE_HEADING_SELECTOR = 'strong'
    

    try:
        # 1. Fetch the full article page
        response = requests.get(article_url, timeout=15)
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
        article_wrapper = soup.select_one(ARTICLE_SELECTOR)
        
        narasi_text, penjelasan_text, kesimpulan_text = 'N/A', 'N/A', 'N/A'
        
        if article_wrapper:
            # FIX: Use regex to find headings (r'narasi', re.I) is correct for case insensitivity
            narasi_heading = article_wrapper.find(ARTICLE_HEADING_SELECTOR, string=re.compile(r'narasi', re.I)) 
            penjelasan_heading = article_wrapper.find(ARTICLE_HEADING_SELECTOR, string=re.compile(r'penjelasan', re.I))
            kesimpulan_heading = article_wrapper.find(ARTICLE_HEADING_SELECTOR, string=re.compile(r'kesimpulan', re.I))
            
            # --- Extract Content ---
            if narasi_heading:
                narasi_text = extract_content_between(narasi_heading, ARTICLE_HEADING_SELECTOR)
            if penjelasan_heading:
                penjelasan_text = extract_content_between(penjelasan_heading, ARTICLE_HEADING_SELECTOR)
            
            # Use None to capture all content until the end of the section (FIXED STOP TAG)
            if kesimpulan_heading:
                kesimpulan_text = extract_content_between(kesimpulan_heading, None)

        return {
            'title': title,
            'source': source,
            'date': publication_date,
            'category': category,
            'narasi': narasi_text,      # <-- New Column
            'penjelasan': penjelasan_text, # <-- New Column
            'kesimpulan': kesimpulan_text, # <-- New Column
            'url': article_url,
            'status': 'hoax',
        }

    except requests.exceptions.RequestException as e:
        print(f"Error fetching article {article_url}: {e}")
        return None

# --- 2. LINK HARVESTING WITH INTERACTION (Selenium) ---
def get_all_links_with_interaction(base_url, max_pages):
    """
    Menggunakan Selenium untuk mengklik 'Semua' sekali, lalu menggunakan tombol 'Next' 
    untuk menavigasi halaman berikutnya.
    """
    all_links = set()
    
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    with webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options) as driver:
        
        page_counter = 1
        
        # 1. Navigasi ke halaman awal
        driver.get(LIST_PAGE_URL) 
        print(f"Mengunjungi halaman awal: {LIST_PAGE_URL}")
        
        # --- KLIK TOMBOL "SEMUA" SEKALI (Untuk mengaktifkan filter) ---
        try:
            semua_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-category='all']"))
            )
            driver.execute_script("arguments[0].click();", semua_button)
            print(">>> Berhasil mengklik tombol 'Semua' pada Page 1. Filter diaktifkan.")
            time.sleep(5.0) 

        except Exception:
            print(f"Tombol 'Semua' gagal diklik. Melanjutkan tanpa klik.")
        
        # --- LOOP UTAMA: KLIK TOMBOL "NEXT" ---
        while page_counter <= max_pages:
            print(f"\n--- Mengumpulkan tautan dari Halaman {page_counter} ---")
            
            # Scrape HTML halaman saat ini
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Kumpulkan tautan (Logic Pembersihan Tautan)
            link_elements = soup.select('a[href*="/articles/"]')

            for link_tag in link_elements:
                relative_url = link_tag.get('href')
                
                if relative_url and "/articles/" in relative_url:
                    article_path = relative_url.split('/articles/')[-1]
                    article_id = article_path.split('-')[0].split('/')[0] 
                    absolute_url = f"{base_url}/articles/{article_id}"
                    all_links.add(absolute_url)
            
            # 3. Coba Klik Tombol "Next"
            try:
                # ⚠️ Ganti selector ini berdasarkan Image 00d5d2.png: Mencari tombol panah Next
                # Mencari tombol dengan class 'sprites-next'
                next_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, 'sprites-next'))
                )
                
                driver.execute_script("arguments[0].click();", next_button)
                print(f"Berhasil mengklik tombol 'Next' (sprites-next).")
                
                page_counter += 1
                time.sleep(5.0) # Tunggu halaman baru memuat

            except NoSuchElementException:
                print(f"Tombol 'Next' (sprites-next) tidak ditemukan. Selesai.")
                break 
            
            except TimeoutException:
                 print(f"Timeout menunggu tombol 'Next' (sprites-next) di Page {page_counter}. Selesai.")
                 break
            
            except Exception as e:
                print(f"Error tak terduga saat klik 'Next': {e}. Selesai.")
                break

    return list(all_links)
    


# --- 3. MAIN EXECUTION ---

all_article_links = set()
final_scraped_data = []

print(f"--- Stage 1: Collecting Links from {PAGES_NUM} List Pages ---")


# Replace the loop with the new Selenium function
all_article_links_list = get_all_links_with_interaction(BASE_URL, PAGES_NUM)

print(f"\nCollected a total of {len(all_article_links_list)} unique article links.")
print("--- Stage 2: Scraping Full Content for Each Article ---")

# Loop through every collected link to scrape the full article content
for i, link in enumerate(all_article_links_list):
    print(f"Scraping article {i+1}/{len(all_article_links_list)}: {link}")
    
    article_data = scrape_full_article(link)
    
    if article_data:
        final_scraped_data.append(article_data)
        
    # Apply polite delay between article requests
    time.sleep(5.0)

# --- 3. SAVE DATA ---
if final_scraped_data:
    df = pd.DataFrame(final_scraped_data)
    df.to_csv('news_turnbackhoax.csv', index=False, encoding='utf-8-sig')
    print(f"\nSuccess! Scraped a total of {len(final_scraped_data)} full articles and saved to news_turnbackhoax.csv")
else:
    print("\nNo full article content was scraped in the end.")