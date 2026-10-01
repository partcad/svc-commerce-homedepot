#
# svc-commerce-homedepot, 2026
#
# Licensed under Apache License, Version 2.0.
#
# A metric plain washer, drawn by cq_warehouse: the geometry of the store's
# 'metric-washer' template, which every washer in the catalog is an instance of.
#
# As for 'metric_nut.py': //pub/std/metric/cqwarehouse publishes none of
# cq_warehouse's washers yet, and this belongs there once it does.
#
# The washer sits on the XY plane, one face at Z=0 and its axis along Z, which
# is where the catalog puts its ports.
#
if __name__ != "__cqgi__":
    from cq_server.ui import show_object

from cq_warehouse.fastener import PlainWasher

size = "M6"
fastener_type = "iso7089"

washer = PlainWasher(size=size, fastener_type=fastener_type)

show_object(washer)
