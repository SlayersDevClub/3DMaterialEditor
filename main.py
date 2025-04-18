import os
import tkinter as tk
from ttkbootstrap import Window
from src import MasterMaterialEditor

def set_app_icon(root):
    """
    Sets the window icon using an icon image in the ./graphics folder.
    """
    # Determine the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Build a cross-platform path to your icon file
    icon_path = os.path.join(script_dir, "graphics", "icon.png")
    # Load the icon using tkinter's PhotoImage
    icon = tk.PhotoImage(file=icon_path)
    root.iconphoto(False, icon)
    # Keep a reference so it doesn't get garbage collected
    root.icon = icon

def main():
    # Create your themed window
    root = Window(themename="darkly")
    root.title("Master Material Editor")
    # Set the icon for the app
    set_app_icon(root)
    # Pass the configured window into your MaterialEditorApp class
    MasterMaterialEditor.MaterialEditorApp(root)
    # Start the event loop
    root.mainloop()

if __name__ == "__main__":
    main()
