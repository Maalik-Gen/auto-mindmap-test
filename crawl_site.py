import asyncio, json, os
from urllib.parse import urljoin
from hashlib import md5
from playwright.async_api import async_playwright

START_URL = "https://www.340bpriceguide.net/"
MAX_PAGES = 50
SCREENSHOT_DIR = "screenshots"

async def crawl():
    pages, edges, visited, to_visit = {}, [], set(), [START_URL]
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        while to_visit and len(pages) < MAX_PAGES:
            url = to_visit.pop()
            if url in visited:
                continue
            visited.add(url)

            print(f"[Crawling] {url}")
            await page.goto(url)
            await page.wait_for_load_state("networkidle")

            title = (await page.title()).strip() or url
            pages[url] = title

            # --- take screenshot ---
            filename = md5(url.encode()).hexdigest() + ".png"
            screenshot_path = os.path.join(SCREENSHOT_DIR, filename)
            await page.screenshot(path=screenshot_path, full_page=True)
            pages[url] = {"title": title, "screenshot": screenshot_path}

            # --- collect links ---
            anchors = await page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => ({href:e.href, text:(e.innerText || e.textContent || '').trim()}))"
            )
            for a in anchors:
                href = urljoin(url, a["href"])
                if href.startswith(START_URL):
                    if href not in visited and href not in to_visit:
                        to_visit.append(href)
                    if a["text"]:
                        edges.append({"source": url, "target": href, "text": a["text"]})

            # --- collect buttons (stand-alone actions) ---
            buttons = await page.eval_on_selector_all(
                "button, input[type=button]",
                "els => els.map(e => ({text:(e.innerText || e.value || '').trim()}))"
            )
            for b in buttons:
                if b["text"]:
                    edges.append({"source": url, "target": None, "text": b["text"]})

        await browser.close()

    with open("site_structure.json", "w", encoding="utf-8") as f:
        json.dump({"pages": pages, "edges": edges}, f, indent=2)

if __name__ == "__main__":
    asyncio.run(crawl())