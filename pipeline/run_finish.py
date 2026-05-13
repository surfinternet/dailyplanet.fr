"""
Called from cron_pipeline.sh to update the run JSON with final status.
Usage: python pipeline/run_finish.py RUN_ID STATUS [--git-note "..."]
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(__file__))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("status")
    parser.add_argument("--git-note", default=None)
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    import run_tracker
    run_tracker.finish(args.run_id, args.status, git_note=args.git_note)
    print(f"[run_finish] {args.run_id} → {args.status}")


if __name__ == "__main__":
    main()
