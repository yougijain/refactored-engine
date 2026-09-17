# Tableau workbook schema

`tests/test_workbook_schema.py` validates `tableau/retail_margin_intelligence.twb` against the
files in this folder.

| File | What it is |
| --- | --- |
| `twb_2026.1.0.xsd` | Tableau's published workbook schema for the 2026.1 document format, vendored verbatim |
| `LICENSE-tableau-document-schemas.txt` | The Apache License 2.0 the schema is distributed under |
| `tableau_user_namespace.xsd` | A stand-in for Tableau's `user:` namespace, written for this project (see below) |

## Source

- Repository: [tableau/tableau-document-schemas](https://github.com/tableau/tableau-document-schemas)
- Path: `schemas/2026_1/twb_2026.1.0.xsd`
- Commit: `f4bce1eb55f0c1c010c0ef826cf531528d5910eb`
- Copyright (c) 2024 Salesforce, Inc. Licensed under the Apache License, Version 2.0.

The schema is unmodified. `.gitattributes` exempts it from line-ending normalisation so the
committed bytes match the upstream file.

## Why there is a stand-in for the `user:` namespace

The TWB schema imports `http://www.tableausoftware.com/xml/user` without a `schemaLocation`,
and Tableau does not publish a schema for that namespace — it holds free-form UI state such as
`user:op`. Strict validators will not compile a schema with an unresolved import, so
`tableau_user_namespace.xsd` declares the single attribute group the TWB schema references and
accepts any attribute in that namespace.

## What passing does and does not prove

Tableau describes XSD validation as **syntactic**: passing means the XML has the structure
Tableau requires, not that the workbook will open. The schema also does not check calculated
field contents or references between named parts of a workbook.

That is why there are two test files. `test_workbook_schema.py` checks structure against this
schema; `test_workbook_integrity.py` checks what the schema cannot — that every field,
calculation, pill, zone and window refers to something that exists. Tableau's only semantic
check is a Tableau Cloud / Server REST endpoint, which needs a site to run against.

## Updating to a newer format

1. Download the newer `twb_YYYY.R.0.xsd` into this folder and delete the old one — the test
   expects exactly one.
2. Set `TWB_VERSION` in `tools/generate_workbook.py` to match (`2026.2.0` → `26.2`).
3. Regenerate the workbook and run `pytest tests/test_workbook_schema.py`.
4. Update the source commit above.

A workbook declaring format `26.1` opens in Tableau 2026.1 and later, but not in earlier
versions.
