import os
import platform
import subprocess
import tkinter.messagebox as messagebox

def save_blender_path(path, working_dir, config_filename="editor_config.txt"):
    if not working_dir:
        return
    with open(os.path.join(working_dir, config_filename), "w") as f:
        f.write(path)

def load_blender_path(working_dir, config_filename="editor_config.txt"):
    if not working_dir:
        return None
    path = os.path.join(working_dir, config_filename)
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read().strip()
    return None

def launch_blender_daemon(blender_path, working_dir):
    if not blender_path or not working_dir:
        return None, None

    if not os.path.isfile(blender_path):
        messagebox.showerror("Blender Error", f"Blender executable not found at:\n{blender_path}")
        return None, None

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    blend_file = os.path.join(base_dir, "data", "preview.blend")
    daemon_script = os.path.join(base_dir, "src", "blender_daemon.py")

    if platform.system() == "Windows":
        bat_path = os.path.join(os.path.dirname(__file__), "start_blender_daemon.bat")
        if os.path.exists(bat_path):
            process = subprocess.Popen(bat_path, shell=True)
        else:
            messagebox.showerror("Missing .bat File", f"Expected to find: {bat_path}")
            return None, None
    else:
        process = subprocess.Popen([
            blender_path, "-b", blend_file, "--python", daemon_script
        ])

    pid_path = os.path.join(working_dir, "blender_pid.txt")
    with open(pid_path, "w") as f:
        f.write(str(process.pid))

    return process, pid_path

def kill_blender_daemon(pid_path):
    if not pid_path or not os.path.exists(pid_path):
        return
    try:
        with open(pid_path, "r") as f:
            pid = int(f.read().strip())

        if platform.system() == "Windows":
            subprocess.call(["taskkill", "/PID", str(pid), "/F"])
        else:
            subprocess.call(["kill", "-9", str(pid)])

        os.remove(pid_path)
    except Exception as e:
        print(f"⚠️ Could not terminate Blender daemon: {e}")
