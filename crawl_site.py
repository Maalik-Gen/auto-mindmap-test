import asyncio
import json
import os
from urllib.parse import urlparse
from hashlib import md5
from playwright.async_api import async_playwright

START_URL = "https://teamupventures.com/"
MAX_PAGES = 50
SCREENSHOT_DIR = "screenshots"

def normalize_url(u: str) -> str:
    """
    Normalize URL but KEEP fragment so we can detect sections.
    """
    parsed = urlparse(u)
    base = parsed.scheme + "://" + parsed.netloc + parsed.path.rstrip("/")
    if parsed.fragment:
        return base + "#" + parsed.fragment
    return base

async def crawl():
    pages = {}
    edges_set = set()
    visited = set()
    to_visit = [START_URL]
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        while to_visit and len(pages) < MAX_PAGES:
            url = normalize_url(to_visit.pop())
            if url in visited:
                continue
            visited.add(url)

            print(f"[Crawling] {url}")
            try:
                await page.goto(url, timeout=30000)
                await page.wait_for_load_state("load")
            except Exception as e:
                print(f"⚠️ Failed to load {url}: {e}")
                continue

            # --- get title ---
            title = (await page.title()).strip() or url

            # --- take full-page screenshot ---
            filename = md5(url.encode()).hexdigest() + ".png"
            screenshot_path = os.path.join(SCREENSHOT_DIR, filename)
            await page.screenshot(path=screenshot_path, full_page=True)

            # --- get a short description safely ---
            description = ""
            meta_el = await page.query_selector("meta[name='description']")
            if meta_el:
                description = await meta_el.get_attribute("content")

            if not description:
                # fallback: first visible paragraph text
                p_el = await page.query_selector("p")
                if p_el:
                    raw_text = await p_el.inner_text()
                    description = raw_text[:200]

            # 🔹NEW: Take section-specific screenshots
            section_entries = []
            sections = await page.query_selector_all("section, div[id]")
            for i, sec in enumerate(sections):
                box = await sec.bounding_box()
                if box and box["width"] > 50 and box["height"] > 50:
                    sec_file = os.path.join(
                        SCREENSHOT_DIR,
                        f"{md5((url+str(i)).encode()).hexdigest()}_section.png"
                    )
                    try:
                        await page.screenshot(path=sec_file, clip=box)
                        section_entries.append({
                            "id": await sec.get_attribute("id"),
                            "screenshot": sec_file
                        })
                    except Exception as e:
                        print(f"⚠️ Section screenshot failed: {e}")

            # 🔹NEW: Save page info with description and sections
            pages[url] = {
                "title": title,
                "description": (description or "").strip(),
                "screenshot": screenshot_path,
                "sections": section_entries
            }

            # --- collect links ---
            anchors = await page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => ({href:e.getAttribute('href'), "
                "full:e.href, text:(e.innerText || e.textContent || '').trim()}))"
            )

            for a in anchors:
                full_href = normalize_url(a["full"])
                text = a["text"].strip()
                parsed = urlparse(full_href)

                if full_href.startswith(START_URL) and parsed.fragment:
                    # internal fragment → treat as section
                    section_id = parsed.fragment
                    pseudo_url = START_URL.rstrip("/") + f"/__section_{section_id}"
                    section_title = " ".join(
                        word.capitalize() for word in section_id.replace("-", " ").split()
                    )
                    if pseudo_url not in pages:
                        pages[pseudo_url] = {
                            "title": section_title,
                            "description": "",
                            "screenshot": screenshot_path,
                            "sections": []
                        }
                    if text:
                        edges_set.add((url, pseudo_url, text))

                elif full_href.startswith(START_URL):
                    clean_href = full_href.split("#")[0].rstrip("/")
                    if clean_href not in visited and clean_href not in to_visit:
                        to_visit.append(clean_href)
                    if text:
                        edges_set.add((url, clean_href, text))

            # --- collect buttons ---
            buttons = await page.eval_on_selector_all(
                "button, input[type=button]",
                "els => els.map(e => ({text:(e.innerText || e.value || '').trim()}))"
            )
            for b in buttons:
                if b["text"]:
                    edges_set.add((url, None, b["text"]))

        await browser.close()

    edges = [{"source": s, "target": t, "text": txt} for s, t, txt in edges_set]

    with open("site_structure.json", "w", encoding="utf-8") as f:
        json.dump({"pages": pages, "edges": edges}, f, indent=2)

if __name__ == "__main__":
    asyncio.run(crawl())