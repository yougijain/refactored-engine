"""Regenerate tableau/retail_margin_intelligence.twb from the live mart schemas.

A .twb is XML, so the workbook scaffold - connections, column metadata, calculated fields,
sheets and dashboard layout - can be generated from the warehouse rather than clicked
together. Reading the schemas out of DuckDB means every field name and type in the workbook
matches the published CSVs exactly, and a schema change cannot silently leave a dead
reference behind in the workbook.

The output targets the Tableau 2026.1 document format and follows Tableau's guidance for
directly authored workbooks: `version` matches the schema, and the manifest is a single
`<ManifestByVersion />`. tests/test_workbook_schema.py validates it against Tableau's
published XSD, vendored in tableau/schema/.

WARNING: this OVERWRITES the workbook. Once it has been styled in Tableau Desktop, treat
the .twb as the source of truth and stop running this. It exists to rebuild the scaffold
after a schema change, and to document how the workbook was constructed.

Usage: python tools/generate_workbook.py   (requires a built warehouse)
"""

from __future__ import annotations

import uuid
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import duckdb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tableau" / "retail_margin_intelligence.twb"
NS = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")
# Tableau document format. Must match the vendored XSD in tableau/schema/.
TWB_VERSION = "26.1"

# duckdb type -> (tableau local type, remote type code, default aggregation, role, class)
TYPE_MAP = {
    "DATE": ("date", 133, "Year", "dimension", "ordinal"),
    "VARCHAR": ("string", 129, "Count", "dimension", "nominal"),
    "BOOLEAN": ("boolean", 11, "Count", "dimension", "nominal"),
    "DOUBLE": ("real", 5, "Sum", "measure", "quantitative"),
    "DECIMAL": ("real", 5, "Sum", "measure", "quantitative"),
    "INTEGER": ("integer", 20, "Sum", "measure", "quantitative"),
    "BIGINT": ("integer", 20, "Sum", "measure", "quantitative"),
    "HUGEINT": ("integer", 20, "Sum", "measure", "quantitative"),
}

SOURCES = [
    ("oi",  "Order Lines",       "fct_order_items"),
    ("ful", "Fulfilment",        "fct_fulfilment_daily"),
    ("dsc", "Discount Bands",    "fct_discount_bands"),
    ("coh", "Cohort Repeat",     "fct_cohort_repeat"),
    ("pay", "Channel Payback",   "fct_channel_payback"),
    ("ret", "Returns",           "fct_returns"),
    ("prd", "Product",           "dim_product"),
]

# Numeric columns that are labels, not things to add up.
DIMENSION_OVERRIDES = {
    "oi":  ["order_sequence", "discount_band_rank", "days_late"],
    "dsc": ["discount_band_rank"],
    "coh": ["period_index"],
    "pay": ["period_index"],
    "ret": ["quantity_ordered"],
}

CURRENCY = "£#,##0"
CURRENCY_2DP = "£#,##0.00"

# (name, caption, datatype, class, role, default format, formula)
CALCS = {
    "oi": [
        ("Calculation_101", "Contribution Margin Rate", "real", "quantitative", "measure", "p1",
         "SUM([contribution_margin]) / SUM([net_revenue])"),
        ("Calculation_102", "Average Order Value", "real", "quantitative", "measure", CURRENCY_2DP,
         "SUM([net_revenue]) / COUNTD([order_id])"),
        ("Calculation_103", "Margin per Order", "real", "quantitative", "measure", CURRENCY_2DP,
         "SUM([contribution_margin]) / COUNTD([order_id])"),
        ("Calculation_104", "Return Line Rate", "real", "quantitative", "measure", "p1",
         "SUM(IIF([is_returned], 1, 0)) / COUNT([order_item_id])"),
        ("Calculation_105", "Freight as % of Revenue", "real", "quantitative", "measure", "p1",
         "SUM([net_shipping_cost]) / SUM([net_revenue])"),
        ("Calculation_106", "Discount as % of Gross", "real", "quantitative", "measure", "p1",
         "SUM([discount_amount]) / SUM([gross_revenue])"),
        ("Calculation_107", "Category Contribution Share", "real", "quantitative", "measure", "p1",
         "SUM([contribution_margin]) / TOTAL(SUM([contribution_margin]))"),
        ("Calculation_108", "Margin Basis", "real", "quantitative", "measure", CURRENCY,
         "IF [Parameters].[Parameter 1] = 'Contribution Margin' THEN SUM([contribution_margin]) "
         "ELSE SUM([net_revenue]) END"),
    ],
    "ful": [
        ("Calculation_201", "On-Time Rate", "real", "quantitative", "measure", "p1",
         "SUM([on_time_orders]) / SUM([orders])"),
        ("Calculation_202", "Average Days Late", "real", "quantitative", "measure", "n2",
         "SUM([days_late_total]) / SUM([orders])"),
        ("Calculation_203", "Revenue on Late Parcels", "real", "quantitative", "measure", CURRENCY,
         "SUM([late_net_revenue])"),
        ("Calculation_204", "Late Revenue Share", "real", "quantitative", "measure", "p1",
         "SUM([late_net_revenue]) / SUM([net_revenue])"),
        ("Calculation_205", "Freight Subsidy per Order", "real", "quantitative", "measure", CURRENCY_2DP,
         "SUM([net_shipping_cost]) / SUM([orders])"),
    ],
    "dsc": [
        ("Calculation_301", "Margin per Unit", "real", "quantitative", "measure", CURRENCY_2DP,
         "SUM([contribution_margin]) / SUM([units])"),
        ("Calculation_302", "Net Revenue per Unit", "real", "quantitative", "measure", CURRENCY_2DP,
         "SUM([net_revenue]) / SUM([units])"),
        ("Calculation_303", "Contribution Margin Rate", "real", "quantitative", "measure", "p1",
         "SUM([contribution_margin]) / SUM([net_revenue])"),
        ("Calculation_304", "Units per Line", "real", "quantitative", "measure", "n2",
         "SUM([units]) / SUM([order_lines])"),
    ],
    "coh": [
        ("Calculation_401", "Repeat Rate", "real", "quantitative", "measure", "p1",
         "SUM([active_customers]) / SUM([cohort_customers])"),
        ("Calculation_402", "Cumulative Margin per Customer", "real", "quantitative", "measure", CURRENCY_2DP,
         "SUM([cumulative_contribution_margin]) / SUM([cohort_customers])"),
    ],
    "pay": [
        ("Calculation_501", "CAC", "real", "quantitative", "measure", CURRENCY_2DP,
         "SUM([acquisition_spend]) / SUM([cohort_customers])"),
        ("Calculation_502", "Margin net of CAC per Customer", "real", "quantitative", "measure", CURRENCY_2DP,
         "SUM([cumulative_margin_net_of_cac]) / SUM([cohort_customers])"),
        ("Calculation_503", "Payback Multiple", "real", "quantitative", "measure", "n2",
         "SUM([cumulative_contribution_margin]) / SUM([acquisition_spend])"),
    ],
    "ret": [
        ("Calculation_601", "Margin Lost", "real", "quantitative", "measure", CURRENCY,
         "SUM([margin_lost])"),
        ("Calculation_602", "Write-off Share", "real", "quantitative", "measure", "p1",
         "SUM(IIF([is_restocked], 0, [margin_lost])) / SUM([margin_lost])"),
    ],
    "prd": [
        ("Calculation_701", "Realised Margin Rate", "real", "quantitative", "measure", "p1",
         "SUM([contribution_margin]) / SUM([net_revenue])"),
        ("Calculation_702", "Margin Gap vs List", "real", "quantitative", "measure", "p1",
         "SUM([contribution_margin]) / SUM([net_revenue]) - AVG([list_margin_rate])"),
    ],
}

CATEGORY_COLOURS = {
    "Apparel": "#2e5e8f",
    "Footwear": "#4a8fbf",
    "Electronics": "#c1462c",
    "Home & Kitchen": "#e08e45",
    "Beauty": "#4f9d69",
    "Sports & Outdoors": "#7b6aa8",
}
EXPERIENCE_COLOURS = {
    "Clean": "#2e7d32",
    "Returned": "#f9a825",
    "Delivered late": "#ef6c00",
    "Late and returned": "#c62828",
}
CARRIER_COLOURS = {
    "Swiftline": "#2e5e8f",
    "Metro Post": "#4a8fbf",
    "Regional Freight": "#c1462c",
}
BAND_COLOURS = {
    "0%": "#d9d9d9",
    "1-10%": "#bcd4e6",
    "10-20%": "#7fa8c9",
    "20-30%": "#d98b6a",
    "30%+": "#c1462c",
}
DISPOSITION_COLOURS = {"Recovered": "#4f9d69", "Written off": "#c1462c"}


def uid(label: str) -> str:
    return "{" + str(uuid.uuid5(NS, label)) + "}"


def a(value) -> str:
    return quoteattr(str(value))


def base_type(duck_type: str):
    key = duck_type.split("(")[0].upper()
    return TYPE_MAP.get(key, TYPE_MAP["VARCHAR"])


def datasource_xml(key, caption, table, columns) -> str:
    ds, conn, filename = f"federated.{key}", f"textscan.{key}", f"{table}.csv"
    parts = [
        f"    <datasource caption={a(caption)} inline='true' name={a(ds)} version='{TWB_VERSION}'>",
        "      <connection class='federated'>",
        "        <named-connections>",
        f"          <named-connection caption={a(filename)} name={a(conn)}>",
        f"            <connection class='textscan' directory='../data/marts' filename={a(filename)} password='' server='' />",
        "          </named-connection>",
        "        </named-connections>",
        f"        <relation connection={a(conn)} name={a(filename)} table={a('[' + table + '#csv]')} type='table' />",
        "        <metadata-records>",
    ]
    for ordinal, (name, duck_type, *_rest) in enumerate(columns):
        local_type, remote_type, aggregation, _role, _cls = base_type(duck_type)
        parts += [
            "          <metadata-record class='column'>",
            f"            <remote-name>{escape(name)}</remote-name>",
            f"            <remote-type>{remote_type}</remote-type>",
            f"            <local-name>[{escape(name)}]</local-name>",
            f"            <parent-name>[{table}#csv]</parent-name>",
            f"            <remote-alias>{escape(name)}</remote-alias>",
            f"            <ordinal>{ordinal}</ordinal>",
            f"            <local-type>{local_type}</local-type>",
            f"            <aggregation>{aggregation}</aggregation>",
            "            <contains-null>true</contains-null>",
            "          </metadata-record>",
        ]
    parts += ["        </metadata-records>", "      </connection>", "      <aliases enabled='yes' />"]

    types = dict((c[0], c[1]) for c in columns)
    for name in DIMENSION_OVERRIDES.get(key, []):
        local_type, *_ = base_type(types[name])
        parts.append(f"      <column datatype='{local_type}' name='[{name}]' role='dimension' type='ordinal' />")
    for calc_name, calc_caption, datatype, cls, role, fmt, formula in CALCS.get(key, []):
        fmt_attr = f" default-format={a(fmt)}" if fmt else ""
        parts += [
            f"      <column caption={a(calc_caption)} datatype='{datatype}'{fmt_attr} name='[{calc_name}]' "
            f"role='{role}' type='{cls}'>",
            f"        <calculation class='tableau' formula={a(formula)} />",
            "      </column>",
        ]
    parts.append("    </datasource>")
    return "\n".join(parts)


def parameters_xml() -> str:
    return "\n".join([
        f"    <datasource hasconnection='false' inline='true' name='Parameters' version='{TWB_VERSION}'>",
        "      <aliases enabled='yes' />",
        "      <column caption='Margin Basis' datatype='string' name='[Parameter 1]' param-domain-type='list' "
        "role='measure' type='nominal' value='&quot;Contribution Margin&quot;'>",
        "        <calculation class='tableau' formula='&quot;Contribution Margin&quot;' />",
        "        <members>",
        "          <member value='&quot;Contribution Margin&quot;' />",
        "          <member value='&quot;Net Revenue&quot;' />",
        "        </members>",
        "      </column>",
        "    </datasource>",
    ])


def parameter_dependency() -> str:
    return "\n".join([
        "          <datasource-dependencies datasource='Parameters'>",
        "            <column caption='Margin Basis' datatype='string' name='[Parameter 1]' "
        "param-domain-type='list' role='measure' type='nominal' value='&quot;Contribution Margin&quot;'>",
        "              <calculation class='tableau' formula='&quot;Contribution Margin&quot;' />",
        "              <members>",
        "                <member value='&quot;Contribution Margin&quot;' />",
        "                <member value='&quot;Net Revenue&quot;' />",
        "              </members>",
        "            </column>",
        "          </datasource-dependencies>",
    ])


def dep_column(name, datatype, role, cls):
    return f"          <column datatype='{datatype}' name='[{name}]' role='{role}' type='{cls}' />"


def dep_calc(key, calc_name):
    for name, caption, datatype, cls, role, fmt, formula in CALCS[key]:
        if name == calc_name:
            fmt_attr = f" default-format={a(fmt)}" if fmt else ""
            return "\n".join([
                f"          <column caption={a(caption)} datatype='{datatype}'{fmt_attr} name='[{name}]' "
                f"role='{role}' type='{cls}'>",
                f"            <calculation class='tableau' formula={a(formula)} />",
                "          </column>",
            ])
    raise KeyError(calc_name)


def dep_instance(column, derivation, name, cls):
    return (f"          <column-instance column='[{column}]' derivation='{derivation}' name='[{name}]' "
            f"pivot='key' type='{cls}' />")


def palette_style(ds, instance, mapping):
    rows = "\n".join(
        f"          <map to='{colour}'><bucket>&quot;{escape(member)}&quot;</bucket></map>"
        for member, colour in mapping.items()
    )
    return "\n".join([
        "      <style>",
        "        <style-rule element='mark'>",
        f"          <encoding attr='color' field='[{ds}].[{instance}]' palette='custom' type='palette'>",
        rows,
        "          </encoding>",
        "        </style-rule>",
        "      </style>",
    ])


def categorical_filter(ds, instance, members):
    entries = "\n".join(
        f"          <groupfilter function='member' level='[{instance}]' member={a(m)} />" for m in members
    )
    return "\n".join([
        f"        <filter class='categorical' column='[{ds}].[{instance}]'>",
        "          <groupfilter function='union' user:op='manual'>",
        entries,
        "          </groupfilter>",
        "        </filter>",
        "        <slices>",
        f"          <column>[{ds}].[{instance}]</column>",
        "        </slices>",
    ])


def range_filter(ds, instance, minimum, maximum):
    return "\n".join([
        f"        <filter class='quantitative' column='[{ds}].[{instance}]' included-values='in-range'>",
        f"          <min>{minimum}</min>",
        f"          <max>{maximum}</max>",
        "        </filter>",
        "        <slices>",
        f"          <column>[{ds}].[{instance}]</column>",
        "        </slices>",
    ])


def worksheet(name, ds_caption, ds, deps, mark, rows, cols, encodings,
              extra_datasources=(), filters=(), style=None):
    encoding_xml = "\n".join(f"            <{kind} column='{col}' />" for kind, col in encodings)
    ds_list = [f"          <datasource caption={a(ds_caption)} name={a(ds)} />"]
    ds_list += [f"          <datasource name={a(extra)} />" for extra in extra_datasources]
    parts = [
        f"    <worksheet name={a(name)}>",
        "      <table>",
        "        <view>",
        "          <datasources>",
        *ds_list,
        "          </datasources>",
        deps,
    ]
    parts += list(filters)
    parts += ["          <aggregation value='true' />", "        </view>"]
    parts.append(style if style else "      <style />")
    parts += [
        "        <panes>",
        "          <pane id='1'>",
        "            <view><breakdown value='auto' /></view>",
        f"            <mark class='{mark}' />",
        "            <encodings>",
        encoding_xml,
        "            </encodings>",
        "          </pane>",
        "        </panes>",
        f"        <rows>{rows}</rows>",
        f"        <cols>{cols}</cols>",
        "      </table>",
        f"      <simple-id uuid={a(uid('sheet:' + name))} />",
        "    </worksheet>",
    ]
    return "\n".join(p for p in parts if p)


def dashboard(name, title, subtitle, zones, width=1500, height=950):
    zone_xml = ["\n".join([
        "        <zone h='7000' id='2' type-v2='text' w='100000' x='0' y='0'>",
        "          <formatted-text>",
        f"            <run bold='true' fontsize='16'>{escape(title)}</run>",
        "            <run>&#13;&#10;</run>",
        f"            <run fontcolor='#5a5a5a' fontsize='10'>{escape(subtitle)}</run>",
        "          </formatted-text>",
        "        </zone>",
    ])]
    zone_id = 3
    for sheet_name, x, y, w, h in zones:
        zone_xml.append(f"        <zone h='{h}' id='{zone_id}' name={a(sheet_name)} w='{w}' x='{x}' y='{y}' />")
        zone_id += 1
    return "\n".join([
        f"    <dashboard name={a(name)}>",
        "      <style />",
        f"      <size maxheight='{height}' maxwidth='{width}' minheight='{height}' minwidth='{width}' />",
        "      <zones>",
        "        <zone h='100000' id='1' type-v2='layout-basic' w='100000' x='0' y='0'>",
        *zone_xml,
        "        </zone>",
        "      </zones>",
        f"      <simple-id uuid={a(uid('dash:' + name))} />",
        "    </dashboard>",
    ])


def build_sheets() -> list[str]:
    sheets = []

    # 1 - Contribution margin by category, switchable to net revenue by the parameter -----
    deps = "\n".join([
        "          <datasource-dependencies datasource='federated.oi'>",
        dep_column("category", "string", "dimension", "nominal"),
        dep_column("net_revenue", "real", "measure", "quantitative"),
        dep_column("contribution_margin", "real", "measure", "quantitative"),
        dep_calc("oi", "Calculation_108"),
        dep_instance("category", "None", "none:category:nk", "nominal"),
        dep_instance("Calculation_108", "User", "usr:Calculation_108:qk", "quantitative"),
        "          </datasource-dependencies>",
        parameter_dependency(),
    ])
    sheets.append(worksheet(
        "Category Contribution", "Order Lines", "federated.oi", deps, "Bar",
        "[federated.oi].[usr:Calculation_108:qk]", "[federated.oi].[none:category:nk]",
        [("color", "[federated.oi].[none:category:nk]"),
         ("text", "[federated.oi].[usr:Calculation_108:qk]")],
        extra_datasources=("Parameters",),
        style=palette_style("federated.oi", "none:category:nk", CATEGORY_COLOURS),
    ))

    # 2 - Promised margin against delivered margin, per product -------------------------
    deps = "\n".join([
        "          <datasource-dependencies datasource='federated.prd'>",
        dep_column("product_id", "string", "dimension", "nominal"),
        dep_column("category", "string", "dimension", "nominal"),
        dep_column("list_margin_rate", "real", "measure", "quantitative"),
        dep_column("net_revenue", "real", "measure", "quantitative"),
        dep_column("contribution_margin", "real", "measure", "quantitative"),
        dep_calc("prd", "Calculation_701"),
        dep_instance("product_id", "None", "none:product_id:nk", "nominal"),
        dep_instance("category", "None", "none:category:nk", "nominal"),
        dep_instance("list_margin_rate", "Avg", "avg:list_margin_rate:qk", "quantitative"),
        dep_instance("net_revenue", "Sum", "sum:net_revenue:qk", "quantitative"),
        dep_instance("Calculation_701", "User", "usr:Calculation_701:qk", "quantitative"),
        "          </datasource-dependencies>",
    ])
    sheets.append(worksheet(
        "Promised vs Realised Margin", "Product", "federated.prd", deps, "Circle",
        "[federated.prd].[usr:Calculation_701:qk]", "[federated.prd].[avg:list_margin_rate:qk]",
        [("color", "[federated.prd].[none:category:nk]"),
         ("size", "[federated.prd].[sum:net_revenue:qk]"),
         ("text", "[federated.prd].[none:product_id:nk]")],
        style=palette_style("federated.prd", "none:category:nk", CATEGORY_COLOURS),
    ))

    # 3 - Margin trend -------------------------------------------------------------------
    deps = "\n".join([
        "          <datasource-dependencies datasource='federated.oi'>",
        dep_column("order_month", "date", "dimension", "ordinal"),
        dep_column("category", "string", "dimension", "nominal"),
        dep_column("contribution_margin", "real", "measure", "quantitative"),
        dep_instance("order_month", "Month", "tmn:order_month:qk", "quantitative"),
        dep_instance("category", "None", "none:category:nk", "nominal"),
        dep_instance("contribution_margin", "Sum", "sum:contribution_margin:qk", "quantitative"),
        "          </datasource-dependencies>",
    ])
    sheets.append(worksheet(
        "Margin Trend by Category", "Order Lines", "federated.oi", deps, "Area",
        "[federated.oi].[sum:contribution_margin:qk]", "[federated.oi].[tmn:order_month:qk]",
        [("color", "[federated.oi].[none:category:nk]")],
        style=palette_style("federated.oi", "none:category:nk", CATEGORY_COLOURS),
    ))

    # 4 - Margin per unit across discount depth, held within category --------------------
    deps = "\n".join([
        "          <datasource-dependencies datasource='federated.dsc'>",
        dep_column("category", "string", "dimension", "nominal"),
        dep_column("discount_band", "string", "dimension", "nominal"),
        dep_column("discount_band_rank", "integer", "dimension", "ordinal"),
        dep_column("units", "integer", "measure", "quantitative"),
        dep_column("net_revenue", "real", "measure", "quantitative"),
        dep_column("contribution_margin", "real", "measure", "quantitative"),
        dep_calc("dsc", "Calculation_301"),
        dep_instance("category", "None", "none:category:nk", "nominal"),
        dep_instance("discount_band", "None", "none:discount_band:nk", "nominal"),
        dep_instance("discount_band_rank", "None", "none:discount_band_rank:ok", "ordinal"),
        dep_instance("Calculation_301", "User", "usr:Calculation_301:qk", "quantitative"),
        "          </datasource-dependencies>",
    ])
    sheets.append(worksheet(
        "Discount Elasticity", "Discount Bands", "federated.dsc", deps, "Bar",
        "[federated.dsc].[usr:Calculation_301:qk]",
        "([federated.dsc].[none:category:nk] / [federated.dsc].[none:discount_band_rank:ok])",
        [("color", "[federated.dsc].[none:discount_band:nk]"),
         ("text", "[federated.dsc].[usr:Calculation_301:qk]")],
        style=palette_style("federated.dsc", "none:discount_band:nk", BAND_COLOURS),
    ))

    # 5 - Units bought at each depth ------------------------------------------------------
    deps = "\n".join([
        "          <datasource-dependencies datasource='federated.dsc'>",
        dep_column("category", "string", "dimension", "nominal"),
        dep_column("discount_band", "string", "dimension", "nominal"),
        dep_column("discount_band_rank", "integer", "dimension", "ordinal"),
        dep_column("units", "integer", "measure", "quantitative"),
        dep_column("order_lines", "integer", "measure", "quantitative"),
        dep_calc("dsc", "Calculation_304"),
        dep_instance("category", "None", "none:category:nk", "nominal"),
        dep_instance("discount_band", "None", "none:discount_band:nk", "nominal"),
        dep_instance("discount_band_rank", "None", "none:discount_band_rank:ok", "ordinal"),
        dep_instance("Calculation_304", "User", "usr:Calculation_304:qk", "quantitative"),
        "          </datasource-dependencies>",
    ])
    sheets.append(worksheet(
        "Units per Line by Depth", "Discount Bands", "federated.dsc", deps, "Line",
        "[federated.dsc].[usr:Calculation_304:qk]", "[federated.dsc].[none:discount_band_rank:ok]",
        [("color", "[federated.dsc].[none:category:nk]")],
        style=palette_style("federated.dsc", "none:category:nk", CATEGORY_COLOURS),
    ))

    # 6 - On-time rate by lane -------------------------------------------------------------
    deps = "\n".join([
        "          <datasource-dependencies datasource='federated.ful'>",
        dep_column("fulfilment_centre", "string", "dimension", "nominal"),
        dep_column("carrier", "string", "dimension", "nominal"),
        dep_column("orders", "integer", "measure", "quantitative"),
        dep_column("on_time_orders", "integer", "measure", "quantitative"),
        dep_calc("ful", "Calculation_201"),
        dep_instance("fulfilment_centre", "None", "none:fulfilment_centre:nk", "nominal"),
        dep_instance("carrier", "None", "none:carrier:nk", "nominal"),
        dep_instance("Calculation_201", "User", "usr:Calculation_201:qk", "quantitative"),
        "          </datasource-dependencies>",
    ])
    sheets.append(worksheet(
        "On-Time Rate by Lane", "Fulfilment", "federated.ful", deps, "Square",
        "[federated.ful].[none:fulfilment_centre:nk]", "[federated.ful].[none:carrier:nk]",
        [("color", "[federated.ful].[usr:Calculation_201:qk]"),
         ("text", "[federated.ful].[usr:Calculation_201:qk]")],
    ))

    # 7 - Revenue riding on late parcels ----------------------------------------------------
    deps = "\n".join([
        "          <datasource-dependencies datasource='federated.ful'>",
        dep_column("order_month", "date", "dimension", "ordinal"),
        dep_column("carrier", "string", "dimension", "nominal"),
        dep_column("late_net_revenue", "real", "measure", "quantitative"),
        dep_instance("order_month", "Month", "tmn:order_month:qk", "quantitative"),
        dep_instance("carrier", "None", "none:carrier:nk", "nominal"),
        dep_instance("late_net_revenue", "Sum", "sum:late_net_revenue:qk", "quantitative"),
        "          </datasource-dependencies>",
    ])
    sheets.append(worksheet(
        "Revenue on Late Parcels", "Fulfilment", "federated.ful", deps, "Bar",
        "[federated.ful].[sum:late_net_revenue:qk]", "[federated.ful].[tmn:order_month:qk]",
        [("color", "[federated.ful].[none:carrier:nk]")],
        style=palette_style("federated.ful", "none:carrier:nk", CARRIER_COLOURS),
    ))

    # 8 - What a bad first order costs --------------------------------------------------------
    deps = "\n".join([
        "          <datasource-dependencies datasource='federated.coh'>",
        dep_column("period_index", "integer", "dimension", "ordinal"),
        dep_column("first_order_experience", "string", "dimension", "nominal"),
        dep_column("active_customers", "integer", "measure", "quantitative"),
        dep_column("cohort_customers", "integer", "measure", "quantitative"),
        dep_calc("coh", "Calculation_401"),
        dep_instance("period_index", "None", "none:period_index:ok", "ordinal"),
        dep_instance("first_order_experience", "None", "none:first_order_experience:nk", "nominal"),
        dep_instance("Calculation_401", "User", "usr:Calculation_401:qk", "quantitative"),
        "          </datasource-dependencies>",
    ])
    sheets.append(worksheet(
        "First-Order Experience", "Cohort Repeat", "federated.coh", deps, "Line",
        "[federated.coh].[usr:Calculation_401:qk]", "[federated.coh].[none:period_index:ok]",
        [("color", "[federated.coh].[none:first_order_experience:nk]")],
        filters=[range_filter("federated.coh", "none:period_index:ok", 1, 12)],
        style=palette_style("federated.coh", "none:first_order_experience:nk", EXPERIENCE_COLOURS),
    ))

    # 9 - Acquisition payback ------------------------------------------------------------------
    deps = "\n".join([
        "          <datasource-dependencies datasource='federated.pay'>",
        dep_column("period_index", "integer", "dimension", "ordinal"),
        dep_column("acquisition_channel", "string", "dimension", "nominal"),
        dep_column("cohort_customers", "integer", "measure", "quantitative"),
        dep_column("acquisition_spend", "real", "measure", "quantitative"),
        dep_column("cumulative_margin_net_of_cac", "real", "measure", "quantitative"),
        dep_calc("pay", "Calculation_502"),
        dep_instance("period_index", "None", "none:period_index:ok", "ordinal"),
        dep_instance("acquisition_channel", "None", "none:acquisition_channel:nk", "nominal"),
        dep_instance("Calculation_502", "User", "usr:Calculation_502:qk", "quantitative"),
        "          </datasource-dependencies>",
    ])
    sheets.append(worksheet(
        "CAC Payback by Channel", "Channel Payback", "federated.pay", deps, "Line",
        "[federated.pay].[usr:Calculation_502:qk]", "[federated.pay].[none:period_index:ok]",
        [("color", "[federated.pay].[none:acquisition_channel:nk]")],
        filters=[range_filter("federated.pay", "none:period_index:ok", 0, 18)],
    ))

    # 10 - Return reasons, ranked by margin rather than by count -------------------------------
    deps = "\n".join([
        "          <datasource-dependencies datasource='federated.ret'>",
        dep_column("return_reason", "string", "dimension", "nominal"),
        dep_column("disposition", "string", "dimension", "nominal"),
        dep_column("category", "string", "dimension", "nominal"),
        dep_column("margin_lost", "real", "measure", "quantitative"),
        dep_calc("ret", "Calculation_601"),
        dep_instance("return_reason", "None", "none:return_reason:nk", "nominal"),
        dep_instance("disposition", "None", "none:disposition:nk", "nominal"),
        dep_instance("category", "None", "none:category:nk", "nominal"),
        dep_instance("Calculation_601", "User", "usr:Calculation_601:qk", "quantitative"),
        "          </datasource-dependencies>",
    ])
    sheets.append(worksheet(
        "Return Reasons by Margin Lost", "Returns", "federated.ret", deps, "Bar",
        "[federated.ret].[none:return_reason:nk]", "[federated.ret].[usr:Calculation_601:qk]",
        [("color", "[federated.ret].[none:disposition:nk]"),
         ("text", "[federated.ret].[usr:Calculation_601:qk]")],
        style=palette_style("federated.ret", "none:disposition:nk", DISPOSITION_COLOURS),
    ))

    return sheets


SHEET_NAMES = [
    "Category Contribution",
    "Promised vs Realised Margin",
    "Margin Trend by Category",
    "Discount Elasticity",
    "Units per Line by Depth",
    "On-Time Rate by Lane",
    "Revenue on Late Parcels",
    "First-Order Experience",
    "CAC Payback by Channel",
    "Return Reasons by Margin Lost",
]

DASHBOARDS = [
    ("1 · Margin Reality",
     "Where the Margin Actually Is",
     "Contribution margin after discount, returns and freight - not gross revenue. "
     "Use the Margin Basis parameter to switch the first chart between the two.",
     [("Category Contribution", 0, 7000, 50000, 46000),
      ("Promised vs Realised Margin", 50000, 7000, 50000, 46000),
      ("Margin Trend by Category", 0, 53000, 100000, 47000)]),
    ("2 · Pricing & Discounting",
     "What Discount Depth Buys",
     "Margin per unit and units per line at each discount band, held within category so a "
     "mix shift cannot masquerade as elasticity.",
     [("Discount Elasticity", 0, 7000, 58000, 93000),
      ("Units per Line by Depth", 58000, 7000, 42000, 93000)]),
    ("3 · Fulfilment & Its Cost",
     "Late Parcels and What They Cost",
     "On-time rate by fulfilment centre and carrier, the revenue riding on the parcels that "
     "missed, and the repeat rate of customers whose first order was one of them.",
     [("On-Time Rate by Lane", 0, 7000, 42000, 44000),
      ("Revenue on Late Parcels", 42000, 7000, 58000, 44000),
      ("First-Order Experience", 0, 51000, 100000, 49000)]),
    ("4 · Acquisition & Returns",
     "What Each Channel Costs, and What Comes Back",
     "Cumulative contribution margin net of acquisition cost per customer, and the return "
     "reasons ranked by margin destroyed rather than by unit count.",
     [("CAC Payback by Channel", 0, 7000, 58000, 93000),
      ("Return Reasons by Margin Lost", 58000, 7000, 42000, 93000)]),
]


# Parameters whose control card is shown on a worksheet.
SHEET_PARAMETERS: dict[str, list[str]] = {}


def worksheet_cards(parameters=()) -> str:
    """The shelf and card layout Tableau Desktop writes for a new worksheet."""
    right = []
    if parameters:
        right = [
            "        <edge name='right'>",
            "          <strip size='160'>",
            *[f"            <card param={a(p)} type='parameter' />" for p in parameters],
            "          </strip>",
            "        </edge>",
        ]
    return "\n".join([
        "      <cards>",
        "        <edge name='left'>",
        "          <strip size='160'>",
        "            <card type='pages' />",
        "            <card type='filters' />",
        "            <card type='marks' />",
        "          </strip>",
        "        </edge>",
        "        <edge name='top'>",
        "          <strip size='2147483647'>",
        "            <card type='columns' />",
        "          </strip>",
        "          <strip size='2147483647'>",
        "            <card type='rows' />",
        "          </strip>",
        "          <strip size='31'>",
        "            <card type='title' />",
        "          </strip>",
        "        </edge>",
        *right,
        "      </cards>",
    ])


def main() -> None:
    con = duckdb.connect(str(ROOT / "data" / "warehouse.duckdb"), read_only=True)
    columns = {key: con.execute(f"describe {table}").fetchall() for key, _c, table in SOURCES}
    con.close()

    datasources = [parameters_xml()]
    datasources += [datasource_xml(key, caption, table, columns[key]) for key, caption, table in SOURCES]

    windows = ["  <windows source-height='30'>"]
    for sheet in SHEET_NAMES:
        windows += [
            f"    <window class='worksheet' name={a(sheet)}>",
            worksheet_cards(SHEET_PARAMETERS.get(sheet, ())),
            "      <viewpoint><zoom type='entire-view' /></viewpoint>",
            f"      <simple-id uuid={a(uid('win:' + sheet))} />",
            "    </window>",
        ]
    for name, _title, _subtitle, zones, *_rest in DASHBOARDS:
        windows += [
            f"    <window class='dashboard' name={a(name)}>",
            "      <viewpoints>",
            *[f"        <viewpoint name={a(sheet)}><zoom type='entire-view' /></viewpoint>"
              for sheet, *_xywh in zones],
            "      </viewpoints>",
            "      <active id='-1' />",
            f"      <simple-id uuid={a(uid('win:' + name))} />",
            "    </window>",
        ]
    windows.append("  </windows>")

    document = "\n".join([
        "<?xml version='1.0' encoding='utf-8' ?>",
        f"<workbook original-version='{TWB_VERSION}' source-build='0.0.0 (0000.0.0.0)' source-platform='win' "
        f"version='{TWB_VERSION}' xmlns:user='http://www.tableausoftware.com/xml/user'>",
        "  <document-format-change-manifest>",
        "    <ManifestByVersion />",
        "  </document-format-change-manifest>",
        "  <preferences>",
        "    <preference name='ui.encoding.shelf.height' value='24' />",
        "    <preference name='ui.shelf.height' value='26' />",
        "  </preferences>",
        "  <datasources>",
        "\n".join(datasources),
        "  </datasources>",
        "  <worksheets>",
        "\n".join(build_sheets()),
        "  </worksheets>",
        "  <dashboards>",
        "\n".join(dashboard(*d) for d in DASHBOARDS),
        "  </dashboards>",
        "\n".join(windows),
        "  <explain-data enabled-for-viewer='true' extreme-values-enabled-for-all='true'>",
        "    <explanation-types />",
        "  </explain-data>",
        "</workbook>",
        "",
    ])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(document, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(document):,} chars, "
          f"{len(SHEET_NAMES)} sheets, {len(DASHBOARDS)} dashboards)")


if __name__ == "__main__":
    main()
