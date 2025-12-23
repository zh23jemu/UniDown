import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QLineEdit, QPushButton, 
                             QLabel, QFileDialog, QFormLayout, QFrame)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon

class ModernTab(QWidget):
    def __init__(self, platform_name):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 40, 30, 40)
        layout.setSpacing(20)

        # Title/Logo Area
        title_label = QLabel(f"{platform_name} Video Downloader")
        title_label.setObjectName("tabTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Input Area
        input_container = QFrame()
        input_container.setObjectName("inputContainer")
        input_layout = QVBoxLayout(input_container)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(f"Paste your {platform_name} video link here...")
        self.url_input.setMinimumHeight(50)
        input_layout.addWidget(self.url_input)

        layout.addWidget(input_container)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.download_btn = QPushButton("Analyze Video")
        self.download_btn.setMinimumHeight(45)
        self.download_btn.setObjectName("primaryButton")
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.download_btn, 1)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        layout.addStretch()

class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 40, 30, 40)
        
        title_label = QLabel("Global Settings")
        title_label.setObjectName("tabTitle")
        layout.addWidget(title_label)
        layout.addSpacing(20)

        form_frame = QFrame()
        form_frame.setObjectName("settingsFrame")
        form_layout = QFormLayout(form_frame)
        form_layout.setVerticalSpacing(25)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Download Path
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Default download folder...")
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setFixedWidth(80)
        self.browse_btn.clicked.connect(self.select_folder)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_btn)
        
        form_layout.addRow("Download Path:", path_layout)

        # Proxy
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("e.g. http://127.0.0.1:7890")
        form_layout.addRow("Proxy Server:", self.proxy_input)

        layout.addWidget(form_frame)
        
        # Save Button
        save_btn = QPushButton("Apply Settings")
        save_btn.setObjectName("primaryButton")
        save_btn.setFixedWidth(150)
        layout.addSpacing(20)
        layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addStretch()

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Directory")
        if folder:
            self.path_input.setText(folder)

class UniDownApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UniDown - Ultimate Video Downloader")
        self.resize(700, 500)
        
        self.init_ui()
        self.apply_styles()
        
        # Set App Icon
        self.setWindowIcon(QIcon("assets/icon.png"))

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(60)
        header_layout = QHBoxLayout(header)
        
        logo_label = QLabel("UniDown")
        logo_label.setObjectName("logo")
        header_layout.addWidget(logo_label)
        header_layout.addStretch()
        
        main_layout.addWidget(header)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        
        self.tab_bilibili = ModernTab("Bilibili")
        self.tab_youtube = ModernTab("YouTube")
        self.tab_settings = SettingsTab()

        self.tabs.addTab(self.tab_bilibili, "Bilibili")
        self.tabs.addTab(self.tab_youtube, "YouTube")
        self.tabs.addTab(self.tab_settings, "Settings")

        main_layout.addWidget(self.tabs)

        # Status Bar
        self.statusBar().showMessage("Ready")

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
            }
            #header {
                background-color: #252525;
                border-bottom: 2px solid #333;
            }
            #logo {
                color: #00a8ff;
                font-size: 24px;
                font-weight: bold;
                padding-left: 20px;
            }
            QTabWidget::pane {
                border: none;
                background-color: #1a1a1a;
            }
            QTabBar::tab {
                background-color: #252525;
                color: #888;
                padding: 12px 30px;
                font-size: 14px;
                border: none;
            }
            QTabBar::tab:selected {
                background-color: #1a1a1a;
                color: #00a8ff;
                border-bottom: 3px solid #00a8ff;
            }
            QTabBar::tab:hover {
                color: #ccc;
            }
            #tabTitle {
                font-size: 28px;
                font-weight: bold;
                color: #efefef;
                margin-bottom: 10px;
            }
            QLineEdit {
                background-color: #2a2a2a;
                border: 2px solid #3a3a3a;
                border-radius: 8px;
                color: #fff;
                padding: 10px 15px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #00a8ff;
            }
            QPushButton {
                background-color: #333;
                color: #fff;
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #444;
            }
            #primaryButton {
                background-color: #00a8ff;
                font-size: 16px;
            }
            #primaryButton:hover {
                background-color: #0097e6;
            }
            QLabel {
                color: #ccc;
                font-size: 14px;
            }
            #settingsFrame {
                background-color: #252525;
                border-radius: 12px;
                padding: 20px;
            }
            QStatusBar {
                background-color: #252525;
                color: #666;
            }
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = UniDownApp()
    window.show()
    sys.exit(app.exec())
