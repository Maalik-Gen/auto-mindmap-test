import asyncio
import os
import json
from urllib.parse import urlparse
from hashlib import md5
from playwright.async_api import async_playwright
# from openai import OpenAI
# from dotenv import load_dotenv

# -------------------------------
# CONFIG
# -------------------------------
START_URL = "https://www.340bpriceguide.net/"
MAX_PAGES = 100
SCREENSHOT_DIR = "screenshots"

# -------------------------------
# LOAD ENV + OPENAI CLIENT (commented out)
# -------------------------------
# load_dotenv()
# api_key = os.getenv("OPENAI_API_KEY")
# if not api_key:
#     raise ValueError("❌ OPENAI_API_KEY not found. Did you set it in your .env file?")
# client = OpenAI(api_key=api_key)

# -------------------------------
# UTILS
# -------------------------------
def normalize_url(u: str) -> str:
    parsed = urlparse(u)
    base = parsed.scheme + "://" + parsed.netloc + parsed.path.rstrip("/")
    if parsed.fragment:
        return base + "#" + parsed.fragment
    return base


async def extract_text_content(page) -> str:
    elements = await page.query_selector_all("h1, h2, h3, p")
    texts = []
    for el in elements:
        try:
            txt = (await el.inner_text()).strip()
            if txt:
                texts.append(txt)
        except:
            continue
    return " ".join(texts)[:2000]


# -------------------------------
# CRAWLER
# -------------------------------
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

            # If homepage, scroll to load all content
            if url.rstrip("/") == START_URL.rstrip("/"):
                await page.mouse.wheel(0, 1000)
                await asyncio.sleep(1)

            title = (await page.title()).strip() or url

            # --- full-page screenshot ---
            filename = md5(url.encode()).hexdigest() + ".png"
            screenshot_path = os.path.join(SCREENSHOT_DIR, filename)
            await page.screenshot(path=screenshot_path, full_page=True)

            description = ""

            # 🔹 Section-specific screenshots (improved)
            section_entries = []
            seen_boxes = []
            selectors = [
                "section",
                "main",
                "article",
                "div[class*='about']",
                "div[class*='content']",
                "div[class*='article']",
                "div[class*='post']",
                "div[class*='comment']",
                "footer"
            ]
            sections = []
            for sel in selectors:
                found = await page.query_selector_all(sel)
                sections.extend(found)

            for i, sec in enumerate(sections):
                box = await sec.bounding_box()
                if not box:
                    continue
                if box["width"] < 200 or box["height"] < 200:
                    continue

                # Avoid overlapping / duplicate screenshots
                overlap = any(
                    abs(box["x"] - b["x"]) < 50 and abs(box["y"] - b["y"]) < 50
                    and abs(box["width"] - b["width"]) < 100 and abs(box["height"] - b["height"]) < 100
                    for b in seen_boxes
                )
                if overlap:
                    continue
                seen_boxes.append(box)

                # Expand bounding box a little for context
                box["x"] = max(0, box["x"] - 20)
                box["y"] = max(0, box["y"] - 20)
                box["width"] += 40
                box["height"] += 40

                section_id = await sec.get_attribute("id") or await sec.get_attribute("class") or f"section_{i}"
                section_id = section_id.lower().replace(" ", "_")

                sec_file = os.path.join(SCREENSHOT_DIR, f"{md5((url+section_id).encode()).hexdigest()}_section.png")

                try:
                    await page.screenshot(path=sec_file, clip=box)
                    section_entries.append({
                        "id": section_id,
                        "screenshot": sec_file,
                        "description": ""
                    })
                except Exception as e:
                    print(f"⚠️ Section screenshot failed: {e}")

            # 🔹 Capture buttons and interactive elements
            button_entries = []
            buttons = await page.query_selector_all("button, a[role='button'], .btn, input[type='submit']")
            for j, btn in enumerate(buttons):
                try:
                    visible = await btn.is_visible()
                    if not visible:
                        continue

                    box = await btn.bounding_box()
                    if not box:
                        continue
                    if box["width"] < 50 or box["height"] < 20:
                        continue
                    box["x"] = max(0, box["x"] - 10)
                    box["y"] = max(0, box["y"] - 10)
                    box["width"] += 20
                    box["height"] += 20

                    btn_file = os.path.join(SCREENSHOT_DIR, f"{md5((url+str(j)).encode()).hexdigest()}_button.png")
                    await page.screenshot(path=btn_file, clip=box)
                    button_entries.append(btn_file)
                except Exception as e:
                    print(f"⚠️ Button screenshot failed: {e}")

            pages[url] = {
                "title": title,
                "description": description,
                "screenshot": screenshot_path,
                "sections": section_entries,
                "buttons": button_entries
            }

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
                            "sections": [],
                            "buttons": []
                        }
                    if text:
                        edges_set.add((url, pseudo_url, text))
                elif full_href.startswith(START_URL):
                    clean_href = full_href.split("#")[0].rstrip("/")
                    if clean_href not in visited and clean_href not in to_visit:
                        to_visit.append(clean_href)
                    if text:
                        edges_set.add((url, clean_href, text))

        await browser.close()

    edges = [{"source": s, "target": t, "text": txt} for s, t, txt in edges_set]
    return pages, edges


# -------------------------------
# EXPORT
# -------------------------------
def export_to_json(pages, edges, output_file="site_structure.json"):
    data = {"pages": pages, "edges": edges}
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ JSON file saved as {output_file}")


# -------------------------------
# RUN
# -------------------------------
if __name__ == "__main__":
    pages, edges = asyncio.run(crawl())
    export_to_json(pages, edges, "site_structure.json")
