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
.production-page{position:relative;box-sizing:border-box;width:128mm;min-height:190mm;background:#fff;color:#000}
.production-paper{position:relative;box-sizing:border-box;width:100%;min-height:190mm;margin:0;padding:0;transform:none;font-size:calc(22px * var(--production-print-scale,1));line-height:1.4}
.production-paper .title{font-size:calc(24px * var(--production-print-scale,1))}
.production-paper .timestamp{font-size:calc(20px * var(--production-print-scale,1))}
.production-paper pre{margin-left:0;margin-right:0;font:inherit;white-space:pre-wrap;overflow-wrap:anywhere}
.production-paper pre>div{flex-wrap:wrap;font-size:calc(20px * var(--production-print-scale,1))!important}
.production-paper pre>div>div{flex:1 1 auto!important;overflow:visible!important;white-space:normal!important}
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
<div class="stage"><div class="production-page"><section class="production-paper paper">''' + "".join(body.parts) + '''</section></div></div>
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

