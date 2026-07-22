"""Export or verify the committed experiment JSON Schema."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from aishield.schemas.experiment import ExperimentResult


def rendered_schema() -> str:
    """Render the canonical schema deterministically."""

    schema = ExperimentResult.model_json_schema()
    schema["$id"] = "https://aishield.local/schemas/experiment-result-1.0.json"
    return f"{json.dumps(schema, indent=2, sort_keys=True)}\n"


def main(argv: Sequence[str] | None = None) -> None:
    """Write the schema, or fail when a committed copy has drifted."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify without writing")
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("schemas/experiment-result.schema.json"),
    )
    arguments = parser.parse_args(argv)
    expected = rendered_schema()

    if arguments.check:
        if not arguments.path.exists() or arguments.path.read_text(encoding="utf-8") != expected:
            parser.error(f"schema is out of date: {arguments.path}")
        return

    arguments.path.parent.mkdir(parents=True, exist_ok=True)
    arguments.path.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
