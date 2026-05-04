import requests
from bs4 import BeautifulSoup
import re

url = "https://www.wattpad.com/1404698831-hoa-sơn-tái-khởi-802-1000-chapter-865-chỗ-trống"

headers = {
    "User-Agent": "Mozilla/5.0"
}

res = requests.get(url, headers=headers)
res.raise_for_status()

soup = BeautifulSoup(res.text, "html.parser")

ul = soup.find("ul", class_="table-of-contents")

results = []

for a in ul.find_all("a", class_="on-navigate"):
    href = a.get("href", "")

    match = re.search(r"/(\d+)-", href)
    code = match.group(1) if match else None

    title_div = a.find("div", class_="part-title")
    text = title_div.get_text(strip=True) if title_div else ""

    results.append({
        "code": code,
        "text": text
    })

with open("chapters.txt", "w", encoding="utf-8") as f:
    for line in results:
        print(line)
        f.write(line['code'] + '\n')