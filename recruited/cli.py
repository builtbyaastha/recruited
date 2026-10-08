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
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.cmd == "run":
        print(json.dumps(pipeline.run(args.only, not args.no_enrich), indent=2))
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
