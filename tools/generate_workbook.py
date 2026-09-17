"""Rebuild tableau/saas_revenue_intelligence.twb from the table schemas. Overwrites the workbook."""

from __future__ import annotations

import uuid
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import duckdb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tableau" / "saas_revenue_intelligence.twb"
NS = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")

TYPE_MAP = {
    "DATE": ("date", 133, "Year", "dimension", "ordinal"),
    "VARCHAR": ("string", 129, "Count", "dimension", "nominal"),
    "DOUBLE": ("real", 5, "Sum", "measure", "quantitative"),
    "INTEGER": ("integer", 20, "Sum", "measure", "quantitative"),
    "BIGINT": ("integer", 20, "Sum", "measure", "quantitative"),
    "HUGEINT": ("integer", 20, "Sum", "measure", "quantitative"),
}

DIMENSION_OVERRIDES = {
    "mrr": ["tenure_months", "is_active"],
    "coh": ["period_index"],
    "hea": ["risk_tier_rank"],
    "dim": ["is_active", "active_months"],
}

SOURCES = [
    ("mrr", "MRR Movement", "fct_mrr_monthly"),
    ("ret", "Retention Monthly", "fct_retention_monthly"),
    ("ttm", "Retention TTM", "fct_retention_ttm"),
    ("coh", "Cohort Retention", "fct_cohort_retention"),
    ("hea", "Account Health", "fct_account_health"),
    ("dim", "Customer Dimension", "dim_customer"),
]

CALCS = {
    "mrr": [
        ("Calculation_101", "Signed Movement MRR", "real", "quantitative", "measure", "$#,##0",
         "[new_mrr] + [expansion_mrr] + [reactivation_mrr] - [contraction_mrr] - [churned_mrr]", False),
        ("Calculation_102", "Active Customers", "integer", "quantitative", "measure", None,
         "COUNTD(IF [is_active] = 1 THEN [customer_id] END)", True),
        ("Calculation_103", "ARPA", "real", "quantitative", "measure", "$#,##0",
         "SUM([mrr]) / COUNTD(IF [is_active] = 1 THEN [customer_id] END)", True),
        ("Calculation_104", "Account Peak MRR", "real", "quantitative", "measure", "$#,##0",
         "{ FIXED [customer_id] : MAX([mrr]) }", False),
        ("Calculation_105", "Expansion Rate", "real", "quantitative", "measure", "p1",
         "SUM([expansion_mrr]) / SUM([prior_mrr])", True),
        ("Calculation_106", "Gross MRR Churn Rate", "real", "quantitative", "measure", "p1",
         "SUM([churned_mrr]) / SUM([prior_mrr])", True),
    ],
    "ret": [
        ("Calculation_201", "Net Revenue Retention (MoM)", "real", "quantitative", "measure", "p1",
         "SUM([retention_base_ending_mrr]) / SUM([retention_base_mrr])", True),
        ("Calculation_202", "Gross Revenue Retention (MoM)", "real", "quantitative", "measure", "p1",
         "(SUM([retention_base_mrr]) - SUM([churned_mrr]) - SUM([contraction_mrr])) / SUM([retention_base_mrr])", True),
        ("Calculation_203", "Logo Churn Rate (monthly)", "real", "quantitative", "measure", "p1",
         "SUM([churned_customers]) / SUM([starting_customers])", True),
        ("Calculation_204", "Net New MRR", "real", "quantitative", "measure", "$#,##0",
         "SUM([new_mrr]) + SUM([expansion_mrr]) + SUM([reactivation_mrr]) - SUM([contraction_mrr]) - SUM([churned_mrr])", True),
        ("Calculation_205", "ARR", "real", "quantitative", "measure", "$#,##0",
         "SUM([ending_mrr]) * 12", True),
        ("Calculation_206", "SaaS Quick Ratio", "real", "quantitative", "measure", "n2",
         "(SUM([new_mrr]) + SUM([expansion_mrr]) + SUM([reactivation_mrr])) / "
         "IIF(SUM([contraction_mrr]) + SUM([churned_mrr]) = 0, NULL, SUM([contraction_mrr]) + SUM([churned_mrr]))", True),
    ],
    "coh": [
        ("Calculation_301", "Logo Retention %", "real", "quantitative", "measure", "p1",
         "SUM([active_customers]) / SUM([cohort_customers])", True),
        ("Calculation_302", "Net Revenue Retention %", "real", "quantitative", "measure", "p1",
         "SUM([retained_mrr]) / SUM([cohort_initial_mrr])", True),
        ("Calculation_303", "Cohort Metric", "real", "quantitative", "measure", "p1",
         "IF [Parameters].[Parameter 1] = 'Logo Retention' "
         "THEN SUM([active_customers]) / SUM([cohort_customers]) "
         "ELSE SUM([retained_mrr]) / SUM([cohort_initial_mrr]) END", True),
    ],
    "ttm": [
        ("Calculation_601", "Net Revenue Retention (TTM)", "real", "quantitative", "measure", "p1",
         "SUM([retained_mrr]) / SUM([base_mrr])", True),
        ("Calculation_602", "Gross Revenue Retention (TTM)", "real", "quantitative", "measure", "p1",
         "SUM([retained_mrr_capped]) / SUM([base_mrr])", True),
        ("Calculation_603", "Logo Retention (TTM)", "real", "quantitative", "measure", "p1",
         "SUM([retained_customers]) / SUM([base_customers])", True),
        ("Calculation_604", "Expansion Above Base (TTM)", "real", "quantitative", "measure", "$#,##0",
         "SUM([retained_mrr]) - SUM([retained_mrr_capped])", True),
    ],
    "hea": [
        ("Calculation_401", "90-Day Churn Rate", "real", "quantitative", "measure", "p1",
         "AVG([churned_within_90_days])", True),
        ("Calculation_402", "Seat Utilisation", "real", "quantitative", "measure", "p1",
         "SUM([active_users]) / SUM([licensed_seats])", True),
        ("Calculation_403", "MRR at Risk", "real", "quantitative", "measure", "$#,##0",
         "SUM(IIF([risk_tier] = 'At Risk' OR [risk_tier] = 'Critical', [mrr], 0))", True),
    ],
    "dim": [
        ("Calculation_501", "Active Customers", "integer", "quantitative", "measure", None,
         "COUNTD(IF [is_active] = 1 THEN [customer_id] END)", True),
        ("Calculation_502", "Average Revenue per Account", "real", "quantitative", "measure", "$#,##0",
         "SUM([current_mrr]) / COUNTD(IF [is_active] = 1 THEN [customer_id] END)", True),
        ("Calculation_503", "Net Expansion Ratio", "real", "quantitative", "measure", "n2",
         "AVG([net_expansion_ratio])", True),
    ],
}

SEGMENT_COLOURS = {"Enterprise": "#1f4e79", "Mid-Market": "#2e75b6", "SMB": "#9dc3e6"}
MOVEMENT_COLOURS = {
    "New": "#2e7d32", "Expansion": "#66bb6a", "Reactivation": "#a5d6a7",
    "Contraction": "#ef9a9a", "Churn": "#c62828", "Retained": "#bdbdbd",
}
RISK_COLOURS = {"Healthy": "#2e7d32", "Watch": "#f9a825", "At Risk": "#ef6c00", "Critical": "#c62828"}


def uid(label: str) -> str:
    return "{" + str(uuid.uuid5(NS, label)) + "}"


def a(value) -> str:
    return quoteattr(str(value))


def schema(con, table):
    return con.execute(f"describe {table}").fetchall()


def base_type(duck_type: str):
    key = duck_type.split("(")[0].upper()
    return TYPE_MAP.get(key, TYPE_MAP["VARCHAR"])


def datasource_xml(key, caption, table, columns) -> str:
    ds = f"federated.{key}"
    conn = f"textscan.{key}"
    filename = f"{table}.csv"
    parts = [
        f"    <datasource caption={a(caption)} inline='true' name={a(ds)} version='18.1'>",
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
        local_type, remote_type, aggregation, _role, _ctype = base_type(duck_type)
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

    for name in DIMENSION_OVERRIDES.get(key, []):
        duck_type = dict((c[0], c[1]) for c in columns)[name]
        local_type, *_ = base_type(duck_type)
        parts.append(
            f"      <column datatype='{local_type}' name='[{name}]' role='dimension' type='ordinal' />"
        )
    for calc_name, calc_caption, datatype, ctype, role, fmt, formula, _agg in CALCS.get(key, []):
        fmt_attr = f" default-format={a(fmt)}" if fmt else ""
        parts += [
            f"      <column caption={a(calc_caption)} datatype='{datatype}'{fmt_attr} name='[{calc_name}]' "
            f"role='{role}' type='{ctype}'>",
            f"        <calculation class='tableau' formula={a(formula)} />",
            "      </column>",
        ]
    parts.append("    </datasource>")
    return "\n".join(parts)


def parameters_xml() -> str:
    return "\n".join([
        "    <datasource hasconnection='false' inline='true' name='Parameters' version='18.1'>",
        "      <aliases enabled='yes' />",
        "      <column caption='Cohort Metric' datatype='string' name='[Parameter 1]' param-domain-type='list' "
        "role='measure' type='nominal' value='&quot;Logo Retention&quot;'>",
        "        <calculation class='tableau' formula='&quot;Logo Retention&quot;' />",
        "        <members>",
        "          <member value='&quot;Logo Retention&quot;' />",
        "          <member value='&quot;Net Revenue Retention&quot;' />",
        "        </members>",
        "      </column>",
        "    </datasource>",
    ])


def dep_column(name, datatype, role, ctype):
    return f"          <column datatype='{datatype}' name='[{name}]' role='{role}' type='{ctype}' />"


def dep_calc(key, calc_name):
    for name, caption, datatype, ctype, role, fmt, formula, _agg in CALCS[key]:
        if name == calc_name:
            fmt_attr = f" default-format={a(fmt)}" if fmt else ""
            return "\n".join([
                f"          <column caption={a(caption)} datatype='{datatype}'{fmt_attr} name='[{name}]' "
                f"role='{role}' type='{ctype}'>",
                f"            <calculation class='tableau' formula={a(formula)} />",
                "          </column>",
            ])
    raise KeyError(calc_name)


def dep_instance(column, derivation, name, ctype):
    return (f"          <column-instance column='[{column}]' derivation='{derivation}' name='[{name}]' "
            f"pivot='key' type='{ctype}' />")


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
    parts += [
        "          <aggregation value='true' />",
        "        </view>",
    ]
    if style:
        parts.append(style)
    else:
        parts.append("      <style />")
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
    zone_xml = []
    zone_id = 3
    zone_xml.append("\n".join([
        "        <zone h='7000' id='2' type-v2='text' w='100000' x='0' y='0'>",
        "          <formatted-text>",
        f"            <run bold='true' fontsize='16'>{escape(title)}</run>",
        "            <run>&#13;&#10;</run>",
        f"            <run fontcolor='#5a5a5a' fontsize='10'>{escape(subtitle)}</run>",
        "          </formatted-text>",
        "        </zone>",
    ]))
    for sheet_name, x, y, w, h in zones:
        zone_xml.append(
            f"        <zone h='{h}' id='{zone_id}' name={a(sheet_name)} w='{w}' x='{x}' y='{y}' />"
        )
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


def main() -> None:
    con = duckdb.connect(str(ROOT / "data" / "warehouse.duckdb"), read_only=True)
    columns = {key: schema(con, table) for key, _caption, table in SOURCES}
    con.close()

    datasources = [parameters_xml()]
    for key, caption, table in SOURCES:
        datasources.append(datasource_xml(key, caption, table, columns[key]))

    sheets = []

    # 1. MRR trend ------------------------------------------------------------------
    deps = "\n".join([
        "          <datasource-dependencies datasource='federated.mrr'>",
        dep_column("month", "date", "dimension", "ordinal"),
        dep_column("segment", "string", "dimension", "nominal"),
        dep_column("mrr", "real", "measure", "quantitative"),
        dep_instance("month", "Month", "tmn:month:qk", "quantitative"),
        dep_instance("segment", "None", "none:segment:nk", "nominal"),
        dep_instance("mrr", "Sum", "sum:mrr:qk", "quantitative"),
        "          </datasource-dependencies>",
    ])
    sheets.append(worksheet(
        "MRR Trend by Segment", "MRR Movement", "federated.mrr", deps, "Area",
        "[federated.mrr].[sum:mrr:qk]", "[federated.mrr].[tmn:month:qk]",
        [("color", "[federated.mrr].[none:segment:nk]")],
        style=palette_style("federated.mrr", "none:segment:nk", SEGMENT_COLOURS),
    ))

    # 2. MRR movement bridge --------------------------------------------------------
    deps = "\n".join([
        "          <datasource-dependencies datasource='federated.mrr'>",
        dep_column("month", "date", "dimension", "ordinal"),
        dep_column("movement_type", "string", "dimension", "nominal"),
        dep_column("new_mrr", "real", "measure", "quantitative"),
        dep_column("expansion_mrr", "real", "measure", "quantitative"),
        dep_column("reactivation_mrr", "real", "measure", "quantitative"),
        dep_column("contraction_mrr", "real", "measure", "quantitative"),
        dep_column("churned_mrr", "real", "measure", "quantitative"),
        dep_calc("mrr", "Calculation_101"),
        dep_instance("month", "Month", "tmn:month:qk", "quantitative"),
        dep_instance("movement_type", "None", "none:movement_type:nk", "nominal"),
        dep_instance("Calculation_101", "Sum", "sum:Calculation_101:qk", "quantitative"),
        "          </datasource-dependencies>",
    ])
    sheets.append(worksheet(
        "MRR Movement Bridge", "MRR Movement", "federated.mrr", deps, "Bar",
        "[federated.mrr].[sum:Calculation_101:qk]", "[federated.mrr].[tmn:month:qk]",
        [("color", "[federated.mrr].[none:movement_type:nk]")],
        style=palette_style("federated.mrr", "none:movement_type:nk", MOVEMENT_COLOURS),
    ))

    # 3. Trailing-twelve-month retention -------------------------------------------
    deps = "\n".join([
        "          <datasource-dependencies datasource='federated.ttm'>",
        dep_column("month", "date", "dimension", "ordinal"),
        dep_column("segment", "string", "dimension", "nominal"),
        dep_column("base_mrr", "real", "measure", "quantitative"),
        dep_column("retained_mrr", "real", "measure", "quantitative"),
        dep_column("retained_mrr_capped", "real", "measure", "quantitative"),
        dep_calc("ttm", "Calculation_601"),
        dep_instance("month", "Month", "tmn:month:qk", "quantitative"),
        dep_instance("segment", "None", "none:segment:nk", "nominal"),
        dep_instance("Calculation_601", "User", "usr:Calculation_601:qk", "quantitative"),
        "          </datasource-dependencies>",
    ])
    sheets.append(worksheet(
        "Net Revenue Retention (TTM)", "Retention TTM", "federated.ttm", deps, "Line",
        "[federated.ttm].[usr:Calculation_601:qk]", "[federated.ttm].[tmn:month:qk]",
        [("color", "[federated.ttm].[none:segment:nk]")],
        style=palette_style("federated.ttm", "none:segment:nk", SEGMENT_COLOURS),
    ))

    # 4. Cohort retention triangle ---------------------------------------------------
    deps = "\n".join([
        "          <datasource-dependencies datasource='federated.coh'>",
        dep_column("cohort_month", "date", "dimension", "ordinal"),
        dep_column("period_index", "integer", "dimension", "ordinal"),
        dep_column("active_customers", "integer", "measure", "quantitative"),
        dep_column("cohort_customers", "integer", "measure", "quantitative"),
        dep_column("retained_mrr", "real", "measure", "quantitative"),
        dep_column("cohort_initial_mrr", "real", "measure", "quantitative"),
        dep_calc("coh", "Calculation_303"),
        dep_instance("cohort_month", "MonthYear", "my:cohort_month:ok", "ordinal"),
        dep_instance("period_index", "None", "none:period_index:ok", "ordinal"),
        dep_instance("Calculation_303", "User", "usr:Calculation_303:qk", "quantitative"),
        "          </datasource-dependencies>",
        "          <datasource-dependencies datasource='Parameters'>",
        "            <column caption='Cohort Metric' datatype='string' name='[Parameter 1]' "
        "param-domain-type='list' role='measure' type='nominal' value='&quot;Logo Retention&quot;'>",
        "              <calculation class='tableau' formula='&quot;Logo Retention&quot;' />",
        "              <members>",
        "                <member value='&quot;Logo Retention&quot;' />",
        "                <member value='&quot;Net Revenue Retention&quot;' />",
        "              </members>",
        "            </column>",
        "          </datasource-dependencies>",
    ])
    sheets.append(worksheet(
        "Cohort Retention Triangle", "Cohort Retention", "federated.coh", deps, "Square",
        "[federated.coh].[my:cohort_month:ok]", "[federated.coh].[none:period_index:ok]",
        [("color", "[federated.coh].[usr:Calculation_303:qk]"),
         ("text", "[federated.coh].[usr:Calculation_303:qk]")],
        extra_datasources=("Parameters",),
    ))

    # 5. Churn reasons ---------------------------------------------------------------
    deps = "\n".join([
        "          <datasource-dependencies datasource='federated.mrr'>",
        dep_column("churn_reason", "string", "dimension", "nominal"),
        dep_column("movement_type", "string", "dimension", "nominal"),
        dep_column("segment", "string", "dimension", "nominal"),
        dep_column("churned_mrr", "real", "measure", "quantitative"),
        dep_instance("churn_reason", "None", "none:churn_reason:nk", "nominal"),
        dep_instance("movement_type", "None", "none:movement_type:nk", "nominal"),
        dep_instance("segment", "None", "none:segment:nk", "nominal"),
        dep_instance("churned_mrr", "Sum", "sum:churned_mrr:qk", "quantitative"),
        "          </datasource-dependencies>",
    ])
    sheets.append(worksheet(
        "Churned MRR by Reason", "MRR Movement", "federated.mrr", deps, "Bar",
        "[federated.mrr].[none:churn_reason:nk]", "[federated.mrr].[sum:churned_mrr:qk]",
        [("color", "[federated.mrr].[none:segment:nk]")],
        filters=[categorical_filter("federated.mrr", "none:movement_type:nk", ['"Churn"'])],
        style=palette_style("federated.mrr", "none:segment:nk", SEGMENT_COLOURS),
    ))

    # 6. Health tier vs future churn --------------------------------------------------
    deps = "\n".join([
        "          <datasource-dependencies datasource='federated.hea'>",
        dep_column("risk_tier", "string", "dimension", "nominal"),
        dep_column("risk_tier_rank", "integer", "dimension", "ordinal"),
        dep_column("churned_within_90_days", "integer", "measure", "quantitative"),
        dep_calc("hea", "Calculation_401"),
        dep_instance("risk_tier", "None", "none:risk_tier:nk", "nominal"),
        dep_instance("risk_tier_rank", "None", "none:risk_tier_rank:ok", "ordinal"),
        dep_instance("Calculation_401", "User", "usr:Calculation_401:qk", "quantitative"),
        "          </datasource-dependencies>",
    ])
    sheets.append(worksheet(
        "Churn Risk by Health Tier", "Account Health", "federated.hea", deps, "Bar",
        "[federated.hea].[usr:Calculation_401:qk]",
        "([federated.hea].[none:risk_tier_rank:ok] / [federated.hea].[none:risk_tier:nk])",
        [("color", "[federated.hea].[none:risk_tier:nk]"),
         ("text", "[federated.hea].[usr:Calculation_401:qk]")],
        style=palette_style("federated.hea", "none:risk_tier:nk", RISK_COLOURS),
    ))

    # 7. Account matrix ----------------------------------------------------------------
    deps = "\n".join([
        "          <datasource-dependencies datasource='federated.dim'>",
        dep_column("customer_id", "string", "dimension", "nominal"),
        dep_column("company_name", "string", "dimension", "nominal"),
        dep_column("latest_risk_tier", "string", "dimension", "nominal"),
        dep_column("segment", "string", "dimension", "nominal"),
        dep_column("is_active", "integer", "dimension", "ordinal"),
        dep_column("avg_seat_utilization", "real", "measure", "quantitative"),
        dep_column("current_mrr", "real", "measure", "quantitative"),
        dep_instance("customer_id", "None", "none:customer_id:nk", "nominal"),
        dep_instance("latest_risk_tier", "None", "none:latest_risk_tier:nk", "nominal"),
        dep_instance("is_active", "None", "none:is_active:ok", "ordinal"),
        dep_instance("avg_seat_utilization", "Avg", "avg:avg_seat_utilization:qk", "quantitative"),
        dep_instance("current_mrr", "Sum", "sum:current_mrr:qk", "quantitative"),
        "          </datasource-dependencies>",
    ])
    sheets.append(worksheet(
        "Account Matrix", "Customer Dimension", "federated.dim", deps, "Circle",
        "[federated.dim].[sum:current_mrr:qk]", "[federated.dim].[avg:avg_seat_utilization:qk]",
        [("color", "[federated.dim].[none:latest_risk_tier:nk]"),
         ("size", "[federated.dim].[sum:current_mrr:qk]"),
         ("text", "[federated.dim].[none:customer_id:nk]")],
        filters=[categorical_filter("federated.dim", "none:is_active:ok", ["1"])],
        style=palette_style("federated.dim", "none:latest_risk_tier:nk", RISK_COLOURS),
    ))

    # 8. Account watchlist --------------------------------------------------------------
    deps = "\n".join([
        "          <datasource-dependencies datasource='federated.dim'>",
        dep_column("company_name", "string", "dimension", "nominal"),
        dep_column("segment", "string", "dimension", "nominal"),
        dep_column("latest_plan_name", "string", "dimension", "nominal"),
        dep_column("latest_risk_tier", "string", "dimension", "nominal"),
        dep_column("is_active", "integer", "dimension", "ordinal"),
        dep_column("current_mrr", "real", "measure", "quantitative"),
        dep_instance("company_name", "None", "none:company_name:nk", "nominal"),
        dep_instance("segment", "None", "none:segment:nk", "nominal"),
        dep_instance("latest_plan_name", "None", "none:latest_plan_name:nk", "nominal"),
        dep_instance("latest_risk_tier", "None", "none:latest_risk_tier:nk", "nominal"),
        dep_instance("is_active", "None", "none:is_active:ok", "ordinal"),
        dep_instance("current_mrr", "Sum", "sum:current_mrr:qk", "quantitative"),
        "          </datasource-dependencies>",
    ])
    sheets.append(worksheet(
        "Account Watchlist", "Customer Dimension", "federated.dim", deps, "Text",
        "([federated.dim].[none:latest_risk_tier:nk] / [federated.dim].[none:segment:nk] / "
        "[federated.dim].[none:company_name:nk])",
        "[federated.dim].[sum:current_mrr:qk]",
        [("text", "[federated.dim].[sum:current_mrr:qk]"),
         ("color", "[federated.dim].[none:latest_risk_tier:nk]")],
        filters=[
            categorical_filter("federated.dim", "none:is_active:ok", ["1"]),
            categorical_filter("federated.dim", "none:latest_risk_tier:nk", ['"At Risk"', '"Critical"']),
        ],
        style=palette_style("federated.dim", "none:latest_risk_tier:nk", RISK_COLOURS),
    ))

    dashboards = [
        dashboard(
            "1 · Executive Summary",
            "Executive Summary",
            "MRR, where it came from, and retention.",
            [("MRR Trend by Segment", 0, 7000, 100000, 44000),
             ("MRR Movement Bridge", 0, 51000, 55000, 49000),
             ("Net Revenue Retention (TTM)", 55000, 51000, 45000, 49000)],
        ),
        dashboard(
            "2 · Retention & Churn",
            "Retention & Churn",
            "Cohort retention, churn reasons and churn by health tier.",
            [("Cohort Retention Triangle", 0, 7000, 100000, 52000),
             ("Churned MRR by Reason", 0, 59000, 55000, 41000),
             ("Churn Risk by Health Tier", 55000, 59000, 45000, 41000)],
        ),
        dashboard(
            "3 · Account Health",
            "Account Health",
            "Active accounts by usage and revenue, and the at-risk list.",
            [("Account Matrix", 0, 7000, 58000, 93000),
             ("Account Watchlist", 58000, 7000, 42000, 93000)],
        ),
    ]

    windows = ["  <windows source-height='30'>"]
    for sheet in ["MRR Trend by Segment", "MRR Movement Bridge", "Net Revenue Retention (TTM)",
                  "Cohort Retention Triangle", "Churned MRR by Reason", "Churn Risk by Health Tier",
                  "Account Matrix", "Account Watchlist"]:
        windows += [
            f"    <window class='worksheet' name={a(sheet)}>",
            "      <viewpoint><zoom type='entire-view' /></viewpoint>",
            f"      <simple-id uuid={a(uid('win:' + sheet))} />",
            "    </window>",
        ]
    for dash in ["1 · Executive Summary", "2 · Retention & Churn", "3 · Account Health"]:
        windows += [
            f"    <window class='dashboard' name={a(dash)}>",
            "      <active id='-1' />",
            f"      <simple-id uuid={a(uid('win:' + dash))} />",
            "    </window>",
        ]
    windows.append("  </windows>")

    document = "\n".join([
        "<?xml version='1.0' encoding='utf-8' ?>",
        "<!-- build 20261.0 -->",
        "<workbook original-version='18.1' source-build='2022.4.0' source-platform='win' version='18.1' "
        "xmlns:user='http://www.tableausoftware.com/xml/user'>",
        "  <preferences>",
        "    <preference name='ui.encoding.shelf.height' value='24' />",
        "    <preference name='ui.shelf.height' value='26' />",
        "  </preferences>",
        "  <datasources>",
        "\n".join(datasources),
        "  </datasources>",
        "  <worksheets>",
        "\n".join(sheets),
        "  </worksheets>",
        "  <dashboards>",
        "\n".join(dashboards),
        "  </dashboards>",
        "\n".join(windows),
        "</workbook>",
        "",
    ])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(document, encoding="utf-8")
    print(f"wrote {OUT} ({len(document):,} chars)")


if __name__ == "__main__":
    main()
