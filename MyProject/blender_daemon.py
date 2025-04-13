import bpy
import os
import time
import math
import mathutils
import errno

base_path = os.path.dirname(__file__)
config_path = os.path.join(base_path, "material_config.txt")
signal_path = os.path.join(base_path, "signal.txt")
done_path = os.path.join(base_path, "done.txt")
preview_path = os.path.join(base_path, "preview.png")
preview_model_dir = os.path.join(base_path, "preview_model")
model_info_path = os.path.join(preview_model_dir, "model.txt")
camera_config_path = os.path.join(base_path, "camera_config.txt")


def safe_remove(path, retries=5, delay=0.1):
    for _ in range(retries):
        try:
            os.remove(path)
            return True
        except PermissionError as e:
            if e.errno == errno.EACCES:
                time.sleep(delay)
            else:
                raise
    print(f"⚠️ Could not remove {path} after {retries} attempts.")
    return False


def apply_material_settings(bsdf):
    with open(config_path, "r") as f:
        line = f.read().strip()
        try:
            r, g, b, rough, metal = map(float, line.split(","))
            bsdf.inputs["Base Color"].default_value = (r, g, b, 1)
            bsdf.inputs["Roughness"].default_value = rough
            bsdf.inputs["Metallic"].default_value = metal
        except ValueError:
            print(f"❌ Invalid material config: {line}")


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
            full_path = os.path.join(preview_model_dir, name)
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


scene = bpy.context.scene
scene.render.filepath = preview_path
scene.render.image_settings.file_format = 'PNG'
scene.render.resolution_x = 512
scene.render.resolution_y = 512
scene.render.resolution_percentage = 100

material = bpy.data.materials.get("PreviewMaterial")
if not material:
    material = bpy.data.materials.new("PreviewMaterial")
    material.use_nodes = True
bsdf = material.node_tree.nodes.get("Principled BSDF")

for f in [done_path, signal_path]:
    if os.path.exists(f):
        safe_remove(f)

print("✅ Blender daemon running...")

while True:
    if os.path.exists(signal_path):
        try:
            obj = setup_preview_object()
            if obj and bsdf:
                if not obj.data.materials:
                    obj.data.materials.append(material)
                else:
                    obj.data.materials[0] = material
                camera = bpy.data.objects.get("Camera")
                light = bpy.data.objects.get("Light")
                apply_material_settings(bsdf)
                if camera and light:
                    frame_camera_and_light(obj, camera, light)
                bpy.ops.render.render(write_still=True)
                with open(done_path, "w") as f:
                    f.write("done")
                print("✅ Preview rendered and saved.")
        except Exception as e:
            print("❌ Error during render:", e)
        safe_remove(signal_path)
    time.sleep(0.1)
