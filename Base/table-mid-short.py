# Once PartCAD reloads the package after this example is added,
# press "Save" to have the result inspected.

import cadquery as cq
result = cq.Workplane("front").box(50.80,828.40,76.20)
if "show_object" in locals():
  show_object(result)
