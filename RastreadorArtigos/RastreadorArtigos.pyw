from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox

try:
    import requests  # noqa: F401
    import openpyxl  # noqa: F401
except ImportError:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Dependências ausentes",
        "Execute iniciar.bat ou instale as dependências com:\n\npython -m pip install -r requirements.txt",
    )
    raise SystemExit(1)

from app.gui import App


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    root = tk.Tk()
    App(root, base_dir)
    root.mainloop()
