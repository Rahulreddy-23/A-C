"""Pure design queries, bounded per component/unit, with explicit allocation facts."""

from dhf.trace import confirmed_links


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
            if component is None or u["attributes"]["component"] == component
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
                            "from_component": unit["attributes"]["component"],
                            "to_component": nodes[target]["attributes"]["component"],
                            "call": call,
                        }
                    )
        reqs = {
            a["id"]
            for a in of_type("software_req")
            if component is None or a["attributes"].get("component") == component
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
                    "component": u["attributes"]["component"],
                    "interfaces": u["attributes"]["signatures"],
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
                        "responsibility": a["attributes"]["responsibility"],
                        "safety_class": a["attributes"]["safety_class"],
                    }
                    for a in items
                ]
            },
        )
    if name == "architecture_diagram":
        items = of_type("component", "software_unit")
        ids = {a["id"] for a in items}
        lines = ["flowchart LR"] + [
            f'  {a["id"].replace("-", "_")}["{a["id"]}: {a["title"].replace(chr(34), chr(39))}"]'
            for a in items
        ]
        lines += [
            f"  {e['src'].replace('-', '_')} -->|allocated to| {e['dst'].replace('-', '_')}"
            for e in edges
            if e["type"] == "allocated_to" and e["src"] in ids and e["dst"] in ids
        ]
        for d in structure()["dependencies"]:
            lines.append(
                f"  {d['from_component'].replace('-', '_')} -->|{d['call']}| "
                f"{d['to_component'].replace('-', '_')}"
            )
        return pack(
            items, {"diagram": "\n".join(lines), "diagram_format": "mermaid", **structure()}
        )
    if name in ("component_design", "component_allocation"):
        component = nodes[params["entity"]]
        requirements = relation({component["id"]}, "allocated_to", "in")
        requirements = [r for r in requirements if r["type"] == "software_req"]
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
                        "component": a["attributes"]["component"],
                        "signatures": a["attributes"]["signatures"],
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
                        "severity": a["attributes"]["severity"],
                        "controls": [r["id"] for r in relation({a["id"]}, "mitigates", "in")],
                    }
                    for a in of_type("hazard")
                ]
            },
        )
    if name == "architecture_matrix":
        items = of_type("software_req", "component")
        return pack(
            items,
            {
                "rows": [
                    {
                        "requirement": a["id"],
                        "revision": a["source"]["revision"],
                        "components": [r["id"] for r in relation({a["id"]}, "allocated_to")],
                    }
                    for a in of_type("software_req")
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
        items = [unit, nodes[unit["attributes"]["component"]]]
        facts = {"unit": unit["id"], "component": unit["attributes"]["component"]}
        if name == "unit_identity":
            facts["rows"] = [facts.copy() | {"path": unit["attributes"]["path"]}]
        elif name == "unit_interfaces":
            facts["rows"] = [{"signature": s} for s in unit["attributes"]["signatures"]]
        elif name == "unit_structures":
            facts["rows"] = [{"structure": s} for s in unit["attributes"]["data_structures"]]
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
