#
# svc-commerce-homedepot, 2026
#
# Licensed under Apache License, Version 2.0.
#
"""Unit tests for the catalog repository plugin (no network, no CAD kernel).

The title rules, the configs they produce, the key/value dispatch, the shipped
product records and the script that maintains them are exercised directly.

    python -m pytest catalog-plugin
"""

import csv
import importlib.util
import json
import os
import re
import runpy

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plugin = _load("catalog_repo")
update = _load("update_products")

_M = "//pub/std/metric/m:"


def _served(title, slug="a-product", **extra):
    """(category, config) for a record made of one title."""
    return plugin.classify(dict({"id": "123456789", "title": title, "slug": slug}, **extra))


def _config(title, **extra):
    category, config = _served(title, **extra)
    assert category is not None, config
    return category, config


def _reason(title, **extra):
    category, why = _served(title, **extra)
    assert category is None, "served as %s: %s" % (category, why)
    return why


# --- the key/value protocol ---------------------------------------------------------


def test_the_root_holds_the_categories_and_nothing_else():
    assert plugin.get("deps") == ["lumber", "plywood", "bolts", "screws", "nuts", "washers"]
    meta = plugin.get("meta")
    assert meta["objectKinds"] == []
    assert plugin.get("objects/part") == {}
    assert plugin.get("files/anything") is None


def test_a_category_holds_parts_only():
    for category in plugin.CATEGORIES:
        assert plugin.get(category + "/deps") == []
        assert plugin.get(category + "/meta")["objectKinds"] == ["part"]
        assert plugin.get(category + "/objects/sketch") == {}
        assert plugin.get(category + "/objects/part"), category


def test_every_category_names_the_store_as_its_supplier():
    # A plugin-served package has no partcad.yaml for 'suppliers:' to be in, so
    # it is in the metadata: without it, a quote that names no provider finds
    # nobody to ask about any part of the catalog.
    for category in plugin.CATEGORIES:
        assert plugin.get(category + "/meta")["suppliers"] == {"//pub/svc/commerce/homedepot:homedepot": {}}


def test_one_part_is_the_part_the_enumeration_lists():
    parts = plugin.get("bolts/objects/part")
    item_id, config = next(iter(parts.items()))
    assert plugin.get("bolts/objects/part/" + item_id) == config
    # Asked for in another category, it is not there.
    assert plugin.get("nuts/objects/part/" + item_id) is None
    assert plugin.get("bolts/objects/part/000000000") is None


def test_the_script_answers_as_partcad_runs_it():
    # PartCAD runs the file with runpy, the request injected, under the API's name.
    path = os.path.join(_HERE, "catalog_repo.py")
    result = runpy.run_path(path, init_globals={"request": {"key": "nuts/meta"}}, run_name="get")["output"]
    assert result == {"result": plugin.get("nuts/meta")}


def test_the_cache_version_is_an_integer_literal():
    # PartCAD reads it out of the source with 'ast', without running anything.
    with open(os.path.join(_HERE, "catalog_repo.py")) as f:
        assert re.search(r"^CACHE_VERSION = \d+$", f.read(), re.M)


# --- lumber ---------------------------------------------------------------------------


def test_lumber_is_the_standard_at_its_nominal_size():
    category, config = _config("2 in. x 4 in. x 8 ft. #2 Premium Grade Fir Dimensional Lumber")
    assert category == "lumber"
    assert config["type"] == "enrich"
    assert config["source"] == "//pub/svc/commerce/homedepot:dimensional-lumber"
    # The standard's frame: the "4" is the width, the "2" the height.
    assert config["with"] == {"width": 4, "height": 2, "length": 96}
    assert "implements" not in config


def test_a_stud_length_has_a_fraction():
    _, config = _config("2 in. x 4 in. x 92-5/8 in. Prime Whitewood Stud")
    assert config["with"]["length"] == 92.625
    _, config = _config("2 in. x 4 in. x 92 5/8 in. #2 Premium Grade Whitewood Stud")
    assert config["with"]["length"] == 92.625


def test_a_post_and_a_board_are_lumber_too():
    assert _config("4 in. x 4 in. x 8 ft. #1 Pressure-Treated Post")[1]["with"] == {
        "width": 4,
        "height": 4,
        "length": 96,
    }
    assert _config("1 in. x 4 in. x 8 ft. Common Board")[1]["with"] == {"width": 4, "height": 1, "length": 96}


def test_lumber_that_is_not_dressed_to_the_standard_is_left_out():
    assert "rough" in _reason("4 in. x 4 in. x 8 ft. Rough Green Western Red Cedar Lumber")
    assert "s1s2e" in _reason("ProWood 2 in. x 4 in. x 10 ft. S1S2E Spruce Dimensional Lumber")
    assert "decking" in _reason("Outdoor Select 2 in. x 6 in. x 12 ft. Pressure-Treated Decking Boards")


def test_a_stated_actual_size_has_to_be_the_standards():
    # Within 1/16 in. of 1-1/2 x 3-1/2: an instance of the standard.
    _config("2 in. x 4 in. x 8 ft. Lumber (Actual: 1.5 in. x 3.5 in. x 96 in.)")
    _config("Timber (Common: 4 in. x 4 in. x 10 ft.; Actual: 3.56 in. x 3.56 in. x 120 in.)")
    # A quarter of an inch out is a different board.
    assert "actual size" in _reason("2 in. x 4 in. x 8 ft. Lumber (Actual: 1.75 in. x 3.5 in. x 96 in.)")


def test_a_section_the_standard_does_not_have_is_left_out():
    assert "nominal" in _reason("5/4 in. x 6 in. x 8 ft. Premium Lumber")
    assert "standard nominal section" in _reason("2 in. x 7 in. x 8 ft. Dimensional Lumber")


# --- plywood --------------------------------------------------------------------------


def test_a_panel_sold_by_its_actual_thickness_is_the_nominal_one():
    category, config = _config("Plytanium 23/32 in. x 4 ft. x 8 ft. BC Sanded Pine Plywood")
    assert category == "plywood"
    assert config["source"] == "//pub/svc/commerce/homedepot:plywood"
    assert config["with"] == {"width": 48, "length": 96, "thickness": 0.75}
    assert _config("15/32 in. x 4 ft. x 8 ft. CDX Plywood")[1]["with"]["thickness"] == 0.5
    assert _config("19/32 in. x 4 ft. x 8 ft. Sheathing Plywood")[1]["with"]["thickness"] == 0.625
    assert _config("11/32 in. x 4 ft. x 8 ft. Sheathing Plywood")[1]["with"]["thickness"] == 0.375
    # ... and one sold by its nominal thickness is that.
    assert _config("3/4 in. x 4 ft. x 8 ft. Birch Plywood")[1]["with"]["thickness"] == 0.75
    assert _config("1/4 in. x 2 ft. x 4 ft. Pine Sanded Plywood")[1]["with"] == {
        "width": 24,
        "length": 48,
        "thickness": 0.25,
    }


def test_a_panel_is_modelled_as_big_as_it_says_it_is():
    _, config = _config("Sanded Plywood (Common: 23/32 in. x 2 ft. x 2 ft.; Actual: 0.703 in. x 23.75 in. x 23.75 in.)")
    assert config["with"] == {"width": 23.75, "length": 23.75, "thickness": 0.75}


def test_a_panel_of_no_one_stated_thickness_is_left_out():
    assert "'or'" in _reason("Plytanium 11/32 in. or 3/8 in. x 4 ft. x 8 ft. BC Sanded Pine Plywood")
    assert "one stated thickness" in _reason("Swaner Hardwood 5.2 mm (1/4 in. Category) 4 ft. x 8 ft. Birch Plywood")
    assert "category" in _reason(
        "Sande Plywood (1/2 in. Category x 4 ft. x 8 ft.; Actual: 0.472 in. x 48 in. x 96 in.)"
    )
    assert "size" in _reason("Fir 15/32 4 x 8 CDX (4-PLY) Plywood")
    assert "actual size" in _reason("3/4 in. x 4 ft. x 8 ft. Plywood (Actual: 0.625 in. x 48 in. x 96 in.)")


# --- bolts and screws -----------------------------------------------------------------


def test_a_hex_bolt_is_cq_warehouses_and_implements_the_m_bolt():
    category, config = _config("Everbilt M4-0.7 x 20 mm Class 8.8 Zinc Plated Hex Bolt (2-Pack)")
    assert category == "bolts"
    assert config["source"] == "//pub/std/metric/cqwarehouse:fastener/hexhead-iso4017"
    assert config["with"] == {"size": "M4-0.7", "length": 20, "simple": False}
    # On the bearing face, its Z up into the head: cq_warehouse's frame.
    assert config["implements"] == {_M + "m-bolt-length;size=4,length=20": [[0, 0, 0], [1, 0, 0], 0]}
    assert config["count_per_sku"] == 2


@pytest.mark.parametrize(
    "title, category, part",
    [
        ("Everbilt M6-1.0 x 30 mm Zinc-Plated Steel Flange Bolt (2 per Bag)", "bolts", "hexheadwithflange-din1665"),
        ("Everbilt M10-1.5x30mm Zinc Hex Head External Hex Drive Cap Screw 2-Pieces", "bolts", "hexhead-iso4017"),
        ("Hillman M8-1.25 x 30 mm Internal Hex Socket Cap-Head Cap Screws (5-Pack)", "screws", "socketheadcap-iso4762"),
        ("Hillman M5-0.8 x 16 mm Internal Hex Button-Head Cap Screws (10-Pack)", "screws", "buttonhead-iso7380-1"),
        ("Hillman M5-0.8 x 16 mm Internal Hex Flat-Head Cap Screw (12-Pack)", "screws", "countersunk-iso10642"),
        ("Everbilt M5-0.8 x 20 mm Phillips Flat Head Stainless Steel Machine Screw", "screws", "countersunk-iso7046"),
        ("Everbilt M5-0.8 x 20mm Zinc Pan Head Phillips Drive Machine Screw", "screws", "raisedcheesehead-iso7045"),
        ("Everbilt M6-1.0 x 16 mm Combination Pan Head Machine Screw (2-Pack)", "screws", "raisedcheesehead-iso7045"),
    ],
)  # fmt: skip
def test_each_head_is_drawn_by_its_cq_warehouse_part(title, category, part):
    got, config = _config(title)
    assert got == category
    assert config["source"] == "//pub/std/metric/cqwarehouse:fastener/" + part


def test_a_machine_screw_is_a_bolt_in_the_standards_sense():
    # It goes into a thread that is there; 'm-screw' is for one that cuts its own.
    _, config = _config("Everbilt M3-0.5 x 10 mm Phillips Pan Head Zinc Plated Machine Screw (3-Pack)")
    assert list(config["implements"]) == [_M + "m-bolt-length;size=3,length=10"]


def test_every_spelling_of_a_thread_is_read():
    for title in (
        "Everbilt M8-1.25 x 25 mm Zinc Hex Bolt",
        "Everbilt 8 mm-1.25 x 25 mm Zinc-Plated Metric Hex Bolt",
        "Everbilt M8 -1.25 x 25 mm Hex Bolt",
        "Everbilt M8-1.25x25mm Zinc Hex Head External Hex Drive Hex Bolt 1-Piece",
        "Everbilt M8 x 25 mm Zinc Hex Bolt",  # no pitch: ISO's way of writing the coarse one
    ):
        assert _config(title)[1]["with"]["size"] == "M8-1.25", title
    assert _config("Everbilt M3-.5 x 10 mm Socket Cap Screw")[1]["with"]["size"] == "M3-0.5"
    assert _config("Everbilt 10 mm - 1.5 mm x 25 mm Metric Flat-Head Phillips Machine Screw")[1]["with"] == {
        "size": "M10-1.5",
        "length": 25,
        "simple": False,
    }


def test_a_fine_thread_is_not_the_standards():
    assert "coarse" in _reason("Everbilt M10-1.25 x 50 mm Class 8.8 Zinc Plated Hex Bolt")
    assert "coarse" in _reason("Everbilt M12-1.5 x 40 mm Zinc Class 8.8 Metric Hex Bolt")


def test_a_title_with_a_typo_in_it_is_not_read_as_something_else():
    assert "coarse" in _reason("Everbilt M8-40 x 40 mm External Hex Hex-Head Cap Screws (2-Pack)")
    assert "coarse" in _reason("Everbilt M4-7 x 30 mm. Phillips -Slotted Pan-Head Machine Screws")
    assert "thread" in _reason("Everbilt 14 mm x 2.0 in. x 40 mm Grade 8.8 Zinc Plated Hex Head Cap Screw")
    assert "length" in _reason("Everbilt M6 x 30 Zinc-Plated Pan-Head Combo Drive Machine Screws (2-Pieces)")


def test_a_size_that_has_no_geometry_is_left_out():
    assert "geometry" in _reason("Everbilt M7-1.0 x 60 mm Class 8.8 Zinc Plated Hex Bolt")


def test_kits_and_other_fasteners_are_left_out():
    assert "with nuts" in _reason("MYWISH M8 x 16 mm Uncoated Flange Bolt with Nuts and Washers (10-Pack)")
    assert "carriage" in _reason("Everbilt M8-1.25 x 50 mm Carriage Bolt")
    assert "wood" in _reason("Everbilt M4 x 20 mm Wood Screw")


# --- nuts and washers -----------------------------------------------------------------


def test_a_nut_is_a_thread_right_through_entered_from_either_face():
    category, config = _config("Everbilt 4 mm-0.7 Zinc-Plated Metric Hex Nut (2-Piece)")
    assert category == "nuts"
    assert config["source"] == "//pub/svc/commerce/homedepot:metric-nut"
    assert config["with"] == {"size": "M4-0.7", "fastener_type": "iso4032"}
    # ISO 4032's M4 is 3.2 mm tall; the far face is turned over.
    assert config["implements"] == {
        _M
        + "m-threaded-thru-depth;size=4,depth=3.2": {
            "bottom": [[0, 0, 0], [1, 0, 0], 0],
            "top": [[0, 0, 3.2], [1, 0, 0], 180],
        }
    }


def test_each_nut_is_its_standards():
    assert _config("Everbilt M8-1.25 Zinc Flange Nut 2-Pieces")[1]["with"]["fastener_type"] == "din1665"
    assert _config("Everbilt M8-1.25 Zinc Jam Nut")[1]["with"]["fastener_type"] == "iso4035"
    _, config = _config("Prime-Line M8-1.25 Metric Grade A2-70 Stainless Steel Acorn Cap Nuts (10-Pack)")
    assert config["with"]["fastener_type"] == "din1587"
    # A cap nut's thread is blind: one opening.
    assert config["implements"] == {_M + "m-tapped-hole;size=8,depth=6.5": {"bottom": [[0, 0, 0], [1, 0, 0], 0]}}
    assert config["count_per_sku"] == 10


def test_a_nut_nothing_can_draw_is_left_out():
    assert "lock nut" in _reason("Everbilt M10-1.5 Zinc-Plated Nylon Lock Nut")
    assert "lock nut" in _reason("Everbilt M12-1.75 Zinc-Plated Metric Flange Lock Nut (2-Piece per Bag)")
    assert "wing nut" in _reason("Everbilt M5-0.8 Metric Zinc Plated Wing Nut (3-Pack)")
    # cq_warehouse's table makes the M10 cap nut 88 mm tall.
    assert "geometry" in _reason("Everbilt M10-1.5 Stainless Steel Cap Nut")


def test_a_washer_is_a_clearance_hole_through_its_thickness():
    category, config = _config("Everbilt M6 Zinc-Plated Metric Flat Washer (5-Piece/Bag)")
    assert category == "washers"
    assert config["source"] == "//pub/svc/commerce/homedepot:metric-washer"
    assert config["with"] == {"size": "M6", "fastener_type": "iso7089"}
    assert config["implements"] == {
        _M
        + "m-thru-depth;size=6,depth=1.8": {
            "bottom": [[0, 0, 0], [1, 0, 0], 0],
            "top": [[0, 0, 1.8], [1, 0, 0], 180],
        }
    }
    assert config["count_per_sku"] == 5


def test_a_washer_is_named_by_the_screw_it_takes():
    for title in (
        "Everbilt 8 mm Stainless Steel Metric Flat Washer (3-Piece)",
        "Hillman Stainless Steel Metric Flat Washer (M8 Screw Size)",
        "Everbilt M8 Zinc-Plated Metric Flat Washer (5-Piece/Bag)",
    ):
        assert _config(title)[1]["with"]["size"] == "M8", title
    assert _config("Hillman Metric Stainless Fender Washer (M8)")[1]["with"]["fastener_type"] == "iso7093"


def test_a_stated_outside_diameter_has_to_be_the_standards():
    _config("Everbilt 10 mm x 20 mm Zinc-Plated Steel Metric Flat Washers (3-Pack)")
    assert "outside diameter" in _reason("Everbilt 10 mm x 25 mm Zinc-Plated Steel Metric Flat Washers (3-Pack)")


def test_a_lock_washer_is_left_out():
    assert "lock washer" in _reason("Everbilt M8 Zinc-Plated Split Lock Washers (4-Pieces)")
    assert "lock washer" in _reason("Everbilt M6 Zinc Grade 10.9 Metric Lock Washer (5-Piece per Bag)")


# --- one product ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title, count",
    [
        ("Everbilt M6-1.0 x 30 mm Class 8.8 Zinc Plated Hex Bolt", 1),
        ("... Hex Bolt (2-Pack)", 2),
        ("... Hex Bolt (2 per Bag)", 2),
        ("... Hex Nut 5PC (19A)", 5),
        ("... Flange Nut Metric (2-Bag)", 2),
        ("... Flat Washer (5-Piece/Bag)", 5),
        ("... Lock Washer (5-Piece per Bag)", 5),
        ("... Cap Screw Hex Head M10-1.5x70 mm Zinc 1Piece", 1),
        ("Everbilt 4-Piece M4 Stainless Steel Metric Lock Washer", 4),
        ("... Hex Head Cap Screws Treated with NL-19 (10-Pack)", 10),
        ("... Machine Screw (2-Pack) (D43-S)", 2),
        ("... (2-Pack) ... (3-Pack)", None),
    ],
)  # fmt: skip
def test_the_pack_size_is_what_a_quote_divides_by(title, count):
    assert plugin._pack(title) == count


def test_a_product_is_bought_by_its_item_id():
    category, config = plugin.classify(
        {"id": "204275876", "title": "Everbilt 4 mm-0.7 Zinc-Plated Metric Hex Nut (2-Piece)", "slug": "x"}
    )
    assert config["vendor"] == "homedepot"
    assert config["sku"] == "204275876"
    assert config["count_per_sku"] == 2
    assert config["desc"] == "Everbilt 4 mm-0.7 Zinc-Plated Metric Hex Nut (2-Piece)"


def test_a_product_listed_under_titles_that_disagree_is_left_out():
    title = "Everbilt M5-0.8 x 12mm Zinc Pan Head Phillips Drive Machine Screw 4-Pieces"
    assert "disagree" in _reason(
        title, alt_titles=["Everbilt M5-0.8x12mm Zinc Pan Head Phillips Drive Machine Screw 2-Pieces"]
    )
    # Titles that only word the same product differently are fine.
    _config(
        "Everbilt M6-1.0 x 30 mm Class 10.9 Zinc Plated Hex Bolt (2-Pack)",
        alt_titles=["Everbilt M6 x 30 mm Zinc-Plated Steel Hex-Head Cap Screws (2 per Bag)"],
    )


def test_a_product_whose_url_names_another_kind_is_left_out():
    title = "Everbilt Cap Screw Hex Head M10-1.5x70 mm Zinc 1Piece"
    slug = "Everbilt-M10-1-5x70-mm-Zinc-Socket-Cap-Head-Internal-Hex-Drive-Cap-Screw-2-Pieces-837111"
    assert "disagree" in _reason(title, slug=slug)
    assert _config(title, slug="Everbilt-M10-Hex-Head-Cap-Screw-837111")[0] == "bolts"


# --- the shipped records ----------------------------------------------------------------


def _records():
    with open(os.path.join(_HERE, "products.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_the_shipped_records_are_what_update_products_writes():
    records = _records()
    ids = [r["id"] for r in records]
    assert ids == sorted(ids), "sorted by item ID, so that a diff is the products that changed"
    assert len(ids) == len(set(ids))
    for record in records:
        assert re.fullmatch(r"[0-9]{9}", record["id"])
        assert set(record) <= set(update._FIELDS)
        assert record["title"] and record["slug"]


def test_the_products_this_package_already_lists_are_served_as_it_lists_them():
    # The hand-written parts in partcad.yaml name four of the same SKUs, with
    # the same sizes; the catalog has to agree with them.
    served = {}
    for category in plugin.CATEGORIES:
        served.update(plugin.catalog(category))
    assert served["202094172"]["with"] == {"width": 4, "height": 2, "length": 96}  # lumber/2x4x8
    assert served["100061386"]["with"] == {"width": 48, "length": 96, "thickness": 0.75}  # plywood/23-32x4x8
    assert served["204273651"]["with"]["size"] == "M4-0.7"  # the M4-0.7 x 20 mm bolt
    assert served["204273651"]["count_per_sku"] == 2
    assert served["204275876"]["with"]["size"] == "M4-0.7"  # the M4-0.7 hex nut
    assert served["204275876"]["count_per_sku"] == 2


def test_every_category_serves_something_from_the_shipped_records():
    counts = {category: len(plugin.catalog(category)) for category in plugin.CATEGORIES}
    assert all(counts.values()), counts


# --- the inlined tables -----------------------------------------------------------------


def _cq_warehouse_tables():
    spec = importlib.util.find_spec("cq_warehouse")
    if spec is None or not spec.submodule_search_locations:
        pytest.skip("cq_warehouse is not installed here")
    return spec.submodule_search_locations[0]


def _csv(directory, name):
    with open(os.path.join(directory, name)) as f:
        return list(csv.DictReader(f))


def test_the_nut_heights_are_cq_warehouses():
    directory = _cq_warehouse_tables()
    files = {"iso4032": "hex_nut_parameters.csv", "iso4035": "hex_nut_parameters.csv"}
    files.update({"din1665": "hex_nut_with_flange_parameters.csv", "din1587": "domed_cap_nut_parameters.csv"})
    for fastener_type, heights in plugin.NUT_HEIGHT.items():
        table = {row["Size"]: row for row in _csv(directory, files[fastener_type])}
        for size, height in heights.items():
            assert float(table[size][fastener_type + ":m"]) == height, (fastener_type, size)


def test_the_washer_sizes_are_cq_warehouses():
    directory = _cq_warehouse_tables()
    table = {row["Size"]: row for row in _csv(directory, "plain_washer_parameters.csv")}
    for fastener_type, sizes in plugin.WASHER_SIZE.items():
        for size, dimensions in sizes.items():
            got = tuple(float(table[size]["%s:%s" % (fastener_type, key)]) for key in ("d1", "d2", "h"))
            assert got == dimensions, (fastener_type, size)


# --- update_products.py -----------------------------------------------------------------


def _write(path, records):
    with open(path, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


def test_update_merges_a_listing_and_keeps_the_title_it_replaces(tmp_path, monkeypatch, capsys):
    products = tmp_path / "products.jsonl"
    monkeypatch.setattr(update, "PRODUCTS", str(products))
    _write(products, [{"id": "204273651", "title": "Old Title M4-0.7 x 20 mm Hex Bolt", "slug": "s", "model": "1"}])
    listing = tmp_path / "listing.jsonl"
    _write(
        listing,
        [
            {
                "id": "204273651",
                "title": "Everbilt M4-0.7 x 20 mm Hex Bolt",
                "slug": "s",
                "url": "https://www.homedepot.com/p/s/204273651",
                "query": "dropped",
            },
            {"id": "20427365", "title": "Not an item ID", "slug": "s"},
            {"id": "204273652", "title": "Wrong URL", "slug": "s", "url": "https://www.homedepot.com/p/t/204273652"},
        ],
    )
    update.main([str(listing)])
    assert update.read(str(products)) == [
        {
            "id": "204273651",
            "title": "Everbilt M4-0.7 x 20 mm Hex Bolt",
            "slug": "s",
            "alt_titles": ["Old Title M4-0.7 x 20 mm Hex Bolt"],
            "model": "1",
        }
    ]
    assert "1 products, 1 served" in capsys.readouterr().out
