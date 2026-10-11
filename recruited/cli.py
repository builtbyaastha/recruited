import argparse
import json
import logging
import sys

from . import db, digest, pipeline, service
from .matching.resume import read_text


def main(argv=None):
    p = argparse.ArgumentParser(prog="recruited")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run the daily ingest + enrich pipeline")
    r.add_argument("--only", nargs="*", help="sources: hn rss yc")
    r.add_argument("--no-enrich", action="store_true")
    m = sub.add_parser("match", help="match a resume file against stored jobs")
    m.add_argument("resume")
    m.add_argument("--location", default="")
    m.add_argument("--remote-only", action="store_true")
    m.add_argument("--limit", type=int, default=15)
    d = sub.add_parser("digest", help="email (or print) new matches from the last day")
    d.add_argument("resume")
    d.add_argument("--to", help="recipient; omit to print instead of sending")
    d.add_argument("--hours", type=int, default=24)
    sub.add_parser("stats", help="summarise what is in the database")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.cmd == "run":
        print(json.dumps(pipeline.run(args.only, not args.no_enrich), indent=2))
    elif args.cmd == "stats":
        with db.session() as conn:
            q = lambda sql: conn.execute(sql).fetchall()
            print("companies:", q("SELECT COUNT(*) FROM companies")[0][0],
                  "| with job board:", q("SELECT COUNT(*) FROM companies WHERE ats_type IS NOT NULL")[0][0],
                  "| jobs:", q("SELECT COUNT(*) FROM jobs")[0][0])
            for r in q("SELECT source, type, COUNT(*) FROM signals GROUP BY 1, 2 ORDER BY 3 DESC"):
                print(f"  signals {r[0]:<20} {r[1]:<8} {r[2]}")
            for r in q("SELECT COALESCE(source, '?'), COUNT(*) FROM jobs GROUP BY 1 ORDER BY 2 DESC"):
                print(f"  jobs    {r[0]:<20} {r[1]}")
            print("latest signals:")
            for r in q("SELECT s.type, c.name, s.amount, s.round, s.source FROM signals s "
                       "JOIN companies c ON c.id=s.company_id ORDER BY s.published_at DESC LIMIT 15"):
                print("  ", " | ".join(x or "" for x in r))
    elif args.cmd == "digest":
        with db.session() as conn:
            built = digest.build(conn, read_text(open(args.resume, "rb").read(), args.resume), args.hours)
        if not built:
            print("No new matching jobs.")
        elif args.to:
            digest.send(*built, args.to)
            print("Sent.")
        else:
            print(built[0], "\n", built[1], sep="")
    else:
        data = open(args.resume, "rb").read()
        with db.session() as conn:
            out = service.match_resume(conn, read_text(data, args.resume), location=args.location,
                                       remote_only=args.remote_only, limit=args.limit)
        print("Profile:", json.dumps(out["profile"]))
        for i, m_ in enumerate(out["matches"], 1):
            print(f"{i:>2}. [{m_['score']:.2f}] {m_['title']} @ {m_['company']} — {m_['reason']}\n    {m_['url']}")
        if not out["matches"]:
            print("No jobs yet — run `python -m recruited run` first.", file=sys.stderr)


if __name__ == "__main__":
    main()
