#!/usr/bin/env python3
"""
X (Twitter) Impersonation Scanner
Generates handle variants and checks which ones exist on X using Apify.
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from scanner.variants import generate_variants
from scanner.checker import check_handles_batch
from scanner.reporter import generate_report

load_dotenv()


def load_handles(source: str) -> list[str]:
    """Load handles from a file or comma-separated CLI string."""
    path = Path(source)
    if path.exists():
        handles = [line.strip().lstrip("@") for line in path.read_text().splitlines() if line.strip()]
    else:
        handles = [h.strip().lstrip("@") for h in source.split(",") if h.strip()]
    return handles


def main():
    parser = argparse.ArgumentParser(
        description="Scan X (Twitter) for impersonation accounts of given handles."
    )
    parser.add_argument(
        "handles",
        help="Comma-separated handles OR path to a .txt file (one handle per line)",
    )
    parser.add_argument(
        "--output",
        default="report",
        help="Output file base name (default: report → report.json + report.csv)",
    )
    parser.add_argument(
        "--max-variants",
        type=int,
        default=50,
        help="Max variants to check per handle (default: 50)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="How many Apify calls to run in parallel (default: 5)",
    )
    args = parser.parse_args()

    handles = load_handles(args.handles)
    if not handles:
        print("No handles found. Provide a comma-separated list or a .txt file.")
        sys.exit(1)

    print(f"\n🔍 Scanning {len(handles)} handle(s): {', '.join('@' + h for h in handles)}\n")

    # Step 1: Generate variants
    all_variants: dict[str, list[str]] = {}
    for handle in handles:
        variants = generate_variants(handle, max_variants=args.max_variants)
        all_variants[handle] = variants
        print(f"  @{handle} → {len(variants)} variants generated")

    print(f"\n⚙️  Checking variants on X via Apify (concurrency={args.concurrency})...\n")

    # Step 2: Check which variants exist
    results = check_handles_batch(all_variants, concurrency=args.concurrency)

    # Step 3: Generate report
    json_path, csv_path = generate_report(results, base_name=args.output)

    existing = sum(1 for r in results if r["exists"])
    print(f"\n✅ Done. {existing} impersonation account(s) found across {len(results)} variants checked.")
    print(f"   📄 JSON report: {json_path}")
    print(f"   📊 CSV  report: {csv_path}\n")


if __name__ == "__main__":
    main()
