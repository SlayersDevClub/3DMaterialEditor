import tkinter as tk 
from tkinter import filedialog, colorchooser, messagebox


def pick_color():
    rgb = colorchooser.askcolor()[0]
    if rgb:
        print("you picked color", rgb)
        return  tuple(c / 255.0 for c in rgb)
    else:
        return None

