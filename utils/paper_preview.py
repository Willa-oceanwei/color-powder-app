"""Display existing report content on an isolated, zoomable paper surface."""

from html import escape
from html.parser import HTMLParser


class _PrintBody(HTMLParser):
    allowed = {"div", "pre", "span", "b", "strong", "br", "p"}
    blocked = {"script", "style", "iframe", "object"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_body = False
        self.blocked_depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.in_body = True
        elif self.in_body:
            if tag in self.blocked:
                self.blocked_depth += 1
            elif not self.blocked_depth and tag in self.allowed:
                attributes = "".join(f' {key}="{escape(value or "", quote=True)}"'
                                     for key, value in attrs if key in ("class", "style"))
                self.parts.append(f"<{tag}{attributes}>")

    def handle_endtag(self, tag):
        if tag == "body":
            self.in_body = False
        elif self.in_body:
            if tag in self.blocked:
                self.blocked_depth = max(0, self.blocked_depth - 1)
            elif not self.blocked_depth and tag in self.allowed and tag != "br":
                self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if self.in_body and not self.blocked_depth:
            self.parts.append(escape(data))


def build_paper_preview(content, *, title, document=False):
    if document:
        body = _PrintBody()
        body.feed(content)
        paper = "".join(body.parts)
    else:
        lines = (content or "").splitlines()
        if lines and lines[0] == "```" and lines[-1] == "```":
            lines = lines[1:-1]
        paper = f'<div class="title">{escape(title)}</div><pre>{escape(chr(10).join(lines))}</pre>'
    return '''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<title>''' + escape(title) + '''預覽</title><style>
*{box-sizing:border-box}body{margin:0;color:#000;background:#e5e7eb;letter-spacing:0;font:16px Arial,"Microsoft JhengHei",sans-serif}
.toolbar{display:flex;align-items:center;gap:10px;padding:8px}.toolbar select{font:inherit;min-height:38px;min-width:140px;padding:5px 10px;border-radius:4px}
.stage{overflow:auto;padding:12px;height:520px}.paper{background:#fff;color:#000;width:210mm;min-height:148mm;padding:10mm;margin:0 auto;zoom:var(--scale,1)}
.title{text-align:center;font:24px Arial,"Microsoft JhengHei",sans-serif;margin-bottom:16px}.timestamp{text-align:center;font:20px Arial,sans-serif;margin-bottom:2px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:18px/1.5 "Courier New","Microsoft JhengHei",monospace;margin:0}b.num{font-weight:normal}
.paper .timestamp+.title{margin-bottom:22px}
</style></head><body><div class="toolbar"><label for="zoom">縮放</label><select id="zoom" onchange="resize()">
<option value="width">符合寬度</option><option value="page">整頁</option><option value="0.75">75%</option><option value="1">100%</option><option value="1.25">125%</option><option value="1.5">150%</option><option value="2">200%</option></select></div>
<div class="stage"><section class="paper">''' + paper + '''</section></div><script>
const stage=document.querySelector('.stage'),paper=document.querySelector('.paper');
function resize(){stage.style.height=Math.max(160,innerHeight-document.querySelector('.toolbar').offsetHeight)+'px';
const mode=document.getElementById('zoom').value,width=(stage.clientWidth-24)/paper.offsetWidth;
const scale=mode==='width'?width:mode==='page'?Math.min(width,(stage.clientHeight-24)/paper.offsetHeight):Number(mode);
document.documentElement.style.setProperty('--scale',Math.max(.15,scale));}
addEventListener('resize',resize);resize();
</script></body></html>'''
