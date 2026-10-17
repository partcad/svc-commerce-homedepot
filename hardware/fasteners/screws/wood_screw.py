# A screw for wood, drawn from the sizes a product page gives for it.
#
# Every screw this store sells for wood is this one script with different
# parameters (see 'wood-screw' in partcad.yaml). The sizes are in inches, as
# they are sold; the geometry is in millimetres, as everywhere in PartCAD.
#
# The frame is the one the screw's ports are placed in:
#
# * the screw's axis is Z, and the point is at the bottom;
# * z = 0 is the plane that is flush with the surface once the screw is driven
#   home: the top of a flat (countersunk) head, the underside of a washer head;
# * so a flat head is below z = 0 and a washer head above it, and the tip is at
#   z = -length, since a flat-head screw is measured overall and one with a
#   washer head from under the head.
#
# The thread is drawn as the cylinder it fills and the plain shank above it as
# a thinner one, which is what tells the two apart in a drawing; the helix is
# left out.
import math

import cadquery as cq

length = 2.0  # in.: overall for a flat head, under the head for a washer head
diameter = 0.164  # in.: the thread's major diameter (#8)
shank = 0.12  # in.: the plain shank between the head and the thread
thread_length = 1.24  # in.
head = "flat"  # flat | washer
head_diameter = 0.31  # in.
head_height = 0.0  # in.: of a washer head, above the surface

MM = 25.4
L = length * MM
r = diameter * MM / 2.0
r_shank = min(shank * MM / 2.0, r)
r_head = head_diameter * MM / 2.0
T = min(thread_length * MM, L)
# A gimlet point, about one and a half thread diameters long.
point = min(3.0 * r, T)

# The profile, as (radius, z) from the top of the axis around to its bottom,
# revolved about Z.
if head == "washer":
    h = max(head_height * MM, 0.5)
    profile = [(0.0, h), (r_head, h), (r_head, 0.0)]
    under_head = 0.0
else:
    # An 82 degree countersink, from the head's rim down to the shank.
    under_head = -(r_head - r_shank) / math.tan(math.radians(41.0))
    profile = [(0.0, 0.0), (r_head, 0.0)]

z_thread = -(L - T)
if z_thread < under_head:
    profile += [(r_shank, under_head), (r_shank, z_thread), (r, z_thread)]
else:
    profile += [(r, under_head)]
profile += [(r, -(L - point)), (0.0, -L)]

result = cq.Workplane("XZ").polyline(profile).close().revolve(360.0, (0, 0, 0), (0, 1, 0))

show_object(result)
