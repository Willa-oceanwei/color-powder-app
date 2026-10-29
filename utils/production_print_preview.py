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
@media screen {
body{margin:0;transform:none;background:#101820}
.toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:8px}
.toolbar button,.toolbar select{font:16px Arial,"Microsoft JhengHei",sans-serif;min-height:38px;padding:5px 10px}
.toolbar .hint{font:13px "Microsoft JhengHei",sans-serif}
.stage{height:340px;overflow:auto;padding:8px}
.production-paper{box-sizing:border-box;width:190mm;min-height:128mm;margin:0 auto;padding:0;background:#fff;color:#000;zoom:var(--production-scale,1)}
}
@media print {
.toolbar{display:none!important}
.stage{height:auto!important;overflow:visible!important;padding:0!important}
.production-paper{width:auto!important;min-height:0!important;margin:0!important;padding:0!important;zoom:1!important;outline:none!important;box-shadow:none!important}
}
</style></head><body>
<div class="toolbar">
<button type="button" id="production-print" onclick="window.print()">列印 A5（位置測試）</button>
<label for="production-zoom">縮放</label><select id="production-zoom" onchange="fitProduction()">
<option value="page" selected>完整內容</option><option value="width">符合寬度</option>
<option value="0.75">75%</option><option value="1">100%</option><option value="1.25">125%</option>
</select><span class="hint">原有 A5 下載仍可使用</span></div>
<div class="stage"><section class="production-paper paper">''' + "".join(body.parts) + '''</section></div>
<script>
const stage=document.querySelector('.stage'),paper=document.querySelector('.production-paper');
function fitProduction(){
stage.style.height=Math.max(160,innerHeight-document.querySelector('.toolbar').offsetHeight)+'px';
const mode=document.getElementById('production-zoom').value;
const width=(stage.clientWidth-24)/paper.offsetWidth;
const scale=mode==='width'?width:mode==='page'?Math.min(width,(stage.clientHeight-24)/paper.offsetHeight):Number(mode);
document.documentElement.style.setProperty('--production-scale',Math.max(.15,scale));
}
addEventListener('resize',fitProduction);fitProduction();
</script></body></html>''')
