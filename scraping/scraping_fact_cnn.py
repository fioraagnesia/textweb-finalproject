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
from requests.exceptions import RequestException

# --- CONFIGURATION ---
BASE_URL = "https://www.cnnindonesia.com"
# The list page URL. You can iterate through pages by changing the URL pattern.
LIST_PAGE_URL = f"{BASE_URL}/indeks/2?page="
# PAGES_NUM = 3 # Set this to the number of list pages you want to process
MAX_LIMIT = 5

def extract_content_between(start_element, stop_tag):
    """
    Ekstrak teks HANYA dari tag <p> yang berada di antara dua penanda,
    mengabaikan semua tag lain dan membersihkan teks iklan/skrip.
    """
    content_list = []
    current_element = start_element.find_next_sibling()

    while current_element:
        # 1. Hentikan jika tag berhenti ditemukan
        if stop_tag and current_element.name == stop_tag:
            break

        # 2. Filter Ketat: HANYA mengambil elemen <p>
        if current_element.name == 'p':
            # Ambil teks bersih dari paragraf
            text_content = current_element.get_text(strip=True)

            # Tambahkan ke daftar hanya jika bukan iklan/konten kosong
            if text_content and 'ADVERTISEMENT' not in text_content.upper() and 'GPT_INLINE' not in text_content.upper():
                 content_list.append(text_content)

        # Lanjutkan ke elemen berikutnya (mengabaikan <div>, <span>, etc. yang bukan <p>)
        current_element = current_element.find_next_sibling()

    # ⚠️ Menggabungkan dengan dua karakter newline (\n\n) untuk mewakili pemisah paragraf
    return '\n\n'.join(content_list)


# --- 1. FUNCTIONS FOR DATA EXTRACTION ---
def scrape_full_article(article_url):
    """Fetches a single article and extracts the full content using requests."""

    # --- CSS Selectors for an INDIVIDUAL Article Page ---
    # ⚠️ These are common guesses. Adjust these if they don't work.
    # ⚠️ Mengubah selector sesuai dengan struktur CNNIndonesia.com
    TITLE_SELECTOR = 'h1' # Selector umum untuk judul
    SOURCE_SELECTOR = 'span.text-cnn_red' # CNNI sering menggunakan span untuk sumber/penulis
    DATE_SELECTOR = 'div.text-cnn_grey' # Selector untuk kontainer tanggal teks lengkap
    CATEGORY_SELECTOR = 'a.text-sm.text-cnn_black_light2' # Selector untuk tautan kategori (Olahraga, Nasional, dll.)

    ARTICLE_SELECTOR = 'div[class*="detail-text"]' # <-- SELECTOR KONTEN UTAMA

    try:
        # 1. Fetch the full article page
        # Define a standard browser User-Agent globally
        HEADERS = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'
        }

        # In your functions:
        response = requests.get(article_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        html = response.text
        with open("dump.html", "w", encoding="utf-8") as f:
            f.write(html)

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
                if text_content and 'ADVERTISEMENT' not in text_content.upper():
                    cleaned_paragraphs.append(text_content)

            # Menggabungkan semua paragraf dengan pemisah baris ganda (\n\n)
            full_text = '\n\n'.join(cleaned_paragraphs)


        return {
            'title': title,
            'source': source,
            'date': publication_date,
            'category': category,
            'narasi': narasi_text,      # <-- New Column
            'url': article_url,
            'status': 'fact',
        }

    except requests.exceptions.RequestException as e:
        print(f"Error fetching article {article_url}: {e}")
        return None

# --- 2. LINK HARVESTING WITH INTERACTION (Selenium) ---
def get_all_links_via_url(base_url, max_limit):
    """
    Mengumpulkan tautan hingga mencapai batas MAX_LIMIT, dengan navigasi
    langsung melalui penambahan nomor halaman di URL.
    """
    all_links = set()
    page_counter = 1

    while len(all_links) < max_limit:
        page_url = f"{base_url}/indeks/2?page={page_counter}"
        print(f"\n--- Mengumpulkan tautan dari Halaman {page_counter} (Terkumpul: {len(all_links)}/{max_limit}) ---")

        try:
            HEADERS = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'
            }

            # In your functions:
            response = requests.get(page_url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            html = response.text
            with open("dump.html", "w", encoding="utf-8") as f:
                f.write(html)

            links_before_update = len(all_links)

            # ⚠️ Selector umum untuk link artikel di situs berita (Mungkin perlu disesuaikan)
            link_elements = soup.select('article a')

            for link_tag in link_elements:
                if len(all_links) >= max_limit:
                    break

                relative_url = link_tag.get('href')
                if relative_url and len(relative_url) > 10 and not relative_url.endswith('index.html'):
                  absolute_url = urljoin(base_url, relative_url)
                  all_links.add(absolute_url)

            links_added = len(all_links) - links_before_update

            # Kondisi Berhenti
            if links_added == 0 and page_counter > 1:
                print("Tidak ada tautan unik baru ditemukan. Berhenti scraping.")
                break

            if len(all_links) >= max_limit:
                 break

            # Navigasi ke Halaman Berikutnya
            page_counter += 1
            time.sleep(5.0)

        except RequestException as e:
            print(f"Gagal memuat halaman {page_url}. Error: {e}. Berhenti.")
            break

    return list(all_links)



# --- 3. MAIN EXECUTION ---

final_scraped_data = []

print(f"--- Stage 1: Collecting Links based on Data Limit ({MAX_LIMIT} Links) ---")

all_article_links_list = get_all_links_via_url(BASE_URL, MAX_LIMIT)

print(f"\nCollected a total of {len(all_article_links_list)} unique article links.")
print("--- Stage 2: Scraping Full Content for Each Article ---")

# Loop melalui link yang dikumpulkan
for i, link in enumerate(all_article_links_list):
    # Hanya scrape artikel yang masih dibutuhkan untuk mencapai batas
    if i >= MAX_LIMIT:
        break

    print(f"Scraping article {i+1}/{len(all_article_links_list)}: {link}")

    article_data = scrape_full_article(link)

    if article_data:

        # ⚠️ LOGIKA FILTERING JUDUL ⚠️
        title = article_data['title'].upper().strip() # Ambil judul, jadikan huruf besar, dan hapus spasi

        # Periksa apakah judul dimulai dengan FOTO: atau VIDEO:
        if title.startswith('FOTO:') or title.startswith('VIDEO:') or title.startswith('INFOGRAFIS:'):
            print(f"    ➡️ Skipping: Judul dimulai dengan FOTO: atau VIDEO: ({article_data['title']})")
            continue # Melompati iterasi ini (tidak akan ditambahkan ke data final)

        # Jika tidak diskip, tambahkan ke data final
        final_scraped_data.append(article_data)

    time.sleep(5.0)


# --- 3. SAVE DATA ---
if final_scraped_data:
    df = pd.DataFrame(final_scraped_data)
    df.to_csv('news_cnnIndonesia.csv', index=False, encoding='utf-8-sig')
    print(f"\nSuccess! Scraped a total of {len(final_scraped_data)} full articles and saved to news_cnnIndonesia.csv")
else:
    print("\nNo full article content was scraped in the end.")


