"""Local operator command. Protect shell access and the printed token."""
import argparse
import os

from .server import MAX_INCIDENT_ID, MIN_INCIDENT_ID, Incidents


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.getenv("PORTFOLIO_DB", "incidents.db"))
    parser.add_argument("--incident-id", type=int, required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--actor", required=True)
    args = parser.parse_args()
    if not MIN_INCIDENT_ID <= args.incident_id <= MAX_INCIDENT_ID:
        parser.error("incident ID must fit a signed 64-bit integer")
    if not (1 <= len(args.body) <= 1000) or not args.body.strip() or not args.actor.strip():
        parser.error("note length and actor are required")
    try:
        token = Incidents(args.db).approve_note(args.incident_id, args.body, args.actor)
    except ValueError as exc:
        parser.error(str(exc))
    print(token)


if __name__ == "__main__":
    main()
