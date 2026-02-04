"""
JCT Worker CLI entry point.

Usage:
    python -m devops_control_tower.worker [OPTIONS]

Options:
    --executor TYPE     Executor type (default: stub)
    --poll-interval N   Seconds between polls (default: from config)
    --claim-limit N     Tasks to claim per poll (default: from config)
"""
from __future__ import annotations

import argparse
import sys

from .loop import run_worker


def main() -> int:
    """Main entry point for worker CLI."""
    parser = argparse.ArgumentParser(
        description="JCT Worker - processes queued tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with default settings
    python -m devops_control_tower.worker

    # Run with custom poll interval
    python -m devops_control_tower.worker --poll-interval 10

    # Run with specific executor (v0: stub only)
    python -m devops_control_tower.worker --executor stub
        """,
    )

    parser.add_argument(
        "--executor",
        type=str,
        default="stub",
        help="Executor type (default: stub)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=None,
        help="Seconds between poll cycles (default: from config)",
    )
    parser.add_argument(
        "--claim-limit",
        type=int,
        default=None,
        help="Max tasks to claim per poll cycle (default: from config)",
    )

    args = parser.parse_args()

    print(f"Starting JCT Worker...")
    print(f"  Executor: {args.executor}")
    print(f"  Poll interval: {args.poll_interval or 'from config'}")
    print(f"  Claim limit: {args.claim_limit or 'from config'}")
    print()

    try:
        run_worker(
            executor_type=args.executor,
            poll_interval=args.poll_interval,
            claim_limit=args.claim_limit,
        )
        return 0
    except KeyboardInterrupt:
        print("\nWorker stopped by user")
        return 0
    except Exception as e:
        print(f"Worker error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
