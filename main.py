#!/usr/bin/env python3
"""
X (Twitter) Impersonation Scanner
- Checks the original handles (profile, tweets, mentions)
- Generates variants and checks which ones exist on X
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from scanner.variants import generate_variants
from scanner.checker import check_handles_batch, check_originals
from scanner.reporter import generate_report
from scanner.saver import save_all_content

load_dotenv()


def load_handles(source: str) -> list[str]:
    path = Path(source)
    if path.exists():
        return [
            line.strip().lstrip("@")
            for line in path.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
    return [h.strip().lstrip("@") for h in source.split(",") if h.strip()]


def main():
    parser = argparse.ArgumentParser(
        description="Scan X (Twitter) for impersonation accounts of given handles."
    )
    parser.add_argument(
        "handles",
        help="Comma-separated handles OR path to a .txt file (one handle per line)",
    )
    parser.add_argument("--output",       default="report",         help="Output file base name")
    parser.add_argument("--max-variants", type=int, default=50,     help="Max variants per handle (default: 50)")
    parser.add_argument("--concurrency",  type=int, default=3,      help="Parallel Apify calls (default: 3)")
    parser.add_argument("--images-dir",   default="profile_images", help="Folder for profile pictures")
    parser.add_argument("--content-dir",  default="saved_content",  help="Folder for text files")
    parser.add_argument("--no-images",    action="store_true",      help="Skip downloading profile pictures")
    parser.add_argument("--no-save",      action="store_true",      help="Skip saving text files")
    parser.add_argument("--no-originals", action="store_true",      help="Skip checking the original handles")
    args = parser.parse_args()

    handles = load_handles(args.handles)
    if not handles:
        print("No handles found. Provide a comma-separated list or a .txt file.")
        sys.exit(1)

    download_images = not args.no_images
    all_results: list[dict] = []

    print(f"\n🔍 Handles to scan: {', '.join('@' + h for h in handles)}\n")

    # Step 1: Check the original handles themselves
    if not args.no_originals:
        original_results = check_originals(
            handles,
            download_images=download_images,
            images_dir=args.images_dir,
        )
        all_results.extend(original_results)

    # Step 2: Generate and check variants
    print(f"\n⚙️  Generating variants (max {args.max_variants} per handle)...\n")
    all_variants: dict[str, list[str]] = {}
    for handle in handles:
        variants = generate_variants(handle, max_variants=args.max_variants)
        all_variants[handle] = variants
        print(f"  @{handle} → {len(variants)} variants generated")

    print(f"\n⚙️  Checking variants on X (concurrency={args.concurrency}, images={'yes' if download_images else 'no'})...\n")
    variant_results = check_handles_batch(
        all_variants,
        concurrency=args.concurrency,
        download_images=download_images,
        images_dir=args.images_dir,
    )
    all_results.extend(variant_results)

    # Step 3: Generate JSON + CSV report
    json_path, csv_path = generate_report(all_results, base_name=args.output)

    # Step 4: Save text files for all found accounts (originals + variants)
    saved_files = []
    if not args.no_save:
        saved_files = save_all_content(all_results, output_dir=args.content_dir)

    # Summary
    originals_found = [r for r in all_results if r.get("is_original") and r.get("exists")]
    existing        = [r for r in all_results if not r.get("is_original") and r.get("exists")]
    with_mentions   = [r for r in existing if r.get("mention_count", 0) > 0]
    with_images     = [r for r in all_results if r.get("profile_image_local")]

    print(f"\n✅ Done.")
    print(f"   Original handles found    : {len(originals_found)}/{len(handles)}")
    print(f"   Variants checked          : {len(variant_results)}")
    print(f"   Impersonation accts found : {len(existing)}")
    print(f"   With external mentions    : {len(with_mentions)}")
    if download_images:
        print(f"   Profile pics saved        : {len(with_images)}  → {args.images_dir}/")
    if saved_files:
        print(f"   Text files saved          : {len(saved_files)}  → {args.content_dir}/")
    print(f"   📄 JSON : {json_path}")
    print(f"   📊 CSV  : {csv_path}\n")


if __name__ == "__main__":
    main()
