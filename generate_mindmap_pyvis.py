import json
from urllib.parse import urlparse
from collections import defaultdict
from pyvis.network import Network

# ---------------- CONFIG ----------------
INPUT_FILE = "site_structure.json"
OUTPUT_FILE = "site_graph.html"
MAX_EDGES = None  # None = no limit
# ----------------------------------------

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    site = json.load(f)

pages = site.get("pages", {})
edges = site.get("edges", [])

def get_title(url: str) -> str:
    return (pages.get(url) or url).strip()

# Pick a reasonable root
root_url = next((u for u in pages if "home" in u.lower()), next(iter(pages), "Website"))
root_name = urlparse(root_url).netloc or "Website"

# Build edge map
children_map = defaultdict(list)
for e in edges:
    src = e.get("source")
    tgt = e.get("target")
    text = e.get("text", "")
    if src and tgt:
        children_map[src].append((tgt, text))

# Create network with larger size and better physics
net = Network(
    height="1000px", width="100%", bgcolor="#222222", font_color="white",
    directed=True, notebook=False
)
net.force_atlas_2based()  # Good starting layout for big graphs

# Add root node
net.add_node(root_url, label=root_name, shape="star", size=50, color="#FFAA00")

# Add edges
limit = MAX_EDGES if MAX_EDGES is not None else float("inf")
edge_count = 0
visited = set([root_url])

def add_children(parent):
    global edge_count
    if edge_count >= limit: return
    for child, text in children_map.get(parent, []):
        if edge_count >= limit: break
        if child not in visited:
            visited.add(child)
            net.add_node(child, label=get_title(child), size=20, color="#4DA6FF")
        net.add_edge(parent, child, title=text or "", width=1)
        edge_count += 1
        add_children(child)

add_children(root_url)

# Physics tweaks to spread it out more
net.set_options("""
var options = {
  nodes: {
    shape: 'dot',
    size: 20,
    font: { size: 18 }
  },
  edges: {
    smooth: true,
    color: { inherit: true },
    width: 1
  },
  physics: {
    stabilization: false,
    barnesHut: {
      gravitationalConstant: -5000,
      centralGravity: 0.1,
      springLength: 250,
      springConstant: 0.05,
      damping: 0.1
    }
  }
}
""")

net.show(OUTPUT_FILE)
print(f"✅ Generated {OUTPUT_FILE} with {edge_count} edges")
