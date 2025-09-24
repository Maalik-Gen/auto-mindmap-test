# generate_site_graph_debug.py
import json
import os
import sys
import traceback
from urllib.parse import urlparse
from collections import defaultdict, deque
from pyvis.network import Network
from datetime import datetime
import base64

INPUT_FILE = "site_structure.json"
OUTPUT_FILE = "site_graph.html"
MAX_EDGES = None  # limit edges for testing (None = no limit)
SCREENSHOT_DIR = "screenshots"

def log(msg):
    print(msg, flush=True)

def file_mtime(path):
    try:
        ts = os.path.getmtime(path)
        return datetime.fromtimestamp(ts).isoformat()
    except Exception:
        return None

def encode_image(path):
    """Return base64 data URL for an image if it exists."""
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
            return f"data:image/png;base64,{encoded}"
    return None

try:
    log("START: debug run")
    log(f"Reading JSON: {INPUT_FILE}")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        site = json.load(f)

    pages = site.get("pages", {})
    edges = site.get("edges", [])
    log(f"Pages count: {len(pages)} | Edges count: {len(edges)}")

    def get_title(url: str):
        data = pages.get(url, {})
        if isinstance(data, dict):
            return data.get("title", url)
        return str(data).strip()

    def get_screenshot(url: str):
        data = pages.get(url, {})
        if isinstance(data, dict):
            path = data.get("screenshot")
            return encode_image(path)
        return None

    # Pick root page
    root_url = next((u for u in pages if "home" in u.lower()), next(iter(pages), None))
    if not root_url:
        raise RuntimeError("No pages found in JSON")
    root_name = urlparse(root_url).netloc or "Website"
    log(f"Root chosen: {root_url} (root_name: {root_name})")

    # Build adjacency map
    children_map = defaultdict(list)
    for e in edges:
        src, tgt = e.get("source"), e.get("target")
        text = e.get("text", "")
        if src and tgt:
            children_map[src].append((tgt, text))

    # Initialize PyVis network
    log("Initializing PyVis network")
    net = Network(
        height="1000px",
        width="100%",
        bgcolor="#222222",
        font_color="white",
        directed=True,
        notebook=False
    )
    net.force_atlas_2based()

    # Add root node
    root_title = get_title(root_url)
    root_image = get_screenshot(root_url)
    net.add_node(
        root_url,
        label=root_name,
        shape="image" if root_image else "star",
        size=50,
        color="#FFAA00",
        image=root_image,
        title=root_title
    )

    # Traverse and add children
    limit = MAX_EDGES if MAX_EDGES is not None else float("inf")
    edge_count = 0
    visited = {root_url}

    def add_children(root_parent):
        global edge_count
        q = deque([root_parent])
        while q and edge_count < limit:
            parent = q.popleft()
            for child, text in children_map.get(parent, []):
                if edge_count >= limit:
                    break
                if not child:
                    continue  # skip empty targets (like buttons)
                if child not in visited:
                    visited.add(child)
                    title = get_title(child)
                    screenshot = get_screenshot(child)
                    log(f"Adding node: {child} | Title: {title[:40]} | Screenshot: {'Yes' if screenshot else 'No'}")
                    net.add_node(
                        child,
                        label=title[:30],
                        shape="image" if screenshot else "dot",
                        size=30,
                        color="#4DA6FF",
                        image=screenshot,
                        title=title
                    )
                    q.append(child)
                net.add_edge(parent, child, title=text or "", width=1)
                edge_count += 1

    log("Building graph (traversal starts)")
    add_children(root_url)
    log(f"Traversal complete. Edge count: {edge_count}")

    # Physics & layout tweaks (stabilization to stop jitter)
    net.set_options("""
{
  "nodes": { "font": { "size": 18 } },
  "edges": { "smooth": true, "color": { "inherit": true }, "width": 1 },
  "physics": {
    "enabled": true,
    "stabilization": { "enabled": true, "iterations": 2000, "updateInterval": 50 },
    "barnesHut": {
      "gravitationalConstant": -2000,
      "centralGravity": 0.2,
      "springLength": 500,
      "springConstant": 0.02,
      "damping": 0.25
    }
  }
}
""")

    log(f"Writing HTML to {OUTPUT_FILE} (absolute: {os.path.abspath(OUTPUT_FILE)})")
    net.write_html(OUTPUT_FILE)

    mtime = file_mtime(OUTPUT_FILE)
    log(f"✅ WROTE HTML: {OUTPUT_FILE}  last modified: {mtime}")
    log(f"FINISHED: Generated {OUTPUT_FILE} with {edge_count} edges")

except Exception as exc:
    log("ERROR: exception caught during run:")
    traceback.print_exc(file=sys.stdout)
    sys.exit(1)
