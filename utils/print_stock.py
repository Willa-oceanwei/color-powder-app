"""Physical cut-sheet geometry, independent of accounting calculations."""

TRIPLICATE_LABEL = "三聯紙 240 × 140 mm"


def stock_geometry(rotation=0, hole_margin=12.5):
    if rotation not in (0, 90) or not 0 <= hole_margin <= 25:
        raise ValueError("Invalid feed settings")
    scale = min((240 - 2 * hole_margin) / 210, 140 / 148)
    x, y = (240 - 210 * scale) / 2, (140 - 148 * scale) / 2
    return (240, 140, x, y, scale) if rotation == 0 else (140, 240, 140 - y, x, scale)


def stock_sheet(section, *, active=True):
    return '<div class="stock-page' + (' active' if active else '') + '">' + section + '</div>'


def stock_style(rotation=0, hole_margin=12.5, *, paginated=False):
    width, height, x, y, scale = stock_geometry(rotation, hole_margin)
    display = "none" if paginated else "block"
    zoom = "--preview-zoom" if paginated else "--shipment-preview-zoom"
    return f'''@page{{size:{width}mm {height}mm;margin:0}}
.stock-page{{display:{display};width:{width}mm;height:{height}mm;position:relative;background:#fff;margin:10px auto;break-after:page;overflow:hidden;page:auto}}
.stock-page.active{{display:block}}
.stock-page>.sheet{{display:block!important;position:absolute;margin:0!important;zoom:1!important;transform-origin:0 0;transform:translate({x:.6f}mm,{y:.6f}mm) rotate({rotation}deg) scale({scale:.9f});break-after:auto!important;page-break-after:auto!important;page:auto!important}}
@media screen{{.stock-page{{zoom:var({zoom},.86)}}}}
@media print{{.stock-page{{display:block!important;margin:0;zoom:1;page-break-after:always}}.stock-page:last-child{{break-after:auto;page-break-after:auto}}}}
'''
