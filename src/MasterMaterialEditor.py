# Material Editor GUI Scaffold
# Requirements: ttkinter, Pillow, csv, shutil
import ttkbootstrap as ttk
from ttkbootstrap import Window, Style
import tkinter as tk
from tkinter import filedialog, colorchooser, messagebox
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
        self.style = Style()
        self.root.title("Material Editor")
        self.working_dir = None
        self.materials = []
        self.current_index = None
        self.blender_path = None
        self.daemon_process = None
        self.preview_path = None

        self._render_in_progress = False
        self._retry_render = False

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.setup_gui()

    def setup_gui(self):
        menubar = ttk.Menu(self.root)

        file_menu = ttk.Menu(menubar, tearoff=0)
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

        edit_menu = ttk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Camera Settings", command=self.open_camera_settings)
        edit_menu.add_separator()
        edit_menu.add_command(label="Refresh All Previews", command=self.refresh_all_previews)


        preview_menu = ttk.Menu(menubar, tearoff=0)
        preview_menu.add_command(label="Material Gallery", command=self.open_material_gallery)
        preview_menu.add_separator()
        preview_menu.add_command(label="Use Custom Model", command=self.set_custom_preview_model)
        preview_menu.add_separator()
        preview_menu.add_command(label="Use Sphere Primitive", command=lambda: self.set_primitive_preview("sphere"))
        preview_menu.add_command(label="Use Cube Primitive", command=lambda: self.set_primitive_preview("cube"))
        preview_menu.add_command(label="Use Cylinder Primitive", command=lambda: self.set_primitive_preview("cylinder"))

        menubar.add_cascade(label="File", menu=file_menu)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        menubar.add_cascade(label="Preview", menu=preview_menu)
        self.root.config(menu=menubar)

        self.left_frame = ttk.Frame(self.root, width=200)
        self.left_frame.pack(side=ttk.LEFT, fill=ttk.Y)
        self.right_frame = ttk.Frame(self.root)
        self.right_frame.pack(side=ttk.RIGHT, expand=True, fill=ttk.BOTH)

        self.material_listbox = ttk.Treeview(self.left_frame)
        self.material_listbox.pack(fill=ttk.BOTH, expand=True)
        self.material_listbox.bind("<<TreeviewSelect>>", self.on_material_select)

        self.preview_label = ttk.Label(
            self.right_frame,
            text="Preview not available",
            relief="sunken",
            anchor="center"
        )
        self.preview_label.pack(fill="both", expand=True, pady=(0, 10))

        self.name_var = ttk.StringVar()
        ttk.Label(self.right_frame, text="Material Name").pack()
        ttk.Entry(self.right_frame, textvariable=self.name_var).pack(fill=ttk.X)

        self.color = (1.0, 1.0, 1.0)
        ttk.Button(self.right_frame, text="Pick Albedo Color", command=self.pick_color).pack(fill=ttk.X)

        self.roughness = ttk.DoubleVar(value=0.5)
        ttk.Label(self.right_frame, text="Smoothness").pack()
        ttk.Scale(self.right_frame, from_=0, to=1, variable=self.roughness,
                orient="horizontal", command=lambda v: self.render_preview()).pack(fill=ttk.X)


        self.metalness = ttk.DoubleVar(value=0.0)
        ttk.Label(self.right_frame, text="Metalness").pack()
        ttk.Scale(self.right_frame, from_=0, to=1, variable=self.metalness,
                orient="horizontal", command=lambda v: self.render_preview()).pack(fill=ttk.X)


        self.map_vars = {}
        for map_type in ["albedo_map", "metalness_map", "detail_map", "emmissive_map"]:
            var = ttk.StringVar()
            var.trace_add("write", lambda *args: self.schedule_preview_render())
            self.map_vars[map_type] = var
            row = ttk.Frame(self.right_frame)
            row.pack(fill=ttk.X)
            ttk.Label(row, text=map_type).pack(side=ttk.LEFT)
            ttk.Entry(row, textvariable=var).pack(side=ttk.LEFT, fill=ttk.X, expand=True)
            ttk.Button(row, text="...", command=lambda mt=map_type: self.pick_map(mt)).pack(side=ttk.RIGHT)

        ttk.Button(self.right_frame, text="Save Changes", command=self.save_current_material).pack(fill=ttk.X, pady=10)

    def on_slider_changed(self, value):
        if hasattr(self, '_slider_timer'):
            self.root.after_cancel(self._slider_timer)
        self._slider_timer = self.root.after(100, self.render_preview)

    def schedule_preview_render(self):
        self.render_preview()

    def trigger_render_signal(self):
        if self._render_in_progress:
            self._retry_render = True
            return
        self.render_preview()


    def pick_color(self):
        rgb = colorchooser.askcolor()[0]
        if rgb:
            self.color = tuple(c / 255.0 for c in rgb)
            self.schedule_preview_render()

    def pick_map(self, map_type):
        file = filedialog.askopenfilename(title=f"Select {map_type} texture")
        if file and self.working_dir and self.current_index is not None:
            mat = self.materials[self.current_index]

            # Create folders
            material_folder = os.path.join(self.working_dir, "materials", mat['Name'])
            texture_folder = os.path.join(material_folder, "textures")
            os.makedirs(texture_folder, exist_ok=True)

            # Copy file
            filename = os.path.basename(file)
            dest = os.path.join(texture_folder, filename)
            shutil.copy(file, dest)

            # Update dictionary and UI field
            relative_path = os.path.join("materials", mat['Name'], "textures", filename)
            self.map_vars[map_type].set(relative_path)
            mat[map_type] = relative_path

            print(f"✅ {map_type} set to {relative_path}")

            # Ensure all 7 fields are written (even if some maps are missing)
            albedo_map = mat.get("albedo_map", "")
            metalness_map = mat.get("metalness_map", "")

            config_path = os.path.join(material_folder, "material_config.txt")
            try:
                with open(config_path, "w") as f:
                    f.write(f"{mat['albedo_r']},{mat['albedo_g']},{mat['albedo_b']},"
                            f"{mat['smoothness_multiplier']},{mat['metalness_multiplier']},"
                            f"{mat.get('albedo_map','')},{mat.get('metalness_map','')}")
                print(f"💾 Saved config to {config_path}")
            except Exception as e:
                print("❌ Failed to write material config:", e)


            self.render_preview()

    def on_material_select(self, event=None):
        selection = self.material_listbox.selection()
        if not selection:
            return

        current_index = self.material_listbox.index(selection[0])
        self.current_index = current_index

        mat = self.materials[current_index]
        material_folder = os.path.join(self.working_dir, "materials", mat['Name'])
        material_config_path = os.path.join(material_folder, "material_config.txt")

        # Load config values (preferred over CSV)
        if os.path.exists(material_config_path):
            try:
                with open(material_config_path, "r") as f:
                    r, g, b, rough, metal = map(float, f.read().strip().split(","))
                    self.color = (r, g, b)
                    self.roughness.set(rough)
                    self.metalness.set(metal)
                    print(f"✅ Loaded config from: {material_config_path}")
            except Exception as e:
                print("❌ Failed to load config:", e)
        else:
            # Fall back to CSV values only if no config file exists
            self.color = (float(mat['albedo_r']), float(mat['albedo_g']), float(mat['albedo_b']))
            self.roughness.set(float(mat['smoothness_multiplier']))
            self.metalness.set(float(mat['metalness_multiplier']))

        self.name_var.set(mat['Name'])

        # Load maps
        for map_type in self.map_vars:
            tex_name = mat.get(map_type, '')
            if tex_name:
                local_path = os.path.join("materials", mat['Name'], "textures", os.path.basename(tex_name))
                self.map_vars[map_type].set(local_path)
            else:
                self.map_vars[map_type].set('')

        # Load preview
        preview_path = os.path.join(material_folder, "preview.png")
        if os.path.exists(preview_path):
            try:
                img = Image.open(preview_path).resize((256, 256))
                self.preview_image = ImageTk.PhotoImage(img)
                self.preview_label.config(image=self.preview_image, text="")
            except Exception as e:
                print("❌ Failed to load preview image:", e)


    def render_preview(self):
        if not self.working_dir or self.current_index is None:
            return

        mat = self.materials[self.current_index]
        mat['Name'] = self.name_var.get()
        mat['albedo_r'], mat['albedo_g'], mat['albedo_b'] = self.color
        mat['smoothness_multiplier'] = self.roughness.get()
        mat['metalness_multiplier'] = self.metalness.get()
        for k in self.map_vars:
            mat[k] = self.map_vars[k].get()

        app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        data_path = os.path.join(app_dir, "data")
        config_path = os.path.join(data_path, "material_config.txt")
        command_path = os.path.join(data_path, "command.txt")
        preview_path = os.path.join(data_path, "preview.png")

        with open(config_path, "w") as f:
            f.write(f"{mat['albedo_r']},{mat['albedo_g']},{mat['albedo_b']},"
                    f"{mat['smoothness_multiplier']},{mat['metalness_multiplier']},"
                    f"{mat.get('albedo_map', '')},{mat.get('metalness_map', '')}")

        with open(command_path, "w") as f:
            f.write("render")

        # Save a copy to material's own folder
        material_folder = os.path.join(self.working_dir, "materials", mat['Name'])
        os.makedirs(material_folder, exist_ok=True)
        local_config_path = os.path.join(material_folder, "material_config.txt")
        with open(local_config_path, "w") as f:
            f.write(f"{mat['albedo_r']},{mat['albedo_g']},{mat['albedo_b']},"
                    f"{mat['smoothness_multiplier']},{mat['metalness_multiplier']},"
                    f"{mat.get('albedo_map', '')},{mat.get('metalness_map', '')}")

            
        def wait_for_render():
            start = time.time()
            while not os.path.exists(preview_path):
                if time.time() - start > 10:
                    print("❌ Timeout waiting for render")
                    return
                time.sleep(0.05)
            try:
                img = Image.open(preview_path).resize((256, 256))
                self.preview_image = ImageTk.PhotoImage(img)
                self.preview_label.config(image=self.preview_image, text="")

                material_folder = os.path.join(self.working_dir, "materials", mat['Name'])
                os.makedirs(material_folder, exist_ok=True)
                final_preview = os.path.join(material_folder, "preview.png")
                shutil.copy(preview_path, final_preview)
                print(f"✅ Saved preview to: {final_preview}")
            except Exception as e:
                print("❌ Error loading preview image:", e)




        threading.Thread(target=wait_for_render, daemon=True).start()
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
        cam_win = ttk.Toplevel(self.root)
        cam_win.title("Camera Settings")

        def update_setting(label, default):
            return ttk.DoubleVar(value=default)

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
            row = ttk.Frame(cam_win)
            row.pack(fill=ttk.X, padx=10, pady=2)
            ttk.Label(row, text=label).pack(side=ttk.LEFT)
            ttk.Scale(row, from_=-10, to=10, resolution=0.1, orient="horizontal", variable=var).pack(side=ttk.RIGHT, fill=ttk.X, expand=True)

        ttk.Button(cam_win, text="Apply Changes", command=self.restart_blender_daemon).pack(pady=10)

    def restart_blender_daemon(self):
        if self.daemon_process:
            try:
                self.daemon_process.terminate()
            except Exception:
                pass
        self.launch_blender_daemon()

    def on_close(self):
        # Safely shut down Blender daemon if running
        if self.daemon_process and self.daemon_process.poll() is None:
            try:
                self.daemon_process.terminate()
                self.daemon_process.wait(timeout=3)
                print("✅ Blender daemon terminated.")
            except Exception as e:
                print(f"⚠️ Failed to terminate Blender daemon: {e}")

        # Also clean up PID file if you're using one
        if hasattr(self, 'blender_pid_path') and self.blender_pid_path and os.path.exists(self.blender_pid_path):
            try:
                os.remove(self.blender_pid_path)
            except Exception:
                pass

        # Now close the UI
        self.root.destroy()


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

    def refresh_all_previews(self):
        if not self.materials or not self.working_dir:
            return

        def render_next(index=0):
            if index >= len(self.materials):
                print("✅ All previews refreshed.")
                return

            self.current_index = index
            mat = self.materials[index]
            self.name_var.set(mat['Name'])
            self.color = (float(mat['albedo_r']), float(mat['albedo_g']), float(mat['albedo_b']))
            self.roughness.set(float(mat['smoothness_multiplier']))
            self.metalness.set(float(mat['metalness_multiplier']))
            for k in self.map_vars:
                self.map_vars[k].set(mat.get(k, ''))

            def after_render():
                self.root.after(100, lambda: render_next(index + 1))

            self.render_preview(callback=after_render)

        render_next()

    def open_material_gallery(self):
        if not self.working_dir:
            return

        gallery = ttk.Toplevel(self.root)
        gallery.title("Material Gallery")
        gallery.geometry = "800x600"

        canvas = ttk.Canvas(gallery)
        frame = ttk.Frame(canvas)
        scrollbar = ttk.Scrollbar(gallery, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)


        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=frame, anchor="nw")

        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        frame.bind("<Configure>", on_configure)

        thumb_size = (96, 96)
        columns = 4


        for index, mat in enumerate(self.materials):
            row = index // columns
            col = index % columns

            mat_name = mat['Name']
            mat_folder = os.path.join(self.working_dir, "materials", mat_name)
            preview_path = os.path.join(mat_folder, "preview.png")

            thumb_frame = ttk.Frame(frame, relief="ridge", borderwidth=1, padding=4)
            thumb_frame.grid(row=row, column=col, padx=5, pady=5)

            try:
                img = Image.open(preview_path).resize(thumb_size)
            except:
                img = Image.new("RGB", thumb_size, (80, 80, 80))
            img_tk = ImageTk.PhotoImage(img)

            def make_click_handler(index=index):
                return lambda e: self.select_material_from_index(index)

            label = ttk.Label(thumb_frame, image=img_tk)
            label.image = img_tk  # keep reference
            label.pack()
            label.bind("<Button-1>", make_click_handler())

            name_label = ttk.Label(thumb_frame, text=mat_name, wraplength=thumb_size[0])
            name_label.pack()

    def select_material_from_index(self, index):
        if index < 0 or index >= len(self.materials):
            return
        self.material_listbox.selection_set(self.material_listbox.get_children()[index])
        self.material_listbox.focus(self.material_listbox.get_children()[index])
        self.on_material_select()
    def launch_blender_daemon(self):
        if not self.blender_path or not self.working_dir:
            return

        current_dir = os.path.dirname(os.path.abspath(__file__))

        app_dir = os.path.abspath(os.path.join(current_dir, ".."))
        data_path = os.path.join(app_dir, "data")

        blend_file = os.path.join(data_path, "preview.blend")

        daemon_script = os.path.join(current_dir, "blender_daemon.py")

        # Launch Blender in background
        process = subprocess.Popen([
            self.blender_path, "-b", blend_file, "--python", daemon_script
        ])

        self.daemon_process = process
        self.blender_pid_path = os.path.join(self.working_dir, "blender_pid.txt")

        # Save PID
        with open(self.blender_pid_path, "w") as f:
            f.write(str(process.pid))

    def new_project(self):
        self.working_dir = filedialog.askdirectory(title="Select New Project Folder")
        if not self.working_dir:
            return
        self.materials.clear()
        for item in self.material_listbox.get_children():
            # Get the selected item ID
            selected_item = self.material_listbox.selection()[0]


        os.makedirs(os.path.join(self.working_dir, "textures"), exist_ok=True)
        os.makedirs(os.path.join(self.working_dir, "exports"), exist_ok=True)
        os.makedirs(os.path.join(self.working_dir, "materials"), exist_ok=True)  # New folder for material-specific folders

        self.load_blender_path()
        self.launch_blender_daemon()
        messagebox.showinfo("New Project", "New project initialized. You can now add materials.")

    def open_project(self):
        self.working_dir = filedialog.askdirectory(title="Select Project Folder")
        if not self.working_dir:
            return

        csv_path = os.path.join(self.working_dir, "materials.csv")        
        self.materials.clear()
        #self.material_listbox.delete(0, ttk.END)
        for item in self.material_listbox.get_children():
            # Get the selected item ID
            selected_item = self.material_listbox.selection()[0]


        if os.path.exists(csv_path):
            with open(csv_path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    self.materials.append(row)
                    self.material_listbox.insert("", "end", text=...)


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
        for item in self.material_listbox.selection():
            self.material_listbox.selection_remove(item)
        # Insert the new material and get its item ID
        item_id = self.material_listbox.insert("", "end", text=new_mat['Name'])

        # Deselect previous selections
        for item in self.material_listbox.selection():
            self.material_listbox.selection_remove(item)

        # Select and focus the newly inserted item
        self.material_listbox.selection_set(item_id)
        self.material_listbox.focus(item_id)

        self.on_material_select()


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

        # Update the label in the listbox
        try:
            # Find the correct item using selection
            selection = self.material_listbox.selection()
            if selection:
                self.material_listbox.item(selection[0], text=mat['Name'])
        except Exception as e:
            print("⚠️ Could not update list item:", e)

            # Also save a copy of the config into the material's folder
            material_folder = os.path.join(self.working_dir, "materials", mat['Name'])
            os.makedirs(material_folder, exist_ok=True)
            material_config_path = os.path.join(material_folder, "material_config.txt")

            try:
                with open(material_config_path, "w") as f:
                    f.write(f"{mat['albedo_r']},{mat['albedo_g']},{mat['albedo_b']},"
                            f"{mat['smoothness_multiplier']},{mat['metalness_multiplier']},"
                            f"{mat.get('albedo_map','')},{mat.get('metalness_map','')}")
                print(f"✅ Saved config to: {material_config_path}")
            except Exception as e:
                print("❌ Failed to save per-material config:", e)

        # Save a copy to material's own folder
        material_folder = os.path.join(self.working_dir, "materials", mat['Name'])
        os.makedirs(material_folder, exist_ok=True)
        local_config_path = os.path.join(material_folder, "material_config.txt")
        with open(local_config_path, "w") as f:
            f.write(f"{mat['albedo_r']},{mat['albedo_g']},{mat['albedo_b']},"
                    f"{mat['smoothness_multiplier']},{mat['metalness_multiplier']}")
        # Wait for any in-progress render to finish
        def wait_then_copy():
            while getattr(self, "_render_in_progress", False):
                time.sleep(0.1)

            # Now copy the current preview to the material folder
            app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            data_path = os.path.join(app_dir, "data")
            central_preview_path = os.path.join(data_path, "preview.png")

            material_folder = os.path.join(self.working_dir, "materials", mat['Name'])
            os.makedirs(material_folder, exist_ok=True)
            final_preview = os.path.join(material_folder, "preview.png")

            try:
                shutil.copy(central_preview_path, final_preview)
                print(f"✅ Final preview saved to: {final_preview}")
            except Exception as e:
                print("❌ Failed to save final preview:", e)

        threading.Thread(target=wait_then_copy, daemon=True).start()


    def render_preview(self):
        if not self.working_dir or self.current_index is None:
            return

        # Get the current material and update its values from the UI.
        mat = self.materials[self.current_index]
        mat['Name'] = self.name_var.get()
        mat['albedo_r'], mat['albedo_g'], mat['albedo_b'] = self.color
        mat['smoothness_multiplier'] = self.roughness.get()
        mat['metalness_multiplier'] = self.metalness.get()
        for k in self.map_vars:
            mat[k] = self.map_vars[k].get()

        # Instead of writing to a material-specific folder here,
        # we write the configuration to the central data folder.
        # (Your daemon script will read from this central location.)
        app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        data_path = os.path.join(app_dir, "data")
        central_config_path = os.path.join(data_path, "material_config.txt")
        central_signal_path = os.path.join(data_path, "signal.txt")
        central_done_path   = os.path.join(data_path, "done.txt")
        central_preview_path = os.path.join(data_path, "preview.png")

        with open(central_config_path, "w") as f:
            f.write(f"{mat['albedo_r']},{mat['albedo_g']},{mat['albedo_b']},"
                    f"{mat['smoothness_multiplier']},{mat['metalness_multiplier']}")

        # Remove previous "done" signal if it exists, then signal the daemon.
        if os.path.exists(central_done_path):
            os.remove(central_done_path)
        with open(central_signal_path, "w") as f:
            f.write("go")

        # Start a thread that waits for the daemon to finish rendering.
        def wait_for_render():
            while not os.path.exists(central_done_path):
                time.sleep(0.1)
            try:
                img = Image.open(central_preview_path).resize((256, 256))
            except Exception as e:
                print("Error loading preview:", e)
                return
            self.preview_image = ImageTk.PhotoImage(img)
            self.preview_label.config(image=self.preview_image, text="")

            # Now copy the live preview into the specific material folder.
            # Create (or ensure) the material's folder exists.
            material_folder = os.path.join(self.working_dir, "materials", mat['Name'])
            os.makedirs(material_folder, exist_ok=True)
            final_preview = os.path.join(material_folder, "preview.png")
            try:
                shutil.copy(central_preview_path, final_preview)
                print(f"✅ Saved preview to: {final_preview}")
            except Exception as e:
                print("❌ Failed to copy preview:", e)

        threading.Thread(target=wait_for_render, daemon=True).start()


    def export_to_unity(self):
        if self.current_index is None:
            messagebox.showinfo("Export", "Select a material first.")
            return

        mat = self.materials[self.current_index]
        export_dir = os.path.join(self.working_dir, "exports", mat['Name'])

        os.makedirs(os.path.join(export_dir, "textures"), exist_ok=True)

        for map_type in ["albedo_map", "metalness_map", "detail_map", "emmissive_map"]:
            src = os.path.join(self.working_dir, "materials", mat['Name'], mat[map_type])
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

