"""Print variable fields on preprinted two-column small-label stock."""

from html import escape


def generate_small_label_html(rows, *, paper_stock="a4_driver", selected_positions=None):
    if not rows:
        return ""
    margin = 0.6
    label_width = 6.3
    positions = list(range(10)) if selected_positions is None else sorted(set(selected_positions))
    if any(type(position) is not int or not 0 <= position < 10 for position in positions):
        raise ValueError("Small label positions must be integers from 0 to 9")
    if not positions:
        return ""
    sheets = []
    for start in range(0, len(rows), len(positions)):
        slots = []
        for index, row in zip(positions, rows[start:start + len(positions)]):
            top = round(0.25 + (index // 2) * 4.5, 3)
            left = round(margin + (index % 2) * (label_width + 0.3), 3)
            fields = []
            # Leave the printed captions, unit, checkboxes, and company block clear.
            for key, x, y, width in (("編號", 0.15, 0.3, 2.45),
                                      ("日期", 3.15, 0.3, 1.35),
                                      ("名稱", 0.65, 1.0, 4.8),
                                      ("比例", 2.2, 1.95, 1.45)):
                y = round(y + (0, 0.1, 0.3, 0.5, 0.6)[index // 2], 3)
                if key == "日期":
                    x = round(x - (0.3 if index % 2 == 1 else 0.2), 3)
                if key == "名稱" and index // 2 == 4:
                    y = round(y + 0.1, 3)
                value = str(row.get(key) or "").strip()
                if key == "比例" and value.lower().endswith("g/kg"):
                    value = value[:-4].strip()
                font_size = 12 if key in ("編號", "名稱") else 11
                fields.append(f'<div class="field" data-field="{key}" data-size="{font_size}" style="left:{x}cm;top:{y}cm;width:{width}cm">{escape(value)}</div>')
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
.field[data-size="12"] {{ font-size: 12pt; }}
.field[data-field="編號"] {{ font-weight: 700; }}
</style><script>
function fitLabelText() {{
 document.querySelectorAll('.field').forEach(field => {{
  field.style.fontSize = field.dataset.size + 'pt';
  if (field.scrollWidth > field.clientWidth) {{
   const size = parseFloat(getComputedStyle(field).fontSize);
   field.style.fontSize = (size * field.clientWidth / field.scrollWidth) + 'px';
  }}
 }});
}}
window.onload = async () => {{ await document.fonts.ready; fitLabelText(); window.print(); }};
window.addEventListener('beforeprint', fitLabelText);
</script></head><body>{''.join(sheets)}</body></html>'''
