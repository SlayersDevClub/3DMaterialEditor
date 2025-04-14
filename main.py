import os
import tkinter as tk
from ttkbootstrap import Window
from src import MasterMaterialEditor

def set_app_icon(root):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(script_dir, "graphics", "icon.png")
    icon = tk.PhotoImage(file=icon_path)
    root.iconphoto(False, icon)
    root.icon = icon

def main():
    root = Window(themename="darkly")
    root.title("Master Material Editor")
    set_app_icon(root)
    app = MasterMaterialEditor.MaterialEditorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
