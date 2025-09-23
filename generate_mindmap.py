import os
import json

# --- AI code removed ---
# import openai
# openai.api_key = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_KEY")

# Load the crawled site structure
with open("site_structure.json", "r", encoding="utf-8") as f:
    site = json.load(f)

lines = [
    "```mermaid",
    "mindmap",
    "  root((Books to Scrape))"   # Root node
]

for page in site:
    title = (page.get("title") or page.get("url", "Untitled")).replace('"', "'")
    lines.append(f"    \"{title}\"")

    # Group Buttons
    buttons = page.get("buttons", [])
    if buttons:
        lines.append("      Buttons")
        for b in buttons:
            text = b.get("text", "Unnamed Button") if isinstance(b, dict) else str(b)
            text = text.replace('"', "'")
            lines.append(f"        \"{text}\"")

    # Group Links
    links = page.get("links", [])
    if links:
        lines.append("      Links")
        for l in links[:10]:  # limit to first 10 to avoid clutter
            text = l if isinstance(l, str) else l.get("text") or l.get("href")
            text = text.replace('"', "'")
            lines.append(f"        \"{text}\"")

lines.append("```")

with open("mindmap.md", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("✅ Generated mindmap.md (Mermaid syntax)")