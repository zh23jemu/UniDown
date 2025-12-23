import sys
import re
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QLineEdit, QPushButton, 
                             QLabel, QFileDialog, QFormLayout, QFrame, QDialog,
                             QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QIcon

class ModernTab(QWidget):
    def __init__(self, platform_name):
        super().__init__()
        self.statusBar().showMessage("Ready")

class FormatSelectionDialog(QDialog):
    def __init__(self, info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Download Format")
        self.resize(800, 500)
        self.selected_format = None
        
        formats = info.get('formats', [])
        title = info.get('title', 'Unknown Title')
        duration_sec = info.get('duration', 0)
        
        # Format duration
        if duration_sec:
            mins, secs = divmod(int(duration_sec), 60)
            hours, mins = divmod(mins, 60)
            if hours > 0:
                duration_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
            else:
                duration_str = f"{mins:02d}:{secs:02d}"
        else:
            duration_str = "Unknown"

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Video Info Header
        info_frame = QFrame()
        info_frame.setObjectName("infoFrame")
        info_layout = QVBoxLayout(info_frame)
        
        title_label = QLabel(f"Title: {title}")
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #00a8ff;")
        
        duration_label = QLabel(f"Duration: {duration_str}")
        duration_label.setStyleSheet("color: #aaa;")
        
        info_layout.addWidget(title_label)
        info_layout.addWidget(duration_label)
        layout.addWidget(info_frame)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Code", "Extension", "Resolution", "Size", "Note"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)
        
        # Populate table
        self.table.setRowCount(len(formats))
        for i, fmt in enumerate(formats):
            # Code
            self.table.setItem(i, 0, QTableWidgetItem(str(fmt.get('format_id', ''))))
            # Extension
            self.table.setItem(i, 1, QTableWidgetItem(str(fmt.get('ext', ''))))
            # Resolution
            res = f"{fmt.get('width', '?')}x{fmt.get('height', '?')}"
            self.table.setItem(i, 2, QTableWidgetItem(res))
            # Size
            filesize = fmt.get('filesize') or fmt.get('filesize_approx')
            size_str = f"{filesize/1024/1024:.1f} MB" if filesize else "N/A"
            self.table.setItem(i, 3, QTableWidgetItem(size_str))
            # Note description
            note = fmt.get('format_note', '')
            vcodec = fmt.get('vcodec', 'none')
            acodec = fmt.get('acodec', 'none')
            if vcodec != 'none' and acodec == 'none':
                note += " (Video Only)"
            elif vcodec == 'none' and acodec != 'none':
                note += " (Audio Only)"
            self.table.setItem(i, 4, QTableWidgetItem(note))

        # Options
        self.chk_merge = QCheckBox("Merge Best Audio (Use for Video-Only streams)")
        self.chk_merge.setChecked(True)
        layout.addWidget(self.chk_merge)

        # Buttons
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        download_btn = QPushButton("Download")
        download_btn.setObjectName("primaryButton")
        download_btn.clicked.connect(self.accept_selection)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(download_btn)
        layout.addLayout(btn_layout)
        
        # Apply styles
        self.setStyleSheet("""
            QDialog { background-color: #1a1a1a; color: #fff; }
            #infoFrame { background-color: #252525; border-radius: 8px; padding: 10px; }
            QTableWidget { background-color: #252525; color: #fff; gridline-color: #333; border: none; }
            QHeaderView::section { background-color: #333; color: #ccc; padding: 5px; border: none; }
            QTableWidget::item:selected { background-color: #00a8ff; color: #fff; }
            QPushButton { background-color: #333; color: #fff; padding: 8px 15px; border-radius: 4px; }
            QPushButton#primaryButton { background-color: #00a8ff; }
            QCheckBox { color: #ccc; spacing: 8px; }
        """)

    def accept_selection(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            return
        
        row = selected_items[0].row()
        fmt_id = self.table.item(row, 0).text()
        fmt_note = self.table.item(row, 4).text()
        
        self.selected_format = fmt_id
        # Logic: If video-only and merge checked, append +bestaudio
        if "Video Only" in fmt_note and self.chk_merge.isChecked():
            self.selected_format += "+bestaudio"
            
        self.accept()

class AnalysisWorker(QThread):
    finished = Signal(object) # Returns info dict
    error = Signal(str)
    
    def __init__(self, url, proxy=None):
        super().__init__()
        self.url = url
        self.proxy = proxy
        
    def run(self):
        ydl_opts = {
            'quiet': True,
            'no_color': True
        }
        if self.proxy:
            ydl_opts['proxy'] = self.proxy
            
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                self.finished.emit(info)
        except Exception as e:
            # Clean ANSI codes from error message
            error_msg = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', str(e))
            self.error.emit(error_msg)

class DownloadCancelledException(Exception):
    pass

class DownloadWorker(QThread):
    finished = Signal(str)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, url, path, format_str=None, proxy=None):
        super().__init__()
        self.url = url
        self.path = path
        self.format_str = format_str
        self.proxy = proxy
        self._is_cancelled = False
        self._current_file = None

    def stop(self):
        self._is_cancelled = True

    def run(self):
        ydl_opts = {
            'format': self.format_str if self.format_str else 'best',
            'outtmpl': f'{self.path}/%(title)s.%(ext)s',
            'noplaylist': True,
            'progress_hooks': [self.progress_hook],
            'quiet': True,
            'no_warnings': True,
            'no_color': True
        }
        if self.proxy:
            ydl_opts['proxy'] = self.proxy

        try:
            import yt_dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # We need to check cancellation before starting extraction or download
                if self._is_cancelled:
                    raise DownloadCancelledException()
                
                self.progress.emit("Starting download...")
                info = ydl.extract_info(self.url, download=True)
                title = info.get('title', 'Video')
                self.finished.emit(f"Download Complete: {title}")
        except DownloadCancelledException:
            self._cleanup_partial_file()
            self.error.emit("Download cancelled by user.")
        except Exception as e:
            if "Download cancelled" in str(e):
                self._cleanup_partial_file()
                self.error.emit("Download cancelled by user.")
            else:
                self.error.emit(str(e))

    def _cleanup_partial_file(self):
        if not self._current_file:
            return
            
        # List of potential temp extensions yt-dlp uses
        files_to_check = [
            self._current_file,
            self._current_file + ".part",
            self._current_file + ".ytdl"
        ]
        
        for f_path in files_to_check:
            if os.path.exists(f_path):
                try:
                    os.remove(f_path)
                    print(f"Cleaned up: {f_path}") # Debug info
                except OSError:
                    pass

    def progress_hook(self, d):
        if d.get('filename'):
            self._current_file = d['filename']
            
        if self._is_cancelled:
            # Raising an exception inside the hook is a common way to stop yt-dlp
            raise DownloadCancelledException("Download cancelled")
            
        if d['status'] == 'downloading':
            # Helper to strip ANSI codes
            def clean(s):
                if not s: return ""
                return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', s)

            percent = clean(d.get('_percent_str', '0%')).strip()
            # Try to get total size
            total = clean(d.get('_total_bytes_str') or d.get('_total_bytes_approx_str', 'unknown size'))
            speed = clean(d.get('_speed_str', '0B/s'))
            eta = clean(d.get('_eta_str', '00:00'))
            
            progress_msg = f"{percent} of {total} at {speed} ETA {eta}"
            self.progress.emit(progress_msg)
        elif d['status'] == 'finished':
            self.progress.emit("Finalizing file...")

class ModernTab(QWidget):
    def __init__(self, platform_name, settings_tab=None):
        super().__init__()
        self.platform_name = platform_name
        self.settings_tab = settings_tab
        
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

        # Status Label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.action_btn = QPushButton("Analyze & Download")
        self.action_btn.setMinimumHeight(45)
        self.action_btn.setObjectName("primaryButton")
        self.action_btn.clicked.connect(self.handle_action)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.action_btn, 1)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        self.current_worker = None

    def handle_action(self):
        if self.current_worker and self.current_worker.isRunning():
            self.cancel_download()
        else:
            self.start_analysis()

    def cancel_download(self):
        if self.current_worker:
            self.current_worker.stop()
            self.status_label.setText("Cancelling...")
            self.action_btn.setEnabled(False)

    def extract_clean_url(self, text):
        text = text.strip()
        
        # 1. Try to find a Bilibili URL in the text
        url_match = re.search(r'https?://(?:www\.)?bilibili\.com/video/(BV[a-zA-Z0-9]{10}|av[0-9]+)', text)
        if url_match:
            return url_match.group(0)
            
        # 2. Try to find a Bilibili short link (b23.tv)
        short_match = re.search(r'https?://b23\.tv/[a-zA-Z0-9]+', text)
        if short_match:
            return short_match.group(0)
            
        # 3. Try to find a stand-alone BV or av ID
        id_match = re.search(r'\b(BV[a-zA-Z0-9]{10}|av[0-9]+)\b', text)
        if id_match:
            return f"https://www.bilibili.com/video/{id_match.group(1)}"
            
        # 3. If it looks like a YouTube URL (for the other tab)
        yt_match = re.search(r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', text)
        if yt_match:
            return yt_match.group(0)

        # fallback to the original text if no patterns match
        return text

    def start_analysis(self):
        raw_text = self.url_input.text().strip()
        if not raw_text:
            self.status_label.setText("Please enter a valid URL or Video ID")
            return

        url = self.extract_clean_url(raw_text)
        
        # Get proxy settings
        proxy = None
        if self.settings_tab:
            px = self.settings_tab.proxy_input.text()
            if px: proxy = px

        self.action_btn.setText("Cancel Analysis")
        self.status_label.setText("Analyzing video formats...")
        
        self.current_worker = AnalysisWorker(url, proxy)
        # We need to add stop() to AnalysisWorker too for consistency
        if not hasattr(self.current_worker, 'stop'):
            self.current_worker.stop = lambda: None # Placeholder for now
            
        self.current_worker.finished.connect(self.on_analysis_finished)
        self.current_worker.error.connect(self.on_error)
        self.current_worker.start()

    def on_analysis_finished(self, info):
        self.reset_action_button()
        self.status_label.setText("Select a format to download")
        
        dialog = FormatSelectionDialog(info, self)
        if dialog.exec():
            # User selected something
            format_str = dialog.selected_format
            self.start_real_download(info['webpage_url'], format_str)
        else:
            self.status_label.setText("Download cancelled")

    def start_real_download(self, url, format_str):
        path = "."
        proxy = None
        if self.settings_tab:
            p = self.settings_tab.path_input.text()
            if p: path = p
            px = self.settings_tab.proxy_input.text()
            if px: proxy = px

        self.action_btn.setText("Cancel Download")
        self.action_btn.setEnabled(True)
        self.action_btn.setStyleSheet("background-color: #e74c3c;") # Red for cancel
        
        self.current_worker = DownloadWorker(url, path, format_str, proxy)
        self.current_worker.finished.connect(self.on_finished)
        self.current_worker.error.connect(self.on_error)
        self.current_worker.progress.connect(self.on_progress)
        self.current_worker.start()

    def on_finished(self, msg):
        self.status_label.setText(msg)
        self.reset_action_button()
        self.url_input.clear()

    def on_error(self, err):
        self.status_label.setText(f"Error: {err}")
        self.reset_action_button()

    def on_progress(self, msg):
        self.status_label.setText(msg)

    def reset_action_button(self):
        self.action_btn.setText("Analyze & Download")
        self.action_btn.setEnabled(True)
        self.action_btn.setStyleSheet("") # Restore original from QSS
        self.current_worker = None


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
        
        self.tab_settings = SettingsTab()
        self.tab_bilibili = ModernTab("Bilibili", self.tab_settings)
        self.tab_youtube = ModernTab("YouTube", self.tab_settings)

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
