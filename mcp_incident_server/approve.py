"""Local operator command. Protect shell access and the printed token."""
import argparse
import os

from .server import Incidents


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.getenv("PORTFOLIO_DB", "incidents.db"))
    parser.add_argument("--incident-id", type=int, required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--actor", required=True)
    args = parser.parse_args()
    print(Incidents(args.db).approve_note(args.incident_id, args.body, args.actor))


if __name__ == "__main__":
    main()
