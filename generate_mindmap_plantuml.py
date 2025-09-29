import json
from urllib.parse import urlparse

def site_map_to_plantuml(site_data):
    """
    Build a PlantUML mindmap where:
      • The homepage title becomes the SINGLE root node.
      • All links/buttons branch from this root.
      • No duplicate children per parent.
    """
    pages = site_data.get("pages", {})
    edges = site_data.get("edges", [])

    # --- Determine homepage / root title ---
    if not pages:
        root_name = "Website"
        start_url = None
    else:
        # pick the FIRST crawled page as root
        start_url, start_page = next(iter(pages.items()))
        root_name = start_page.get("title") or urlparse(start_url).netloc or "Website"

    lines = ["@startmindmap", f"* {root_name}"]

    # Build adjacency list
    children_map = {}
    for e in edges:
        src = e["source"]
        tgt = e.get("target")
        txt = e.get("text", "")
        children_map.setdefault(src, []).append((tgt, txt))

    visited_pages = set()

    def add_nodes(url, depth=1):
        if url in visited_pages:
            return
        visited_pages.add(url)

        page = pages.get(url, {})
        prefix = "*" * (depth + 1)
        title = page.get("title") or url
        path = urlparse(url).path or "/"
        lines.append(f"{prefix} {title} ({path})")

        seen_links = set()
        seen_buttons = set()

        for child, label in children_map.get(url, []):
            if child:
                key = (child, label)
                if key in seen_links:
                    continue
                seen_links.add(key)
                label_text = f" ({label})" if label else ""
                lines.append(f"{prefix}* Link{label_text}")
                add_nodes(child, depth + 1)
            else:
                if label in seen_buttons:
                    continue
                seen_buttons.add(label)
                lines.append(f"{prefix}* Button: {label}")

    if start_url:
        add_nodes(start_url, depth=1)

    lines.append("@endmindmap")
    return "\n".join(lines)

def json_to_plantuml(json_file="site_structure.json", puml_file="mindmap.puml"):
    with open(json_file, "r", encoding="utf-8") as f:
        site_data = json.load(f)
    plantuml_code = site_map_to_plantuml(site_data)
    with open(puml_file, "w", encoding="utf-8") as f:
        f.write(plantuml_code)
    print(f"[ok] PlantUML mind map saved to {puml_file}")

if __name__ == "__main__":
    json_to_plantuml("site_structure.json", "mindmap.puml")
