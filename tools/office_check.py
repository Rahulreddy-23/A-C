"""Office-laptop preflight for the real project; prints no secrets and writes nothing.

Usage: uv run python tools/office_check.py [--online]
--online also makes one read-only ADO request to prove the PAT and project are right.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path
from urllib.parse import urlsplit

from dhf.config import setting
from dhf.llm.adapters.copilotstudio import destination_fingerprint

problems: list[str] = []


def check(ok: bool, label: str, fix: str = "") -> bool:
    print(("  OK   " if ok else "  FIX  ") + label)
    if not ok:
        print("         -> " + fix)
        problems.append(label)
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check office-laptop settings without exposing credentials."
    )
    parser.add_argument("--online", action="store_true", help="make one read-only ADO request")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--ado-only", action="store_true", help="check ADO before the flow is set up")
    mode.add_argument(
        "--destination-fingerprint",
        action="store_true",
        help="print only the Copilot destination fingerprint",
    )
    options = parser.parse_args()
    if options.destination_fingerprint:
        try:
            print(destination_fingerprint())
        except ValueError as exc:
            parser.exit(1, str(exc) + "\n")
        return 0
    problems.clear()
    env_file = Path(os.environ.get("DHF_ENV_FILE", ".env"))

    print("Tools")
    check(sys.version_info >= (3, 12), f"Python {sys.version.split()[0]}", "Run with: uv run ...")
    check(shutil.which("git") is not None, "git installed", "Install Git (see README)")
    check(Path("src/dhf").is_dir(), "running from the repository folder", "cd into the A-C folder")

    print("Settings file")
    check(env_file.is_file(), f"settings file {env_file}", "Copy .env.example to .env")

    print("Azure DevOps (read-only)")
    base = setting("ADO_BASE_URL")
    try:
        parsed = urlsplit(base)
        host = parsed.hostname or ""
        real_ado = (
            parsed.scheme == "https"
            and (host == "dev.azure.com" or host.endswith(".visualstudio.com"))
            and parsed.username is None
            and parsed.port in (None, 443)
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        real_ado = False
    real = check(
        real_ado,
        "ADO_BASE_URL points at the real organization",
        "Set ADO_BASE_URL=https://dev.azure.com/<organization>",
    )
    check(
        setting("ADO_PROJECT") not in ("", "Kestrel"),
        "ADO_PROJECT is the real project",
        "Set ADO_PROJECT to the project name",
    )
    check(
        setting("APP_ADO_PAT") not in ("", "mock-app-token"),
        "APP_ADO_PAT is set",
        "Paste the read-only PAT",
    )
    check(
        setting("ADO_READ_ONLY", "auto").lower() not in ("0", "false", "no", "off"),
        "ADO_READ_ONLY keeps the organization read-only",
        "Set ADO_READ_ONLY=auto",
    )
    scope = setting("ADO_SCOPE")
    check(
        bool(scope) and Path(scope).is_file(),
        "ADO_SCOPE file exists",
        "Copy specs/ado_scope.example.yaml to out/real/scope.yaml and set ADO_SCOPE",
    )
    mapping = setting("ADO_MAPPING", "specs/ado_mapping.yaml")
    check(Path(mapping).is_file(), "ADO_MAPPING file exists", "Run step 4 (discover)")
    if mapping == "specs/ado_mapping.yaml":
        print("         note: still the synthetic Kestrel mapping; point it at the reviewed")
        print("               real profile after discovery (guide step 4)")

    if not options.ado_only:
        check_copilot()

    if options.online and real and not problems:
        print("Online check (one read-only request)")
        from dhf.ingest.ado import ADO

        try:
            ado = ADO()
            try:
                types = ado.request("GET", "/_apis/wit/workitemtypes").get("value", [])
            finally:
                ado.close()
            check(True, f"ADO answered: {len(types)} work-item types in the project")
        except Exception as exc:  # Some exception messages include URLs.
            check(False, f"ADO request failed ({type(exc).__name__})", "Check URL, project, PAT")

    print()
    if problems:
        print(f"{len(problems)} item(s) to fix before running the real project.")
        return 1
    print("All checks passed.")
    return 0


def check_copilot() -> None:
    print("Copilot Studio drafting (BD tenant)")
    check(
        setting("DHF_PROVIDER") == "copilotstudio",
        "DHF_PROVIDER=copilotstudio",
        "Set DHF_PROVIDER=copilotstudio",
    )
    check(
        bool(setting("DHF_REAL_DATA_APPROVAL").strip()),
        "DHF_REAL_DATA_APPROVAL records the BD clearance",
        "Set it to the clearance reference",
    )
    try:
        fingerprint = destination_fingerprint()
    except ValueError as exc:
        check(False, "Copilot destination is valid", str(exc))
    else:
        check(
            fingerprint == setting("DHF_REAL_DATA_DESTINATION_SHA256").strip().lower(),
            "Copilot destination matches the recorded clearance",
            "Verify the flow or folder with the BD owner, then record its fingerprint",
        )
    check(
        setting("DHF_COPILOT_USAGE", "reported") in ("reported", "estimated"),
        "DHF_COPILOT_USAGE is reported or estimated",
        "Set DHF_COPILOT_USAGE=estimated unless the flow returns token counts",
    )
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        check(not setting(name), f"{name} is empty on this laptop", "Remove personal API keys")
    if setting("DHF_TEMPLATE_SET") != "bd":
        print("  note DHF_TEMPLATE_SET is not bd; drafts use generic IEC 62304 headings")


if __name__ == "__main__":
    sys.exit(main())
