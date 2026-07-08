"""
Main entry point for Perler Beads Designer application - Tkinter Version
"""
import sys
import os

# Add project root directory to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.ui.main_window import MainWindow


def main():
    """Main application entry point"""
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
