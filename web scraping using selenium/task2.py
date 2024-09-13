import json
import logging
import threading
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

logging.basicConfig(filename="scraping_errors.log", level=logging.ERROR, format="%(asctime)s - %(message)s")
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
base_url = 'https://www.4icu.org'

def get_state_links():
    driver.get(f'{base_url}/de/universities/')
    table = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'table')))
    a_tags = table.find_elements(By.TAG_NAME, 'a')
    state_links = []

    for a_tag in a_tags:
        state_name = a_tag.text.strip()
        href = a_tag.get_attribute('href')
        state_url = href if href.startswith('https') else base_url + href
        state_links.append({'state_name': state_name, 'state_url': state_url})
    logging.info(f"Found {len(state_links)} states.")
    return state_links

def get_university_links(state_url):
    try:
        driver.get(state_url)
        table = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'tbody')))
        university_links = [a.get_attribute('href') for a in table.find_elements(By.TAG_NAME, 'a') if
                            '/about/add.htm' not in a.get_attribute('href')]
        return university_links
    except Exception as e:
        logging.error(f"Error fetching universities for {state_url}: {e}")
        return []

def extract_university_details(uni_url, state_name):
    try:
        driver.get(uni_url)
        uni_name = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'h1[itemprop="name"]'))).text.strip()
        logo = driver.find_element(By.CSS_SELECTOR, 'img[itemprop="logo"]').get_attribute('src')
        city_name = driver.find_element(By.CSS_SELECTOR, 'span[itemprop="addressLocality"]').text.strip()
        founded_year = driver.find_element(By.CSS_SELECTOR, 'span[itemprop="foundingDate"]').text.strip()
        uni_type = driver.find_element(By.CSS_SELECTOR, 'p.lead strong').text.strip()
        uni_link = driver.find_element(By.CSS_SELECTOR, 'a[itemprop="url"]').get_attribute('href')
        social_links = driver.find_elements(By.CSS_SELECTOR, 'a[itemprop="sameAs"]')
        social_media_map = {
            'facebook': '',
            'twitter': '',
            'instagram': '',
            'linkedin': '',
            'youtube': ''
        }
        for link in social_links:
            url = link.get_attribute('href')
            if 'facebook.com' in url:
                social_media_map['facebook'] = url
            elif 'twitter.com' in url:
                social_media_map['twitter'] = url
            elif 'instagram.com' in url:
                social_media_map['instagram'] = url
            elif 'linkedin.com' in url:
                social_media_map['linkedin'] = url
            elif 'youtube.com' in url:
                social_media_map['youtube'] = url
        contact_info = driver.find_elements(By.TAG_NAME, 'td')
        phone_number = ''
        fax_number = ''
        for td in contact_info:
            text = td.text.strip()
            if re.match(r'^\+49', text):
                if not phone_number:
                    phone_number = text
                elif not fax_number:
                    fax_number = text
        return {
            "Name": uni_name,
            "Location": {
                "Country": "Germany",
                "State": state_name,
                "City": city_name
            },
            "Logo Url": logo,
            "Uni Type": uni_type,
            "Established Year": founded_year,
            "Contact": {
                "Facebook": social_media_map['facebook'],
                "Twitter": social_media_map['twitter'],
                "Instagram": social_media_map['instagram'],
                "Official Website": uni_link,
                "Linkedin": social_media_map['linkedin'],
                "Youtube": social_media_map['youtube'],
                "Phone Number": phone_number,
                "Fax Number": fax_number
            }
        }
    except Exception as e:
        logging.error(f"Error extracting details for {uni_url}: {e}")
        return None

def fetch_universities_for_state(state):
    state_name = state['state_name']
    state_url = state['state_url']
    university_links = get_university_links(state_url)
    universities_data = []
    for uni_url in university_links:
        details = extract_university_details(uni_url, state_name)
        if details:
            universities_data.append(details)
    return universities_data

def save_data(universities):
    with open('universities.json', 'w', encoding='utf-8') as f:
        json.dump(universities, f, ensure_ascii=False, indent=4)
    logging.info(f"Data saved to universities.json")

def main():
    states = get_state_links()
    all_universities = []
    threads = []
    universities_lock = threading.Lock()
    def thread_task(state):
        universities = fetch_universities_for_state(state)
        with universities_lock:
            all_universities.extend(universities)
    for state in states:
        thread = threading.Thread(target=thread_task, args=(state,))
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
    save_data(all_universities)
    driver.quit()

if __name__ == "__main__":
    main()
