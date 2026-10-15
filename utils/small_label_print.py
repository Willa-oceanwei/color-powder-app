"""Print variable fields on preprinted two-column small-label stock."""

from html import escape


def generate_small_label_html(rows, *, paper_stock="custom"):
    if not rows:
        return ""
    margin = 0.6
    label_width = 6.3
    sheets = []
    for start in range(0, len(rows), 10):
        slots = []
        for index, row in enumerate(rows[start:start + 10]):
            top = round(0.25 + (index // 2) * 4.5, 3)
            left = round(margin + (index % 2) * (label_width + 0.3), 3)
            fields = []
            # Leave the printed captions, unit, checkboxes, and company block clear.
            for key, x, y, width in (("編號", 0.15, 0.3, 2.45),
                                      ("日期", 3.15, 0.3, 1.35),
                                      ("名稱", 1.15, 1.0, 4.8),
                                      ("比例", 2.2, 1.95, 1.45)):
                if index // 2 >= 2:
                    y = round(y + 0.3, 3)
                value = str(row.get(key) or "").strip()
                if key == "比例" and value.lower().endswith("g/kg"):
                    value = value[:-4].strip()
                fields.append(f'<div class="field" style="left:{x}cm;top:{y}cm;width:{width}cm">{escape(value)}</div>')
            slots.append(f'<div class="label-slot" style="left:{left}cm;top:{top}cm;width:{label_width}cm">{"".join(fields)}</div>')
        sheets.append(f'<div class="sheet">{"".join(slots)}</div>')
    size = "A4" if paper_stock == "a4_driver" else "14cm 23cm"
    sheet_width, sheet_height = (21, 29.7) if paper_stock == "a4_driver" else (14, 23)
    return f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<title>生產單小標籤列印</title><style>
@page {{ size: {size}; margin: 0; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; padding: 0; }}
.sheet {{ position: relative; width: {sheet_width}cm; height: {sheet_height}cm;
overflow: hidden; break-after: page; page-break-after: always; break-inside: avoid-page; }}
.sheet:last-child {{ break-after: auto; page-break-after: auto; }}
.label-slot {{ position: absolute; height: 4.5cm; }}
.field {{ position: absolute; white-space: nowrap; line-height: 1;
font: 11pt Arial, "Microsoft JhengHei", sans-serif; }}
</style><script>
function fitLabelText() {{
 document.querySelectorAll('.field').forEach(field => {{
  field.style.fontSize = '11pt';
  if (field.scrollWidth > field.clientWidth) {{
   const size = parseFloat(getComputedStyle(field).fontSize);
   field.style.fontSize = (size * field.clientWidth / field.scrollWidth) + 'px';
  }}
 }});
}}
window.onload = async () => {{ await document.fonts.ready; fitLabelText(); window.print(); }};
window.addEventListener('beforeprint', fitLabelText);
</script></head><body>{''.join(sheets)}</body></html>'''
