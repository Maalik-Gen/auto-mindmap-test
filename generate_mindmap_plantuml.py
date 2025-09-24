import json
import os
from urllib.parse import urlparse

# --- Convert JSON to PlantUML mind map ---
def site_map_to_plantuml(site_data, root_name="Website"):
    """
    site_data format:
    {
        "pages": {
            url: {"title": "...", "screenshot": "path/to/file.png"}
        },
        "edges": [
            {"source": url, "target": url|None, "text": "link/button text"}
        ]
    }
    """
    pages = site_data.get("pages", {})
    edges = site_data.get("edges", [])
    lines = ["@startmindmap", f"* {root_name}"]

    # Track outgoing connections
    children_map = {}
    for e in edges:
        src = e["source"]
        tgt = e.get("target")
        txt = e.get("text", "")
        if tgt:
            children_map.setdefault(src, []).append((tgt, txt))
        else:
            # Buttons (no target)
            children_map.setdefault(src, []).append((None, txt))

    visited = set()

    def add_nodes(url, depth=2):
        if url in visited:
            return
        visited.add(url)

        page = pages.get(url, {})
        prefix = "*" * depth
        title = page.get("title") or url
        path = urlparse(url).path or "/"

        # If screenshot exists, annotate it
        screenshot = page.get("screenshot")
        if screenshot and os.path.exists(screenshot):
            lines.append(f"{prefix} {title} ({path}) [[{screenshot}]]")
        else:
            lines.append(f"{prefix} {title} ({path})")

        for child, label in children_map.get(url, []):
            if child is None:
                # Standalone button
                lines.append(f"{prefix}* Button: {label}")
            else:
                # Link with text
                label_text = f" ({label})" if label else ""
                lines.append(f"{prefix}* Link{label_text}")
                add_nodes(child, depth + 2)

    # Start from the START_URL or any root (no parent concept, so just pick all)
    for root_url in pages.keys():
        if root_url not in visited:
            add_nodes(root_url, depth=2)

    lines.append("@endmindmap")
    return "\n".join(lines)


def json_to_plantuml(json_file="site_structure.json", puml_file="mindmap.puml"):
    with open(json_file, "r", encoding="utf-8") as f:
        site_data = json.load(f)

    plantuml_code = site_map_to_plantuml(site_data, root_name="340B Price Guide")

    with open(puml_file, "w", encoding="utf-8") as f:
        f.write(plantuml_code)

    print(f"[ok] PlantUML mind map saved to {puml_file}")


if __name__ == "__main__":
    json_to_plantuml("site_structure.json", "mindmap.puml")
