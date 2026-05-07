"""
pip install selenium beautifulsoup4
Cần cài Chrome browser (không cần chromedriver riêng - selenium 4.6+ tự download)
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import re
import time


def get_driver():
    options = Options()
    # Bỏ comment dòng dưới nếu muốn chạy ẩn (không hiện cửa sổ Chrome)
    # options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--window-size=1280,900")
    driver = webdriver.Chrome(options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def get_code_list(url: str) -> list[dict]:
    driver = get_driver()
    results = []

    try:
        driver.get(url)

        # Chờ table-of-contents load xong
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CLASS_NAME, "table-of-contents"))
        )
        time.sleep(2)  # Chờ JS render xong

        soup = BeautifulSoup(driver.page_source, "html.parser")
        ul = soup.find("ul", class_="table-of-contents")

        if not ul:
            print("Không tìm thấy table-of-contents!")
            return results

        for a in ul.find_all("a", class_="on-navigate"):
            href = a.get("href", "")
            match = re.search(r"/(\d+)-", href)
            code = match.group(1) if match else None

            title_div = a.find("div", class_="part-title")
            text = title_div.get_text(strip=True) if title_div else ""

            results.append({"code": code, "text": text})

    finally:
        driver.quit()

    return results


if __name__ == "__main__":
    url = "https://www.wattpad.com/1438214355-hoa-s%C6%A1n-t%C3%A1i-kh%E1%BB%9Fi-1121-1321-chapter-1121-b%E1%BA%B1ng-h%E1%BB%AFu"

    results = get_code_list(url)

    with open("chapters.txt", "w", encoding="utf-8") as f:
        for item in results:
            print(item)
            if item["code"]:
                f.write(item["code"] + "\n")

    print(f"\nĐã lưu {len(results)} chapter vào chapters.txt")