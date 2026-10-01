#
# svc-commerce-homedepot, 2026
#
# Licensed under Apache License, Version 2.0.
#
"""A PartCAD 'basic' repository plugin that serves The Home Depot's catalog.

Published as ``//pub/svc/commerce/homedepot/catalog``: this package's external
dependency 'catalog' is the root, and its children - served from here - are the
categories. Each category holds the store's products as parts, named by the
store's own item ID (the "Internet #" a product URL ends with), which is also
the SKU the 'homedepot' store provider orders by.

Only products that a standard in the PartCAD index can describe are served:

* dimensional lumber and plywood, as instances of
  ``//pub/std/imperial/dimensional-lumber`` at the product's nominal size;
* metric fasteners, which implement the ``//pub/std/metric/m`` interfaces and
  take their geometry from ``//pub/std/metric/cqwarehouse`` (bolts and screws)
  or from the store's own cq_warehouse templates (nuts and washers).

Everything is derived from the product's title, which is read and not guessed
at: a title the rules below do not understand completely is left out, with the
reason, rather than served as something it may not be. The titles themselves
are the records in 'products.jsonl' beside this file; see 'update_products.py'.

PartCAD runs this script once per data request (via ``runpy``); the answer is
returned in the global ``output`` as ``{"result": <value>}``. Keys are scoped by
sub-package, e.g. ``bolts/objects/part`` or ``nuts/objects/part/204275876``.
"""

import json
import os
import re
import sys

# When this plugin's answers stopped meaning what they meant before.
#
# PartCAD keys the cache of everything this returns on this number, and nothing
# else tells it that the rules below have changed: an existing checkout goes on
# being served what it cached until this is raised. Raise it with any change to
# what a product is served as - a rule, a table, a template - and with any
# change to 'products.jsonl'.
#
# v1 was the first catalog; v2 draws the fasteners with their threads and names
# the store as every category's supplier.
CACHE_VERSION = 2

_VENDOR = "homedepot"
_STORE = "//pub/svc/commerce/homedepot"

# The standards, and what of each a product is an instance of.
_LUMBER = _STORE + ":dimensional-lumber"  # an alias of //pub/std/imperial/dimensional-lumber:lumber
_PLYWOOD = _STORE + ":plywood"  # an alias of //pub/std/imperial/dimensional-lumber:plywood
_NUT = _STORE + ":metric-nut"  # cq_warehouse's nuts, which //pub/std/metric/cqwarehouse lacks
_WASHER = _STORE + ":metric-washer"  # ... and its washers
_CQWAREHOUSE = "//pub/std/metric/cqwarehouse:fastener/"
_M = "//pub/std/metric/m:"

# Who sells what the catalog holds: this package's own store provider. Stated
# in every category's metadata, because a package served by a plugin has no
# partcad.yaml for a 'suppliers:' section to be in, and a part is looked for at
# the suppliers of the package it is in - so without it a quote that names no
# provider finds nobody to ask.
SUPPLIERS = {_STORE + ":homedepot": {}}

_PRODUCTS_FILE = "products.jsonl"

# The sub-packages, in the order a reader would look for them.
CATEGORIES = {
    "lumber": "Dimensional lumber, as instances of //pub/std/imperial/dimensional-lumber:lumber.",
    "plywood": "Plywood panels, as instances of //pub/std/imperial/dimensional-lumber:plywood.",
    "bolts": "Metric hex and flange bolts, implementing //pub/std/metric/m:m-bolt-length.",
    "screws": "Metric machine screws, implementing //pub/std/metric/m:m-bolt-length.",
    "nuts": "Metric nuts, implementing the //pub/std/metric/m tapped openings.",
    "washers": "Metric plain washers, implementing //pub/std/metric/m:m-thru-depth.",
}

# A category holds parts and nothing else, and the root holds only the
# categories. Said in every package's metadata so that PartCAD does not ask
# after the other nine kinds of object, one run of this script per kind.
_ROOT_OBJECT_KINDS = []
_CATEGORY_OBJECT_KINDS = ["part"]

_INCH_MM = 25.4

# --- numbers -----------------------------------------------------------------


def _number(value):
    """A float as the int it is, if it is one, so configs read '30' and not '30.0'."""
    value = round(float(value), 6)
    return int(value) if value == int(value) else value


def _num(value):
    """A number as it is written in an interface reference: 'size=6,length=30'."""
    return "%g" % _number(value)


# --- what a title says ---------------------------------------------------------


def _words(text):
    """A title (or a URL slug) reduced to lower-case words, for matching keywords.

    Hyphens and slashes are word breaks here: "Flat-Head", "Flat Head" and the
    slug's "Flat-Head" are one spelling, and so are "Socket Cap-Head" and
    "Socket Cap Head". Numbers are not read out of this form - a slug has lost
    its decimal points - only words.
    """
    return " ".join(re.sub(r"[-/]", " ", text.lower()).split())


# How many pieces one SKU is: "(2-Pack)", "2-Pieces", "5PC", "(3 per Bag)",
# "(5-Piece/Bag)", "(2-Piece per Bag)", "(2-Bag)", "1Piece". A part is one piece
# and the store sells it by the SKU, so this is the 'count_per_sku' a quote
# divides by.
_PACK_RES = (
    re.compile(r"(?<![\w.])(\d+)\s*-?\s*(?:packs?|pieces?|pcs?|pk)\b", re.I),
    re.compile(r"(?<![\w.])(\d+)\s+per\s+(?:bag|pack|box)\b", re.I),
    re.compile(r"(?<![\w.])(\d+)\s*-\s*bag\b", re.I),
)


def _pack(title):
    """The pieces per SKU the title states, 1 if it states none, None if it contradicts itself."""
    counts = {int(m.group(1)) for r in _PACK_RES for m in r.finditer(title)}
    if not counts:
        return 1
    if len(counts) > 1 or 0 in counts:
        return None
    return counts.pop()


# --- lumber and plywood ---------------------------------------------------------
#
# What //pub/std/imperial/dimensional-lumber models: the nominal size is the
# parameter and the dressed size is the geometry (PS 20: a nominal 1 in. is
# 3/4 in., 2 to 7 in. lose 1/2 in., 8 in. and up lose 3/4 in.; plywood is 1/32
# in. thinner than its nominal thickness). Each part is made to a tolerance - the
# standard's own default, 1/16 in. for lumber and 1/32 in. for plywood - and a
# product whose title states an actual size outside that is not an instance of
# the standard, whatever its nominal size says.

_LUMBER_SIZES = (1, 2, 3, 4, 5, 6, 8, 10, 12)  # the standard's 'enum'
_LUMBER_TOLERANCE_IN = 1.6 / _INCH_MM
_PLYWOOD_TOLERANCE_IN = 0.8 / _INCH_MM


def _dressed(nominal):
    """The actual size of a nominal lumber dimension, in inches (PS 20)."""
    if nominal == 1:
        return 0.75
    return nominal - (0.5 if nominal < 8 else 0.75)


_LENGTH = r"(?P<len>\d+(?:\.\d+)?)(?:[\s-]+(?P<num>\d+)/(?P<den>\d+))?\s*(?P<unit>in|ft)\b\.?"
_LUMBER_RE = re.compile(r"(?<![\d/.])(?P<a>\d+)\s*in\.?\s*x\s*(?P<b>\d+)\s*in\.?\s*x\s*" + _LENGTH, re.I)
_PANEL_RE = re.compile(
    r"(?<![\d/.])(?P<t>\d+/\d+|\d*\.\d+|\d+)\s*in\.?\s*(?:x\s*)?"
    r"(?P<w>\d+(?:\.\d+)?)\s*(?P<wu>ft|in)\.?\s*x\s*(?P<l>\d+(?:\.\d+)?)\s*(?P<lu>ft|in)\b",
    re.I,
)
# "(Actual: 0.703 in. x 48 in. x 96 in.)", "Actual Post Size: 3.5 in. x ...",
# "Actual Dimensions: 0.70 in. x ...", "(actual 0.188 in. x 48 in. x 96 in.)".
_ACTUAL_RE = re.compile(
    r"actual[^:\d]{0,20}:?\s*(?P<a>\d*\.?\d+)\s*in\.?\s*x\s*(?P<b>\d*\.?\d+)\s*in\.?\s*x\s*(?P<c>\d*\.?\d+)\s*in\b",
    re.I,
)

# Lumber that is not dressed to PS 20, or not a rectangle, or not wood, whatever
# size its title gives: rough-sawn and band-sawn faces, a board surfaced on one
# side only, decking (radius edges), tongue and groove, pickets, mouldings.
_LUMBER_NOT = re.compile(
    r"\b(rough|band sawn|s1s2e|decking|tongue|groove|t&g|lattice|round|gothic|dog ear|picket|"
    r"steel|metal|vinyl|composite|pvc|moulding|molding|trim)\b"
)
_LUMBER_IS = re.compile(r"\b(lumber|stud|studs|post|posts|board|boards|timber|furring)\b")

# Not a plywood panel of one stated thickness: a thickness given only as a
# "category", or as one of two, or in millimetres; and the engineered panels
# and profiled sheets that are sold beside plywood.
_PLYWOOD_NOT = re.compile(
    r"\b(category|or|mm|\d+mm|osb|mdf|tongue|groove|t&g|siding|t1 11|beadboard|underlayment|hardboard|particle)\b"
)
_PLYWOOD_IS = re.compile(r"\b(plywood|plyform)\b")


def _length_in(m):
    value = float(m.group("len"))
    if m.group("num"):
        value += int(m.group("num")) / int(m.group("den"))
    return value * (12 if m.group("unit").lower() == "ft" else 1)


def _actual(title):
    """The actual size a title states, as three floats in inches, or None."""
    m = _ACTUAL_RE.search(title)
    return None if m is None else tuple(float(m.group(k)) for k in "abc")


def _lumber(title):
    """(config, None) for a piece of dimensional lumber, or (None, why not)."""
    words = _words(title)
    m = _LUMBER_RE.search(title)
    if m is None:
        return None, "no nominal 'A in. x B in. x L' size"
    if _LUMBER_NOT.search(words):
        return None, "not dressed lumber of a standard section: %r" % _LUMBER_NOT.search(words).group(1)
    if not _LUMBER_IS.search(words):
        return None, "not said to be lumber"
    height, width = sorted((int(m.group("a")), int(m.group("b"))))
    if height not in _LUMBER_SIZES or width not in _LUMBER_SIZES:
        return None, "not a standard nominal section: %d x %d" % (height, width)
    length = _length_in(m)
    if not 6 <= length <= 480:
        return None, "not a plausible length: %g in." % length
    actual = _actual(title)
    if actual is not None:
        expected = (_dressed(height), _dressed(width), length)
        if any(abs(a - e) > _LUMBER_TOLERANCE_IN for a, e in zip(sorted(actual[:2]) + [actual[2]], expected)):
            return None, "the stated actual size is not the standard's: %s" % (actual,)
    return {
        "type": "enrich",
        "source": _LUMBER,
        "with": {"width": width, "height": height, "length": _number(length)},
    }, None


def _nominal_panel_thickness(text):
    """A plywood thickness label as the nominal thickness the standard takes.

    A panel sold as "23/32 in." is the one the trade calls 3/4 in.: the label is
    its actual thickness, and the nominal one is 1/32 in. more. So an odd number
    of 32nds is an actual size and anything else is the nominal one.
    """
    if "/" in text:
        num, den = (int(v) for v in text.split("/"))
        if den == 32 and num % 2:
            return (num + 1) / 32
        return num / den
    return float(text)


def _plywood(title):
    """(config, None) for a plywood panel, or (None, why not)."""
    words = _words(title)
    if not _PLYWOOD_IS.search(words):
        return None, "not said to be plywood"
    if _PLYWOOD_NOT.search(words):
        return None, "not one plywood panel of one stated thickness: %r" % _PLYWOOD_NOT.search(words).group(1)
    # The actual size is read on its own, and taken out first, so that a title
    # giving only "Actual: 0.703 in. x 48 in. x 96 in." is not read as a label.
    actual = _actual(title)
    m = _PANEL_RE.search(_ACTUAL_RE.sub("", title))
    if m is None:
        return None, "no 'T in. x W ft. x L ft.' size"
    thickness = _nominal_panel_thickness(m.group("t"))
    if not 0 < thickness <= 1.25 or abs(thickness * 32 - round(thickness * 32)) > 1e-9:
        return None, "not a plausible panel thickness: %s in." % m.group("t")
    sides = sorted(float(m.group(k)) * (12 if m.group(k + "u").lower() == "ft" else 1) for k in "wl")
    if actual is not None:
        if abs(actual[0] - (thickness - 1 / 32)) > _PLYWOOD_TOLERANCE_IN:
            return None, "the stated actual size is not the standard's: %g in. thick" % actual[0]
        # The standard's width and length are the actual ones, so a panel whose
        # title says how big it really is is modelled that big.
        sides = sorted(actual[1:])
    return {
        "type": "enrich",
        "source": _PLYWOOD,
        "with": {"width": _number(sides[0]), "length": _number(sides[1]), "thickness": _number(thickness)},
    }, None


# --- metric fasteners --------------------------------------------------------------
#
# ISO 261's coarse pitch per nominal size, which is the thread //pub/std/metric/m
# states (its 'threadStep') and the one cq_warehouse's sizes are named by. An
# ISO designation that gives no pitch - "M6" - means this one; a fine thread is
# written out ("M10-1.25") and is a different thread, which neither standard
# names, so a product that has one is left out.
COARSE_PITCH = {
    1: 0.25, 1.2: 0.25, 1.4: 0.3, 1.6: 0.35, 2: 0.4, 2.5: 0.45, 3: 0.5, 3.5: 0.6,
    4: 0.7, 5: 0.8, 6: 1, 7: 1, 8: 1.25, 10: 1.5, 12: 1.75, 14: 2, 16: 2, 18: 2.5,
    20: 2.5, 22: 2.5, 24: 3, 27: 3, 30: 3.5, 33: 3.5, 36: 4,
}  # fmt: skip

# The sizes each //pub/std/metric/cqwarehouse part is declared for (its 'size'
# enum), by the part a head type is drawn with.
_SCREW_PARTS = {
    "hexhead-iso4017": (1.6, 2, 2.5, 3, 3.5, 4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 27, 30, 33, 36),
    "hexheadwithflange-din1665": (5, 6, 8, 10, 12, 14, 16, 20),
    "socketheadcap-iso4762": (1.6, 2, 2.5, 3, 3.5, 4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24),
    "buttonhead-iso7380-1": (3, 4, 5, 6, 8, 10, 12, 16),
    "countersunk-iso10642": (3, 4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24),
    "countersunk-iso7046": (1.6, 2, 2.5, 3, 3.5, 4, 5, 6, 8, 10),
    "raisedcheesehead-iso7045": (1.6, 2, 2.5, 3, 3.5, 4, 5, 6, 8, 10),
}

# The height of each nut cq_warehouse draws ('m' in its tables), by type and
# coarse size - which is also how deep its thread is, so it is what the ports
# on the far face and the interface's depth have to agree with. Inlined because
# this script runs without a CAD kernel and so without cq_warehouse; the test
# beside it checks it against cq_warehouse's own tables where those can be read.
NUT_HEIGHT = {
    # ISO 4032, the regular hexagon nut.
    "iso4032": {
        "M1.6-0.35": 1.3, "M2-0.4": 1.6, "M2.5-0.45": 2.0, "M3-0.5": 2.4, "M3.5-0.6": 2.8, "M4-0.7": 3.2,
        "M5-0.8": 4.7, "M6-1": 5.2, "M8-1.25": 6.8, "M10-1.5": 8.4, "M12-1.75": 10.8, "M14-2": 12.8,
        "M16-2": 14.8, "M18-2.5": 15.8, "M20-2.5": 18.0, "M22-2.5": 19.4, "M24-3": 21.5, "M27-3": 23.8,
        "M30-3.5": 25.6, "M33-3.5": 28.7, "M36-4": 31.0,
    },
    # ISO 4035, the thin ("jam") nut. cq_warehouse writes its M3 as "M3-0.45",
    # which is not the coarse M3 and so is never asked for.
    "iso4035": {
        "M1.6-0.35": 1.0, "M2-0.4": 1.2, "M2.5-0.45": 1.6, "M3.5-0.6": 2.0, "M4-0.7": 2.2, "M5-0.8": 2.7,
        "M6-1": 3.2, "M8-1.25": 4.0, "M10-1.5": 5.0, "M12-1.75": 6.0, "M14-2": 7.0, "M16-2": 8.0,
        "M18-2.5": 9.0, "M20-2.5": 10.0, "M22-2.5": 11.0, "M24-3": 12.0, "M27-3": 13.5, "M30-3.5": 15.0,
        "M33-3.5": 16.5, "M36-4": 18.0,
    },
    # DIN 1665, the hexagon nut with a flange.
    "din1665": {
        "M5-0.8": 5.0, "M6-1": 6.0, "M8-1.25": 8.0, "M10-1.5": 10.0, "M12-1.75": 12.0, "M14-2": 14.0,
        "M16-2": 16.0, "M20-2.5": 20.0,
    },
    # DIN 1587, the domed cap ("acorn") nut; the height is that of its blind
    # thread. cq_warehouse 0.8.0 gives its M10 as 88 mm, where DIN 1587 says 8,
    # and would build it that tall - so that one size is left out until it is
    # fixed there.
    "din1587": {
        "M4-0.7": 3.2, "M5-0.8": 4.0, "M6-1": 5.0, "M8-1.25": 6.5, "M12-1.75": 10.0, "M14-2": 11.0,
        "M16-2": 13.0, "M18-2.5": 15.0, "M20-2.5": 16.0, "M22-2.5": 18.0, "M24-3": 19.0,
    },
}  # fmt: skip

# Each plain washer cq_warehouse draws, as (hole, outside diameter, thickness):
# ISO 7089 the ordinary one, and ISO 7093 the large series a fender washer is.
WASHER_SIZE = {
    "iso7089": {
        "M1.6": (1.7, 4.0, 0.35), "M2": (2.2, 5.0, 0.35), "M2.5": (2.7, 6.0, 0.55), "M3": (3.2, 7.0, 0.55),
        "M3.5": (3.7, 8.0, 0.55), "M4": (4.3, 9.0, 0.9), "M5": (5.3, 10.0, 1.1), "M6": (6.4, 12.0, 1.8),
        "M7": (7.4, 14.0, 1.8), "M8": (8.4, 16.0, 1.8), "M10": (10.5, 20.0, 2.2), "M12": (13.0, 24.0, 2.7),
        "M14": (15.0, 28.0, 2.7), "M16": (17.0, 30.0, 3.3), "M18": (19.0, 34.0, 3.3), "M20": (21.0, 37.0, 3.3),
        "M22": (23.0, 39.0, 3.3), "M24": (25.0, 44.0, 4.3), "M27": (28.0, 50.0, 4.3), "M30": (31.0, 56.0, 4.3),
        "M33": (34.0, 60.0, 5.6), "M36": (37.0, 66.0, 5.6),
    },
    "iso7093": {
        "M2.5": (2.7, 8.0, 0.9), "M3": (3.2, 9.0, 0.9), "M3.5": (3.7, 11.0, 0.9), "M4": (4.3, 12.0, 1.1),
        "M5": (5.3, 15.0, 1.4), "M6": (6.4, 18.0, 1.8), "M7": (7.4, 22.0, 2.2), "M8": (8.4, 24.0, 2.2),
        "M10": (10.5, 30.0, 2.7), "M12": (13.0, 37.0, 3.3), "M14": (15.0, 44.0, 3.3), "M16": (17.0, 50.0, 3.3),
        "M18": (20.0, 56.0, 4.6), "M20": (22.0, 60.0, 4.6), "M24": (26.0, 72.0, 6.0), "M30": (33.0, 92.0, 7.0),
        "M36": (39.0, 110.0, 9.2),
    },
}  # fmt: skip

# "M6-1.0", "M6 -1.0", "M8 - 1.25", "M3-.5", "(M10-1.50)", and "M6" alone.
_THREAD_M_RE = re.compile(r"(?<![\w.])M\s?(?P<d>\d+(?:\.\d+)?)(?:\s*-\s*(?P<p>\d*\.\d+|\d+))?(?![\d.])", re.I)
# "4 mm-0.7", "5 mm - 0.8", "10 mm - 1.5 mm".
_THREAD_MM_RE = re.compile(r"(?<![\w.])(?P<d>\d+(?:\.\d+)?)\s*mm\s*-\s*(?P<p>\d*\.\d+|\d+)(?:\s*mm\b)?", re.I)
# What follows the designation of a screw: "x 20 mm", "x20mm", "x 30 Mm", "x 16 mm.".
_SCREW_LENGTH_RE = re.compile(r"\s*x\s*(?P<len>\d+(?:\.\d+)?)\s*mm\b", re.I)
# A washer is named by the screw it takes: "M8", "8 mm", "(M6 Screw Size)",
# "10 mm x 20 mm" (hole by outside diameter).
_WASHER_SIZE_RE = re.compile(
    r"(?<![\w.])(?:M\s?(?P<m>\d+(?:\.\d+)?)|(?P<mm>\d+(?:\.\d+)?)\s*mm)(?![\d.])"
    r"(?:\s*x\s*(?P<od>\d+(?:\.\d+)?)\s*mm\b)?",
    re.I,
)

# Not one fastener of the kinds below, whatever else the title says.
_FASTENER_NOT = re.compile(
    r"\b(kit|assortment|assorted|with nuts?|with washers?|set screws?|wood|sheet metal|self tapping|"
    r"self drilling|thread forming|thumb|eye|u bolt|lag|studs?|threaded rod|shoulder|truss|oval|"
    r"round head|rivet|anchor|hanger|toggle)\b"
)

# What a fastener is, from the words of its title or its URL. Ordered: the first
# rule that matches decides, so "Flange Lock Nut" is a lock nut before it is a
# flange nut, and "Internal Hex Flat-Head" is a socket screw before it is a
# flat head.
_KINDS = (
    # Washers.
    (r"\bwashers?\b", r"\b(lock|split|tooth|toothed|wave|spring|belleville)\b", "lock washer"),
    (r"\bwashers?\b", r"\bfender\b", "fender washer"),
    (r"\bwashers?\b", r"\bflat\b", "flat washer"),
    (r"\bwashers?\b", r"", "washer"),
    # Nuts.
    (r"\bnuts?\b", r"\b(lock|nylon|nylock|tension|prevailing)\b", "lock nut"),
    (r"\bnuts?\b", r"\bwing\b", "wing nut"),
    (r"\bnuts?\b", r"\bcoupling\b", "coupling nut"),
    (r"\bnuts?\b", r"\b(t|tee|kep|cage|square|slotted|castle|speed|push|barrel|weld)\b", "special nut"),
    (r"\bnuts?\b", r"\b(cap|acorn|domed)\b", "cap nut"),
    (r"\bnuts?\b", r"\bflange\b", "flange nut"),
    (r"\bnuts?\b", r"\bjam\b", "jam nut"),
    (r"\bnuts?\b", r"\bhex\b", "hex nut"),
    (r"\bnuts?\b", r"", "nut"),
    # Bolts and screws.
    (r"\b(bolts?|screws?)\b", r"\bcarriage\b", "carriage bolt"),
    (r"\b(bolts?|screws?)\b", r"\bflange\b", "flange bolt"),
    (r"\b(bolts?|screws?)\b", r"\bbutton\b", "button head socket cap screw"),
    (r"\b(bolts?|screws?)\b", r"\bflat head\b.*\b(internal hex|socket)\b|\b(internal hex|socket)\b.*\bflat head\b",
     "flat head socket cap screw"),
    (r"\b(bolts?|screws?)\b", r"\bsocket (cap|head)\b|\bcap head\b.*\binternal hex\b|\binternal hex\b.*\bcap head\b",
     "socket head cap screw"),
    (r"\b(bolts?|screws?)\b", r"\bflat head\b", "flat head machine screw"),
    (r"\b(bolts?|screws?)\b", r"\bpan head\b", "pan head machine screw"),
    (r"\b(bolts?|screws?)\b", r"\bhex (bolts?|head|cap)\b|\bexternal hex\b", "hex bolt"),
    (r"\b(bolts?|screws?)\b", r"", "bolt"),
)  # fmt: skip
_KINDS = tuple((re.compile(noun), re.compile(feature), kind) for noun, feature, kind in _KINDS)

# What each kind is served as: its category, what draws it, and what it implements.
_BOLT_KIND = {
    "hex bolt": ("bolts", "hexhead-iso4017"),
    "flange bolt": ("bolts", "hexheadwithflange-din1665"),
    "socket head cap screw": ("screws", "socketheadcap-iso4762"),
    "button head socket cap screw": ("screws", "buttonhead-iso7380-1"),
    "flat head socket cap screw": ("screws", "countersunk-iso10642"),
    "flat head machine screw": ("screws", "countersunk-iso7046"),
    "pan head machine screw": ("screws", "raisedcheesehead-iso7045"),
}
_NUT_KIND = {"hex nut": "iso4032", "jam nut": "iso4035", "flange nut": "din1665", "cap nut": "din1587"}
_WASHER_KIND = {"flat washer": "iso7089", "fender washer": "iso7093"}

# Why a kind the store sells is not served, for the ones that are not.
_UNSERVED = {
    "lock washer": "no standard geometry for a split or toothed lock washer",
    "washer": "a washer of no kind the rules know",
    "lock nut": "no standard geometry for a prevailing-torque (nylon insert or all-metal) lock nut",
    "wing nut": "no standard geometry for a wing nut",
    "coupling nut": "no standard geometry for a coupling nut",
    "special nut": "no standard geometry for this kind of nut",
    "nut": "a nut of no kind the rules know",
    "carriage bolt": "no standard geometry for a metric carriage bolt",
    "bolt": "a bolt or screw of no head type the rules know",
}


def _kind(text):
    """What a fastener is, from its title or its URL slug, or None if it is none."""
    words = _words(text)
    for noun, feature, kind in _KINDS:
        if noun.search(words) and feature.search(words):
            return kind
    return None


def _thread(title):
    """(diameter, pitch, end of the designation) of the first metric thread a title gives."""
    found = [m for r in (_THREAD_M_RE, _THREAD_MM_RE) for m in [r.search(title)] if m is not None]
    if not found:
        return None
    m = min(found, key=lambda m: m.start())
    pitch = m.group("p")
    return float(m.group("d")), (None if pitch is None else float(pitch)), m.end()


def _coarse(diameter, pitch):
    """The cq_warehouse size ("M6-1") of a coarse thread, or (None, why not)."""
    diameter = _number(diameter)
    coarse = COARSE_PITCH.get(diameter)
    if coarse is None:
        return None, "not an ISO 261 size: M%g" % diameter
    if pitch is not None and abs(pitch - coarse) > 1e-6:
        return None, "not the coarse thread: M%g-%g, where the coarse one is M%g-%g" % (
            diameter,
            pitch,
            diameter,
            coarse,
        )
    return "M%s-%s" % (_num(diameter), _num(coarse)), None


def _location(z=0.0, flipped=False):
    """A port on the fastener's axis, at height 'z'.

    PartCAD's convention is that a port's +Z points into the part it belongs
    to, which is also the way a part travels when it is connected through it.
    cq_warehouse builds every fastener with its bearing face on the XY plane:
    a screw's head stands on it with the shank below, and a nut or a washer
    sits on it with the rest of its thickness above. So the bearing face is the
    origin unturned, and the far face of a nut or a washer is turned over.
    """
    return [[0, 0, _number(z)], [1, 0, 0], 180 if flipped else 0]


def _screw(kind, title):
    """(category, config) for a bolt or a machine screw, or (None, why not)."""
    category, part = _BOLT_KIND[kind]
    thread = _thread(title)
    if thread is None:
        return None, "no metric thread designation"
    diameter, pitch, end = thread
    size, why = _coarse(diameter, pitch)
    if size is None:
        return None, why
    if _number(diameter) not in _SCREW_PARTS[part]:
        return None, "no geometry for this size: %s M%g" % (part, diameter)
    m = _SCREW_LENGTH_RE.match(title, end)
    if m is None:
        return None, "no length in mm after the thread designation"
    length = _number(m.group("len"))
    reference = "%sm-bolt-length;size=%s,length=%s" % (_M, _num(diameter), _num(length))
    return category, {
        "type": "enrich",
        "source": _CQWAREHOUSE + part,
        # With its thread: 'simple' would draw a plain cylinder at the
        # thread's major diameter instead, which is cheaper to render and is
        # not what is on the shelf.
        "with": {"size": size, "length": length, "simple": False},
        # A machine screw is a bolt in //pub/std/metric/m's sense: it goes into
        # a thread that is already there, a tapped hole or a nut, rather than
        # cutting its own, which is what its 'm-screw' is for.
        "implements": {reference: _location()},
    }


def _nut(kind, title):
    """(category, config) for a nut, or (None, why not)."""
    fastener_type = _NUT_KIND[kind]
    thread = _thread(title)
    if thread is None:
        return None, "no metric thread designation"
    diameter, pitch, _ = thread
    size, why = _coarse(diameter, pitch)
    if size is None:
        return None, why
    height = NUT_HEIGHT[fastener_type].get(size)
    if height is None:
        return None, "no geometry for this size: %s %s" % (fastener_type, size)
    if fastener_type == "din1587":
        # A cap nut's thread is blind: one opening, on its bearing face.
        reference = "%sm-tapped-hole;size=%s,depth=%s" % (_M, _num(diameter), _num(height))
        implements = {reference: {"bottom": _location()}}
    else:
        # A nut is a thread right through, entered from either face.
        reference = "%sm-threaded-thru-depth;size=%s,depth=%s" % (_M, _num(diameter), _num(height))
        implements = {reference: {"bottom": _location(), "top": _location(height, flipped=True)}}
    return "nuts", {
        "type": "enrich",
        "source": _NUT,
        "with": {"size": size, "fastener_type": fastener_type},
        "implements": implements,
    }


def _washer(kind, title):
    """(category, config) for a plain washer, or (None, why not)."""
    fastener_type = _WASHER_KIND[kind]
    m = _WASHER_SIZE_RE.search(title)
    if m is None:
        return None, "no metric size"
    diameter = _number(m.group("m") or m.group("mm"))
    size = "M%s" % _num(diameter)
    dimensions = WASHER_SIZE[fastener_type].get(size)
    if dimensions is None:
        return None, "no geometry for this size: %s %s" % (fastener_type, size)
    _, outside, thickness = dimensions
    if m.group("od") and abs(float(m.group("od")) - outside) > 1e-6:
        return None, "the stated outside diameter is not the standard's: %s mm for %s" % (m.group("od"), fastener_type)
    # A washer's hole is a clearance hole - the screw passes through it - and
    # it is entered from either face.
    reference = "%sm-thru-depth;size=%s,depth=%s" % (_M, _num(diameter), _num(thickness))
    return "washers", {
        "type": "enrich",
        "source": _WASHER,
        "with": {"size": size, "fastener_type": fastener_type},
        "implements": {reference: {"bottom": _location(), "top": _location(thickness, flipped=True)}},
    }


def _fastener(title):
    """(category, config) for a metric fastener, or (None, why not)."""
    words = _words(title)
    not_one = _FASTENER_NOT.search(words)
    if not_one:
        return None, "not one fastener of a standard kind: %r" % not_one.group(1)
    kind = _kind(title)
    if kind in _BOLT_KIND:
        return _screw(kind, title)
    if kind in _NUT_KIND:
        return _nut(kind, title)
    if kind in _WASHER_KIND:
        return _washer(kind, title)
    return None, _UNSERVED.get(kind, "not a fastener")


# --- one product -----------------------------------------------------------------------


def _read(title):
    """(category, config) for what one title describes, or (None, why not).

    A title is lumber, plywood or a fastener by what it says it is; the size
    rules then decide whether it is an instance of the standard.
    """
    words = _words(title)
    if _PLYWOOD_IS.search(words):
        config, why = _plywood(title)
        return ("plywood", config) if config else (None, why)
    if _LUMBER_RE.search(title) or (_LUMBER_IS.search(words) and _thread(title) is None):
        config, why = _lumber(title)
        return ("lumber", config) if config else (None, why)
    return _fastener(title)


def _same(a, b):
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def classify(record):
    """(category, config) for one product record, or (None, why it is not served).

    The title decides. A product the store has also listed under other titles
    ('alt_titles') is served only if every one of them that can be read says
    the same - the same size, the same kind and the same pack - since otherwise
    there is no telling which of them the SKU is today. Its URL slug is checked
    for the kind of fastener it names, which is the one thing a slug keeps: its
    decimal points are gone.
    """
    title = record["title"]
    category, config = _read(title)
    if category is None:
        return None, config
    count = _pack(title)
    if count is None:
        return None, "the title states more than one pack size"
    for other in record.get("alt_titles") or ():
        other_category, other_config = _read(other)
        if other_category is None:
            continue
        if other_category != category or not _same(other_config, config) or _pack(other) not in (count, 1):
            return None, "listed under titles that disagree: %r" % other
    kind = _kind(title) if category not in ("lumber", "plywood") else None
    slug_kind = _kind(record.get("slug") or "") if kind else None
    if kind and slug_kind and slug_kind != kind:
        return None, "the title and the URL disagree about what it is: %s, %s" % (kind, slug_kind)

    config = dict(config)
    config["desc"] = title
    # The purchasing record. The item ID is what the 'homedepot' provider puts
    # in the cart as it is, with no lookup on the website first.
    config["vendor"] = _VENDOR
    config["sku"] = record["id"]
    config["count_per_sku"] = count
    return category, config


# --- the products --------------------------------------------------------------------

_products_loaded = None


def _load_products():
    """The product records shipped beside this script, in file order."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), _PRODUCTS_FILE)
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _products():
    global _products_loaded
    if _products_loaded is None:
        try:
            _products_loaded = _load_products()
        except (OSError, ValueError) as e:
            print("homedepot catalog: cannot read %s: %s" % (_PRODUCTS_FILE, e), file=sys.stderr)
            _products_loaded = []
    return _products_loaded


def catalog(category):
    """{item ID: config} of every product served in one category."""
    served = {}
    for record in _products():
        got, config = classify(record)
        if got == category:
            served[record["id"]] = config
    return served


# --- the key/value protocol ------------------------------------------------------------


def get(key):
    """Answer one key of the repository protocol; None if this package has no such key."""
    first, _, sub = key.partition("/")

    if first not in CATEGORIES:
        # The root: its children are the categories, and it holds nothing.
        if key == "deps":
            return list(CATEGORIES)
        if key == "meta":
            return {
                "desc": "The Home Depot products a PartCAD standard describes, by category.",
                "objectKinds": list(_ROOT_OBJECT_KINDS),
            }
        if key.startswith("objects/"):
            return {}
        return None

    if sub == "deps":
        return []
    if sub == "meta":
        return {
            "desc": CATEGORIES[first],
            "objectKinds": list(_CATEGORY_OBJECT_KINDS),
            "suppliers": dict(SUPPLIERS),
        }
    if sub == "objects/part":
        return catalog(first)
    if sub.startswith("objects/part/"):
        return catalog(first).get(sub[len("objects/part/") :])
    if sub.startswith("objects/"):
        return {}
    return None


# The dispatch has to be last. PartCAD runs this file with
# runpy.run_path(run_name=request["api"]), which executes it top to bottom,
# so get() must not be called until every helper above it has been defined.
if __name__ == "get":
    output = {"result": get(request["key"])}  # noqa: F821 - injected by the runtime
elif __name__ == "__main__":
    for name in CATEGORIES:
        print("%-8s %4d" % (name, len(catalog(name))))
else:
    output = {}
