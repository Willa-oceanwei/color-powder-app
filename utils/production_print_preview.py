"""Online A5 production printing, separate from the unchanged download document."""

import re

from .paper_preview import _PrintBody, theme_preview


PRODUCTION_A5_ACTION_STYLE = """<style>
.stApp .st-key-production_a5_create_actions :is([data-testid="stButton"],[data-testid="stDownloadButton"],[data-testid="stPopover"]) button {
background:#0b2f4a!important;color:#fff!important;border:1px solid #527086!important;border-radius:6px!important;
min-height:38px!important;padding:.4rem .75rem!important;font-size:1rem!important;font-weight:600!important;white-space:nowrap;
}
.stApp .st-key-production_a5_create_actions :is([data-testid="stButton"],[data-testid="stDownloadButton"],[data-testid="stPopover"]) button p {font-size:1rem!important;font-weight:600!important;}
.stApp .st-key-production_a5_create_actions :is([data-testid="stButton"],[data-testid="stDownloadButton"],[data-testid="stPopover"]) button:not(:disabled):is(:hover,:focus) {background:#124466!important;border-color:#65b5e2!important;color:#fff!important;}
.stApp .st-key-production_a5_create_actions :is([data-testid="stButton"],[data-testid="stDownloadButton"],[data-testid="stPopover"]) button:focus-visible {outline:2px solid #8cc8ea!important;outline-offset:2px;}
.stApp .st-key-production_a5_create_actions button:disabled {opacity:.45!important;}
body:has(.st-key-production_a5_create_actions) [data-testid="stPopoverBody"]:has(iframe) {width:min(960px,calc(100vw - 40px))!important;max-width:calc(100vw - 40px)!important;}
body:has(.st-key-production_a5_create_actions) [data-testid="stPopoverBody"]:has(iframe) :is([data-testid="stVerticalBlock"],[data-testid="stElementContainer"],.element-container) {width:100%!important;max-width:100%!important;}
body:has(.st-key-production_a5_create_actions) [data-testid="stPopoverBody"]:has(iframe) iframe {width:100%!important;}
@media(max-width:680px){
.stApp .st-key-production_a5_create_actions [data-testid="stHorizontalBlock"] {flex-wrap:wrap!important;gap:8px!important;}
.stApp .st-key-production_a5_create_actions [data-testid="stHorizontalBlock"]>:is([data-testid="stColumn"],[data-testid="column"]) {min-width:0!important;width:auto!important;}
.stApp .st-key-production_a5_create_actions [data-testid="stHorizontalBlock"]>:is([data-testid="stColumn"],[data-testid="column"]):nth-child(-n+2) {flex:1 1 calc(50% - 4px)!important;}
.stApp .st-key-production_a5_create_actions [data-testid="stHorizontalBlock"]>:is([data-testid="stColumn"],[data-testid="column"]):nth-child(3) {display:none!important;}
.stApp .st-key-production_a5_create_actions [data-testid="stHorizontalBlock"]>:is([data-testid="stColumn"],[data-testid="column"]):nth-child(4) {flex:0 0 auto!important;margin-left:auto;}
.stApp .st-key-production_a5_create_actions :is([data-testid="stDownloadButton"],[data-testid="stPopover"]) button p {font-size:.875rem!important;}
}
</style>"""


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
.stage{box-sizing:border-box;width:100%;max-width:900px;height:340px;overflow:auto;padding:8px;margin:0 auto}
.production-paper{box-sizing:border-box;width:190mm;min-height:128mm;margin:0 auto;padding:0;background:#fff;color:#000;zoom:var(--production-scale,1)}
}
@media print {
.toolbar{display:none!important}
.stage{height:auto!important;overflow:visible!important;padding:0!important}
.production-paper{width:auto!important;min-height:0!important;margin:0!important;padding:0!important;zoom:1!important;outline:none!important;box-shadow:none!important}
}
</style></head><body>
<div class="toolbar">
<button type="button" id="production-print" onclick="window.print()">列印 A5</button>
<label for="production-zoom">預覽縮放</label><select id="production-zoom" onchange="fitProduction()">
<option value="page" selected>完整內容</option><option value="width">符合寬度</option>
<option value="0.75">75%</option><option value="1">100%</option><option value="1.25">125%</option>
</select><span class="hint">標準原版面；列印比例請在列印視窗調整；原有 A5 下載仍可使用</span></div>
<div class="stage"><section class="production-paper paper">''' + "".join(body.parts) + '''</section></div>
<script>
const stage=document.querySelector('.stage'),paper=document.querySelector('.production-paper');
function fitProduction(){
stage.style.height=Math.max(160,innerHeight-document.querySelector('.toolbar').offsetHeight)+'px';
const mode=document.getElementById('production-zoom').value;
const width=(stage.clientWidth-24)/paper.offsetWidth;
const scale=mode==='width'?Math.min(1,width):mode==='page'?Math.min(1,width,(stage.clientHeight-24)/paper.offsetHeight):Number(mode);
document.documentElement.style.setProperty('--production-scale',Math.max(.15,scale));
}
addEventListener('resize',fitProduction);fitProduction();
</script></body></html>''')
