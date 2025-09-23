import json
from urllib.parse import urlparse
from collections import defaultdict

# ---------------- CONFIG ----------------
MAX_EDGES = None   # Adjust this for testing (set to None for no limit)
INPUT_FILE = "site_structure.json"
OUTPUT_FILE = "mindmap.md"
# ----------------------------------------

# ---- Load JSON ----
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    site = json.load(f)

pages = site.get("pages", {})
edges = site.get("edges", [])

# ---- Helpers ----
def get_title(url: str) -> str:
    """Return a clean page title or fallback to URL."""
    return (pages.get(url) or url).strip().replace('"', "'")

def clean_label(text: str) -> str:
    """Truncate overly long labels for readability."""
    return (text[:60] + "…") if len(text) > 60 else text

# ---- Determine root ----
# Prefer a URL containing "home" if available, otherwise first key
root_url = next((u for u in pages if "home" in u.lower()), next(iter(pages), "Website"))
root_name = urlparse(root_url).netloc or "Website"

# ---- Prepare mermaid lines ----
lines = [
    "```mermaid",
    "mindmap",
    f"  root(({root_name}))"
]

# ---- Build children mapping ----
children_map = defaultdict(list)
for e in edges:
    src = e.get("source")
    tgt = e.get("target")
    text = e.get("text", "")
    if src and tgt:
        children_map[src].append((tgt, text))

# ---- Recursive builder ----
edge_count = 0
limit = MAX_EDGES if MAX_EDGES is not None else float("inf")
visited = set()

def add_children(parent_url: str, indent: int = 4):
    """Depth-first traversal to build a clean hierarchy."""
    global edge_count
    if edge_count >= limit:
        return
    for child_url, link_text in children_map.get(parent_url, []):
        if edge_count >= limit:
            break
        if parent_url == child_url:  # avoid self-loops
            continue
        child_title = get_title(child_url)
        label = clean_label(f"{link_text} → {child_title}" if link_text else child_title)
        lines.append(" " * indent + f'"{label}"')
        edge_count += 1
        if child_url not in visited:
            visited.add(child_url)
            add_children(child_url, indent + 2)

# ---- Build the tree ----
visited.add(root_url)
add_children(root_url, indent=4)

# ---- Write output ----
lines.append("```")
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Generated {OUTPUT_FILE} with {edge_count} edges (limit {MAX_EDGES})")