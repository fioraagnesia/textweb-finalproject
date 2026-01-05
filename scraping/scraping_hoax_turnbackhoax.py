import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# === CONFIGURATIONS ===
BASE_URL = "https://turnbackhoax.id"
LIST_PAGE_URL = f"{BASE_URL}/articles?category=all&page="
PAGES_NUM = 500 # Set this to the number of list pages you want to process

# --- LINK HARVESTING FUNCTION (Index Page) with interaction using Selenium ---
def get_all_links_with_interaction(base_url, max_pages):
    """
    Use Selenium to click "Semua" once, then using the "Next" button to navigate the next page.
    (Modified based on the website's usage)
    """
    all_links = set()
    # Chrome Options object configuration
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # Manage Chrome Browser using Selenium
    with webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options) as driver:
        page_counter = 1
        
        # Navigate to the first page
        driver.get(LIST_PAGE_URL) 
        print(f"Visit the start page: {LIST_PAGE_URL}")
        
        # Click the "Semua" button ONCE (to activate the filter) 
        try:
            semua_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-category='all']"))
            )
            driver.execute_script("arguments[0].click();", semua_button)
            print(">>> Successfully clicked the 'Semua' button on Page 1. Filter is activated.")
            time.sleep(5.0) 

        except Exception:
            print(f"The 'Semua' button failed to click. Continue without clicking.")
        
        # -- MAIN LOOP: Click "Next" button --
        while page_counter <= max_pages:
            print(f"\n--- Collecting links from Page {page_counter} ---")
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Collect the links
            link_elements = soup.select('a[href*="/articles/"]')
            for link_tag in link_elements:
                relative_url = link_tag.get('href')
                
                if relative_url and "/articles/" in relative_url:
                    article_path = relative_url.split('/articles/')[-1]
                    article_id = article_path.split('-')[0].split('/')[0] 
                    absolute_url = f"{base_url}/articles/{article_id}"
                    all_links.add(absolute_url)
            
            # Click the "Next" button
            try:
                # Find the "Next" button icon 
                next_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, 'sprites-next'))
                )
                
                driver.execute_script("arguments[0].click();", next_button)
                print(f"Successfully clicked the 'Next' button (sprites-next).")
                
                # Move to the next page
                page_counter += 1
                time.sleep(5.0)

            except NoSuchElementException:
                print(f"The 'Next' (sprites-next) button was not found. Terminating.")
                break 
            
            except TimeoutException:
                 print(f"Timeout waiting for 'Next' button on Page {page_counter}. Terminating.")
                 break
            
            except Exception as e:
                print(f"Unexpected error when clicking 'Next': {e}. Terminating.")
                break

    return list(all_links)


# --- EXTRACT CONTENT FUNCTION ---
def extract_content_between(start_element, stop_tag):
    content_list = []
    current_element = start_element.find_next_sibling()
    
    while current_element:
        if stop_tag and current_element.name == stop_tag:
            break
        
        # Filter unrelevant tags 
        if current_element.name in ['script', 'style', 'header', 'footer', 'noscript']:
            current_element = current_element.find_next_sibling()
            continue

        # Append text 
        if current_element.name == 'p' or ('class' in current_element.attrs and 'quoted' in current_element['class']):
            content_list.append(current_element.get_text(strip=True))
        elif current_element.string and current_element.string.strip():
             content_list.append(current_element.string.strip())

        # Move to the next sibling element (same level)
        current_element = current_element.find_next_sibling()
    
    # Join the texts
    return ' '.join(content_list)


# --- DATA EXTRACTION FUNCTION (Scrape Article Detail) ---
def scrape_full_article(article_url):
    """Fetches a single article and extracts the full content using requests."""
    # CSS Selectors for an INDIVIDUAL Article Page 
    TITLE_SELECTOR = 'h1'
    CATEGORY_SELECTOR = 'p span a' 
    DATE_SELECTOR = 'time' 
    SOURCE_SELECTOR = 'p time + span' 
    ARTICLE_SELECTOR = 'section.article--main' 
    ARTICLE_HEADING_SELECTOR = 'strong'
    
    try:
        # Fetch the full article page
        response = requests.get(article_url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Metadata defaults
        title, category, source, publication_date, narasi_text, penjelasan_text = 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A'

        # Extract Metadata 
        # 1. Title
        title_element = soup.select_one(TITLE_SELECTOR)
        if title_element:
             title = title_element.get_text(strip=True)
        
        # 2. Category
        category_element = soup.select_one(CATEGORY_SELECTOR)
        if category_element:
             category = category_element.get_text(strip=True)

        # 3. Source
        source_element = soup.select_one(SOURCE_SELECTOR)
        if source_element:
             source = source_element.get_text(strip=True)
        
        # 4. Date
        date_element = soup.select_one(DATE_SELECTOR)
        if date_element:
            publication_date = date_element.get('datetime') or date_element.get_text(strip=True)
        
        # 5. Full Text (Narasi, Penjelasan, Kesimpulan)
        article_wrapper = soup.select_one(ARTICLE_SELECTOR)
        narasi_text, penjelasan_text, kesimpulan_text = 'N/A', 'N/A', 'N/A'
        
        if article_wrapper:
            # Find the headings
            narasi_heading = article_wrapper.find(ARTICLE_HEADING_SELECTOR, string=re.compile(r'narasi', re.I)) 
            penjelasan_heading = article_wrapper.find(ARTICLE_HEADING_SELECTOR, string=re.compile(r'penjelasan', re.I))
            kesimpulan_heading = article_wrapper.find(ARTICLE_HEADING_SELECTOR, string=re.compile(r'kesimpulan', re.I))
            
            # Extract Content between the headings
            if narasi_heading:
                narasi_text = extract_content_between(narasi_heading, ARTICLE_HEADING_SELECTOR)
            if penjelasan_heading:
                penjelasan_text = extract_content_between(penjelasan_heading, ARTICLE_HEADING_SELECTOR)
            if kesimpulan_heading:
                kesimpulan_text = extract_content_between(kesimpulan_heading, None)     # None to capture all content until the end of the section

        return {
            'title': title,
            'source': source,
            'date': publication_date,
            'category': category,
            'narasi': narasi_text,      
            'penjelasan': penjelasan_text, 
            'kesimpulan': kesimpulan_text, 
            'url': article_url,
            'status': 'hoax'
        }

    except requests.exceptions.RequestException as e:
        print(f"Error fetching article {article_url}: {e}")
        return None


    
# === MAIN EXECUTION ===
all_article_links = set()
final_scraped_data = []

print(f"--- Stage 1: Collecting Links from {PAGES_NUM} List Pages ---")
all_article_links_list = get_all_links_with_interaction(BASE_URL, PAGES_NUM)
print(f"\nCollected a total of {len(all_article_links_list)} unique article links.")

print("--- Stage 2: Scraping Full Content for Each Article ---")
# Loop through every collected link to scrape the full article content
for i, link in enumerate(all_article_links_list):
    print(f"Scraping article {i+1}/{len(all_article_links_list)}: {link}")
    
    article_data = scrape_full_article(link)
    
    if article_data:
        final_scraped_data.append(article_data)
        
    time.sleep(5.0)


# --- Save Data ---
if final_scraped_data:
    df = pd.DataFrame(final_scraped_data)
    df.to_csv('news_turnbackhoax.csv', index=False, encoding='utf-8-sig')
    print(f"\nSuccess! Scraped a total of {len(final_scraped_data)} full articles and saved to news_turnbackhoax.csv")
else:
    print("\nNo full article content was scraped in the end.")