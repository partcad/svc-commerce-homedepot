# The Home Depot catalog for PartCAD

Exposes the products of The Home Depot that a PartCAD standard describes as
PartCAD parts, published as `//pub/svc/commerce/homedepot/catalog`. Each
category is a sub-package, and each product in it is a part named by the
store's own **item ID** — the "Internet #" a product URL ends with, which is
also the SKU the package's `homedepot` store provider orders by, as it is,
without looking anything up on the website first.

Only two families are served for now, because they are the two the PartCAD
index has standards for:

* **dimensional lumber and plywood**, as instances of
  [`//pub/std/imperial/dimensional-lumber`](https://github.com/partcad/partcad-standard-imperial-dimensional-lumber)
  at the product's nominal size;
* **metric fasteners**, which implement the
  [`//pub/std/metric/m`](https://github.com/partcad/partcad-standard-metric-m)
  interfaces, so that an assembly can put them together with `connect:`
  instead of by coordinates.

It is the same arrangement as
[`//pub/universe/lego/ldraw`](https://github.com/partcad/partcad-ldraw): a
repository plugin serving a hierarchy of packages over PartCAD's key/value
protocol, from an index shipped beside it, with the interfaces derived from
what each part is called.

| Sub-package | Products                                                              | An instance of                                              | Implements                                      |
|-------------|-----------------------------------------------------------------------|-------------------------------------------------------------|-------------------------------------------------|
| `lumber`    | 185 boards, studs, posts and timbers, untreated and pressure-treated   | `:dimensional-lumber` → `//pub/std/imperial/dimensional-lumber:lumber` | —                                    |
| `plywood`   | 117 sheathing, sanded, hardwood, marine and project panels              | `:plywood` → `//pub/std/imperial/dimensional-lumber:plywood` | —                                              |
| `bolts`     | 88 hex bolts and hex head cap screws, 19 flange bolts                   | `//pub/std/metric/cqwarehouse`: `fastener/hexhead-iso4017`, `fastener/hexheadwithflange-din1665` | `m-bolt-length;size=…,length=…` |
| `screws`    | 20 socket head, 10 button head and 7 flat head socket cap screws; 52 flat head and 61 pan head machine screws | `…/cqwarehouse`: `socketheadcap-iso4762`, `buttonhead-iso7380-1`, `countersunk-iso10642`, `countersunk-iso7046`, `raisedcheesehead-iso7045` | `m-bolt-length;size=…,length=…` |
| `nuts`      | 34 hex nuts (ISO 4032), 5 flange nuts (DIN 1665), 6 cap nuts (DIN 1587) | `:metric-nut`                                               | `m-threaded-thru-depth;size=…,depth=…`; a cap nut `m-tapped-hole;size=…,depth=…` |
| `washers`   | 31 flat washers (ISO 7089), 5 fender washers (ISO 7093)                 | `:metric-washer`                                            | `m-thru-depth;size=…,depth=…`                   |

That is 640 products. The lumber and plywood carry no interfaces, because their
standard defines none: what the standard gives them is their geometry, in the
frame a part cut from one is made in (see the package's own `README.md`).

## Usage

```shell
# The categories, and what is in one
pc list packages -r //pub/svc/commerce/homedepot
pc list parts //pub/svc/commerce/homedepot/catalog/bolts

# A product, its geometry, and the interface it implements
pc info //pub/svc/commerce/homedepot/catalog/bolts:204273651

# What it costs (see "Quotes" below for why --provider)
pc supply quote --provider //pub/svc/commerce/homedepot:homedepot \
    //pub/svc/commerce/homedepot/catalog/bolts:204273651
```

In an assembly, a fastener is put on another by its interface. This is
`hardware/fasteners/catalog_assembly` in this package — the joint
`hardware/fasteners/fastener_assembly` places by hand, built from the catalog:

```yaml
links:
  - part: //pub/svc/commerce/homedepot/catalog/bolts:204273651   # M4-0.7 x 20 mm hex bolt
    name: bolt
  - part: //pub/svc/commerce/homedepot/catalog/washers:204276428 # M4 flat washer, under the head
    connect:
      name: bolt
      withInstance: top
  - part: //pub/svc/commerce/homedepot/catalog/nuts:204275876    # M4-0.7 hex nut, 6.9 mm down
    connect:
      name: bolt
      withInstance: top
      toParams:
        moveZ: 6.9
```

## How a product is read

Everything a part is served as comes from the product's title, by the rules in
`catalog_repo.py`. They read a title and do not guess at one: a title they do
not understand completely is left out, with the reason, rather than served as
something it may not be. `./update_products.py --report --verbose` lists every
product and what became of it.

* **Lumber.** `A in. x B in. x L` — the smaller nominal dimension is the
  standard's `height` and the larger its `width`, both from its `enum`; the
  length is in feet or in inches, fractions included (`92-5/8 in.` studs). A
  board that is not dressed to PS 20 is left out whatever its nominal size:
  rough-sawn, band-sawn, surfaced on one side only (`S1S2E`), radius-edged
  decking, tongue and groove, pickets. So is one whose title states an actual
  size more than the standard's own tolerance (1/16 in.) from PS 20's.
* **Plywood.** `T in. x W ft. x L ft.` — a panel sold by an odd number of
  32nds (`23/32 in.`) is the one the trade calls 1/32 in. thicker, which is the
  nominal thickness the standard takes; any other label is the nominal one. A
  stated actual thickness has to be within the standard's tolerance (1/32 in.)
  of nominal less 1/32, and a stated actual width and length are what the panel
  is modelled as (the 2 x 2 ft. project panels are 23.75 in.). A thickness given
  only in millimetres, as a "category", or as one of two, is left out.
* **Bolts and screws.** The head type picks the cq_warehouse part, the thread
  and the length its `size` and `length`. The thread has to be ISO 261's coarse
  one, which is the thread `//pub/std/metric/m` states and the one
  cq_warehouse's sizes are named by; an ISO designation without a pitch (`M6`)
  means exactly that, and a fine thread (`M10-1.25`) is a different thread
  neither standard names. Every one implements `m-bolt-length`, machine screws
  included: in `//pub/std/metric/m`'s terms a bolt goes into a thread that is
  already there — a tapped hole, a nut — and an `m-screw` is one that cuts its
  own.
* **Nuts and washers.** The kind picks the ISO or DIN type, the thread or the
  screw size picks the size. A washer whose title gives its outside diameter
  (`10 mm x 20 mm`) has to have the standard's.
* **The pack.** `(2-Pack)`, `5-Pieces`, `(3 per Bag)`, `5PC` and the like are
  the part's `count_per_sku`, which is what a quote divides the count by.

Two cross-checks run on every product, because the store retitles products and
a stale title is the commonest way for a record to be wrong. A product that
has been listed under several titles (`alt_titles`) is served only if all of
those that can be read agree — two of the pan head screws were listed as both
2 and 4 to a pack, and there is no telling which the SKU is today. And the URL
slug, which keeps the words of a title if not its decimal points, has to name
the same kind of fastener: one product is titled a hex head cap screw and has
a socket cap screw's URL.

### Where the ports are

PartCAD's convention is that a port's +Z points into the part it belongs to,
which is also the direction a part travels as it is connected through it.
cq_warehouse builds every fastener with its bearing face on the XY plane, so
the ports are placed on that:

* a bolt or a screw has one port, at the origin and unturned: under the head,
  with the shank below it and +Z up into the head. For a flat (countersunk)
  head, cq_warehouse's origin is the narrow end of the head's cone, so it seats
  on the surface of a plain clearance hole, the only kind `//pub/std/metric/m`
  has an interface for;
* a nut or a washer has two, `bottom` at Z=0 and `top` on its far face turned
  over, so either face can go against what it is put on. A cap nut's thread is
  blind and it has only `bottom`.

`moveZ` on the bolt's interface is then how far down the shank a part sits,
measured from the underside of the head, which is what
`catalog_assembly.assy` uses to leave room for what the joint clamps.

### What is not served, and why

Of the 759 products recorded, 119 are not served:

| Products | Why                                                                                                  |
|---------:|------------------------------------------------------------------------------------------------------|
| 31       | a fine thread (`M10-1.25`, `M12-1.5`, ...): `//pub/std/metric/m` and cq_warehouse name the coarse ones only |
| 24       | lock nuts, nylon insert or all-metal: nothing in the index draws one                                 |
| 18       | split and toothed lock washers: likewise                                                             |
| 13       | wing nuts: likewise                                                                                  |
| 14       | lumber that is not dressed to PS 20 (rough, band-sawn, `S1S2E`, decking)                              |
| 7        | a typo in the size: `M8-40`, `M16-32`, `M4-7`, `M8-1.2`, `14 mm x 2.0 in.`, `10 mm to 1.5 m`, `M6 x 30` |
| 6        | plywood of no one stated thickness, or of no size the rules can read                                 |
| 3        | the titles, or the title and the URL, disagree (above)                                               |
| 2        | a size cq_warehouse draws no such fastener in: an M7 hex bolt, an M3 cap nut                        |
| 1        | a kit: flange bolts "with Nuts and Washers"                                                          |

The fastener kinds are left out for want of **geometry**, not of an interface —
a lock nut is a threaded through hole like any other. They become servable the
day the index has a part for them, and since `products.jsonl` keeps them, that
is a rule and a template here rather than a new collection.

The same goes for nuts and washers in general. `//pub/std/metric/cqwarehouse`
publishes cq_warehouse's screws and none of its nuts or washers, so this
package declares two templates of its own, `metric-nut` and `metric-washer`,
that ask the same library for them (`metric_nut.py`, `metric_washer.py`). They
belong in that package, and become aliases of it once they are there. One size
is held back meanwhile: cq_warehouse 0.8.0 gives the DIN 1587 M10 cap nut a
height of 88 mm, where the standard says 8.

## Quotes

`pc supply quote --provider …:homedepot` works for every part here, exactly as
it does for the package's own: the provider is asked whether it stocks the
vendor's SKU and then for a price, and the SKU is the item ID it puts in the
cart. Without `--provider`, PartCAD 0.8.133 looks for the suppliers the part's
own package lists and fails with `AttributeError: 'ProjectExternalRepository'
object has no attribute 'suppliers'` — a package served by a plugin is never
given the attribute, and could not take a `suppliers:` from its metadata if it
were, since those are read when the package is created and the metadata
arrives later. That is a PartCAD issue, shared by every plugin-backed package,
and this one says nothing about suppliers until it is fixed there.

## Maintaining it

`products.jsonl` is the store's own listings, one per line, sorted by item ID
so that a diff is the products that changed:

```json
{"id": "204273651", "title": "Everbilt M4-0.7 x 20 mm Class 8.8 Zinc Plated Hex Bolt (2-Pack)", "slug": "M4-0-7-x-20-mm-Class-8-8-Zinc-Plated-Hex-Bolt-2-Pack-801268", "model": "801268"}
```

Nothing derived is stored: the rules derive it, so a rule that learns something
new serves products that were already collected. To add to it, write the new
listings to a JSON Lines file in the same shape (a `url` is checked against the
id and the slug, and anything else is dropped) and merge them:

```shell
./update_products.py new-listings.jsonl     # merge, then report what is served
./update_products.py --report --verbose     # every product, and what became of it
python -m pytest .                          # the rules, the protocol, the records
```

A listing for an item ID already recorded replaces it, and the title it
replaces is kept among its `alt_titles`.

**Raise `CACHE_VERSION` in `catalog_repo.py`** with any change to what is
served — a rule, a table, a template, or `products.jsonl` itself. PartCAD keys
the cache of every answer this plugin gives on that number and on nothing else,
so an existing checkout goes on being served what it has until it moves.

### Where the listings came from

The records shipped were collected on 2026-10-01 from Home Depot's product
listings as web search returns them — each one's title and product URL, from
which the item ID and the slug are taken — because homedepot.com itself could
not be reached from where they were collected. So they are what the store
called each product when the search engine last saw its page, and they cover
what the searches reached rather than everything stocked: there is no 1x6 or
4x6 lumber yet, for instance, and no M3 or M20 bolt. A crawler of the store's
own category pages is the obvious next step, and it would write the same JSON
Lines this takes.

The four products this package already lists by hand are among them, and the
catalog agrees with all four (a test says so).

## Layout

| Path                     | Purpose                                                                                     |
|--------------------------|---------------------------------------------------------------------------------------------|
| `catalog_repo.py`        | The repository plugin: the categories, the title rules, the configs, the key/value protocol. |
| `products.jsonl`         | The store's listings the catalog is derived from.                                            |
| `update_products.py`     | Merges listings into `products.jsonl` and reports what is served and why the rest is not.    |
| `metric_nut.py`, `metric_washer.py` | The geometry of the `metric-nut` and `metric-washer` templates, by cq_warehouse.  |
| `test_catalog_repo.py`   | Unit tests: no network, no CAD kernel.                                                       |

The directory is not called `catalog`, and must not be. When PartCAD resolves
`//pub/svc/commerce/homedepot/catalog/...` it looks for a sub-folder of that
name before it looks at the package's dependencies, and on finding one without
a `partcad.yaml` it stops there — so every reference to the catalog from an
assembly fails as "Package not found", while the same reference typed at the
command line, after something else has loaded the catalog, works.
