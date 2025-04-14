import bpy
import os
import time
import math
import mathutils
import errno

# Resolve paths
app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
data_path = os.path.join(app_dir, "data")
preview_model_dir = os.path.join(data_path, "preview_model")
model_info_path = os.path.join(preview_model_dir, "model.txt")
config_path = os.path.join(data_path, "material_config.txt")
command_path = os.path.join(data_path, "command.txt")
done_path = os.path.join(data_path, "done.txt")
preview_path = os.path.join(data_path, "preview.png")
camera_config_path = os.path.join(data_path, "camera_config.txt")


def safe_remove(path, retries=5, delay=0.1):
    for _ in range(retries):
        try:
            os.remove(path)
            return True
        except FileNotFoundError:
            return True
        except PermissionError as e:
            if e.errno == errno.EACCES:
                time.sleep(delay)
            else:
                raise
    print(f"⚠️ Could not remove {path} after {retries} attempts.")
    return False


def apply_material_settings():
    if not os.path.exists(config_path):
        print("❌ Missing material config")
        return

    try:
        with open(config_path, "r") as f:
            parts = f.read().strip().split(",")
            if len(parts) < 5:
                print(f"❌ Invalid material config: {','.join(parts)}")
                return

            # Parse the required floats
            r, g, b = map(float, parts[0:3])
            smoothness = float(parts[3])
            metalness = float(parts[4])

            # Optional maps
            albedo_map_path = parts[5].strip() if len(parts) > 5 else ""
            metalness_map_path = parts[6].strip() if len(parts) > 6 else ""

    except Exception as e:
        print("❌ Failed to parse material config:", e)
        return

    material = bpy.data.materials.get("PreviewMaterial")
    if not material:
        print("❌ Material not found")
        return

    node_tree = material.node_tree
    nodes = node_tree.nodes

    group_node = next((n for n in nodes if n.type == "GROUP" and n.node_tree.name == "PBRMaterialGroup"), None)
    albedo_tex_node = nodes.get("AlbedoMap")
    metalness_tex_node = nodes.get("MetalnessMap")

    if not group_node:
        print("❌ PBRMaterialGroup not found")
        return

    # Load images if provided
    if albedo_tex_node and albedo_map_path and os.path.exists(albedo_map_path):
        try:
            albedo_tex_node.image = bpy.data.images.load(albedo_map_path, check_existing=True)
        except Exception as e:
            print("⚠️ Failed to load albedo map:", e)

    if metalness_tex_node and metalness_map_path and os.path.exists(metalness_map_path):
        try:
            metalness_tex_node.image = bpy.data.images.load(metalness_map_path, check_existing=True)
        except Exception as e:
            print("⚠️ Failed to load metalness map:", e)

    # Set group inputs
    inputs = group_node.inputs
    if "AlbedoColor" in inputs:
        inputs["AlbedoColor"].default_value = (r, g, b, 1)
    if "SmoothnessMultiplier" in inputs:
        inputs["SmoothnessMultiplier"].default_value = smoothness
    if "MetalnessMultiplier" in inputs:
        inputs["MetalnessMultiplier"].default_value = metalness

    print("✅ Material values and maps set successfully")


def frame_camera_and_light(obj, camera, light):
    if not os.path.exists(camera_config_path):
        return
    try:
        with open(camera_config_path, "r") as f:
            cx, cy, cz, light_rot = map(float, f.read().strip().split(","))
        camera.location = (cx, cy, cz)
        direction = mathutils.Vector((0, 0, 0)) - camera.location
        camera.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
        light.rotation_euler = (math.radians(light_rot), 0, 0)
    except Exception as e:
        print(f"⚠️ Could not apply camera/light config: {e}")



def smooth_object(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()


def setup_preview_object():
    primitive_fallback = True
    obj = None
    if os.path.exists(model_info_path):
        name = open(model_info_path).read().strip()
        if name.startswith("primitive:"):
            primitive = name.split(":")[1]
            bpy.ops.object.select_all(action='DESELECT')
            for o in bpy.context.scene.objects:
                if o.type == 'MESH':
                    o.select_set(True)
            bpy.ops.object.delete()
            if primitive == "sphere":
                bpy.ops.mesh.primitive_uv_sphere_add()
                obj = bpy.context.active_object
                smooth_object(obj)
            elif primitive == "cube":
                bpy.ops.mesh.primitive_cube_add()
            elif primitive == "cylinder":
                bpy.ops.mesh.primitive_cylinder_add()
            obj = bpy.context.active_object
            if obj:
                obj.name = "PreviewObject"
        else:
            ext = os.path.splitext(name)[1].lower()
            full_path = os.path.join(data_path, name)
            if os.path.exists(full_path):
                bpy.ops.object.select_all(action='DESELECT')
                for o in bpy.context.scene.objects:
                    if o.type == 'MESH':
                        o.select_set(True)
                bpy.ops.object.delete()
                if ext == ".obj":
                    bpy.ops.import_scene.obj(filepath=full_path)
                elif ext == ".fbx":
                    bpy.ops.import_scene.fbx(filepath=full_path)
                elif ext == ".blend":
                    with bpy.data.libraries.load(full_path, link=False) as (data_from, data_to):
                        data_to.objects = data_from.objects
                    for obj in data_to.objects:
                        if obj:
                            bpy.context.collection.objects.link(obj)
                for imported in bpy.context.selected_objects:
                    if imported.type == 'MESH':
                        imported.name = "PreviewObject"
                        smooth_object(imported)
                        obj = imported
                        break

    if not obj:
        obj = bpy.data.objects.get("PreviewObject")

    if obj and obj.name == "PreviewObject":
        if obj.data.name.startswith("Sphere") or "Sphere" in obj.data.name:
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.shade_smooth()

    return obj


# Set render properties
scene = bpy.context.scene
scene.render.filepath = preview_path
scene.render.image_settings.file_format = 'PNG'
scene.render.resolution_x = 512
scene.render.resolution_y = 512
scene.render.resolution_percentage = 100

# Get or create material
material = bpy.data.materials.get("PreviewMaterial")
if not material:
    material = bpy.data.materials.new("PreviewMaterial")
    material.use_nodes = True

# Clean up old signals
if os.path.exists(done_path):
    os.remove(done_path)
if os.path.exists(command_path):
    os.remove(command_path)


print("✅ Blender daemon running...")

# Main render loop
while True:
    if os.path.exists(command_path):
        try:
            obj = setup_preview_object()
            if obj:
                if not obj.data.materials:
                    obj.data.materials.append(material)
                else:
                    obj.data.materials[0] = material
                camera = bpy.data.objects.get("Camera")
                light = bpy.data.objects.get("Light")
                if os.path.exists(config_path):
                    apply_material_settings()
                if camera and light:
                    frame_camera_and_light(obj, camera, light)
                bpy.ops.render.render(write_still=True)
                with open(done_path, "w") as f:
                    f.write("done")
                print(f"✅ Preview rendered to: {preview_path}")
            os.remove(command_path)  # ✅ prevent repeated rendering
        except Exception as e:
            print("❌ Error during render:", e)
