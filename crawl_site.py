import asyncio, json
from playwright.async_api import async_playwright

START_URL = "https://books.toscrape.com/"   # <--- change for testing
MAX_PAGES = 5                       # keep small for demo

async def crawl():
    data, visited, to_visit = [], set(), [START_URL]

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        while to_visit and len(data) < MAX_PAGES:
            url = to_visit.pop()
            if url in visited: continue
            visited.add(url)

            await page.goto(url)
            title = await page.title()
            links = await page.eval_on_selector_all("a", "els => els.map(e => e.href)")
            buttons = await page.eval_on_selector_all("button, input[type=button]", 
                            "els => els.map(e => ({text:e.innerText || e.value, onclick:e.onclick?.toString()}))")

            data.append({"url": url, "title": title, "links": links, "buttons": buttons})

            # add more links to queue (same domain only)
            for l in links:
                if l.startswith(START_URL) and l not in visited:
                    to_visit.append(l)

        await browser.close()

    with open("site_structure.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    asyncio.run(crawl())
