"""Online A5 production printing, separate from the unchanged download document."""

import re

from .paper_preview import _PrintBody, theme_preview


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
.production-page{position:relative;box-sizing:border-box;width:128mm;height:190mm;background:#fff;color:#000}
.production-paper{position:absolute;left:0;top:0;box-sizing:border-box;width:190mm;min-height:128mm;margin:0;padding:0;transform-origin:top left;transform:translateX(128mm) rotate(90deg) scale(var(--production-print-scale,1))}
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
.stage{position:relative;width:128mm!important;height:190mm!important;overflow:visible!important;padding:0!important}
.production-page{margin:0!important;zoom:1!important;break-inside:avoid}
.production-paper{outline:none!important;box-shadow:none!important}
}
</style></head><body>
<div class="toolbar">
<button type="button" id="production-print" onclick="window.print()">列印 A5（位置測試）</button>
<label for="production-zoom">縮放</label><select id="production-zoom" onchange="fitProduction()">
<option value="page" selected>完整內容</option><option value="width">符合寬度</option>
<option value="0.75">75%</option><option value="1">100%</option><option value="1.25">125%</option>
</select><span class="hint">向右旋轉 90°；紙張 A5 直向；原有 A5 下載仍可使用</span></div>
<div class="stage"><div class="production-page"><section class="production-paper paper">''' + "".join(body.parts) + '''</section></div></div>
<script>
const stage=document.querySelector('.stage'),page=document.querySelector('.production-page'),paper=document.querySelector('.production-paper');
function fitRotation(){
// A5 printable area is 128 x 190 mm. Scale longer content before rotating
// so its transformed bounds stay on the page without changing the source.
const scale=Math.min(1,page.clientWidth/Math.max(paper.offsetHeight,paper.scrollHeight),page.clientHeight/Math.max(paper.offsetWidth,paper.scrollWidth));
paper.style.setProperty('--production-print-scale',scale);
}
function fitProduction(){
fitRotation();
stage.style.height=Math.max(160,innerHeight-document.querySelector('.toolbar').offsetHeight)+'px';
const mode=document.getElementById('production-zoom').value;
const width=(stage.clientWidth-24)/page.offsetWidth;
const scale=mode==='width'?width:mode==='page'?Math.min(width,(stage.clientHeight-24)/page.offsetHeight):Number(mode);
document.documentElement.style.setProperty('--production-scale',Math.max(.15,scale));
}
addEventListener('resize',fitProduction);fitProduction();
addEventListener('beforeprint',fitRotation);
if(document.fonts)document.fonts.ready.then(fitProduction);
</script></body></html>''')

