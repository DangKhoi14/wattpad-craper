import cloudscraper
from bs4 import BeautifulSoup
import re
import os
import time
import random
from urllib.parse import quote, urlparse, urljoin

OUTPUT_DIR = "wattpad_chapters"
MAX_RETRIES = 3

scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

scraper.headers.update({
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive',
    'Referer': 'https://www.google.com/',
    'Sec-Ch-Ua': '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'cross-site',
    'Upgrade-Insecure-Requests': '1'
})

def sanitize_filename(text: str, max_length: int = 100) -> str:
    """Lấy dòng đầu tiên làm tên file và làm sạch ký tự cấm."""
    lines = text.strip().split('\n')
    name = lines[0] if lines else "untitled"
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:max_length] or "untitled"

def extract_title_from_header(soup: BeautifulSoup) -> str:
    """Trích xuất tiêu đề chương từ thẻ h1 trong header."""
    header = soup.find("header", class_=re.compile(r"panel-reading", re.I))
    if header:
        h1 = header.find("h1")
        if h1:
            return sanitize_filename(h1.get_text(strip=True))
    return None

def extract_text_from_pre(soup: BeautifulSoup) -> str:
    """Trích xuất nội dung từ các thẻ <pre>."""
    pre_blocks = soup.find_all("pre")
    return "\n\n".join([pre.get_text(separator="\n").strip() for pre in pre_blocks])

def get_next_url(soup: BeautifulSoup) -> str | None:
    """Tìm link đến chương tiếp theo (Next Part)."""
    next_link = soup.find("a", class_=re.compile(r"next-part-link|continue-link", re.I))
    if next_link and next_link.get("href"):
        return urljoin("https://www.wattpad.com", next_link["href"])
    return None

def clean_url(url):
    """Xử lý URL chứa ký tự tiếng Việt để tránh lỗi connection."""
    parts = urlparse(url)
    encoded_path = quote(parts.path)
    return f"{parts.scheme}://{parts.netloc}{encoded_path}"

def fetch_with_retry(url, max_retries=5):
    """Tải trang với logic thử lại và nghỉ ngẫu nhiên."""
    safe_url = clean_url(url)
    for i in range(max_retries):
        try:
            wait = random.uniform(3, 7)
            time.sleep(wait)
            
            response = scraper.get(safe_url, timeout=20)
            
            if response.status_code == 200:
                return response
            elif response.status_code == 403:
                print(f"    [!] Bị Cloudflare chặn (403). Đang đợi lâu hơn...")
                time.sleep(20)
        except Exception as e:
            print(f"    (!) Lần thử {i+1} thất bại: {e}")
            time.sleep(random.uniform(5, 10))
            
    return None

def scrape_chapter_content(url: str):
    all_text = []
    current_page_url = url
    last_valid_soup = None
    first_soup = None

    while current_page_url:
        print(f"    Đang tải trang: {current_page_url}")
        resp = fetch_with_retry(current_page_url)

        if not resp:
            print("    [!] Bỏ qua trang này do lỗi kết nối kéo dài.")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        last_valid_soup = soup

        if first_soup is None:
            first_soup = soup

        text = extract_text_from_pre(soup)
        if text:
            all_text.append(text)

        next_page_tag = soup.find("link", rel="next")
        if next_page_tag and "page/" in next_page_tag.get("href", ""):
            current_page_url = next_page_tag["href"]
            time.sleep(2)
        else:
            current_page_url = None

    return "\n\n".join(all_text), last_valid_soup, first_soup

def run_scraper(start_url: str):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    current_url = start_url
    count = 0

    while current_url:
        count += 1
        print(f"\nXử lý: {current_url}")
        
        content, soup, first_soup = scrape_chapter_content(current_url)
        
        if not content or not soup:
            print("    [!] Không lấy được nội dung chương. Dừng scraper.")
            break

        title = extract_title_from_header(first_soup) or sanitize_filename(content)
        file_path = os.path.join(OUTPUT_DIR, f"{title}.txt")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"    [ OK ] Đã lưu: {title}.txt")

        next_chapter_url = get_next_url(soup)
        if next_chapter_url and next_chapter_url != current_url:
            current_url = next_chapter_url
            print("    --- Nghỉ 5s trước chương mới ---")
            time.sleep(5)
        else:
            print("\n--- Hoàn tất hoặc không tìm thấy chương tiếp theo ---")
            break


def load_codes(file_path="chapters.txt"):
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

if __name__ == "__main__":

    codes = load_codes()

    times = None
    for code in codes:
        target_url = f"https://www.wattpad.com/{code}"
        run_scraper(target_url)

        if times is not None:
            times -= 1
            if times == -1:
                break