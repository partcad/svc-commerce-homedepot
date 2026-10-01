#
# svc-commerce-homedepot, 2026
#
# Licensed under Apache License, Version 2.0.
#
# A metric nut, drawn by cq_warehouse: the geometry of the store's 'metric-nut'
# template, which every nut in the catalog is an instance of.
#
# //pub/std/metric/cqwarehouse publishes cq_warehouse's screws and none of its
# nuts, so this is the same library asked for the other half. It belongs there,
# beside the screws, and this template becomes an alias of it once it is.
#
# The nut sits on the XY plane, its bearing face at Z=0 and its axis along Z,
# which is where the catalog puts its ports.
#
if __name__ != "__cqgi__":
    from cq_server.ui import show_object

from cq_warehouse.fastener import DomedCapNut, HexNut, HexNutWithFlange

size = "M6-1"
fastener_type = "iso4032"
simple = True
hand = "right"

NUT_CLASSES = {
    "iso4032": HexNut,
    "iso4033": HexNut,
    "iso4035": HexNut,
    "din1665": HexNutWithFlange,
    "din1587": DomedCapNut,
}

nut = NUT_CLASSES[fastener_type](
    size=size,
    fastener_type=fastener_type,
    hand=hand,
    simple=simple,
)

show_object(nut)
