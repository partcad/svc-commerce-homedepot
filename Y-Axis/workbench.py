# Once PartCAD reloads the package after this example is added,
# press "Save" to have the result inspected.

import cadquery as cq
result = cq.Workplane("front").box(18.0, 850, 1200)
if "show_object" in locals():
  show_object(result)
