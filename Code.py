import maya.cmds as cmds

def lod_tool():
    if cmds.window("lodToolWin", exists=True):
        cmds.deleteUI("lodToolWin")

    cmds.window("lodToolWin", title="LOD Tool", widthHeight=(350, 220))
    cmds.columnLayout(adjustableColumn=True, rowSpacing=10)

    cmds.text(label="Select a mesh to adjust PolyCount", align="center")
    cmds.text("selectedMeshLabel", label="Selected Mesh: None", align="center")

    def on_slider_change(val):
        cmds.text("reductionLabel", edit=True, label=f"Reduction: {int(val)}%")
        update_reduction(int(val))

    cmds.floatSlider("reductionSlider", min=0, max=99, value=0, step=1, dragCommand=on_slider_change)
    cmds.text("reductionLabel", label="Reduction: 0%", align="center")

    lod_data = {"mesh": None, "polyReduceNode": None}

    def select_mesh(*_):
        sel = cmds.ls(selection=True)
        if not sel:
            cmds.warning("Select a mesh first.")
            return
        mesh = sel[0]
        shapes = cmds.listRelatives(mesh, shapes=True, fullPath=True) or []
        if not shapes or cmds.nodeType(shapes[0]) != "mesh":
            cmds.warning("Not a mesh.")
            return

        if lod_data["polyReduceNode"] and cmds.objExists(lod_data["polyReduceNode"]):
            cmds.delete(lod_data["polyReduceNode"])

        lod_data["mesh"] = mesh
        res = cmds.polyReduce(mesh, version=1, termination=0, percentage=0, keepBorder=True, replaceOriginal=True, ch=True)

        if res and len(res) > 1:
            lod_data["polyReduceNode"] = res[1]
        else:
            history = cmds.listHistory(mesh) or []
            for node in reversed(history):
                if cmds.nodeType(node) == "polyReduce":
                    lod_data["polyReduceNode"] = node
                    break

        if not lod_data["polyReduceNode"]:
            cmds.warning("Couldn't create polyReduce node.")
            lod_data["mesh"] = None
            return

        cmds.text("selectedMeshLabel", edit=True, label=f"Selected Mesh: {mesh}")
        cmds.floatSlider("reductionSlider", edit=True, value=0)
        cmds.text("reductionLabel", edit=True, label="Reduction: 0%")

    def update_reduction(value):
        pr_node = lod_data.get("polyReduceNode")
        if not pr_node or not cmds.objExists(pr_node):
            cmds.warning("No polyReduce node found. Select a mesh first.")
            return
        cmds.setAttr(pr_node + ".termination", 0)
        cmds.setAttr(pr_node + ".percentage", value)
        cmds.dgdirty(pr_node)

    # -------------------
    # Topology Check Function
    # -------------------
    def check_topology(*_):
        sel = cmds.ls(selection=True)
        if not sel:
            cmds.warning("Select a mesh first to check topology.")
            return
        mesh = sel[0]
        shapes = cmds.listRelatives(mesh, shapes=True, fullPath=True) or []
        if not shapes:
            cmds.warning("No mesh shape found.")
            return
        shape = shapes[0]

        print("\n========== Topology Check ==========")
        faces = cmds.polyEvaluate(shape, face=True)
        print(f"Selected Mesh: {mesh}")
        print(f"Total Faces: {faces}")

        # --- Check if N-Gons are already highlighted ---
        shader_name = "ngonHighlight_MAT"
        sg_name = shader_name + "SG"

        # If highlight shader exists, remove it and restore original material
        if cmds.objExists(shader_name):
            cmds.delete(shader_name, sg_name)
            print("🧹 Removed N-Gon highlight shader — scene restored to original materials.")
            return

        # --- Invalid geometry checks ---
        bad_edges = cmds.polyInfo(invalidEdges=True) or []
        bad_verts = cmds.polyInfo(invalidVertices=True) or []
        lamina = cmds.polyInfo(laminaFaces=True) or []
        non_manifold = cmds.polyInfo(nonManifoldEdges=True) or []

        if bad_edges: print("Invalid Edges:", bad_edges)
        if bad_verts: print("Invalid Vertices:", bad_verts)
        if lamina: print("Lamina Faces:", lamina)
        if non_manifold: print("Non-Manifold Edges:", non_manifold)

        # --- N-Gon detection ---
        ngons = []
        print("\nChecking for N-Gons (faces with more than 4 sides)...")

        for face_id in range(faces):
            verts_info = cmds.polyInfo(f"{mesh}.f[{face_id}]", faceToVertex=True)
            if verts_info:
                vert_count = len(verts_info[0].split()) - 2  #
                if vert_count > 4:
                    ngons.append(f"{mesh}.f[{face_id}]")

        if ngons:
            print(f"⚠ Found {len(ngons)} N-Gons:")
            for ngon in ngons:
                print(f"  {ngon}")

            # --- Create red highlight shader ---
            shader = cmds.shadingNode('lambert', asShader=True, name=shader_name)
            sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=sg_name)
            cmds.connectAttr(shader + ".outColor", sg + ".surfaceShader", force=True)
            cmds.setAttr(shader + ".color", 1, 0, 0, type="double3")  

            # Assign to N-Gon faces
            cmds.select(ngons, replace=True)
            cmds.hyperShade(assign=shader_name)
            print("Highlighted N-Gons in red for easy viewing.")
            print("Run 'Check Topology' again to remove the red highlight.")
        else:
            print("No N-Gons found.")

        print("====================================\n")


    # -------------------
    # UI Buttons
    # -------------------
    cmds.button(label="Select Mesh", command=select_mesh)
    cmds.button(label="Check Topology (N-Gons etc.)", bgc=(0.3, 0.6, 0.3), command=check_topology)

    cmds.showWindow("lodToolWin")


# -------------------
# Colour Changer (unchanged)
# -------------------
class ColourChanger:
    
    def create_temp_shader(name):
        if not cmds.objExists(name):
            shader = cmds.shadingNode('lambert', asShader=True, name=name)
        else:
            shader = name
        return shader

    gradient_mat = create_temp_shader('polyDensityGradient_MAT')

    
    def interpolate_colour(value, low, high):
        if value <= low:
            return (0.0, 0.2, 1.0)  # Blue
        elif value >= high:
            return (1.0, 0.0, 0.0)  # Red
        else:
            t = (value - low) / (high - low)
            if t < 0.5:
                t2 = t / 0.5
                return (0.0, 0.2 * (1 - t2) + 1.0 * t2, 1.0 - 1.0 * t2)
            else:
                t2 = (t - 0.5) / 0.5
                return (1.0 * t2, 1.0 - 1.0 * t2, 0.0)

    
    def apply_colour_gradient(mesh, low_threshold=100, high_threshold=5000):
        shapes = cmds.listRelatives(mesh, shapes=True, fullPath=True) or []
        if not shapes:
            return
        shape = shapes[0]
        face_count = cmds.polyEvaluate(shape, face=True)
        colour = ColourChanger.interpolate_colour(face_count, low_threshold, high_threshold)
        cmds.setAttr(f"{ColourChanger.gradient_mat}.color", *colour, type='double3')
        cmds.select(mesh, replace=True)
        cmds.hyperShade(assign=ColourChanger.gradient_mat)
        cmds.select(clear=True)



lod_tool()
