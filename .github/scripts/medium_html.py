"""Rewrite Pandoc's HTML of docs/medium.md into markup Medium's "Import a story" keeps intact.

- Labelled bullet lists (each item starts with bold text) become one paragraph per item.
- Numbered lists become "Step N." paragraphs, numbered across code blocks.
- Code blocks become <pre> with explicit <br> line breaks and &nbsp; indentation (Medium drops raw newlines and leading spaces).
- A lone image becomes <figure> with its alt text as the caption.
Usage: python medium_html.py in.html out.html
"""
import html
import re
import sys

src = open(sys.argv[1], encoding="utf-8").read()
step = 0


def labelled_list(m):
    items = re.findall(r"<li>(.*?)</li>", m.group(1), re.S)
    if not items or not all(i.strip().startswith("<strong>") for i in items):
        return m.group(0)
    return "\n".join(f"<p>{i.strip()}</p>" for i in items)


def numbered_list(m):
    global step
    start = re.search(r'start="(\d+)"', m.group(1))
    step = int(start.group(1)) - 1 if start else 0
    out = []
    for item in re.findall(r"<li>(.*?)</li>", m.group(2), re.S):
        step += 1
        out.append(f"<p><strong>Step {step}.</strong> {item.strip()}</p>")
    return "\n".join(out)


def code_block(m):
    text = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).rstrip("\n")
    def keep_indent(line):
        body = line.lstrip(" ")
        return "&nbsp;" * (len(line) - len(body)) + html.escape(body)

    return "<pre>" + "<br>".join(keep_indent(line) for line in text.split("\n")) + "</pre>"


def figure(m):
    tag = m.group(1)
    alt = re.search(r'alt="([^"]*)"', tag)
    cap = f"<figcaption>{alt.group(1)}</figcaption>" if alt else ""
    return f"<figure>{tag}{cap}</figure>"


out = re.sub(r"<ul>(.*?)</ul>", labelled_list, src, flags=re.S)
out = re.sub(r"<ol([^>]*)>(.*?)</ol>", numbered_list, out, flags=re.S)
out = re.sub(r"<pre[^>]*><code[^>]*>(.*?)</code></pre>", code_block, out, flags=re.S)
out = re.sub(r"<p>(<img [^>]*>)</p>", figure, out)
open(sys.argv[2], "w", encoding="utf-8").write(out)
