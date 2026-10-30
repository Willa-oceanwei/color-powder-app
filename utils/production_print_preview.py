"""Online A5 production printing, separate from the unchanged download document."""

import re
from html import escape
from html.parser import HTMLParser

from .paper_preview import _PrintBody, theme_preview


class _ProductionLine(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.text = ""
        self.prefix = ""
        self.bold = []
        self.current = None
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        if tag == "b":
            if not self.bold:
                self.prefix = self.text
            self.current = [dict(attrs).get("class", ""), ""]

    def handle_endtag(self, tag):
        if tag == "b" and self.current is not None:
            self.bold.append(self.current)
            self.current = None

    def handle_data(self, data):
        self.text += data
        if self.current is not None:
            self.current[1] += data


def _pack_headers(text):
    if not text.startswith(" " * 14):
        return None
    remaining = text[14:]
    headers = []
    for index in range(4):
        match = re.match(r"\S+ × \S+", remaining)
        if match:
            label = match.group()
            headers.append((index, label))
            remaining = remaining[max(11, len(label)):]
        elif remaining.startswith(" " * 11):
            remaining = remaining[11:]
        else:
            return None
    return headers or None


def _numeric_row(line):
    if len(line.bold) == 5 and all("num" in classes.split() for classes, _ in line.bold[1:]):
        label = line.bold[0][1].strip()
        values = [value.strip() for _, value in line.bold[1:]]
        total = "production-total-label" in line.bold[0][0].split()
    elif len(line.bold) == 4:
        label = line.prefix.strip()
        values = [value.strip() for _, value in line.bold]
        total = False
    else:
        return None
    if not label or not all(not value or re.fullmatch(r"-?\d+(?:\.\d+)?", value) for value in values):
        return None
    return label, values, total


def _group_packaging(source):
    """Associate existing rendered values with their packaging, without recalculation."""
    def convert(match):
        lines = re.split(r"<br\s*/?>", match.group(1), flags=re.I)
        headers = None
        rows = []
        result = []

        def flush():
            if not rows:
                return
            for index, header in headers:
                cells = "".join(
                    '<tr' + (' class="production-total"' if total else '') + '><td>'
                    + escape(label) + '</td><td>' + escape(values[index]) + '</td></tr>'
                    for label, values, total in rows
                )
                result.append(f'<table class="production-group" data-pack-index="{index}"><colgroup><col style="width:60%"><col style="width:40%"></colgroup>'
                              f'<thead><tr><th colspan="2">{escape(header)}</th></tr><tr><th>色粉編號／合計</th><th>用量</th></tr></thead>'
                              f'<tbody>{cells}</tbody></table>')
            rows.clear()

        for raw in lines:
            line = _ProductionLine(raw)
            packing = _pack_headers(line.text)
            if packing:
                flush()
                headers = packing
                continue
            row = _numeric_row(line) if headers else None
            if row:
                rows.append(row)
                continue
            if rows and line.text.strip() and set(line.text.strip()) <= set("＿―_─-"):
                continue
            flush()
            result.append(raw + '<br>')
        flush()
        return '<div class="production-content">' + ''.join(result) + '</div>'

    return re.sub(r"<pre\b[^>]*>(.*?)</pre>", convert, source, flags=re.I | re.S)


def build_production_order_preview(document):
    """Reuse generated A5 styles and safe body without its automatic print script."""
    body = _PrintBody()
    body.feed(document)
    head = re.search(r"<head\b[^>]*>(.*?)</head>", document, flags=re.I | re.S)
    styles = "\n".join(re.findall(r"<style\b[^>]*>.*?</style>", head.group(1) if head else "", flags=re.I | re.S))
    # The document comes from generate_print_page_content; its head styles are
    # fixed application CSS. User-supplied body scripts/events are filtered out.
    return theme_preview('''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<title>生產單線上列印</title>''' + styles + '''
<style id="production-online-preview">
@page{size:A5 portrait;margin:10mm}
.production-page{position:relative;box-sizing:border-box;width:128mm;min-height:190mm;background:#fff;color:#000}
.production-paper{position:relative;box-sizing:border-box;width:100%;min-height:190mm;margin:0;padding:0;transform:none;font-size:calc(22px * var(--production-print-scale,1));line-height:1.4}
.production-paper .title{font-size:calc(24px * var(--production-print-scale,1))}
.production-paper .timestamp{font-size:calc(20px * var(--production-print-scale,1))}
.production-paper pre,.production-content{margin-left:0;margin-right:0;font:inherit;white-space:pre-wrap;overflow-wrap:anywhere}
.production-content>div{flex-wrap:wrap;font-size:calc(20px * var(--production-print-scale,1))!important}
.production-content>div>div{flex:1 1 auto!important;overflow:visible!important;white-space:normal!important}
.production-group{width:100%;table-layout:fixed;border-collapse:collapse;font:inherit;white-space:normal;margin:10px 0}
.production-group th,.production-group td{padding:2px 0;text-align:left;overflow-wrap:anywhere}
.production-group td:last-child{text-align:right}
.production-group th{font-weight:normal}.production-group tr{break-inside:avoid}
.production-group thead{display:table-header-group}.production-total td{border-top:1px solid #000}
@media screen {
body{margin:0;transform:none;background:#101820}
.toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:8px}
.toolbar button,.toolbar select{font:16px Arial,"Microsoft JhengHei",sans-serif;min-height:38px;padding:5px 10px}
.toolbar .hint{font:13px "Microsoft JhengHei",sans-serif}
.stage{height:340px;overflow:auto;padding:8px}
.production-page{margin:0 auto;zoom:var(--production-scale,1)}
}
@media print {
body{margin:0!important;transform:none!important}
.toolbar{display:none!important}
.stage{position:relative;width:128mm!important;height:auto!important;overflow:visible!important;padding:0!important}
.production-page{margin:0!important;zoom:1!important}
.production-paper{outline:none!important;box-shadow:none!important}
}
</style></head><body>
<div class="toolbar">
<button type="button" id="production-print" onclick="window.print()">列印 A5（位置測試）</button>
<label for="production-zoom">預覽縮放</label><select id="production-zoom" onchange="fitProduction()">
<option value="page">完整內容</option><option value="width" selected>符合寬度</option>
<option value="0.75">75%</option><option value="1">100%</option><option value="1.25">125%</option>
</select>
<label for="production-print-scale">列印比例</label><select id="production-print-scale" onchange="applyPrintScale();fitProduction()">
<option value="0.5">50%</option><option value="0.75">75%</option><option value="1" selected>100%</option>
<option value="1.1">110%</option><option value="1.25">125%</option><option value="1.5">150%</option><option value="2">200%</option>
</select><span class="hint">文字正向、標題在上；紙張 A5 直向；列印視窗選 100%。預覽縮放不影響列印；原有 A5 下載仍可使用</span></div>
<div class="stage"><div class="production-page"><section class="production-paper paper">''' + _group_packaging("".join(body.parts)) + '''</section></div></div>
<script>
const stage=document.querySelector('.stage'),page=document.querySelector('.production-page'),paper=document.querySelector('.production-paper');
function applyPrintScale(){
// Only the explicit print-size selection controls printed text size.
// Long content flows onto additional pages instead of shrinking the whole order.
const scale=Number(document.getElementById('production-print-scale').value);
paper.style.setProperty('--production-print-scale',scale);
}
function fitProduction(){
applyPrintScale();
stage.style.height=Math.max(160,innerHeight-document.querySelector('.toolbar').offsetHeight)+'px';
const mode=document.getElementById('production-zoom').value;
const width=(stage.clientWidth-24)/page.offsetWidth;
const scale=mode==='width'?width:mode==='page'?Math.min(width,(stage.clientHeight-24)/page.offsetHeight):Number(mode);
document.documentElement.style.setProperty('--production-scale',Math.max(.15,scale));
}
addEventListener('resize',fitProduction);fitProduction();
addEventListener('beforeprint',applyPrintScale);
if(document.fonts)document.fonts.ready.then(fitProduction);
</script></body></html>''')

