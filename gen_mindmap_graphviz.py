import json
import os
import sys
import traceback
from urllib.parse import urlparse
from collections import defaultdict, deque
from datetime import datetime
import base64
from graphviz import Digraph

INPUT_FILE = "site_structure.json"
OUTPUT_FILE = "site_graph"  # Graphviz will add .svg or .png
FORMAT = "svg"              # or "png", "pdf"
MAX_EDGES = None            # None = no limit

def log(msg):
    print(msg, flush=True)

def file_mtime(path):
    try:
        ts = os.path.getmtime(path)
        return datetime.fromtimestamp(ts).isoformat()
    except Exception:
        return None

try:
    log("START: Graphviz run")
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
            return path if path and os.path.exists(path) else None
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

    # Create Graphviz Digraph
    dot = Digraph(comment="Website Structure", format=FORMAT)
    dot.attr(rankdir="LR", bgcolor="#222222", fontcolor="white")  # Left→Right layout

    # Add root node
    root_title = get_title(root_url)
    root_image = get_screenshot(root_url)
    dot.node(
        root_url,
        label=root_name if not root_image else "",
        shape="star" if not root_image else "none",
        style="filled",
        color="#FFAA00",
        fontcolor="white",
        image=root_image if root_image else None
    )

    # Traverse and add children
    limit = MAX_EDGES if MAX_EDGES is not None else float("inf")
    edge_count = 0
    visited = {root_url}

    q = deque([root_url])
    while q and edge_count < limit:
        parent = q.popleft()
        for child, text in children_map.get(parent, []):
            if edge_count >= limit:
                break
            if not child:
                continue
            if child not in visited:
                visited.add(child)
                title = get_title(child)
                screenshot = get_screenshot(child)
                log(f"Adding node: {child} | Title: {title[:40]} | Screenshot: {'Yes' if screenshot else 'No'}")
                dot.node(
                    child,
                    label=title if not screenshot else "",
                    shape="box" if not screenshot else "none",
                    style="filled",
                    color="#4DA6FF",
                    fontcolor="white",
                    image=screenshot if screenshot else None
                )
                q.append(child)
            dot.edge(parent, child, label=text or "", color="white")
            edge_count += 1

    # Render output
    out_path = dot.render(OUTPUT_FILE, cleanup=True)
    mtime = file_mtime(out_path)
    log(f"✅ WROTE Graphviz file: {out_path} (last modified: {mtime})")
    log(f"FINISHED: Generated graph with {edge_count} edges")

except Exception as exc:
    log("ERROR: exception caught during run:")
    traceback.print_exc(file=sys.stdout)
    sys.exit(1)
