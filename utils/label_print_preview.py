"""Show generated label sheets online with an explicit print action."""

from .paper_preview import theme_preview


def build_label_print_preview(document):
    """Keep the label layout and fitting scripts, replacing automatic printing."""
    document = document.replace("window.print();", "")
    document = document.replace("</head>", """
<style>
@media screen {
body{margin:0}
.label-stage{height:350px;overflow:auto;padding:12px}
.label-pages{width:max-content;margin:0 auto;zoom:var(--label-scale,1)}
.label-pages .sheet{margin-bottom:12px}
}
@media print {
.toolbar{display:none!important}
.label-stage{height:auto!important;overflow:visible!important;padding:0!important}
.label-pages{width:auto!important;margin:0!important;zoom:1!important}
.label-pages .sheet{margin:0!important;outline:none!important;box-shadow:none!important}
}
</style>
</head>""", 1)
    document = document.replace("<body>", """<body>
<div class="toolbar">
<button type="button" class="print-action" onclick="window.print()">列印標籤</button>
<label for="label-zoom">預覽縮放</label>
<select id="label-zoom" onchange="fitLabelPreview()">
<option value="width">符合寬度</option><option value="1">100%</option>
</select>
<span>列印比例請選 100%，並使用已選定的紙張尺寸。</span>
</div>
<div class="label-stage"><div class="label-pages">""", 1)
    document = document.replace("</body>", """
</div></div>
<script>
function fitLabelPreview(){
 const stage=document.querySelector('.label-stage');
 const sheet=document.querySelector('.sheet');
 if(!sheet)return;
 const mode=document.getElementById('label-zoom').value;
 const scale=mode==='width'?Math.min(1,(stage.clientWidth-24)/sheet.offsetWidth):1;
 document.documentElement.style.setProperty('--label-scale',Math.max(.1,scale));
}
addEventListener('load',async()=>{await document.fonts.ready;fitLabelPreview();});
addEventListener('resize',fitLabelPreview);
</script>
</body>""", 1)
    return theme_preview(document)
