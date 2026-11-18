"""Office-laptop preflight for the real project; prints no secrets and writes nothing.

Usage: uv run python tools/office_check.py [--online]
--online also makes one read-only ADO request to prove the PAT and project are right.
"""

import os
import shutil
import sys
from pathlib import Path
from urllib.parse import urlsplit

from dhf.config import setting

problems: list[str] = []


def check(ok: bool, label: str, fix: str = "") -> bool:
    print(("  OK   " if ok else "  FIX  ") + label)
    if not ok:
        print("         -> " + fix)
        problems.append(label)
    return ok


def main() -> int:
    online = "--online" in sys.argv[1:]
    env_file = Path(os.environ.get("DHF_ENV_FILE", ".env"))

    print("Tools")
    check(sys.version_info >= (3, 12), f"Python {sys.version.split()[0]}", "Run with: uv run ...")
    check(shutil.which("git") is not None, "git installed", "Install Git (see README)")
    check(Path("src/dhf").is_dir(), "running from the repository folder", "cd into the A-C folder")

    print("Settings file")
    check(env_file.is_file(), f"settings file {env_file}", "Copy .env.example to .env")

    print("Azure DevOps (read-only)")
    base = setting("ADO_BASE_URL")
    host = urlsplit(base).hostname or ""
    real = check(
        base.startswith("https://") and host not in ("localhost", "127.0.0.1"),
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
    check(Path(mapping).is_file(), f"ADO_MAPPING file exists ({mapping})", "Run step 4 (discover)")
    if mapping == "specs/ado_mapping.yaml":
        print("         note: still the synthetic Kestrel mapping; point it at the reviewed")
        print("               real profile after discovery (guide step 4)")

    print("Copilot Studio drafting (BD tenant)")
    check(
        setting("DHF_PROVIDER") == "copilotstudio",
        "DHF_PROVIDER=copilotstudio",
        "Set DHF_PROVIDER=copilotstudio (personal API keys never receive company data)",
    )
    check(
        bool(setting("DHF_REAL_DATA_APPROVAL").strip()),
        "DHF_REAL_DATA_APPROVAL records the BD clearance",
        "Set it to the clearance reference (e.g. the approval email subject and date)",
    )
    mode = setting("DHF_COPILOT_MODE", "http")
    if mode == "http":
        check(
            setting("DHF_COPILOT_FLOW_URL").startswith("https://"),
            "DHF_COPILOT_FLOW_URL is an https flow URL",
            "Paste the HTTP trigger URL from Power Automate (guide step 6)",
        )
    else:
        exchange = setting("DHF_COPILOT_EXCHANGE_DIR")
        check(
            bool(exchange) and Path(exchange).is_dir(),
            "DHF_COPILOT_EXCHANGE_DIR folder exists",
            "Point it at the OneDrive-synced exchange folder",
        )
    check(
        setting("DHF_COPILOT_USAGE", "reported") in ("reported", "estimated"),
        "DHF_COPILOT_USAGE is reported or estimated",
        "Set DHF_COPILOT_USAGE=estimated unless the flow returns token counts",
    )
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        check(
            not setting(name),
            f"{name} is empty on this laptop",
            "Remove personal API keys from the office laptop settings",
        )
    if setting("DHF_TEMPLATE_SET") != "bd":
        print("  note DHF_TEMPLATE_SET is not bd; drafts use generic IEC 62304 headings")

    if online and real and not problems:
        print("Online check (one read-only request)")
        from dhf.ingest.ado import ADO

        ado = ADO()
        try:
            types = ado.request("GET", "/_apis/wit/workitemtypes").get("value", [])
            check(True, f"ADO answered: {len(types)} work-item types in the project")
        except Exception as exc:  # Report the class only; messages can echo URLs.
            check(False, f"ADO request failed ({type(exc).__name__})", "Check URL, project, PAT")
        finally:
            ado.close()

    print()
    if problems:
        print(f"{len(problems)} item(s) to fix before running the real project.")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
