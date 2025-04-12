# Material Editor GUI Scaffold
# Requirements: tkinter, Pillow, csv, shutil
import tkinter as tk
from tkinter import filedialog, colorchooser, messagebox, simpledialog
from PIL import Image, ImageTk
import csv
import os
import shutil
import subprocess
import time
import threading

CONFIG_FILENAME = "editor_config.txt"

class MaterialEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Material Editor")

        self.working_dir = None
        self.materials = []  # List of dicts per material
        self.current_index = None
        self.blender_path = None
        self.daemon_process = None

        self.preview_path = None

        self.setup_gui()

    def setup_gui(self):
        # Menu bar
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Project", command=self.new_project)
        file_menu.add_command(label="Open Project", command=self.open_project)
        file_menu.add_separator()
        file_menu.add_command(label="Save CSV", command=self.save_csv)
        file_menu.add_separator()
        file_menu.add_command(label="Add Material", command=self.add_material)
        file_menu.add_command(label="Export to Unity", command=self.export_to_unity)
        file_menu.add_separator()
        file_menu.add_command(label="Set Blender Path", command=self.set_blender_path)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)

        preview_menu = tk.Menu(menubar, tearoff=0)
        preview_menu.add_command(label="Use Custom Model", command=self.set_custom_preview_model)
        preview_menu.add_separator()
        preview_menu.add_command(label="Use Sphere Primitive", command=lambda: self.set_primitive_preview("sphere"))
        preview_menu.add_command(label="Use Cube Primitive", command=lambda: self.set_primitive_preview("cube"))
        preview_menu.add_command(label="Use Cylinder Primitive", command=lambda: self.set_primitive_preview("cylinder"))
        preview_menu.add_separator()
        preview_menu.add_command(label="Camera Settings", command=self.open_camera_settings)

        menubar.add_cascade(label="File", menu=file_menu)
        menubar.add_cascade(label="Preview", menu=preview_menu)
        self.root.config(menu=menubar)

        # Main frames
        self.left_frame = tk.Frame(self.root, width=200)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.right_frame = tk.Frame(self.root)
        self.right_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)

        # Material list
        self.material_listbox = tk.Listbox(self.left_frame)
        self.material_listbox.pack(fill=tk.BOTH, expand=True)
        self.material_listbox.bind("<<ListboxSelect>>", self.on_material_select)

        # Right: Material preview + editor
        self.preview_label = tk.Label(self.right_frame, text="Preview not available", relief=tk.SUNKEN)
        self.preview_label.pack(fill=tk.X, pady=(0, 10))

        self.name_var = tk.StringVar()
        tk.Label(self.right_frame, text="Material Name").pack()
        tk.Entry(self.right_frame, textvariable=self.name_var).pack(fill=tk.X)

        self.color = (1.0, 1.0, 1.0)
        tk.Button(self.right_frame, text="Pick Albedo Color", command=self.pick_color).pack(fill=tk.X)

        self.roughness = tk.DoubleVar(value=0.5)
        self.roughness.trace_add("write", lambda *args: self.render_preview())
        tk.Label(self.right_frame, text="Smoothness").pack()
        tk.Scale(self.right_frame, from_=0, to=1, resolution=0.01, variable=self.roughness, orient="horizontal").pack(fill=tk.X)

        self.metalness = tk.DoubleVar(value=0.0)
        self.metalness.trace_add("write", lambda *args: self.render_preview())
        tk.Label(self.right_frame, text="Metalness").pack()
        tk.Scale(self.right_frame, from_=0, to=1, resolution=0.01, variable=self.metalness, orient="horizontal").pack(fill=tk.X)

        self.map_vars = {}
        for map_type in ["albedo_map", "metalness_map", "detail_map", "emmissive_map"]:
            var = tk.StringVar()
            var.trace_add("write", lambda *args: self.render_preview())
            self.map_vars[map_type] = var
            row = tk.Frame(self.right_frame)
            row.pack(fill=tk.X)
            tk.Label(row, text=map_type).pack(side=tk.LEFT)
            tk.Entry(row, textvariable=var).pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Button(row, text="...", command=lambda mt=map_type: self.pick_map(mt)).pack(side=tk.RIGHT)

        tk.Button(self.right_frame, text="Save Changes", command=self.save_current_material).pack(fill=tk.X, pady=10)

    def set_primitive_preview(self, primitive):
        if not self.working_dir:
            messagebox.showwarning("No Project", "Open or create a project first.")
            return

        preview_dir = os.path.join(self.working_dir, "preview_model")
        os.makedirs(preview_dir, exist_ok=True)

        with open(os.path.join(preview_dir, "model.txt"), "w") as f:
            f.write(f"primitive:{primitive}")

        messagebox.showinfo("Primitive Preview Set", f"Primitive shape set to: {primitive}.\nReselect material to see changes.")

    def open_camera_settings(self):
        cam_win = tk.Toplevel(self.root)
        cam_win.title("Camera Settings")

        def update_setting(label, default):
            return tk.DoubleVar(value=default)

        self.cam_x = update_setting("Camera X", 0.0)
        self.cam_y = update_setting("Camera Y", -2.5)
        self.cam_z = update_setting("Camera Z", 2.0)
        self.light_rot = update_setting("Light Rotation", 45.0)

        sliders = [
            ("Camera X", self.cam_x),
            ("Camera Y", self.cam_y),
            ("Camera Z", self.cam_z),
            ("Light Rotation", self.light_rot)
        ]

        for label, var in sliders:
            row = tk.Frame(cam_win)
            row.pack(fill=tk.X, padx=10, pady=2)
            tk.Label(row, text=label).pack(side=tk.LEFT)
            tk.Scale(row, from_=-10, to=10, resolution=0.1, orient="horizontal", variable=var).pack(side=tk.RIGHT, fill=tk.X, expand=True)

        tk.Button(cam_win, text="Apply Changes", command=self.restart_blender_daemon).pack(pady=10)

    def restart_blender_daemon(self):
        if self.daemon_process:
            try:
                self.daemon_process.terminate()
            except Exception:
                pass
        self.launch_blender_daemon()

    def on_close(self):
        if self.daemon_process:
            try:
                self.daemon_process.terminate()
            except Exception as e:
                print("⚠️ Could not terminate Blender:", e)
        self.root.destroy()

        # Main frames
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.left_frame = tk.Frame(self.root, width=200)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.right_frame = tk.Frame(self.root)
        self.right_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)

        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)

        file_menu.add_command(label="New Project", command=self.new_project)
        file_menu.add_command(label="Open Project", command=self.open_project)
        file_menu.add_separator()
        file_menu.add_command(label="Save CSV", command=self.save_csv)
        file_menu.add_separator()
        file_menu.add_command(label="Add Material", command=self.add_material)
        file_menu.add_command(label="Export to Unity", command=self.export_to_unity)
        file_menu.add_separator()
        file_menu.add_command(label="Set Blender Path", command=self.set_blender_path)
        file_menu.add_separator()
        file_menu.add_command(label="Set Custom Preview Model", command=self.set_custom_preview_model)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)

        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)

        # Left: Material list
        self.material_listbox = tk.Listbox(self.left_frame)
        self.material_listbox.pack(fill=tk.BOTH, expand=True)
        self.material_listbox.bind("<<ListboxSelect>>", self.on_material_select)


        # Right: Material preview + editor
        self.preview_label = tk.Label(self.right_frame, text="Preview not available", relief=tk.SUNKEN)
        self.preview_label.pack(fill=tk.X, pady=(0, 10))

        self.name_var = tk.StringVar()
        tk.Label(self.right_frame, text="Material Name").pack()
        tk.Entry(self.right_frame, textvariable=self.name_var).pack(fill=tk.X)

        self.color = (1.0, 1.0, 1.0)
        tk.Button(self.right_frame, text="Pick Albedo Color", command=self.pick_color).pack(fill=tk.X)

        self.roughness = tk.DoubleVar(value=0.5)
        tk.Label(self.right_frame, text="Smoothness").pack()
        tk.Scale(self.right_frame, from_=0, to=1, resolution=0.01, variable=self.roughness, orient="horizontal").pack(fill=tk.X)
        self.roughness.trace_add("write", lambda *args: self.render_preview())

        self.metalness = tk.DoubleVar(value=0.0)
        tk.Label(self.right_frame, text="Metalness").pack()
        tk.Scale(self.right_frame, from_=0, to=1, resolution=0.01, variable=self.metalness, orient="horizontal").pack(fill=tk.X)
        self.metalness.trace_add("write", lambda *args: self.render_preview())

        self.map_vars = {}
        for map_type in ["albedo_map", "metalness_map", "detail_map", "emmissive_map"]:
            var = tk.StringVar()
            self.map_vars[map_type] = var
            row = tk.Frame(self.right_frame)
            row.pack(fill=tk.X)
            tk.Label(row, text=map_type).pack(side=tk.LEFT)
            tk.Entry(row, textvariable=var).pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Button(row, text="...", command=lambda mt=map_type: self.pick_map(mt)).pack(side=tk.RIGHT)

        tk.Button(self.right_frame, text="Save Changes", command=self.save_current_material).pack(fill=tk.X, pady=10)

    def set_blender_path(self):
        path = filedialog.askopenfilename(title="Select Blender Executable")
        if path:
            self.blender_path = path
            self.save_blender_path()
            messagebox.showinfo("Blender Path Set", f"Using Blender at:\n{path}")

    def set_custom_preview_model(self):
        if not self.working_dir:
            messagebox.showwarning("No Project", "Open or create a project first.")
            return

        filepath = filedialog.askopenfilename(
            title="Select Custom Preview Model",
            filetypes=[("3D Model", "*.obj *.fbx *.blend")]
        )

        if filepath:
            preview_dir = os.path.join(self.working_dir, "preview_model")
            os.makedirs(preview_dir, exist_ok=True)

            dest = os.path.join(preview_dir, os.path.basename(filepath))
            shutil.copy(filepath, dest)

            with open(os.path.join(preview_dir, "model.txt"), "w") as f:
                f.write(os.path.basename(filepath))

            messagebox.showinfo("Preview Model Set", f"Using model: {os.path.basename(filepath)}\nRestart Blender to see changes.")


        filepath = filedialog.askopenfilename(
            title="Select Custom Preview Model",
            filetypes=[("3D Model", "*.obj *.fbx *.blend")]
        )

        if filepath:
            preview_dir = os.path.join(self.working_dir, "preview_model")
            os.makedirs(preview_dir, exist_ok=True)

            dest = os.path.join(preview_dir, os.path.basename(filepath))
            shutil.copy(filepath, dest)

            with open(os.path.join(preview_dir, "model.txt"), "w") as f:
                f.write(os.path.basename(filepath))

            messagebox.showinfo("Preview Model Set", f"Using model: {os.path.basename(filepath)}\nRestart Blender to see changes.")

    def save_blender_path(self):
        if not self.working_dir:
            return
        path = os.path.join(self.working_dir, CONFIG_FILENAME)
        with open(path, "w") as f:
            f.write(self.blender_path)

    def load_blender_path(self):
        if not self.working_dir:
            return
        path = os.path.join(self.working_dir, CONFIG_FILENAME)
        if os.path.exists(path):
            with open(path, "r") as f:
                self.blender_path = f.read().strip()

    def launch_blender_daemon(self):
        if not self.blender_path or not self.working_dir:
            return
        blend_file = os.path.join(self.working_dir, "preview.blend")
        daemon_script = os.path.join(self.working_dir, "blender_daemon.py")
        self.daemon_process = subprocess.Popen([
            self.blender_path, "-b", blend_file, "--python", daemon_script
        ])

    def new_project(self):
        self.working_dir = filedialog.askdirectory(title="Select New Project Folder")
        if not self.working_dir:
            return
        self.materials.clear()
        self.material_listbox.delete(0, tk.END)
        os.makedirs(os.path.join(self.working_dir, "textures"), exist_ok=True)
        os.makedirs(os.path.join(self.working_dir, "exports"), exist_ok=True)
        self.load_blender_path()
        self.launch_blender_daemon()
        messagebox.showinfo("New Project", "New project initialized. You can now add materials.")

    def open_project(self):
        self.working_dir = filedialog.askdirectory(title="Select Project Folder")
        if not self.working_dir:
            return

        csv_path = os.path.join(self.working_dir, "materials.csv")
        self.materials.clear()
        self.material_listbox.delete(0, tk.END)

        if os.path.exists(csv_path):
            with open(csv_path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    self.materials.append(row)
                    self.material_listbox.insert(tk.END, row['Name'])

        self.load_blender_path()
        self.launch_blender_daemon()

    def save_csv(self):
        if not self.working_dir:
            return

        if not self.materials:
            return

        csv_path = os.path.join(self.working_dir, "materials.csv")
        fieldnames = list(self.materials[0].keys())
        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for mat in self.materials:
                writer.writerow(mat)
        messagebox.showinfo("Save CSV", "Materials saved successfully.")

    def add_material(self):
        new_mat = {
            'Name': f'Material_{len(self.materials)}',
            'albedo_r': 1.0, 'albedo_g': 1.0, 'albedo_b': 1.0,
            'smoothness_multiplier': 0.5,
            'metalness_multiplier': 0.0,
            'albedo_map': '', 'metalness_map': '', 'detail_map': '', 'emmissive_map': ''
        }
        self.materials.append(new_mat)
        self.material_listbox.insert(tk.END, new_mat['Name'])
        self.material_listbox.select_clear(0, tk.END)
        self.material_listbox.select_set(tk.END)
        self.on_material_select()

    def pick_color(self):
        rgb = colorchooser.askcolor()[0]
        if rgb:
            self.color = tuple(c / 255.0 for c in rgb)
            self.render_preview()

    def pick_map(self, map_type):
        file = filedialog.askopenfilename(title=f"Select {map_type} texture")
        if file and self.working_dir:
            textures_dir = os.path.join(self.working_dir, "textures")
            os.makedirs(textures_dir, exist_ok=True)
            filename = os.path.basename(file)
            dest = os.path.join(textures_dir, filename)
            shutil.copy(file, dest)
            self.map_vars[map_type].set(f"textures/{filename}")

    def on_material_select(self, event=None):
        selection = self.material_listbox.curselection()
        if not selection:
            return
        self.current_index = selection[0]
        mat = self.materials[self.current_index]
        self.name_var.set(mat['Name'])
        self.color = (float(mat['albedo_r']), float(mat['albedo_g']), float(mat['albedo_b']))
        self.roughness.set(float(mat['smoothness_multiplier']))
        self.metalness.set(float(mat['metalness_multiplier']))
        for k in self.map_vars:
            self.map_vars[k].set(mat.get(k, ''))
        self.render_preview()

    def save_current_material(self):
        if self.current_index is None:
            return
        mat = self.materials[self.current_index]
        mat['Name'] = self.name_var.get()
        mat['albedo_r'], mat['albedo_g'], mat['albedo_b'] = self.color
        mat['smoothness_multiplier'] = self.roughness.get()
        mat['metalness_multiplier'] = self.metalness.get()
        for k in self.map_vars:
            mat[k] = self.map_vars[k].get()
        self.material_listbox.delete(self.current_index)
        self.material_listbox.insert(self.current_index, mat['Name'])
        self.render_preview()

    def render_preview(self):
        if not self.working_dir or self.current_index is None:
            return
        config_path = os.path.join(self.working_dir, "material_config.txt")
        signal_path = os.path.join(self.working_dir, "signal.txt")
        done_path = os.path.join(self.working_dir, "done.txt")
        preview_path = os.path.join(self.working_dir, "preview.png")
        self.preview_path = preview_path

        mat = self.materials[self.current_index]

        # Update in-memory values from the current UI state
        mat['Name'] = self.name_var.get()
        mat['albedo_r'], mat['albedo_g'], mat['albedo_b'] = self.color
        mat['smoothness_multiplier'] = self.roughness.get()
        mat['metalness_multiplier'] = self.metalness.get()
        for k in self.map_vars:
            mat[k] = self.map_vars[k].get()

        with open(config_path, "w") as f:
            f.write(f"{mat['albedo_r']},{mat['albedo_g']},{mat['albedo_b']},{mat['smoothness_multiplier']},{mat['metalness_multiplier']}")

        if os.path.exists(done_path):
            os.remove(done_path)
        with open(signal_path, "w") as f:
            f.write("go")

        def wait_for_render():
            while not os.path.exists(done_path):
                time.sleep(0.1)
            img = Image.open(preview_path).resize((256, 256))
            self.preview_image = ImageTk.PhotoImage(img)
            self.preview_label.config(image=self.preview_image, text="")

        threading.Thread(target=wait_for_render, daemon=True).start()

    def export_to_unity(self):
        if self.current_index is None:
            messagebox.showinfo("Export", "Select a material first.")
            return

        mat = self.materials[self.current_index]
        export_dir = os.path.join(self.working_dir, "exports", mat['Name'])
        os.makedirs(os.path.join(export_dir, "textures"), exist_ok=True)

        for map_type in ["albedo_map", "metalness_map", "detail_map", "emmissive_map"]:
            src = os.path.join(self.working_dir, mat[map_type])
            if os.path.exists(src):
                shutil.copy(src, os.path.join(export_dir, "textures", os.path.basename(src)))

        cs_path = os.path.join(export_dir, f"{mat['Name']}.cs")
        with open(cs_path, 'w') as f:
            f.write(f"// Auto-generated material definition\n")
            f.write(f"Material mat = new Material(Shader.Find(\"Standard\"));\n")
            f.write(f"mat.color = new Color({mat['albedo_r']}f, {mat['albedo_g']}f, {mat['albedo_b']}f);\n")
            f.write(f"mat.SetFloat(\"_Glossiness\", {mat['smoothness_multiplier']}f);\n")
            f.write(f"mat.SetFloat(\"_Metallic\", {mat['metalness_multiplier']}f);\n")
            for map_type in ["albedo_map", "metalness_map", "detail_map", "emmissive_map"]:
                tex_var = map_type.replace("_map", "")
                tex_file = os.path.basename(mat[map_type])
                if tex_file:
                    f.write(f"mat.SetTexture(\"_{tex_var}\", Resources.Load<Texture2D>(\"textures/{tex_file}\"));\n")

if __name__ == "__main__":
    root = tk.Tk()
    app = MaterialEditorApp(root)
    root.mainloop()
