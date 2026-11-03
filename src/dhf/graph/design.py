"""Pure design queries, bounded per component/unit, with explicit allocation facts.

Components and units come from code extraction or from imported design documents. Document
evidence carries no signatures, structures or safety class, so those facts read "not
recorded" with the source section named, never an invented value."""

import re

from dhf.models.values import opening_sentence
from dhf.trace import confirmed_links

NOT_RECORDED = "Not recorded in the source"


def documented_at(artifact: dict) -> str:
    """Where a document-derived design element is described. Only the heading path enters
    the facts: a re-issued but unchanged document (a new version in its file name) must not
    stale the sections; the citation link names the document itself."""
    section = artifact["attributes"].get("section", "")
    return "the design document under " + section if section else "the design document"


def design_query(graph: dict, name: str, params: dict) -> dict:
    nodes = {a["id"]: a for a in graph["artifacts"]}
    edges = confirmed_links(graph)

    def of_type(*types: str) -> list[dict]:
        return sorted((a for a in nodes.values() if a["type"] in types), key=lambda a: a["id"])

    def pack(items: list[dict], facts: dict) -> dict:
        return {"evidence": items, "facts": facts}

    def relation(ids: set[str], kind: str, direction: str = "out") -> list[dict]:
        anchor, peer = ("src", "dst") if direction == "out" else ("dst", "src")
        return [nodes[e[peer]] for e in edges if e["type"] == kind and e[anchor] in ids]

    def structure(component: str | None = None) -> dict:
        units = [
            u
            for u in of_type("software_unit")
            if component is None or u["attributes"].get("component") == component
        ]
        dependencies = []
        for unit in units:
            for call in unit["attributes"].get("import_calls", []):
                target = "UNIT-" + call.split(".")[1]
                if target in nodes:
                    dependencies.append(
                        {
                            "from_unit": unit["id"],
                            "to_unit": target,
                            "from_component": unit["attributes"].get("component", ""),
                            "to_component": nodes[target]["attributes"].get("component", ""),
                            "call": call,
                        }
                    )
        reqs = {
            a["id"]
            for a in of_type("software_req")
            if component is None or a["attributes"].get("component") == component
        }
        if component is not None:  # a documented architecture allocates via the SAD matrix
            reqs |= {
                e["src"]
                for e in edges
                if e["type"] == "allocated_to"
                and e["dst"] == component
                and nodes[e["src"]]["type"] in ("software_req", "system_req")
            }
        controls = {
            e["dst"]
            for e in edges
            if e["src"] in reqs
            and e["type"] == "implements"
            and nodes[e["dst"]]["type"] == "risk_control"
        }
        hazards = sorted(
            {e["dst"] for e in edges if e["src"] in controls and e["type"] == "mitigates"}
        )
        return {
            "hazard_controls": [
                {
                    "hazard": h,
                    "title": nodes[h]["title"],
                    "controls": sorted(
                        c
                        for c in controls
                        if any(
                            e["src"] == c and e["dst"] == h and e["type"] == "mitigates"
                            for e in edges
                        )
                    ),
                }
                for h in hazards
            ],
            "unit_allocation": [
                {
                    "unit": u["id"],
                    "component": u["attributes"].get("component", ""),
                    "interfaces": u["attributes"].get("signatures", []),
                }
                for u in units
            ],
            "dependencies": dependencies,
        }

    if name in ("design_scope", "system_context"):
        items = of_type("user_need") if name == "design_scope" else of_type("system_req")
        return pack(items, {"release": params.get("release", "1.1")})
    if name == "components":
        items = of_type("component")
        return pack(
            items,
            {
                "rows": [
                    {
                        "id": a["id"],
                        "name": a["title"],
                        "responsibility": a["attributes"].get("responsibility")
                        or opening_sentence(a["body"])
                        or NOT_RECORDED,
                        "safety_class": a["attributes"].get("safety_class", NOT_RECORDED),
                    }
                    for a in items
                ]
            },
        )
    if name == "architecture_diagram":
        items = of_type("component", "software_unit")
        ids = {a["id"] for a in items}

        def node(id: str) -> str:  # Mermaid node IDs: word characters only
            return re.sub(r"\W", "_", id)

        lines = ["flowchart LR"] + [
            f'  {node(a["id"])}["{a["id"]}: {a["title"].replace(chr(34), chr(39))}"]' for a in items
        ]
        lines += [
            f"  {node(e['src'])} -->|allocated to| {node(e['dst'])}"
            for e in edges
            if e["type"] == "allocated_to" and e["src"] in ids and e["dst"] in ids
        ]
        from pathlib import Path

        import yaml

        for interface in yaml.safe_load(
            Path("specs/render/interfaces.yaml").read_text(encoding="utf-8")
        )["interfaces"]:
            component = nodes.get(interface["component"])
            if component is None or "interfaces" not in component["attributes"]:
                continue  # declared for another product's architecture
            label = " / ".join(
                component["attributes"]["interfaces"][i] for i in interface["indices"]
            )
            lines.append(f'  {interface["id"]}["{label}"]')
            lines.append(f"  {interface['id']} -->|declared interface| {node(component['id'])}")
        for d in structure()["dependencies"]:
            lines.append(
                f"  {node(d['from_component'])} -->|{d['call']}| {node(d['to_component'])}"
            )
        return pack(
            items, {"diagram": "\n".join(lines), "diagram_format": "mermaid", **structure()}
        )
    if name in ("component_design", "component_allocation"):
        component = nodes[params["entity"]]
        requirements = relation({component["id"]}, "allocated_to", "in")
        requirements = [r for r in requirements if r["type"] in ("software_req", "system_req")]
        items = (
            [component, *requirements]
            if name == "component_allocation"
            else [
                component,
                *of_type("adr"),
                *(nodes[h["hazard"]] for h in structure(component["id"])["hazard_controls"]),
            ]
        )
        return pack(
            items,
            {
                "component": component["id"],
                **structure(component["id"]),
                "rows": [
                    {
                        "requirement": r["id"],
                        "revision": r["source"]["revision"],
                        "title": r["title"],
                    }
                    for r in requirements
                ]
                if name == "component_allocation"
                else [],
            },
        )
    if name in ("interfaces", "unit_trace"):
        items = of_type("software_unit", "component")
        units = of_type("software_unit")
        reqs = of_type("software_req") if name == "unit_trace" else []
        return pack(
            [*items, *reqs],
            {
                "rows": [
                    {
                        "unit": a["id"],
                        "component": a["attributes"].get("component", NOT_RECORDED),
                        "signatures": ["Described in " + documented_at(a)]
                        if a["source"]["system"] == "file"
                        else a["attributes"].get("signatures", []),
                        "requirements": [r["id"] for r in relation({a["id"]}, "implements")],
                    }
                    for a in units
                ]
            },
        )
    if name in ("soup_inventory", "soup_purpose"):
        items = of_type("soup")
        return pack(
            items,
            {
                "rows": [
                    {
                        "id": a["id"],
                        "name": a["title"],
                        "version": a["attributes"]["version"],
                        "requirements": [r["id"] for r in relation({a["id"]}, "depends_on", "in")],
                    }
                    for a in items
                ]
                if name == "soup_inventory"
                else []
            },
        )
    if name == "runtime_view":
        return pack(
            of_type("component", "adr", "hazard", "risk_control"),
            {"release": params.get("release", "1.1"), **structure()},
        )
    if name == "architecture_risks":
        items = of_type("hazard", "risk_control", "software_req", "component")
        return pack(
            items,
            {
                "rows": [
                    {
                        "hazard": a["id"],
                        "hazard_name": a["title"],
                        "severity": a["attributes"].get("severity", NOT_RECORDED),
                        "controls": [
                            {"id": r["id"], "title": r["title"]}
                            for r in relation({a["id"]}, "mitigates", "in")
                        ],
                    }
                    for a in of_type("hazard")
                ]
            },
        )
    if name == "architecture_matrix":
        # Every software requirement, plus the system requirements the architecture allocates.
        allocated = {e["src"] for e in edges if e["type"] == "allocated_to"}
        subjects = [
            a
            for a in of_type("system_req", "software_req")
            if a["type"] == "software_req" or a["id"] in allocated
        ]
        items = [*subjects, *of_type("component")]
        return pack(
            items,
            {
                "rows": [
                    {
                        "requirement": a["id"],
                        "revision": a["source"]["revision"],
                        "components": [r["id"] for r in relation({a["id"]}, "allocated_to")],
                    }
                    for a in subjects
                ]
            },
        )
    if name == "architectural_decisions":
        items = of_type("adr")
        return pack(items, {"rows": [{"id": a["id"], "decision": a["body"]} for a in items]})
    if name.startswith("unit_"):
        unit = nodes[params["entity"]]
        requirements = relation({unit["id"]}, "implements")
        controls = relation({r["id"] for r in requirements}, "implements")
        controls = [a for a in controls if a["type"] == "risk_control"]
        tests = relation({r["id"] for r in requirements}, "verifies", "in")
        tests = [
            a for a in tests if a["type"] == "test_case" and a["attributes"].get("level") == "unit"
        ]
        component = unit["attributes"].get("component")
        if component and component not in nodes:  # a data error, never a silent default
            raise ValueError(f"{unit['id']} names component {component}, which is not in evidence")
        items = [unit, *([nodes[component]] if component else [])]
        facts = {"unit": unit["id"], "component": component or NOT_RECORDED}
        documented = unit["source"]["system"] == "file"  # imported from a design document
        if name == "unit_identity":
            facts["rows"] = [
                facts.copy()
                | {"path": unit["attributes"].get("path") or "Described in " + documented_at(unit)}
            ]
        elif name == "unit_interfaces":
            facts["rows"] = [{"signature": s} for s in unit["attributes"].get("signatures", [])]
            if documented:
                facts["notice"] = (
                    "No code is in scope; the interface is described in "
                    + documented_at(unit)
                    + "."
                )
        elif name == "unit_structures":
            facts["rows"] = [
                {"name": s["name"], "bases": s["bases"], "fields": s["fields"]}
                if isinstance(s, dict)
                else {"name": s.split("=", 1)[0].strip(), "bases": "Module value", "fields": s}
                for s in unit["attributes"].get("data_structures", [])
            ]
            if documented:
                facts["notice"] = (
                    "No code is in scope; the internal structure is described in "
                    + documented_at(unit)
                    + "."
                )
        elif name == "unit_allocation":
            items += [*requirements, *controls]
            facts["rows"] = [
                {
                    "requirement": r["id"],
                    "revision": r["source"]["revision"],
                    "controls": [
                        c["id"]
                        for c in relation({r["id"]}, "implements")
                        if c["type"] == "risk_control"
                    ],
                }
                for r in requirements
            ]
            if documented and not requirements:
                facts["notice"] = (
                    "The design documents record no unit-level allocation; requirements are "
                    "allocated to software items in the architecture matrix."
                )
        elif name == "unit_tests":
            items += tests
            facts["rows"] = [{"test": a["id"], "title": a["title"]} for a in tests]
            facts["notice"] = "" if tests else "No explicitly traced unit test case is recorded."
        elif name in ("unit_purpose", "unit_behavior", "unit_errors"):
            # Code source is authoritative; avoid duplicating requirements across every prompt.
            facts["allocated_requirements"] = [r["id"] for r in requirements]
        else:
            raise ValueError("Unknown unit query: " + name)
        return pack(items, facts)
    raise ValueError("Unknown design query: " + name)
