"""Extract 780 CMR Table 1604.11 from a saved Cornell LII HTML page.

Outputs:
- data/ma_780_cmr_table_1604_11.json  canonical metadata + records
- data/ma_780_cmr_table_1604_11.jsonl one record per line for retrieval
- data/ma_780_cmr_table_1604_11.csv   flat table for inspection
"""

from __future__ import annotations

import csv
import html
import json
import re
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_HTML = ROOT / "data" / "raw_780_cmr_chapter_16_cornell.html"
OUT_JSON = ROOT / "data" / "ma_780_cmr_table_1604_11.json"
OUT_JSONL = ROOT / "data" / "ma_780_cmr_table_1604_11.jsonl"
OUT_CSV = ROOT / "data" / "ma_780_cmr_table_1604_11.csv"

SOURCE_URL = "https://www.law.cornell.edu/regulations/massachusetts/780-CMR-CHAPTER-16"


def cell_text(cell_html: str) -> str:
    text = re.sub(r"<\s*sup\s*>(.*?)<\s*/\s*sup\s*>", r"^{\1}", cell_html, flags=re.I | re.S)
    text = re.sub(r"<\s*sub\s*>(.*?)<\s*/\s*sub\s*>", r"_\1", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_int(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    return int(value)


def parse_float(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    return float(value)


def note_refs(value: str) -> list[int]:
    return [int(match) for match in re.findall(r"\^\{(\d+)\}", value)]


def clean_note_refs(value: str) -> str:
    return re.sub(r"\^\{\d+\}", "", value).strip()


def parse_ground_snow(raw: str) -> tuple[int, int | None, list[int]]:
    refs = note_refs(raw)
    cleaned = clean_note_refs(raw)
    if "/" in cleaned:
        snow, elevation = cleaned.split("/", 1)
        return int(snow), int(elevation), refs
    return int(cleaned), None, refs


def extract_main_table(html_text: str) -> str:
    marker = "TABLE 1604.11 SNOW LOADS, WIND SPEEDS, AND SEISMIC PARAMETERS"
    marker_index = html_text.find(marker)
    if marker_index == -1:
        raise ValueError("Could not find Table 1604.11 marker.")
    table_start = html_text.find("<table", marker_index)
    table_end = html_text.find("</table>", table_start)
    if table_start == -1 or table_end == -1:
        raise ValueError("Could not find Table 1604.11 table element.")
    return html_text[table_start : table_end + len("</table>")]


def extract_records(table_html: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, flags=re.I | re.S)
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.I | re.S)
        values = [cell_text(cell) for cell in cells]
        if len(values) != 10:
            continue
        city_raw = values[0]
        if not city_raw or city_raw == "City/Town":
            continue
        if not re.match(r"^\d", values[1]):
            continue

        pg, mean_elevation_ft, pg_note_refs = parse_ground_snow(values[1])
        city_note_refs = note_refs(city_raw)
        all_note_refs = sorted(set(city_note_refs + pg_note_refs))
        city = clean_note_refs(city_raw)

        records.append(
            {
                "city_town": city,
                "ground_snow_load_pg_psf": pg,
                "ground_snow_load_mean_elevation_ft": mean_elevation_ft,
                "minimum_flat_roof_snow_load_pf_psf": parse_int(values[2]),
                "basic_wind_speed_v_mph": {
                    "risk_category_i": parse_int(values[3]),
                    "risk_category_ii": parse_int(values[4]),
                    "risk_category_iii": parse_int(values[5]),
                    "risk_category_iv": parse_int(values[6]),
                },
                "seismic_parameters_g": {
                    "ss": parse_float(values[7]),
                    "s1": parse_float(values[8]),
                    "pga": parse_float(values[9]),
                },
                "note_refs": all_note_refs,
                "source_table": "780 CMR Table 1604.11",
            }
        )
    return records


def dedupe_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    deduped: dict[str, dict[str, object]] = {}
    for record in records:
        key = str(record["city_town"]).casefold()
        if key in deduped:
            if deduped[key] != record:
                raise RuntimeError(f"Conflicting duplicate row for {record['city_town']}.")
            continue
        deduped[key] = record
    return list(deduped.values())


def write_outputs(records: list[dict[str, object]]) -> None:
    metadata = {
        "title": "780 CMR Table 1604.11 Snow Loads, Wind Speeds, and Seismic Parameters",
        "source_url": SOURCE_URL,
        "source_publisher": "Cornell Legal Information Institute",
        "source_regulation": "780 CMR Chapter 16 Structural Design",
        "scraped_on": date.today().isoformat(),
        "record_count": len(records),
        "units": {
            "ground_snow_load_pg_psf": "psf",
            "ground_snow_load_mean_elevation_ft": "ft",
            "minimum_flat_roof_snow_load_pf_psf": "psf",
            "basic_wind_speed_v_mph": "mph",
            "seismic_parameters_g": "g",
        },
        "notes": {
            "1": "The design flat roof snow load shall be the larger of the calculated flat roof snow load using Pg or the value of Pf listed in this table.",
            "2": "Special Wind Region. Local conditions may cause higher wind speeds than the tabulated values. See ASCE/SEI 7.",
            "3": "Increase Pg listed by 0.021 x (Site Elevation - Mean Elevation) when the Site Elevation exceeds the Mean Elevation.",
            "4": "Commentary: The basic wind speed, V, is equivalent to the formally defined ultimate wind speed, Vult, in 780 CMR. Vasd refers to allowable stress wind speeds.",
        },
        "llm_usage_hint": "Lookup by exact Massachusetts city_town. Use basic_wind_speed_v_mph for wind speed by risk category. If note_refs contains 2, warn that special wind region/local conditions may require ASCE/SEI 7 or AHJ confirmation.",
    }

    OUT_JSON.write_text(json.dumps({"metadata": metadata, "records": records}, indent=2) + "\n", encoding="utf-8")

    with OUT_JSONL.open("w", encoding="utf-8", newline="\n") as jsonl_file:
        for record in records:
            jsonl_file.write(json.dumps(record, separators=(",", ":")) + "\n")

    rows = []
    for record in records:
        winds = record["basic_wind_speed_v_mph"]
        seismic = record["seismic_parameters_g"]
        rows.append(
            {
                "city_town": record["city_town"],
                "pg_psf": record["ground_snow_load_pg_psf"],
                "pg_mean_elevation_ft": record["ground_snow_load_mean_elevation_ft"],
                "pf_psf": record["minimum_flat_roof_snow_load_pf_psf"],
                "wind_risk_i_mph": winds["risk_category_i"],
                "wind_risk_ii_mph": winds["risk_category_ii"],
                "wind_risk_iii_mph": winds["risk_category_iii"],
                "wind_risk_iv_mph": winds["risk_category_iv"],
                "ss_g": seismic["ss"],
                "s1_g": seismic["s1"],
                "pga_g": seismic["pga"],
                "note_refs": "|".join(str(ref) for ref in record["note_refs"]),
            }
        )

    with OUT_CSV.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    html_text = RAW_HTML.read_text(encoding="utf-8")
    table_html = extract_main_table(html_text)
    records = dedupe_records(extract_records(table_html))
    if len(records) < 300:
        raise RuntimeError(f"Expected hundreds of municipalities, parsed only {len(records)} records.")
    write_outputs(records)
    print(f"Wrote {len(records)} records:")
    print(f"- {OUT_JSON}")
    print(f"- {OUT_JSONL}")
    print(f"- {OUT_CSV}")


if __name__ == "__main__":
    main()
