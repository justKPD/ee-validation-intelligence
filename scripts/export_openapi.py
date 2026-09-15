"""Export the API's OpenAPI schema and a Markdown endpoint reference into docs/api/."""

from __future__ import annotations

import json
from pathlib import Path

from ee_api.main import create_app

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    schema = create_app().openapi()
    out = ROOT / "docs" / "api"
    out.mkdir(parents=True, exist_ok=True)
    (out / "openapi.json").write_text(json.dumps(schema, indent=1), encoding="utf-8")

    by_tag: dict[str, list[tuple[str, str, str]]] = {}
    for path, ops in schema["paths"].items():
        for method, op in ops.items():
            tag = (op.get("tags") or ["other"])[0]
            params = ", ".join(p["name"] for p in op.get("parameters", []) if p.get("in") == "query")
            by_tag.setdefault(tag, []).append((method.upper(), path, params))

    lines = [
        "# API Reference",
        "",
        f"Generated from the FastAPI OpenAPI schema ({schema['info']['title']} {schema['info']['version']}). "
        "Interactive docs: `/docs` on a running API. Full schema: [openapi.json](openapi.json).",
        "",
    ]
    for tag in sorted(by_tag):
        lines += [f"## {tag}", "", "| Method | Path | Query parameters |", "|---|---|---|"]
        lines += [
            f"| {m} | `{p}` | {q or '—'} |" for m, p, q in sorted(by_tag[tag], key=lambda r: (r[1], r[0]))
        ]
        lines.append("")
    (out / "api-reference.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out / 'openapi.json'} and {out / 'api-reference.md'}")


if __name__ == "__main__":
    main()
