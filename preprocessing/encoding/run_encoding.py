"""Compatibility CLI: delegate the full explicit cohort configuration, never prototype."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main(argv=None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or "--apply" in arguments or "--source" in arguments:
        print(
            "Legacy prototype mode is disabled before writes. Use python -m "
            "preprocessing.encoding.execute with --input-manifest --vocabulary --stopwords "
            "--cohort-ledger --decision-record --output-root --evidence-root --history-root "
            "[--publish] [--dry-run].",
            file=sys.stderr,
        )
        return 1
    from preprocessing.encoding.execute import main as execute_main

    return execute_main(arguments) or 0


if __name__ == "__main__":
    sys.exit(main())
