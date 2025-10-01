import asyncio
import os
from urllib.parse import urlparse
from hashlib import md5
from playwright.async_api import async_playwright
import xml.etree.ElementTree as ET

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

            # --- improved section screenshots ---
            section_entries = []
            seen_boxes = []
            sections = await page.query_selector_all("section")  # only top-level sections
            for i, sec in enumerate(sections):
                box = await sec.bounding_box()
                if not box:
                    continue

                # skip very small boxes
                if box["width"] < 200 or box["height"] < 200:
                    continue

                # check for duplicates (overlap)
                duplicate = False
                for sb in seen_boxes:
                    overlap_x = max(0, min(box["x"] + box["width"], sb["x"] + sb["width"]) - max(box["x"], sb["x"]))
                    overlap_y = max(0, min(box["y"] + box["height"], sb["y"] + sb["height"]) - max(box["y"], sb["y"]))
                    overlap_area = overlap_x * overlap_y
                    smaller_area = min(box["width"] * box["height"], sb["width"] * sb["height"])
                    if smaller_area > 0 and (overlap_area / smaller_area) > 0.8:
                        duplicate = True
                        break
                if duplicate:
                    continue

                # expand box slightly for context
                box["x"] = max(0, box["x"] - 20)
                box["y"] = max(0, box["y"] - 20)
                box["width"] += 40
                box["height"] += 40

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
                    seen_boxes.append(box)
                except Exception as e:
                    print(f"⚠️ Section screenshot failed: {e}")

            # Save page info
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
    return pages, edges


# --- NEW: Export to FreeMind .mm ---
def export_to_freemind(pages, edges, output_file="site_structure.mm"):
    map_el = ET.Element("map", version="1.0.1")

    root_page = pages.get(START_URL, {"title": "Root"})
    root_node = ET.SubElement(map_el, "node", TEXT=root_page["title"])

    children_map = {}
    for e in edges:
        if e["source"] not in children_map:
            children_map[e["source"]] = []
        children_map[e["source"]].append(e["target"])

    def build_tree(parent_node, page_url):
        for child_url in children_map.get(page_url, []):
            if child_url in pages:
                child_page = pages[child_url]
                child_node = ET.SubElement(
                    parent_node,
                    "node",
                    TEXT=child_page["title"] or child_url
                )
                if child_page.get("description"):
                    rc = ET.SubElement(child_node, "richcontent", TYPE="NOTE")
                    rc.text = child_page["description"]
                build_tree(child_node, child_url)

    build_tree(root_node, START_URL)

    tree = ET.ElementTree(map_el)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"✅ FreeMind file saved as {output_file}")


if __name__ == "__main__":
    pages, edges = asyncio.run(crawl())
    export_to_freemind(pages, edges, "site_structure.mm")
