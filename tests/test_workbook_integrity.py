"""Structural tests for the Tableau workbook.

Tableau Desktop is not available in CI, so these tests do what a reviewer would otherwise
have to do by hand: open the .twb, follow every reference in it, and check the thing it
points at exists. They catch the failure that matters most in a versioned workbook - a
column renamed in SQL leaving a dead reference behind, which in Tableau shows up as a
red pill on a dashboard long after the commit that caused it.
"""

from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "tableau" / "retail_margin_intelligence.twb"

FIELD_TOKEN = re.compile(r"\[([^\]]+)\]")
# Names that are legitimately not columns of the datasource being checked.
EXTERNAL = {"Parameters", "Parameter 1"}


@pytest.fixture(scope="module")
def workbook() -> ET.Element:
    assert WORKBOOK.exists(), f"{WORKBOOK.name} missing - run python tools/generate_workbook.py"
    return ET.parse(WORKBOOK).getroot()


@pytest.fixture(scope="module")
def datasources(workbook) -> dict[str, ET.Element]:
    return {ds.get("name"): ds for ds in workbook.find("datasources")}


def csv_header(datasource: ET.Element) -> list[str] | None:
    """Resolve a datasource's text connection to the CSV it reads, and return its header."""
    connection = datasource.find(".//connection[@class='textscan']")
    if connection is None:
        return None
    path = (WORKBOOK.parent / connection.get("directory") / connection.get("filename")).resolve()
    assert path.exists(), f"{datasource.get('name')} points at missing file {path}"
    with path.open(encoding="utf-8", newline="") as fh:
        return next(csv.reader(fh))


def declared_fields(datasource: ET.Element) -> set[str]:
    """Every name a formula in this datasource is allowed to reference."""
    names = {r.findtext("remote-name") for r in datasource.findall(".//metadata-record[@class='column']")}
    names |= {c.get("name").strip("[]") for c in datasource.findall("column")}
    names |= {c.get("caption") for c in datasource.findall("column") if c.get("caption")}
    return {n for n in names if n}


# ------------------------------------------------------------------------ connections ---

def test_workbook_parses_and_has_content(workbook):
    assert len(workbook.find("datasources")) >= 2
    assert len(workbook.find("worksheets")) == 10
    assert len(workbook.find("dashboards")) == 4


def test_every_connection_resolves_to_a_published_mart(datasources):
    connected = [ds for ds in datasources.values() if ds.find(".//connection[@class='textscan']") is not None]
    assert len(connected) == 7
    for ds in connected:
        assert csv_header(ds), f"{ds.get('name')} resolved to an empty file"


def test_column_metadata_matches_the_csv_header(datasources):
    """Ordinals must line up, or Tableau reads the wrong column under the right name."""
    for name, ds in datasources.items():
        header = csv_header(ds)
        if header is None:
            continue
        records = ds.findall(".//metadata-record[@class='column']")
        assert len(records) == len(header), f"{name}: {len(records)} columns declared, {len(header)} in CSV"
        for record in records:
            ordinal = int(record.findtext("ordinal"))
            remote = record.findtext("remote-name")
            assert header[ordinal] == remote, f"{name}: ordinal {ordinal} is '{header[ordinal]}', not '{remote}'"


# ------------------------------------------------------------------------ calculations ---

def test_calculated_fields_only_reference_fields_that_exist(datasources):
    for name, ds in datasources.items():
        available = declared_fields(ds) | EXTERNAL
        for column in ds.findall("column"):
            calculation = column.find("calculation")
            if calculation is None or not calculation.get("formula"):
                continue
            for token in FIELD_TOKEN.findall(calculation.get("formula")):
                assert token in available, (
                    f"{name}.{column.get('caption') or column.get('name')} references [{token}], "
                    f"which is not a field of that datasource"
                )


def test_every_calculated_field_has_a_caption(datasources):
    """An uncaptioned calc shows up in Tableau as 'Calculation_101' and is unusable."""
    for name, ds in datasources.items():
        for column in ds.findall("column"):
            if column.find("calculation") is not None and column.get("param-domain-type") is None:
                assert column.get("caption"), f"{name}.{column.get('name')} has no caption"


# --------------------------------------------------------------------------- worksheets ---

def test_worksheets_reference_declared_datasources(workbook, datasources):
    for sheet in workbook.find("worksheets"):
        for ds in sheet.findall(".//datasources/datasource"):
            assert ds.get("name") in datasources, f"{sheet.get('name')} uses unknown datasource {ds.get('name')}"


def test_worksheet_dependencies_exist_in_their_datasource(workbook, datasources):
    for sheet in workbook.find("worksheets"):
        for dep in sheet.findall(".//datasource-dependencies"):
            ds_name = dep.get("datasource")
            available = declared_fields(datasources[ds_name]) | EXTERNAL
            available |= {c.get("name").strip("[]") for c in dep.findall("column")}
            for instance in dep.findall("column-instance"):
                source = instance.get("column").strip("[]")
                assert source in available, (
                    f"{sheet.get('name')}: column-instance on [{source}] but that field is not "
                    f"declared in {ds_name}"
                )


def test_shelves_reference_declared_column_instances(workbook):
    """Every pill on rows/cols must be an instance the sheet actually declared."""
    for sheet in workbook.find("worksheets"):
        declared = {
            f"[{dep.get('datasource')}].[{ci.get('name').strip('[]')}]"
            for dep in sheet.findall(".//datasource-dependencies")
            for ci in dep.findall("column-instance")
        }
        for shelf in ("rows", "cols"):
            expression = sheet.findtext(f".//{shelf}") or ""
            for pill in re.findall(r"\[[^\]]+\]\.\[[^\]]+\]", expression):
                assert pill in declared, f"{sheet.get('name')} {shelf} uses undeclared pill {pill}"


def test_encodings_reference_declared_column_instances(workbook):
    for sheet in workbook.find("worksheets"):
        declared = {
            f"[{dep.get('datasource')}].[{ci.get('name').strip('[]')}]"
            for dep in sheet.findall(".//datasource-dependencies")
            for ci in dep.findall("column-instance")
        }
        for pane in sheet.findall(".//encodings/*"):
            column = pane.get("column")
            if column:
                assert column in declared, f"{sheet.get('name')} encodes undeclared {column}"


# --------------------------------------------------------------------------- dashboards ---

def test_dashboard_zones_point_at_real_worksheets(workbook):
    sheets = {s.get("name") for s in workbook.find("worksheets")}
    for dash in workbook.find("dashboards"):
        named = [z.get("name") for z in dash.findall(".//zone") if z.get("name")]
        assert named, f"{dash.get('name')} contains no worksheets"
        for zone in named:
            assert zone in sheets, f"{dash.get('name')} references missing sheet '{zone}'"


def test_every_worksheet_is_used_on_a_dashboard(workbook):
    placed = {z.get("name") for d in workbook.find("dashboards") for z in d.findall(".//zone") if z.get("name")}
    for sheet in workbook.find("worksheets"):
        assert sheet.get("name") in placed, f"{sheet.get('name')} is not on any dashboard"


def test_dashboard_zones_stay_inside_the_canvas(workbook):
    for dash in workbook.find("dashboards"):
        for zone in dash.findall(".//zone"):
            if not zone.get("name"):
                continue
            right = int(zone.get("x")) + int(zone.get("w"))
            bottom = int(zone.get("y")) + int(zone.get("h"))
            assert right <= 100000, f"{dash.get('name')}/{zone.get('name')} overflows horizontally"
            assert bottom <= 100000, f"{dash.get('name')}/{zone.get('name')} overflows vertically"


def test_windows_match_sheets_and_dashboards(workbook):
    known = {s.get("name") for s in workbook.find("worksheets")}
    known |= {d.get("name") for d in workbook.find("dashboards")}
    for window in workbook.find("windows"):
        assert window.get("name") in known, f"window '{window.get('name')}' matches nothing"
