import sys
from PySide6.QtWidgets import QApplication
from yimo.gui.main_window import MainWindow
from yimo.gui.style import load_stylesheet
from yimo.gui.icon import load_app_icon

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("YiMo 译墨")
    app.setStyle("Fusion")
    app.setStyleSheet(load_stylesheet())
    app.setWindowIcon(load_app_icon())
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
