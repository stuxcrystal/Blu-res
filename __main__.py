import os
os.environ["TCL_LIBRARY"] = "C:\\Python27\\tcl\\tcl8.5"

from blures.gui import Application

if __name__ == "__main__":
    Application().mainloop()