#!/usr/bin/env python3
#
# svc-commerce-homedepot, 2026
#
# Licensed under Apache License, Version 2.0.
#
"""Merge Home Depot product listings into 'products.jsonl', and say what is served.

The catalog is the store's own listings: each product's item ID (the "Internet
#" its URL ends with), its title, its URL slug and its model number. Nothing
else is recorded, because everything the catalog serves is derived from those
by the rules in 'catalog_repo.py' - so a rule that learns something new serves
products that were already collected, without collecting them again.

A listing is a JSON object per line:

    {"id": "204273651",
     "title": "Everbilt M4-0.7 x 20 mm Class 8.8 Zinc Plated Hex Bolt (2-Pack)",
     "slug": "M4-0-7-x-20-mm-Class-8-8-Zinc-Plated-Hex-Bolt-2-Pack-801268",
     "model": "801268"}

with an optional "alt_titles" for the other titles the same item ID has been
seen under, and an optional "url" that has to agree with the id and the slug.
Any other field is dropped. A listing for an item ID that is already recorded
replaces it, and the title it replaces is kept among the alternatives: the store
retitles products, and a product whose titles disagree about what it is is one
the catalog will not serve.

Usage:

    ./update_products.py listings.jsonl [more.jsonl ...]   # merge, then report
    ./update_products.py --report                         # report only
    ./update_products.py --report --verbose               # ... and every product
"""

import argparse
import collections
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import catalog_repo  # noqa: E402 - imported from beside this script

PRODUCTS = os.path.join(_HERE, catalog_repo._PRODUCTS_FILE)

_ITEM_ID = re.compile(r"[0-9]{9}")
_FIELDS = ("id", "title", "alt_titles", "slug", "model")


def _clean(record, where):
    """The listing as it is recorded, or None (with the reason on stderr) if it is unusable."""
    item_id = str(record.get("id") or "").strip()
    title = " ".join(str(record.get("title") or "").split())
    slug = str(record.get("slug") or "").strip().strip("/")
    if not _ITEM_ID.fullmatch(item_id):
        print("%s: not a Home Depot item ID, skipped: %r" % (where, item_id), file=sys.stderr)
        return None
    if not title or not slug:
        print("%s: %s has no title or no slug, skipped" % (where, item_id), file=sys.stderr)
        return None
    url = record.get("url")
    if url and url.split("?")[0].rstrip("/") != "https://www.homedepot.com/p/%s/%s" % (slug, item_id):
        print(
            "%s: %s: the URL does not name this slug and item ID, skipped: %s" % (where, item_id, url), file=sys.stderr
        )
        return None
    clean = {"id": item_id, "title": title, "slug": slug}
    alternatives = [" ".join(t.split()) for t in record.get("alt_titles") or () if t and t.strip()]
    alternatives = sorted({t for t in alternatives if t != title})
    if alternatives:
        clean["alt_titles"] = alternatives
    model = str(record.get("model") or "").strip()
    if model:
        clean["model"] = model
    return clean


def _merge(old, new):
    """A newer listing of a recorded product: its title wins, the old one is kept aside."""
    merged = dict(new)
    titles = set(old.get("alt_titles") or ()) | set(new.get("alt_titles") or ())
    titles.add(old["title"])
    titles.discard(new["title"])
    if titles:
        merged["alt_titles"] = sorted(titles)
    if "model" not in merged and "model" in old:
        merged["model"] = old["model"]
    return merged


def read(path):
    records = []
    with open(path, encoding="utf-8") as f:
        for number, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = _clean(json.loads(line), "%s:%d" % (path, number))
            except ValueError as e:
                print("%s:%d: not JSON, skipped: %s" % (path, number, e), file=sys.stderr)
                continue
            if record is not None:
                records.append(record)
    return records


def write(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for record in sorted(records, key=lambda r: r["id"]):
            ordered = {key: record[key] for key in _FIELDS if key in record}
            f.write(json.dumps(ordered, ensure_ascii=False) + "\n")


def report(records, verbose=False):
    served = collections.Counter()
    unserved = collections.Counter()
    for record in records:
        category, config = catalog_repo.classify(record)
        if category is None:
            # The reason without the particulars, so that alike ones add up.
            reason = config.split(":")[0].strip()
            unserved[reason] += 1
            if verbose:
                print("  -        %s  %s\n             %s" % (record["id"], record["title"], config))
        else:
            served[category] += 1
            if verbose:
                print("  %-8s %s  %s" % (category, record["id"], record["title"]))
    print("%d products, %d served:" % (len(records), sum(served.values())))
    for category in catalog_repo.CATEGORIES:
        print("  %-8s %4d" % (category, served[category]))
    if unserved:
        print("not served:")
        for reason, count in unserved.most_common():
            print("  %4d  %s" % (count, reason))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("listings", nargs="*", help="JSON Lines files of listings to merge in")
    parser.add_argument("--report", action="store_true", help="only report; merge nothing")
    parser.add_argument("--verbose", action="store_true", help="list every product and what became of it")
    args = parser.parse_args(argv)

    records = {r["id"]: r for r in (read(PRODUCTS) if os.path.exists(PRODUCTS) else [])}
    if not args.report:
        for path in args.listings:
            for record in read(path):
                old = records.get(record["id"])
                records[record["id"]] = record if old is None else _merge(old, record)
        write(PRODUCTS, records.values())
    report(sorted(records.values(), key=lambda r: r["id"]), verbose=args.verbose)


if __name__ == "__main__":
    main()
