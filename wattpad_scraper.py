"""
pip install selenium beautifulsoup4
Yêu cầu: Chrome browser đã cài sẵn (selenium 4.6+ tự tải chromedriver)
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import re
import os
import time
import random
from urllib.parse import urljoin

OUTPUT_DIR = "wattpad_chapters"


def normalize_dots(text: str) -> str:
    # Replace sequences of 6+ dots with exactly 5 dots
    return re.sub(r'\.{6,}', '.....', text)


def get_driver():
    options = Options()
    # Bỏ comment dòng dưới để chạy ẩn không hiện cửa sổ Chrome
    # options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--lang=vi-VN")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def sanitize_filename(text: str, max_length: int = 100) -> str:
    lines = text.strip().split('\n')
    name = lines[0] if lines else "untitled"
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:max_length] or "untitled"


def extract_title_from_header(soup: BeautifulSoup) -> str | None:
    header = soup.find("header", class_=re.compile(r"panel-reading", re.I))
    if header:
        h1 = header.find("h1")
        if h1:
            return sanitize_filename(h1.get_text(strip=True))
    return None


def extract_paragraphs_from_page(soup: BeautifulSoup) -> list[tuple[str, str]]:
    """
    Extract text từ các thẻ <p data-p-id="..."> trong trang.
    Chỉ lấy các thẻ <p> có data-p-id — đây là nội dung truyện chính thức.
    Bỏ qua các comment widget, quảng cáo, và nội dung phụ.

    Returns:
        list of (paragraph_id, paragraph_text) tuples
    """
    results = []
    # Tìm tất cả thẻ <p> có data-p-id (nội dung truyện chính)
    p_tags = soup.find_all("p", attrs={"data-p-id": True})

    for p_tag in p_tags:
        p_id = p_tag.get("data-p-id", "")

        # Loại bỏ các component-wrapper bên trong (comment buttons, ads, etc.)
        for wrapper in p_tag.find_all("div", class_="component-wrapper"):
            wrapper.decompose()

        # Thay <br> thành newline
        for br in p_tag.find_all("br"):
            br.replace_with("\n")

        text = p_tag.get_text(separator="\n").strip()

        # Bỏ các dòng chỉ có ký tự '+' hoặc số trang
        lines = [l for l in text.split("\n") if not re.fullmatch(r'[\+\d\s]*', l)]
        text = "\n".join(lines).strip()

        if text and p_id:
            results.append((p_id, text))

    return results


def get_next_chapter_url(soup: BeautifulSoup) -> str | None:
    nav = soup.find(id="story-part-navigation")
    if nav:
        a = nav.find("a")
        if a and a.get("href"):
            return urljoin("https://www.wattpad.com", a["href"])
    for a in soup.find_all("a", href=True):
        if "continue to next part" in a.get_text(strip=True).lower():
            return urljoin("https://www.wattpad.com", a["href"])
    return None


def fetch_page(driver, url: str) -> BeautifulSoup | None:
    try:
        driver.get(url)
        WebDriverWait(driver, 25).until(
            EC.presence_of_element_located((By.CLASS_NAME, "panel-reading"))
        )
        time.sleep(random.uniform(1.5, 3))
        return BeautifulSoup(driver.page_source, "html.parser")
    except Exception as e:
        print(f"    [!] Lỗi tải trang: {e}")
        return None


def scrape_chapter_content(driver, url: str):
    """
    Cào toàn bộ nội dung 1 chapter, gồm các trang con (page/2, page/3...).
    Sử dụng data-p-id để:
    1. Chỉ lấy nội dung truyện (bỏ qua comment rác)
    2. Tự động loại bỏ đoạn trùng lặp giữa các trang (dedup bằng ID)
    """
    all_paragraphs = []  # list of (p_id, text)
    seen_ids = set()     # theo dõi các paragraph đã lấy
    current_url = url
    first_soup = None
    last_soup = None

    while current_url:
        print(f"    Trang: {current_url}")
        soup = fetch_page(driver, current_url)

        if not soup:
            break

        last_soup = soup
        if first_soup is None:
            first_soup = soup

        page_paragraphs = extract_paragraphs_from_page(soup)

        for p_id, text in page_paragraphs:
            # Chỉ thêm paragraph chưa thấy (tránh overlap giữa các page)
            if p_id not in seen_ids:
                seen_ids.add(p_id)
                all_paragraphs.append(text)

        # Kiểm tra có trang tiếp theo không (page/2, page/3...)
        next_page_tag = soup.find("link", rel="next")
        if next_page_tag:
            href = next_page_tag.get("href", "")
            if "page/" in href:
                current_url = href
                time.sleep(random.uniform(1, 2))
                continue

        current_url = None

    content = "\n\n".join(all_paragraphs)
    return content, last_soup, first_soup


def run_scraper_for_code(driver, code: str):
    start_url = f"https://www.wattpad.com/{code}"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    count = 0
    current_url = start_url

    while current_url:
        count += 1
        print(f"\n  [{count}] {current_url}")

        content, last_soup, first_soup = scrape_chapter_content(driver, current_url)

        if not content or not first_soup:
            print("    [!] Không có nội dung. Dừng toàn bộ.")
            return False

        title = extract_title_from_header(first_soup) or sanitize_filename(content)
        file_path = os.path.join(OUTPUT_DIR, f"{title}.txt")

        if os.path.exists(file_path):
            # file_path = os.path.join(OUTPUT_DIR, f"{title}_{count}.txt")
            print(f'    [!] File đã tồn tại: {os.path.basename(file_path)}.')
            return False

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(normalize_dots(content))

        print(f"    [OK] Lưu: {os.path.basename(file_path)}")

        next_url = get_next_chapter_url(last_soup)
        if next_url and next_url != current_url:
            current_url = next_url
            print("    --- Nghỉ 4-8s ---")
            time.sleep(random.uniform(4, 8))
            
        else:
            print("    --- Hết chapter ---")
            break

    return True


def load_codes(file_path: str = "chapters.txt") -> list[str]:
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


if __name__ == "__main__":
    codes = load_codes()
    print(f"Tổng số code: {len(codes)}")

    driver = get_driver()

    try:
        for i, code in enumerate(codes):
            print(f"\n=== Code {i+1}/{len(codes)}: {code} ===")
            success = run_scraper_for_code(driver, code)
            if not success:
                print("\n[!] Dừng toàn bộ do lỗi hoặc phát hiện file ghi đã tồn tại.")
                break
            if i < len(codes) - 1:
                time.sleep(random.uniform(3, 6))
    finally:
        driver.quit()
        print("\nHoàn tất. Chrome đã đóng.")