"""Validate the workbook against Tableau's published document schema.

test_workbook_integrity.py checks references between parts of the workbook, which the XSD
does not. This file checks the other half: that the XML has the structure Tableau's own
schema requires. Tableau describes XSD validation as syntactic only - passing does not prove
the workbook opens - but failing it does prove the workbook is malformed.

The schema and its provenance are in tableau/schema/.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import xmlschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "tableau" / "schema"
WORKBOOK = ROOT / "tableau" / "retail_margin_intelligence.twb"
USER_NAMESPACE = "http://www.tableausoftware.com/xml/user"


def vendored_xsd() -> Path:
    matches = sorted(SCHEMA_DIR.glob("twb_*.xsd"))
    assert len(matches) == 1, f"expected one vendored TWB schema, found {[m.name for m in matches]}"
    return matches[0]


def schema_format_version() -> str:
    """Tableau pairs schema version 2026.1.0 with workbook format version 26.1."""
    year, release, _patch = ET.parse(vendored_xsd()).getroot().get("version").split(".")
    return f"{year[2:]}.{release}"


@pytest.fixture(scope="module")
def schema() -> xmlschema.XMLSchema:
    return xmlschema.XMLSchema(
        str(vendored_xsd()),
        locations={USER_NAMESPACE: str(SCHEMA_DIR / "tableau_user_namespace.xsd")},
    )


@pytest.fixture(scope="module")
def workbook() -> ET.Element:
    return ET.parse(WORKBOOK).getroot()


def test_workbook_conforms_to_the_tableau_schema(schema):
    errors = list(schema.iter_errors(str(WORKBOOK)))
    detail = "\n".join(f"  {e.path}: {e.reason}" for e in errors[:10])
    assert not errors, f"{len(errors)} violation(s) of {vendored_xsd().name}:\n{detail}"


def test_workbook_declares_the_format_of_the_schema_it_is_validated_against(workbook):
    """Tableau's guidance for directly authored workbooks: the version must match the XSD."""
    expected = schema_format_version()
    assert workbook.get("version") == expected
    assert workbook.get("original-version") == expected
    for datasource in workbook.find("datasources"):
        assert datasource.get("version") == expected, f"{datasource.get('name')} declares {datasource.get('version')}"


def test_workbook_uses_manifest_by_version(workbook):
    """A single <ManifestByVersion /> replaces the hand-maintained feature list."""
    manifest = workbook.find("document-format-change-manifest")
    assert manifest is not None, "missing <document-format-change-manifest>"
    assert [child.tag for child in manifest] == ["ManifestByVersion"]
