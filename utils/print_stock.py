"""Physical cut-sheet geometry, independent of accounting calculations."""

TRIPLICATE_LABEL = "三聯紙 240 × 140 mm"


def stock_geometry(rotation=0, hole_margin=12.5, *, height=140, offset=0, preserve_holes=True):
    if rotation not in (0, 90) or not 0 <= hole_margin <= 25:
        raise ValueError("Invalid feed settings")
    if height not in (140, 280) or not -25 <= offset <= 25:
        raise ValueError("Invalid stock dimensions")
    source_height = 148 if height == 140 else 297
    scale = min((240 - 2 * hole_margin) / 210, height / source_height)
    x, y = (240 - 210 * scale) / 2 + offset, (height - source_height * scale) / 2
    if offset < 0 and preserve_holes:
        x = max(x, hole_margin - 7.5 * scale)
    return (240, height, x, y, scale) if rotation == 0 else (height, 240, height - y, x, scale)


def stock_sheet(section, *, active=True):
    return '<div class="stock-page' + (' active' if active else '') + '">' + section + '</div>'


def stock_style(rotation=0, hole_margin=12.5, *, paginated=False, stock_height=140, offset=0, a4_driver=False):
    # A4 driver calibration is independent of the physical paper's hole strips.
    width, height, x, y, scale = stock_geometry(rotation, hole_margin, height=stock_height, offset=offset, preserve_holes=not a4_driver)
    display = "none" if paginated else "block"
    zoom = "--preview-zoom" if paginated else "--shipment-preview-zoom"
    page_size = "A4 portrait" if a4_driver else f"{width}mm {height}mm"
    print_size = "width:210mm;height:297mm;" if a4_driver else ""
    return f'''@page{{size:{page_size};margin:0}}
.stock-page{{display:{display};width:{width}mm;height:{height}mm;position:relative;background:#fff;margin:10px auto;break-after:page;overflow:hidden;page:auto}}
.stock-page.active{{display:block}}
.stock-page>.sheet{{display:block!important;position:absolute;margin:0!important;zoom:1!important;transform-origin:0 0;transform:translate({x:.6f}mm,{y:.6f}mm) rotate({rotation}deg) scale({scale:.9f});break-after:auto!important;page-break-after:auto!important;page:auto!important}}
@media screen{{.stock-page{{zoom:var({zoom},.86)}}}}
@media print{{.stock-page{{{print_size}display:block!important;margin:0;zoom:1;page-break-after:always}}.stock-page:last-child{{break-after:auto;page-break-after:auto}}}}
'''
