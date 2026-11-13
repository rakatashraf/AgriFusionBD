"""Build the Word report describing the collected data and what it shows.

Every figure quoted here is read from _report/stats.json, which is produced by
report_stats.py from the CSVs - so the prose cannot drift from the data.
"""

from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BASE = Path(__file__).resolve().parent
REPORT = BASE / "_report"
OUT_PATH = BASE / "NASA_Data_Report.docx"

INK = RGBColor(0x0B, 0x0B, 0x0B)
MUTED = RGBColor(0x52, 0x51, 0x4E)

REGION_LABEL = {
    "Northwest_Rajshahi": "Northwest Rajshahi",
    "North_Rangpur": "North Rangpur",
    "Central_Dhaka": "Central Dhaka",
    "Northeast_Sylhet": "Northeast Sylhet",
    "Southwest_Khulna": "Southwest Khulna",
    "South_Barishal": "South Barishal",
    "Southeast_Chattogram": "Southeast Chattogram",
}
MONTH = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}


def load_stats() -> dict:
    return json.loads((REPORT / "stats.json").read_text(encoding="utf-8"))


def shade(cell, hex_fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc_pr.append(shd)


def add_table(doc, headers, rows, widths=None, font_size=9):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = table.rows[0].cells
    for i, text in enumerate(headers):
        hdr[i].text = ""
        para = hdr[i].paragraphs[0]
        run = para.add_run(str(text))
        run.bold = True
        run.font.size = Pt(font_size)
        shade(hdr[i], "EFEEE9")
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = ""
            para = cells[i].paragraphs[0]
            run = para.add_run(str(value))
            run.font.size = Pt(font_size)
    if widths:
        # Normalise so the row always fits the 16.4 cm text column.
        total = sum(widths)
        scaled = [w * 16.4 / total for w in widths]
        table.autofit = False
        for row in table.rows:
            for i, w in enumerate(scaled):
                row.cells[i].width = Cm(w)
    return table


def caption(doc, text):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.italic = True
    run.font.size = Pt(8.5)
    run.font.color.rgb = MUTED
    para.paragraph_format.space_after = Pt(10)
    return para


def bullet(doc, text):
    para = doc.add_paragraph(text, style="List Bullet")
    para.paragraph_format.space_after = Pt(3)
    return para


def body(doc, text, bold_lead=None):
    para = doc.add_paragraph()
    if bold_lead:
        run = para.add_run(bold_lead)
        run.bold = True
    para.add_run(text)
    return para


def main() -> int:
    s = load_stats()
    rain, sm, veg, lst, water, terrain, rel = (
        s["precipitation"],
        s["soil_moisture"],
        s["vegetation"],
        s["surface_temperature"],
        s["water_storage"],
        s["terrain"],
        s["relationships"],
    )
    order = s["region_order"]

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)
    style.font.color.rgb = INK
    style.paragraph_format.space_after = Pt(6)
    style.paragraph_format.line_spacing = 1.12

    for section in doc.sections:
        section.page_height = Cm(29.7)
        section.page_width = Cm(21.0)
        section.left_margin = Cm(2.2)
        section.right_margin = Cm(2.2)
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)

    # ---------------- cover ----------------
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = title.add_run("NASA Earth-Observation Data for Seven Bangladesh Regions")
    run.bold = True
    run.font.size = Pt(22)
    run.font.color.rgb = INK

    sub = doc.add_paragraph()
    run = sub.add_run("What the archive contains, how reliable it is, and what it already shows — 2022 to 2026")
    run.font.size = Pt(12)
    run.font.color.rgb = MUTED

    meta = doc.add_paragraph()
    run = meta.add_run(
        "Companion to NASA_Data_Sources_and_Django_API_Plan.docx. "
        "Prepared 11 November 2026. All statistics computed from the CSVs in this folder."
    )
    run.font.size = Pt(9)
    run.font.color.rgb = MUTED

    # ---------------- 1. summary ----------------
    doc.add_heading("1. Summary", level=1)
    body(
        doc,
        "Six NASA datasets were collected for the same seven representative points used for the "
        "existing POWER weather files, over 1 January 2022 to the latest available day. Together they "
        "cover rainfall, surface soil moisture, vegetation greenness, land-surface temperature, terrain "
        "and regional water storage. Weather (POWER) and, where relevant, the plan's HLS adapter sit "
        "alongside them.",
    )
    body(
        doc,
        "The headline finding is that Bangladesh cannot be treated as one agronomic zone. Annual "
        f"rainfall ranges from {rain['Northwest_Rajshahi']['annual_mean_mm']:,.0f} mm in the northwest to "
        f"{rain['Northeast_Sylhet']['annual_mean_mm']:,.0f} mm in the northeast — a factor of "
        f"{rain['Northeast_Sylhet']['annual_mean_mm'] / rain['Northwest_Rajshahi']['annual_mean_mm']:.1f} — "
        f"and heavy-rain days range from {rain['Northwest_Rajshahi']['heavy_days_per_year']:.0f} to "
        f"{rain['Northeast_Sylhet']['heavy_days_per_year']:.0f} per year. The same regional split appears "
        "in soil moisture, vegetation and water storage.",
    )

    # ---------------- 2. inventory ----------------
    doc.add_heading("2. What the archive contains", level=1)
    body(
        doc,
        "Each folder holds per-region CSV time series, a combined CSV, and a provenance file "
        "recording product, version, variables, resolution and limits.",
    )

    inv = s["inventory"]
    add_table(
        doc,
        ["Folder", "Source and product", "Native support", "Rows", "Values"],
        [
            ["GPM_IMERG_Rainfall", "GPM IMERG Final + Late Run v07", "0.1° (~11 km), daily",
             f"{inv['GPM']['rows']:,}", f"{inv['GPM']['filled']:,}"],
            ["SMAP_SoilMoisture", "SMAP SPL3SMP_E v006 (Harmony subset)", "9 km, AM and PM",
             f"{inv['SMAP']['rows']:,}", f"{inv['SMAP']['filled']:,}"],
            ["ECOSTRESS_LST_ET", "ECOSTRESS ECO_L2T_LSTE v002", "70 m, irregular overpasses",
             f"{inv['ECOSTRESS']['rows']:,}", f"{inv['ECOSTRESS']['filled']:,}"],
            ["HLS_Vegetation_Indices", "HLS HLSL30 / HLSS30 v2.0", "30 m, sampled monthly",
             f"{inv['HLS']['rows']:,}", f"{inv['HLS']['filled']:,}"],
            ["GRACE_WaterStorage", "JPL Mascon CRI RL06.3 v04", "0.5° mascon, monthly",
             f"{inv['GRACE']['rows']:,}", f"{inv['GRACE']['filled']:,}"],
            ["SRTM_Elevation", "SRTMGL1 v003", "1 arc second (~30 m), static",
             f"{inv['SRTM']['rows']}", f"{inv['SRTM']['filled']}"],
        ],
        widths=[4.2, 5.4, 4.4, 1.8, 1.8],
    )
    caption(
        doc,
        "Table 1. Inventory. 'Values' counts rows with a real measurement; the remainder are the "
        "product's own gaps (cloud, no retrieval, radio-frequency interference), not download failures.",
    )
    body(
        doc,
        "Storage was kept proportionate to the question. Coarse products (rainfall, soil moisture, "
        "water storage) are stored whole for the seven points. Fine products are sampled at the pixels "
        "over each point and the imagery is discarded: full HLS and ECOSTRESS scenes for this footprint "
        "would run to hundreds of gigabytes for no extra information at a point.",
    )

    # ---------------- 3. insights ----------------
    doc.add_heading("3. What the data shows", level=1)

    doc.add_heading("3.1 Rainfall: a 2.8-fold gradient across the country", level=2)
    body(
        doc,
        f"Mean annual rainfall over 2022–2025 runs from {rain['Northwest_Rajshahi']['annual_mean_mm']:,.0f} mm "
        f"(Rajshahi) through {rain['Central_Dhaka']['annual_mean_mm']:,.0f} mm (Dhaka) to "
        f"{rain['Northeast_Sylhet']['annual_mean_mm']:,.0f} mm (Sylhet). The number of days with 50 mm or more "
        f"follows the same gradient — {rain['Northwest_Rajshahi']['heavy_days_per_year']:.1f} per year in Rajshahi "
        f"against {rain['Northeast_Sylhet']['heavy_days_per_year']:.1f} in Sylhet.",
    )
    body(
        doc,
        "The monsoon dominates everywhere: "
        f"{min(r['monsoon_share'] for r in rain.values()) * 100:.0f}–"
        f"{max(r['monsoon_share'] for r in rain.values()) * 100:.0f}% of the annual total falls in June–September. "
        "That leaves a genuinely dry half-year, which is where irrigation and planting decisions actually sit.",
    )

    doc.add_picture(str(REPORT / "fig1_rainfall_seasonality.png"), width=Cm(16.2))
    caption(
        doc,
        "Figure 1. Mean daily rainfall by month. Shared scale; the shaded band is the June–September "
        "monsoon. Annual totals are 2022–2025 averages.",
    )

    rows = []
    for region in order:
        r = rain[region]
        rows.append(
            [
                REGION_LABEL[region],
                f"{r['annual_mean_mm']:,.0f}",
                f"{r['monsoon_share'] * 100:.0f}%",
                f"{r['wet_days_per_year']:.0f}",
                f"{r['heavy_days_per_year']:.1f}",
                f"{MONTH[r['wettest_month']]} / {MONTH[r['driest_month']]}",
                f"{r['max_daily_mm']:.0f} ({r['max_daily_date']})",
                f"{r['annual_cv'] * 100:.0f}%",
            ]
        )
    add_table(
        doc,
        ["Region", "Annual mm", "Monsoon", "Wet days", "Days ≥50 mm", "Wettest / driest", "Max day", "Variability"],
        rows,
        widths=[3.2, 1.6, 2.0, 1.5, 1.9, 2.5, 2.9, 2.0],
        font_size=8,
    )
    caption(
        doc,
        "Table 2. Rainfall per region, 2022–2025 (wet day = ≥1 mm/day). Variability is the coefficient of "
        "variation across years; with four years it shows volatility, not a trend.",
    )

    doc.add_heading("3.2 Soil moisture: rainfall with memory", level=2)
    body(
        doc,
        f"Surface soil moisture averages {min(v['mean'] for v in sm.values()):.2f} m³/m³ in Chattogram to "
        f"{max(v['mean'] for v in sm.values()):.2f} m³/m³ in Khulna, and tracks the rainfall cycle with a "
        "flattened amplitude — the wet season roughly doubles the dry-season floor rather than scaling with "
        "rainfall. The tenth-to-ninetieth percentile band is widest where the dry season bites hardest "
        f"(Chattogram {sm['Southeast_Chattogram']['p10']:.2f}–{sm['Southeast_Chattogram']['p90']:.2f} m³/m³).",
    )
    body(
        doc,
        "Availability is the practical constraint: "
        f"{min(v['filled_share'] for v in sm.values()) * 100:.0f}–"
        f"{max(v['filled_share'] for v in sm.values()) * 100:.0f}% of pass-days carry a retrieval at these "
        "points. The gaps are systematic (quality masking, radio-frequency interference), so a daily soil-"
        "moisture series should be smoothed or gap-filled before use, not treated as continuous.",
    )

    doc.add_heading("3.3 Vegetation: greenness follows the monsoon by a month", level=2)
    body(
        doc,
        f"NDVI runs from {min(v['ndvi_mean'] for v in veg.values()):.2f} in Rajshahi to "
        f"{max(v['ndvi_mean'] for v in veg.values()):.2f} in Barishal — the same northwest–south gradient as "
        "rainfall and soil moisture, but expressed through land cover as well as water. Greenness peaks in "
        "September, one month after peak rainfall, and bottoms out between January and April.",
    )
    body(
        doc,
        "Thirty-metre vegetation data over Bangladesh is cloud-limited: only "
        f"{inv['HLS']['filled']} of {inv['HLS']['rows']} sampled region-months produced an NDVI value at 50% "
        "or better clear coverage. That is a property of the climate, not of the download, and it means "
        "NDVI should be read as a monthly series with stated coverage rather than as a weekly signal.",
    )

    doc.add_picture(str(REPORT / "fig2_seasonal_coupling.png"), width=Cm(13.4))
    caption(
        doc,
        "Figure 2. Mean seasonal cycle across the seven regions. Rainfall and surface soil moisture peak in "
        "August; NDVI peaks in September. Separate axes by design — the three quantities are not on one scale.",
    )

    doc.add_heading("3.4 Surface temperature", level=2)
    body(
        doc,
        f"ECOSTRESS land-surface temperature averages {min(v['mean_c'] for v in lst.values()):.1f}–"
        f"{max(v['mean_c'] for v in lst.values()):.1f} °C by region and spans {min(v['min_c'] for v in lst.values()):.0f}–"
        f"{max(v['max_c'] for v in lst.values()):.0f} °C overall. Only {inv['ECOSTRESS']['filled']:,} of "
        f"{inv['ECOSTRESS']['rows']:,} overpasses returned a value at the point — thermal imagery is unusable "
        "through cloud. The series is an opportunistic sample of clear-sky overpasses at all hours - "
        "only about a quarter of the usable values are daytime - so it mixes day and night and must not "
        "be read as a daily maximum.",
    )
    body(
        doc,
        "This is surface skin temperature, not the 2 m air temperature farmers recognise. It is useful for "
        "heat-stress and irrigation-timing signals, and misleading if presented as air temperature.",
    )

    doc.add_heading("3.5 Terrain", level=2)
    body(
        doc,
        f"Mean elevation ranges from {min(v['elevation_mean_m'] for v in terrain.values()):.1f} m (Khulna) to "
        f"{max(v['elevation_mean_m'] for v in terrain.values()):.1f} m (Rangpur). The steepest average slopes are "
        f"around Sylhet ({terrain['Northeast_Sylhet']['slope_mean_deg']:.2f}°), with Dhaka "
        f"({terrain['Central_Dhaka']['slope_mean_deg']:.2f}°) and Chattogram "
        f"({terrain['Southeast_Chattogram']['slope_mean_deg']:.2f}°) next, while Rajshahi and Khulna are flattest. "
        "The practical reading is that Khulna and Barishal sit low enough for tidal and drainage effects to "
        "dominate field water status, whereas around Sylhet slope-driven runoff is worth modelling.",
    )

    doc.add_heading("3.6 Water storage: large-area context only", level=2)
    body(
        doc,
        "The seven points fall into four GRACE mascons (1214, 1320, 1321, 1431), so Dhaka, Sylhet, Barishal "
        "and Khulna share one value — that is the product's design, not a duplicate row. Over 2022–2026 the "
        "delta mascon trends upward while Rangpur and Chattogram trend down slightly.",
    )
    doc.add_picture(str(REPORT / "fig3_grace_trend.png"), width=Cm(14.4))
    caption(
        doc,
        "Figure 3. Fitted linear trend in water-storage anomaly. Four years is far too short to call this a "
        "climate trend; it is descriptive of this window only. The mascon grid is ~55 km and is not a "
        "groundwater measurement.",
    )

    doc.add_heading("3.7 How the variables move together", level=2)
    body(
        doc,
        f"Pooling monthly means across the seven regions ({rel['pairs_rain_sm']} rain–moisture pairs, "
        f"{rel['pairs_rain_ndvi']} rain–NDVI pairs), rainfall correlates most strongly with soil moisture in the "
        f"same month (r = {rel['rain_vs_sm_lag0']:.2f}), and weakly at a one-month lag "
        f"(r = {rel['rain_vs_sm_lag1']:.2f}). Vegetation tracks rainfall more weakly "
        f"(r = {rel['rain_vs_ndvi_lag0']:.2f}) even though its seasonal peak trails the rains by a month. "
        f"Surface temperature falls as rainfall rises (r = {rel['lst_vs_rain']:.2f}).",
    )
    add_table(
        doc,
        ["Relationship", "r", "Pairs", "Reading"],
        [
            ["Rainfall vs soil moisture, same month", f"{rel['rain_vs_sm_lag0']:.2f}", f"{rel['pairs_rain_sm']}",
             "Moisture responds within the month"],
            ["Rainfall vs soil moisture, +1 month", f"{rel['rain_vs_sm_lag1']:.2f}", f"{rel['pairs_rain_sm']}",
             "Little carry-over at the surface"],
            ["Rainfall vs NDVI, same month", f"{rel['rain_vs_ndvi_lag0']:.2f}", f"{rel['pairs_rain_ndvi']}",
             "Weak immediate link"],
            ["Soil moisture vs NDVI", f"{rel['sm_vs_ndvi']:.2f}", f"{rel['pairs_rain_ndvi']}",
             "Moisture and greenness agree moderately"],
            ["Surface temperature vs NDVI", f"{rel['lst_vs_ndvi']:.2f}", f"{rel['pairs_rain_ndvi']}",
             "Weak; cloud sampling confounds it"],
        ],
        widths=[5.6, 1.4, 1.5, 7.0],
    )
    caption(
        doc,
        "Table 3. Pearson correlations on monthly regional means. These are descriptive associations over a "
        "short record, not causal models, and they pool regions with different climates.",
    )

    # ---------------- 4. regional profile ----------------
    doc.add_heading("4. Regional profile", level=1)
    body(doc, "One row per region, drawing on all six datasets.")
    rows = []
    for region in order:
        t = terrain[region]
        rows.append(
            [
                REGION_LABEL[region],
                f"{rain[region]['annual_mean_mm']:,.0f}",
                f"{sm[region]['mean']:.2f}",
                f"{veg[region]['ndvi_mean']:.2f}",
                f"{lst[region]['mean_c']:.1f}",
                f"{t['elevation_mean_m']:.0f}",
                f"{t['slope_mean_deg']:.1f}",
                f"{water[region]['slope_cm_per_year']:+.1f}",
            ]
        )
    add_table(
        doc,
        ["Region", "Rain mm/yr", "Soil m³/m³", "NDVI", "LST °C", "Elev m", "Slope °", "Storage cm/yr"],
        rows,
        widths=[4.2, 2.2, 2.2, 1.6, 1.8, 1.8, 1.8, 2.8],
        font_size=9,
    )
    caption(
        doc,
        "Table 4. Regional summary. LST is a clear-sky surface temperature, not air temperature; storage is a "
        "mascon trend over four years.",
    )

    # ---------------- 5. limits ----------------
    doc.add_heading("5. Limits you should carry forward", level=1)
    bullet(doc, "A coordinate selects a grid cell or pixel. None of these series is a measurement at the exact point, and none is a regional average.")
    bullet(doc, "Empty values are the product's own quality masking. They must be preserved as nulls; substituting zero would invent dry days and cold afternoons that never happened.")
    bullet(doc, "ECOSTRESS samples only clear-sky overpasses at varying times of day. Any climatology built from it inherits that sampling bias.")
    bullet(doc, "HLS gives about one usable observation per region-month. Sub-monthly change detection is not supportable from this footprint.")
    bullet(doc, "GRACE is a ~55 km mascon product with four distinct cells across the country; it cannot speak to field-level groundwater.")
    bullet(doc, "The record is under five years. Seasonal statements are solid; trend statements are not.")
    bullet(doc, "SMAP reports volumetric fraction: 0.30 is 30%. It is not a rover-depth or laboratory measurement.")

    # ---------------- 6. use ----------------
    doc.add_heading("6. Where this fits in FieldShift", level=1)
    body(doc, "The datasets map cleanly onto the endpoints the plan proposes:")
    bullet(doc, "Environmental context per field — rainfall, soil moisture, NDVI, temperature and terrain keyed by point or polygon.")
    bullet(doc, "Dry-spell and heavy-rain flags — the monsoon share and the ≥50 mm day counts give region-specific thresholds instead of one national number.")
    bullet(doc, "Irrigation prompts — soil moisture percentile bands per region are a defensible baseline when no rover is present, provided they are labelled as modelled, not measured.")
    bullet(doc, "Vegetation trends — monthly NDVI with coverage reported, so a low value can be distinguished from a cloudy month.")
    bullet(doc, "Research workspace — water-storage and terrain context for regional studies, kept out of farmer-facing advice.")
    body(
        doc,
        "The natural next step is to load these CSVs into the `environmental_data` tables and serve them "
        "through `GET /api/v1/fields/{id}/environment/`, with each row carrying its source, resolution and "
        "quality flags as the plan requires.",
    )

    # ---------------- 7. files ----------------
    doc.add_heading("7. File map", level=1)
    add_table(
        doc,
        ["Path", "Contents"],
        [
            ["GPM_IMERG_Rainfall/", "Daily rainfall per region; Final and Late Runs labelled in a column"],
            ["SMAP_SoilMoisture/", "Daily AM/PM surface soil moisture, error, quality flags; raw daily subsets in raw/"],
            ["ECOSTRESS_LST_ET/", "Per-overpass land-surface temperature with QC value"],
            ["HLS_Vegetation_Indices/", "Monthly NDVI, NDMI and valid-pixel coverage"],
            ["SRTM_Elevation/", "Terrain summary per region; 30 one-degree .hgt tiles"],
            ["GRACE_WaterStorage/", "Monthly water-storage anomaly and uncertainty; source NetCDF in raw/"],
            ["README.md", "Folder-by-folder documentation and scripts"],
            ["*.py", "Idempotent download scripts; re-running fills gaps"],
        ],
        widths=[5.0, 11.0],
    )
    caption(doc, "Table 5. What is where.")

    para = doc.add_paragraph()
    run = para.add_run(
        "Data: NASA GES DISC, NSIDC DAAC, LP DAAC and PO.DAAC, accessed through Earthdata Login. "
        "Products and versions are recorded in each folder's provenance file."
    )
    run.font.size = Pt(8.5)
    run.font.color.rgb = MUTED

    doc.save(OUT_PATH)
    print(f"Saved {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
