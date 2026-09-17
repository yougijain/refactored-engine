"""Checks that the Tableau workbook matches the data files."""

from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "tableau" / "saas_revenue_intelligence.twb"

FIELD_TOKEN = re.compile(r"\[([^\[\]]+)\]")
QUALIFIED_REF = re.compile(r"\[([^\[\]]+)\]\.\[([^\[\]]+)\]")
BUILTIN_FIELDS = {"Parameters", "Parameter 1"}


@pytest.fixture(scope="session")
def tree():
    assert WORKBOOK.exists(), f"workbook missing at {WORKBOOK}"
    return ET.parse(WORKBOOK).getroot()


@pytest.fixture(scope="session")
def datasources(tree):
    return {ds.get("name"): ds for ds in tree.findall("./datasources/datasource")}


def csv_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return next(csv.reader(handle))


def test_workbook_is_well_formed_xml(tree):
    assert tree.tag == "workbook"
    assert tree.findall("./worksheets/worksheet"), "workbook has no worksheets"
    assert tree.findall("./dashboards/dashboard"), "workbook has no dashboards"


def test_every_connection_points_at_a_file_that_exists(datasources):
    checked = 0
    for name, ds in datasources.items():
        for connection in ds.findall(".//connection[@class='textscan']"):
            target = (WORKBOOK.parent / connection.get("directory") / connection.get("filename")).resolve()
            assert target.exists(), f"{name} points at missing data file {target}"
            checked += 1
    assert checked >= 5, "expected every mart connection to be checked"


def test_metadata_matches_the_published_csv_columns(datasources):
    for name, ds in datasources.items():
        connection = ds.find(".//connection[@class='textscan']")
        if connection is None:
            continue
        path = (WORKBOOK.parent / connection.get("directory") / connection.get("filename")).resolve()
        declared = [record.findtext("remote-name") for record in ds.findall(".//metadata-record[@class='column']")]
        assert declared == csv_header(path), (
            f"{name} columns do not match {path.name}"
        )


def test_every_calculation_resolves_to_a_real_field(datasources):
    for name, ds in datasources.items():
        known = {record.findtext("remote-name") for record in ds.findall(".//metadata-record[@class='column']")}
        known |= {column.get("name").strip("[]") for column in ds.findall("./column")}
        known |= BUILTIN_FIELDS
        for column in ds.findall("./column"):
            calculation = column.find("calculation")
            if calculation is None or not calculation.get("formula"):
                continue
            for token in FIELD_TOKEN.findall(calculation.get("formula")):
                assert token in known, (
                    f"{name}.{column.get('caption') or column.get('name')} references "
                    f"unknown field [{token}]"
                )


def test_worksheets_reference_declared_datasources(tree, datasources):
    for worksheet in tree.findall("./worksheets/worksheet"):
        for ds in worksheet.findall(".//view/datasources/datasource"):
            assert ds.get("name") in datasources, (
                f"{worksheet.get('name')} uses undeclared datasource {ds.get('name')}"
            )


def test_every_shelf_reference_is_declared_in_the_sheet(tree):
    for worksheet in tree.findall("./worksheets/worksheet"):
        declared = set()
        for dependency in worksheet.findall(".//datasource-dependencies"):
            source = dependency.get("datasource")
            for instance in dependency.findall("column-instance"):
                declared.add((source, instance.get("name").strip("[]")))
            for column in dependency.findall("column"):
                declared.add((source, column.get("name").strip("[]")))

        references = []
        for shelf in ("rows", "cols"):
            element = worksheet.find(f".//table/{shelf}")
            if element is not None and element.text:
                references += QUALIFIED_REF.findall(element.text)
        for encoding in worksheet.findall(".//encodings/*"):
            references += QUALIFIED_REF.findall(encoding.get("column", ""))
        for filter_element in worksheet.findall(".//filter"):
            references += QUALIFIED_REF.findall(filter_element.get("column", ""))

        assert references, f"{worksheet.get('name')} places nothing on any shelf"
        for source, instance in references:
            assert (source, instance) in declared, (
                f"{worksheet.get('name')} uses [{source}].[{instance}] without declaring it"
            )


def test_dashboards_only_reference_existing_worksheets(tree):
    sheets = {worksheet.get("name") for worksheet in tree.findall("./worksheets/worksheet")}
    placed = set()
    for dash in tree.findall("./dashboards/dashboard"):
        for zone in dash.findall(".//zone[@name]"):
            assert zone.get("name") in sheets, (
                f"dashboard '{dash.get('name')}' places missing sheet '{zone.get('name')}'"
            )
            placed.add(zone.get("name"))
    assert placed == sheets, f"worksheets not placed on any dashboard: {sorted(sheets - placed)}"


def test_dashboard_zones_stay_inside_their_canvas(tree):
    for dash in tree.findall("./dashboards/dashboard"):
        for zone in dash.findall(".//zone[@name]"):
            x, y = int(zone.get("x")), int(zone.get("y"))
            width, height = int(zone.get("w")), int(zone.get("h"))
            assert 0 <= x and 0 <= y, f"{dash.get('name')}/{zone.get('name')} has a negative origin"
            assert x + width <= 100000, f"{dash.get('name')}/{zone.get('name')} overflows horizontally"
            assert y + height <= 100000, f"{dash.get('name')}/{zone.get('name')} overflows vertically"


def test_dashboard_zones_do_not_overlap(tree):
    for dash in tree.findall("./dashboards/dashboard"):
        boxes = [
            (zone.get("name"), int(zone.get("x")), int(zone.get("y")), int(zone.get("w")), int(zone.get("h")))
            for zone in dash.findall(".//zone[@name]")
        ]
        for i, (name_a, ax, ay, aw, ah) in enumerate(boxes):
            for name_b, bx, by, bw, bh in boxes[i + 1:]:
                overlap = ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah
                assert not overlap, f"{dash.get('name')}: '{name_a}' overlaps '{name_b}'"
