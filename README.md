# //pub/svc/commerce/homedepot

The Home Depot online store.

This package can be used for cost estimates for assemblies that use Homedepot parts.
Placing orders is not implemented yet.

## Dimensional lumber

Lumber and plywood are declared as instances of the standard sizes in
[`//pub/std/imperial/dimensional-lumber`](https://github.com/partcad/partcad-standard-imperial-dimensional-lumber).
Two generic templates, `dimensional-lumber` and `plywood`, are the store's
products of any size: parametric, with the vendor and **no SKU**, since there is
nothing to order until a size is chosen. Each stocked product is an `enrich` of
a template at its nominal size, with the SKU it is sold under. The geometry is
the standard's, in its frame (width along X, length along Y, thickness along Z).

| Part                        | Product                                                   | SKU         |
|-----------------------------|-----------------------------------------------------------|-------------|
| `lumber/2x4x8`              | 2 in. x 4 in. x 8 ft. #2 Premium Grade Fir                | 202094172   |
| `lumber/2x4x20`             | 2 in. x 4 in. x 20 ft. #2 Premium Grade Hem-Fir           | 202083072   |
| `lumber/2x6x8`              | 2 in. x 6 in. x 8 ft. #2 Premium Grade Fir                | 100026460   |
| `lumber/4x4x8`              | 4 in. x 4 in. x 8 ft. #2 Premium Grade Fir                | 202094374   |
| `plywood/23-32x4x8`         | 23/32 in. x 4 ft. x 8 ft. BC Sanded Pine Plywood          | 100061386   |

A part cut to size from one of them names it as its stock, in the same
coordinates:

```yaml
manufacturing:
  method: subtractive
  source: //pub/svc/commerce/homedepot:lumber/4x4x8
  cut:
    cuts:
      - along: +Y
        length: $length in
```

## Catalog

The store's products that a PartCAD standard describes are served as
[`//pub/svc/commerce/homedepot/catalog`](catalog-plugin/README.md), one
sub-package per category, each product a part named by its item ID (the
"Internet #" its URL ends with) and carrying that as its SKU. For now that is
dimensional lumber and plywood, as instances of the standard sizes above, and
metric fasteners, which implement the
[`//pub/std/metric/m`](https://github.com/partcad/partcad-standard-metric-m)
interfaces so that an assembly can put them together with `connect:`:

| Sub-package       | Products | Geometry                                                    | Implements                     |
|-------------------|---------:|-------------------------------------------------------------|--------------------------------|
| `catalog/lumber`  | 185      | `dimensional-lumber`                                        | —                              |
| `catalog/plywood` | 117      | `plywood`                                                   | —                              |
| `catalog/bolts`   | 107      | `//pub/std/metric/cqwarehouse` (hex, flange)                | `m-bolt-length`                |
| `catalog/screws`  | 150      | `//pub/std/metric/cqwarehouse` (socket, button, flat, pan)  | `m-bolt-length`                |
| `catalog/nuts`    | 45       | `metric-nut` (hex, flange, cap)                             | `m-threaded-thru-depth`, `m-tapped-hole` |
| `catalog/washers` | 36       | `metric-washer` (flat, fender)                              | `m-thru-depth`                 |

`metric-nut` and `metric-washer` are two more templates of the same kind as
`dimensional-lumber`: cq_warehouse's nuts and washers, which
`//pub/std/metric/cqwarehouse` does not publish yet.
`hardware/fasteners/catalog_assembly` is `hardware/fasteners/fastener_assembly`
built from the catalog, through those interfaces, with nothing placed by hand:

```shell
$ pc list parts //pub/svc/commerce/homedepot/catalog/nuts
$ pc info //pub/svc/commerce/homedepot/catalog/bolts:204273651
$ pc inspect -a hardware/fasteners/catalog_assembly
```

See [`catalog-plugin/README.md`](catalog-plugin/README.md) for how each product
is read, what is left out and why, and how to add to it.


## Screws for wood

Screws are declared the way the lumber is: one generic template, `wood-screw`,
drawn by `hardware/fasteners/screws/wood_screw.py` from the sizes a product page
gives (in inches), with the vendor and **no SKU**; and each product an `enrich`
of it at its sizes, with the SKU it is sold under and as many to the SKU as come
in the box.

| Part                  | Product                                                                                         | SKU       | In a box |
|-----------------------|-------------------------------------------------------------------------------------------------|-----------|----------|
| `screws/sdws22600db`  | Simpson Strong-Tie 0.220 in. x 6 in. T40 Washer Head Strong-Drive SDWS Timber Screw, Exterior Grade | 321563353 | 12       |
| `screws/spax-8x2`     | SPAX #8 x 2 in. T-Star Plus Drive Flat-Head Partial Thread Yellow Zinc Coated Multi-Material Screw | 202040969 | 161      |

A screw is drawn along Z, point down, with z = 0 the plane that is flush with
the surface once it is driven home. Its `tip` port is what is put against the
place it goes in, with +Z up the shank, and a connection's `drive` takes it in
that far -- which is what the ports of
[`//pub/std/imperial/dimensional-lumber`](https://github.com/partcad/partcad-standard-imperial-dimensional-lumber)
take, in from an edge (`fromEdge`) and into the board (`drive`):

```yaml
- part: //pub/svc/commerce/homedepot:screws/sdws22600db
  connect:
    name: apron
    to: //pub/std/imperial/dimensional-lumber:cuboid
    toPort: y0-x0
    toParams: { fromEdge: 25.4, drive: 63.5 }
    withPort: tip
    how: { selfScrew: true }
```


## Usage
Get an estimate for a hex nut:

```shell
$ pc supply quote --provider homedepot hardware/fasteners/nuts/hex_nuts/4_mm_0_7_zinc_plated_metric_hex_nut_2_piece
...
INFO:  The following quotes are received:
INFO:           //pub/svc/commerce/homedepot:homedepot: HB100174664951: $1.44
INFO:                   hardware/fasteners/nuts/hex_nuts/4_mm_0_7_zinc_plated_metric_hex_nut_2_piece#1
...
```

The same for a product from the catalog, which has to name the provider for
now (see [Quotes](catalog-plugin/README.md#quotes)):

```shell
$ pc supply quote --provider homedepot //pub/svc/commerce/homedepot/catalog/nuts:204275876
```


<br/><br/>

*Generated by [PartCAD](https://partcad.org/)*
