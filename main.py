#!/usr/bin/env python3
import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from src.config import (
    PROJECT_ROOT,
    ACCOUNTS,
    BATCH_SIZE,
    DEFAULT_PROVIDER,
    is_mock_mode,
)
from src.auth import TikTokAuth
from src.uploader import TikTokUploader
from src.metadata_gen import generate_metadata, Metadata
from src.scanner import scan_content, ContentItem

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="TikTok Bulk Upload & Draft Scheduler (CLI)"
    )
    parser.add_argument(
        "--account",
        default="lubanja",
        choices=list(ACCOUNTS.keys()),
        help="Account/profile to use",
    )
    parser.add_argument(
        "--provider",
        default=DEFAULT_PROVIDER,
        choices=["gemini", "openai", "claude", "ollama"],
        help="AI provider for caption generation",
    )
    parser.add_argument(
        "--folder",
        type=str,
        default=None,
        help="Override content folder path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and generate metadata but skip upload",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Skip approval prompts, approve all valid items",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    account = ACCOUNTS[args.account]
    content_folder = Path(args.folder) if args.folder else account.content_folder

    logger.info("Account: %s", account.name)
    logger.info("Content folder: %s", content_folder)
    logger.info("AI provider: %s", args.provider)
    logger.info("API mode: %s", "MOCK" if is_mock_mode() else "LIVE")
    if args.dry_run:
        logger.info("DRY RUN - no uploads will be performed")

    print(f"\n{'='*60}")
    print(f"  TikTok Uploader - {account.name}")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"{'='*60}\n")

    items = scan_content(content_folder, account)
    valid = [i for i in items if not i.skip_reason and not i.already_uploaded]
    skipped = [i for i in items if i.skip_reason or i.already_uploaded]

    print(f"Scanned: {len(items)} files")
    print(f"  Valid: {len(valid)}")
    print(f"  Skipped: {len(skipped)}")
    for s in skipped:
        print(f"    [SKIP] {s.filename} - {s.skip_reason or 'Already uploaded'}")

    if not valid:
        print("\nNo new files to process.")
        return

    approved_items = []
    total_batches = (len(valid) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_num in range(total_batches):
        start = batch_num * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(valid))
        batch = valid[start:end]

        print(f"\n{'-'*60}")
        print(f"  Batch {batch_num + 1}/{total_batches} (items {start + 1}-{end})")
        print(f"{'-'*60}")

        meta_map = {}
        for item in batch:
            meta = generate_metadata(
                item.file_path,
                account.brand_context,
                language=item.language,
                provider=args.provider,
            )
            meta_map[item.filename] = meta

            lang_tag = "[AM]" if item.language == "am" else "[EN]"
            print(f"\n  [{batch.index(item) + 1}] {item.filename}")
            print(f"      Type: {'Video' if item.media_type == 'video' else 'Image'}  |  Size: {item.file_size_mb} MB  |  Lang: {lang_tag}")
            print(f"      Caption: {meta.caption[:120]}...")
            print(f"      Hashtags: {' '.join(t if t.startswith('#') else f'#{t}' for t in meta.hashtags)}")

        if args.auto_approve:
            for item in batch:
                item._meta = meta_map[item.filename]
                approved_items.append(item)
            print(f"\n  [OK] Auto-approved all {len(batch)} items.")
        else:
            for i, item in enumerate(batch):
                prompt_text = f"\n  Approve '{item.filename}'? [Y/n/q(uit batch)]: "
                choice = input(prompt_text).strip().lower() or "y"
                if choice == "q":
                    break
                if choice in ("y", "yes", ""):
                    item._meta = meta_map[item.filename]
                    approved_items.append(item)
                    print(f"    [OK] Approved")
                else:
                    print(f"    [SKIP] Skipped")

    if not approved_items:
        print("\nNo items approved. Exiting.")
        return

    print(f"\n{'='*60}")
    print(f"  Uploading {len(approved_items)} approved posts...")
    print(f"{'='*60}")

    auth = TikTokAuth(account)
    uploader = TikTokUploader(auth, account)
    results = []
    consecutive_failures = 0

    for i, item in enumerate(approved_items):
        meta = getattr(item, '_meta', None) or generate_metadata(
            item.file_path, account.brand_context, language=item.language, provider=args.provider
        )

        if args.dry_run:
            logger.info("[DRY RUN] Would upload %s", item.filename)
            results.append({
                "file": item.filename,
                "status": "DRY_RUN",
                "status_label": "DRY_RUN",
                "attempt": 1,
                "error": None,
            })
            _write_log(account.name, item, meta, {"status_label": "DRY_RUN", "publish_id": None, "attempt": 1, "error": None}, args.provider)
            continue

        attempt = 1
        while attempt <= 2:
            try:
                print(f"  [{i + 1}/{len(approved_items)}] Uploading {item.filename}...")

                if item.media_type == "video":
                    result = uploader.upload_video(item.file_path, meta.caption, meta.hashtags)
                else:
                    result = uploader.upload_photo(item.file_path, meta.caption, meta.hashtags)

                result["status_label"] = "UPLOADED" if attempt == 1 else "UPLOADED_RETRY"
                result["attempt"] = attempt
                result["error"] = None
                consecutive_failures = 0
                print(f"    [OK] {result['status_label']} (ID: {result.get('publish_id', 'N/A')})")
                break

            except Exception as e:
                print(f"    [FAIL] Attempt {attempt} failed: {e}")
                if attempt == 1:
                    print("    [WAIT] Waiting 10s before retry...")
                    time.sleep(10)
                    attempt += 1
                else:
                    result = {
                        "file": item.filename,
                        "status": "FAILED",
                        "status_label": "FAILED",
                        "attempt": attempt,
                        "error": str(e),
                    }
                    consecutive_failures += 1
                    break

        results.append(result)
        _write_log(account.name, item, meta, result, args.provider)

        if consecutive_failures >= 2:
            print("\n  [STOP] 2 consecutive uploads failed - stopping.")
            break

    print(f"\n{'='*60}")
    success = sum(1 for r in results if r.get("status") in ("SEND_TO_USER_INBOX", "DRY_RUN"))
    print(f"  Complete: {success}/{len(results)} succeeded")
    print(f"{'='*60}")


def _write_log(account_name: str, item: ContentItem, meta: Metadata, result: dict, provider: str):
    log_path = PROJECT_ROOT / "logs" / "upload_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "brand": account_name,
        "filename": item.filename,
        "status": result.get("status_label", "UNKNOWN"),
        "publish_id": result.get("publish_id"),
        "caption": meta.caption[:100],
        "hashtags": meta.hashtags,
        "file_size_mb": item.file_size_mb,
        "attempt": result.get("attempt", 1),
        "error_code": None,
        "error_message": result.get("error"),
        "provider_used": provider,
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    main()
