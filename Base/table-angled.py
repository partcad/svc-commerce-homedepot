import cadquery as cq

# Parameters for the parallelogram
base_length = 107.763  # Base length of the parallelogram
side_length = 285  # Length of the inclined side
height = 285      # Vertical distance (height) between the two bases
extrude_depth = 50.8  # Depth of extrusion

# Create a parallelogram by defining its base and offset points
parallelogram = (
    cq.Workplane("XY")
    .polyline([
        (0, 0),  # Start at origin
        (base_length, 0),  # Bottom-right corner
        (base_length + side_length, height),  # Top-right corner
        (side_length, height),  # Top-left corner
        (0, 0)  # Close the loop
    ])
    .close()
    .extrude(extrude_depth)  # Extrude to create a 3D shape
)

# Export to visualize or further process
show_object(parallelogram)
