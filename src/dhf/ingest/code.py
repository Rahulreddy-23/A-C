"""AST extraction boundary; additional languages can implement CodeExtractor."""

import ast
import hashlib
import re
from pathlib import Path
from typing import Protocol

import yaml

from dhf.llm import canonical


class CodeExtractor(Protocol):
    def extract(self, files: dict[str, str], source_url: str, retrieved_at: str) -> dict: ...


class PythonExtractor:
    def extract(self, files: dict[str, str], source_url: str, retrieved_at: str) -> dict:
        artifacts = []
        links = []
        architecture = yaml.safe_load(files.get("architecture.yaml", "[]")) or []
        synthetic = bool(architecture) and all(
            a.get("attributes", {}).get("synthetic") is True for a in architecture
        )
        for path, code in sorted(files.items()):
            if (
                not path.startswith("kestrel/")
                or not path.endswith(".py")
                or path.endswith("__init__.py")
            ):
                continue
            marker = re.search(r"# DHF-COMPONENT: (COMP-\d+)", code)
            if not marker:
                continue
            component = marker[1]
            tree = ast.parse(code)
            signatures = [
                ast.unparse(node).split(":\n", 1)[0]
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            structures = [
                ast.unparse(n)
                for n in tree.body
                if isinstance(n, (ast.ClassDef, ast.Assign, ast.AnnAssign))
            ]
            unit = "UNIT-" + Path(path).stem
            body = code.split("\n", 1)[1].rstrip()
            blob = hashlib.sha1(f"blob {len(code.encode())}\0".encode() + code.encode()).hexdigest()
            artifacts.append(
                {
                    "id": unit,
                    "type": "software_unit",
                    "title": Path(path).stem,
                    "body": body,
                    "attributes": {
                        "synthetic": synthetic,
                        "component": component,
                        "path": path,
                        "signatures": signatures,
                        "data_structures": structures,
                    },
                    "source": {
                        "system": "git",
                        "url": source_url + "?path=/" + path + "&version=GBmain",
                        "native_id": path,
                        "revision": blob,
                        "retrieved_at": retrieved_at,
                    },
                }
            )
            links.append(
                {
                    "src": unit,
                    "dst": component,
                    "type": "allocated_to",
                    "origin": "explicit",
                    "evidence": "DHF-COMPONENT source annotation",
                }
            )
        if "requirements.txt" in files:
            for i, line in enumerate(files["requirements.txt"].splitlines(), 1):
                if "==" not in line:
                    continue
                name, version = line.strip().split("==", 1)
                artifacts.append(
                    {
                        "id": f"SOUP-{i:02}",
                        "type": "soup",
                        "title": name,
                        "body": name,
                        "attributes": {"synthetic": synthetic, "version": version},
                        "source": {
                            "system": "git",
                            "url": source_url + "?path=/requirements.txt",
                            "native_id": name,
                            "revision": hashlib.sha256(line.encode()).hexdigest(),
                            "retrieved_at": retrieved_at,
                        },
                    }
                )
        if "architecture.yaml" in files:
            for item in yaml.safe_load(files["architecture.yaml"]):
                artifacts.append(
                    {
                        **item,
                        "source": {
                            "system": "git",
                            "url": source_url + "?path=/architecture.yaml",
                            "native_id": item["id"],
                            "revision": hashlib.sha256(canonical(item).encode()).hexdigest(),
                            "retrieved_at": retrieved_at,
                        },
                    }
                )
        return {"artifacts": artifacts, "links": links}
