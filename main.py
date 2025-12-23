import sys
import re
import os
import requests
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QLineEdit, QPushButton, 
                             QLabel, QFileDialog, QFormLayout, QFrame, QDialog,
                             QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
                             QListWidget, QListWidgetItem, QAbstractItemView)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QIcon

class ModernTab(QWidget):
    def __init__(self, platform_name):
        super().__init__()
        self.statusBar().showMessage("Ready")

class FormatSelectionDialog(QDialog):
    def __init__(self, info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Download Options")
        self.resize(1000, 600)
        self.info = info
        self.is_playlist = info.get('is_playlist', False)
        self.selected_urls = []
        self.selected_format_id = None
        
        # Determine strict structure based on type
        if self.is_playlist:
            sample_info = info['sample_info']
            video_title = info.get('title', 'Unknown Playlist')
            description = f"Playlist: {len(info['entries'])} items"
        else:
            sample_info = info
            video_title = info.get('title', 'Unknown Title')
            description = self._format_duration(info.get('duration'))

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Info Header
        info_frame = QFrame()
        info_frame.setObjectName("infoFrame")
        info_layout = QVBoxLayout(info_frame)
        title_label = QLabel(f"{video_title}")
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #00a8ff;")
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #aaa;")
        info_layout.addWidget(title_label)
        info_layout.addWidget(desc_label)
        layout.addWidget(info_frame)

        # Main Content Area (Episodes + Formats)
        content_layout = QHBoxLayout()
        
        # Episode Table (only if playlist)
        if self.is_playlist:
            ep_layout = QVBoxLayout()
            ep_label = QLabel("Select Episodes:")
            self.ep_table = QTableWidget()
            self.ep_table.setColumnCount(3)
            self.ep_table.setHorizontalHeaderLabels(["No.", "Duration", "Title"])
            self.ep_table.verticalHeader().setVisible(False)
            self.ep_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            
            # Set Column Widths
            header = self.ep_table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

            # Populate episodes
            playlist_title = info.get('title', '')
            entries = info.get('entries', [])
            self.ep_table.setRowCount(len(entries))
            
            for i, entry in enumerate(entries):
                full_title = entry.get('title') or entry.get('description') or "Unknown"
                
                # 1. Clean Title (remove main video/playlist title prefix)
                display_title = full_title
                if playlist_title and display_title.startswith(playlist_title):
                    display_title = display_title[len(playlist_title):].strip()
                    if display_title.startswith('-') or display_title.startswith('_'):
                        display_title = display_title[1:].strip()
                
                # 2. Format Duration
                duration = entry.get('duration')
                if duration:
                    mins, secs = divmod(int(duration), 60)
                    hours, mins = divmod(mins, 60)
                    dur_str = f"{hours:02d}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins:02d}:{secs:02d}"
                else:
                    dur_str = "--:--"

                # 3. Create Items
                # 序号 + Checkbox
                idx_item = QTableWidgetItem(str(i + 1))
                idx_item.setCheckState(Qt.CheckState.Checked)
                item_url = entry.get('url') or entry.get('webpage_url')
                idx_item.setData(Qt.ItemDataRole.UserRole, item_url)
                self.ep_table.setItem(i, 0, idx_item)
                
                # Duration
                dur_item = QTableWidgetItem(dur_str)
                dur_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.ep_table.setItem(i, 1, dur_item)
                
                # Title
                self.ep_table.setItem(i, 2, QTableWidgetItem(display_title))
                
            ep_layout.addWidget(ep_label)
            ep_layout.addWidget(self.ep_table)
            
            # Select All/None
            sel_btn_layout = QHBoxLayout()
            btn_all = QPushButton("Select All")
            btn_all.clicked.connect(lambda: self._set_all_checked(True))
            btn_none = QPushButton("Select None")
            btn_none.clicked.connect(lambda: self._set_all_checked(False))
            sel_btn_layout.addWidget(btn_all)
            sel_btn_layout.addWidget(btn_none)
            ep_layout.addLayout(sel_btn_layout)
            
            content_layout.addLayout(ep_layout, stretch=2)

        # Format List
        fmt_layout = QVBoxLayout()
        fmt_label = QLabel("Select Resolution/Format (Based on first video):" if self.is_playlist else "Select Format:")
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Code", "Extension", "Resolution", "Size", "Note"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self._populate_formats(sample_info.get('formats', []))
        
        fmt_layout.addWidget(fmt_label)
        fmt_layout.addWidget(self.table)
        content_layout.addLayout(fmt_layout, stretch=2 if self.is_playlist else 1)
        
        layout.addLayout(content_layout)

        # Options
        self.chk_merge = QCheckBox("Merge Best Audio (Recommended for HD Video)")
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

        # Styles
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

    def _format_duration(self, seconds):
        if not seconds: return "Unknown Duration"
        mins, secs = divmod(int(seconds), 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            return f"Duration: {hours:02d}:{mins:02d}:{secs:02d}"
        return f"Duration: {mins:02d}:{secs:02d}"

    def _populate_formats(self, formats):
        # Group formats by resolution and keep only the largest file for each resolution
        resolution_map = {}
        best_audio = None
        best_audio_bitrate = 0
        
        for fmt in formats:
            # Calculate resolution
            width = fmt.get('width', 0)
            height = fmt.get('height', 0)
            resolution = f"{width}x{height}"
            
            vcodec = fmt.get('vcodec', 'none')
            acodec = fmt.get('acodec', 'none')
            
            # Check if it's an audio-only format
            if vcodec == 'none' and acodec != 'none':
                # Get audio bitrate (higher is better)
                bitrate = fmt.get('abr') or fmt.get('tbr') or fmt.get('asr') or 0
                
                # Keep the best audio format
                if bitrate > best_audio_bitrate:
                    best_audio_bitrate = bitrate
                    best_audio = fmt
            else:
                # Skip invalid video resolutions (but not audio)
                if resolution == "0x0":
                    continue
                
                # Get file size
                sz = fmt.get('filesize') or fmt.get('filesize_approx') or 0
                
                # Check if this resolution already exists
                if resolution in resolution_map:
                    # Compare file sizes and keep the larger one
                    existing_sz = resolution_map[resolution].get('filesize') or resolution_map[resolution].get('filesize_approx') or 0
                    if sz > existing_sz:
                        resolution_map[resolution] = fmt
                else:
                    # Add new resolution to map
                    resolution_map[resolution] = fmt
        
        # Convert map to sorted list (by resolution from highest to lowest)
        sorted_formats = []
        for res, fmt in resolution_map.items():
            sorted_formats.append(fmt)
        
        # Sort by resolution (height descending)
        def get_height(fmt):
            try:
                return int(fmt.get('height', 0))
            except:
                return 0
        
        sorted_formats.sort(key=get_height, reverse=True)
        
        # Add best audio format if found
        if best_audio:
            sorted_formats.append(best_audio)
        
        # Populate the table with filtered formats
        self.table.setRowCount(len(sorted_formats))
        for i, fmt in enumerate(sorted_formats):
            self.table.setItem(i, 0, QTableWidgetItem(str(fmt.get('format_id', ''))))
            self.table.setItem(i, 1, QTableWidgetItem(str(fmt.get('ext', ''))))
            
            # Handle resolution display
            width = fmt.get('width', 0)
            height = fmt.get('height', 0)
            vcodec = fmt.get('vcodec', 'none')
            acodec = fmt.get('acodec', 'none')
            
            if vcodec == 'none' and acodec != 'none':
                # Audio-only format
                res_display = "Audio Only"
            else:
                # Video format
                res_display = f"{width}x{height}"
            
            self.table.setItem(i, 2, QTableWidgetItem(res_display))
            
            # Handle size display
            sz = fmt.get('filesize') or fmt.get('filesize_approx')
            size_str = f"{sz/1024/1024:.1f} MB" if sz else "N/A"
            self.table.setItem(i, 3, QTableWidgetItem(size_str))
            
            # Handle note display
            note = fmt.get('format_note', '')
            if vcodec != 'none' and acodec == 'none': 
                note += " (Video Only)"
            elif vcodec == 'none' and acodec != 'none': 
                # For audio, add bitrate info if available
                bitrate = fmt.get('abr') or fmt.get('tbr') or 0
                if bitrate:
                    note += f" (Audio Only, {bitrate} kbps)"
                else:
                    note += " (Audio Only)"
            
            self.table.setItem(i, 4, QTableWidgetItem(note.strip()))

    def _set_all_checked(self, state):
        for i in range(self.ep_table.rowCount()):
            item = self.ep_table.item(i, 0)
            item.setCheckState(Qt.CheckState.Checked if state else Qt.CheckState.Unchecked)

    def accept_selection(self):
        # 1. Get Format
        selected_fmt_items = self.table.selectedItems()
        if not selected_fmt_items:
            # Fallback to 'best' if nothing selected? Or prevent?
            # Let's enforce selection for now
            return

        row = selected_fmt_items[0].row()
        fmt_id = self.table.item(row, 0).text()
        fmt_note = self.table.item(row, 4).text()
        
        final_fmt = fmt_id
        if "Video Only" in fmt_note and self.chk_merge.isChecked():
            final_fmt += "+bestaudio"
        self.selected_format_id = final_fmt

        # 2. Get URLs
        if self.is_playlist:
            self.selected_urls = []
            for i in range(self.ep_table.rowCount()):
                idx_item = self.ep_table.item(i, 0)
                title_item = self.ep_table.item(i, 2)
                if idx_item.checkState() == Qt.CheckState.Checked:
                    # Format as: P01 Title
                    try:
                        seq_num = int(idx_item.text())
                        pref_title = f"P{seq_num:02d} {title_item.text()}"
                    except:
                        pref_title = f"{idx_item.text()} {title_item.text()}"
                        
                    self.selected_urls.append({
                        'url': idx_item.data(Qt.ItemDataRole.UserRole),
                        'title': pref_title
                    })
        else:
            self.selected_urls = [{
                'url': self.info['webpage_url'],
                'title': self.info.get('title', 'video')
            }]

        if not self.selected_urls:
            return  # Must select at least one

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
            'no_color': True,
        }
        
        # Bilibili requires full extraction to get titles for multi-page videos/playlists properly
        # YouTube needs extract_flat to avoid slowly fetching every video in a playlist
        if 'bilibili' not in self.url and 'b23.tv' not in self.url:
             ydl_opts['extract_flat'] = 'in_playlist'
        
        if self.proxy:
            ydl_opts['proxy'] = self.proxy
            
        try:
            # 1. Try Bilibili Specific API for multi-page videos
            if 'bilibili.com' in self.url or 'b23.tv' in self.url:
                try:
                    effective_url = self.url
                    if 'b23.tv' in effective_url:
                        # Follow redirect for short links
                        try:
                            s = requests.Session()
                            if self.proxy:
                                s.proxies = {'http': self.proxy, 'https': self.proxy}
                            r = s.head(effective_url, allow_redirects=True, timeout=5)
                            effective_url = r.url
                        except:
                            pass
                    
                    bvid_match = re.search(r'(BV[a-zA-Z0-9]{10}|av[0-9]+)', effective_url)
                    if bvid_match:
                        bvid = bvid_match.group(1)
                        print(f"[DEBUG] Extracted BV ID: {bvid}")
                        api_url = 'https://api.bilibili.com/x/web-interface/view'
                        params = {'bvid': bvid} if bvid.startswith('BV') else {'aid': bvid[2:]}
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                            'Referer': 'https://www.bilibili.com/'
                        }
                        
                        s = requests.Session()
                        if self.proxy:
                            s.proxies = {'http': self.proxy, 'https': self.proxy}
                        
                        resp = s.get(api_url, params=params, headers=headers, timeout=10)
                        api_data = resp.json()
                        print(f"[DEBUG] API response code: {api_data.get('code')}")
                        
                        if api_data.get('code') == 0:
                            v_data = api_data['data']
                            pages = v_data.get('pages', [])
                            print(f"[DEBUG] Pages count: {len(pages)}")
                            
                            # Only use API for multi-page videos
                            if len(pages) > 1:
                                print(f"[DEBUG] Multi-page video detected")
                                entries = []
                                for p in pages:
                                    p_num = p.get('page', 1)
                                    p_url = f"https://www.bilibili.com/video/{bvid}?p={p_num}"
                                    entries.append({
                                        'title': p.get('part', f"P{p_num}"),
                                        'duration': p.get('duration'),
                                        'url': p_url,
                                        'webpage_url': p_url,
                                        'id': f"{bvid}_p{p_num}"
                                    })
                                
                                import yt_dlp
                                with yt_dlp.YoutubeDL({'quiet': True, 'no_color': True, 'proxy': self.proxy}) as ydl:
                                    # Get format info from the first page
                                    sample_info = ydl.extract_info(entries[0]['url'], download=False)
                                
                                final_info = {
                                    'is_playlist': True,
                                    'title': v_data.get('title', 'Bilibili Multi-page'),
                                    'entries': entries,
                                    'sample_info': sample_info,
                                    'webpage_url': effective_url
                                }
                                self.finished.emit(final_info)
                                return
                            # For single-page videos, fall through to yt-dlp below
                            print(f"[DEBUG] Single-page video, falling through to yt-dlp")
                        else:
                            print(f"[DEBUG] API returned non-zero code: {api_data.get('code')}, {api_data.get('message')}")
                except Exception as e:
                    print(f"Bilibili API failed: {e}")


            # 2. Default extraction with yt-dlp
            print(f"[DEBUG] Starting yt-dlp extraction for: {self.url}")
            import yt_dlp
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # 1. Initial extraction
                    print(f"[DEBUG] Calling ydl.extract_info...")
                    info = ydl.extract_info(self.url, download=False)
                    print(f"[DEBUG] extract_info completed, type: {info.get('_type') if info else 'None'}")
                    
                    # Check if it is a playlist
                    if info.get('_type') == 'playlist' and 'entries' in info:
                        print(f"[DEBUG] Detected as playlist")
                        entries = list(info.get('entries', []))
                        if not entries:
                             raise Exception("Playlist is empty")
                             
                        # Get sample format from the first entry
                        sample_entry = entries[0]
                        sample_url = sample_entry.get('url') or sample_entry.get('webpage_url')
                        if not sample_url:
                            sample_url = self.url 
                        
                        with yt_dlp.YoutubeDL({'quiet':True, 'no_color':True, 'proxy': self.proxy}) as ydl_sample:
                            sample_info = ydl_sample.extract_info(sample_url, download=False)
                        
                        final_info = {
                            'is_playlist': True,
                            'title': info.get('title', 'Playlist'),
                            'entries': entries,
                            'sample_info': sample_info,
                            'webpage_url': info.get('webpage_url', self.url)
                        }
                        self.finished.emit(final_info)
                    
                    else:
                        # Single video
                        print(f"[DEBUG] Detected as single video")
                        if 'formats' not in info:
                            print(f"[DEBUG] No formats, re-extracting...")
                            # Re-extract fully
                            if 'extract_flat' in ydl_opts:
                                ydl_opts.pop('extract_flat')
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl_full:
                                 info = ydl_full.extract_info(self.url, download=False)
                        else:
                            print(f"[DEBUG] Found {len(info.get('formats', []))} formats")

                        info['is_playlist'] = False
                        print(f"[DEBUG] Emitting single video: {info.get('title')}")
                        self.finished.emit(info)
                        print(f"[DEBUG] Emit completed")
            except Exception as yt_err:
                print(f"[DEBUG] yt-dlp extraction error: {yt_err}")
                raise
                    
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

    def __init__(self, urls, path, format_str=None, proxy=None):
        super().__init__()
        # Ensure urls is a list
        self.urls = urls if isinstance(urls, list) else [urls]
        self.path = path
        self.format_str = format_str
        self.proxy = proxy
        self._is_cancelled = False
        self._current_file = None

    def stop(self):
        self._is_cancelled = True

    def run(self):
        total_videos = len(self.urls)
        
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

        import yt_dlp
        
        for i, item_data in enumerate(self.urls):
            url = item_data['url']
            title = item_data['title']
            
            # Check cancellation at start of each video
            if self._is_cancelled:
                self.error.emit("Download cancelled by user.")
                return

            try:
                msg = f"Processing ({i+1}/{total_videos})..." if total_videos > 1 else "Starting download..."
                self.progress.emit(msg)
                
                if not url:
                    raise Exception("Missing video URL")

                # Update outtmpl with specific title
                current_opts = ydl_opts.copy()
                # Sanitize title for filename
                safe_title = re.sub(r'[\\/*?:"<>|]', "_", title).strip()
                current_opts['outtmpl'] = f'{self.path}/{safe_title}.%(ext)s'

                with yt_dlp.YoutubeDL(current_opts) as ydl:
                    if self._is_cancelled: raise DownloadCancelledException()
                    
                    self.progress.emit(f"Analyzing ({i+1}/{total_videos}): {title}")
                    ydl.download([url])
                    
            except DownloadCancelledException:
                self._cleanup_partial_file()
                self.error.emit("Download cancelled by user.")
                return # Stop entire batch
            except Exception as e:
                # If one fails, maybe continue? Or stop? 
                # Let's emit error but try next? Or stop?
                # Usually users prefer stopping on error or explicit error report.
                # For now, let's report error string but continue if it's not cancellation
                if "Download cancelled" in str(e):
                    self._cleanup_partial_file()
                    self.error.emit("Download cancelled by user.")
                    return

                self.error.emit(f"Error on video {i+1}: {str(e)}")
                # Continue to next video?
                continue
        
        if not self._is_cancelled:
            self.finished.emit("Batch Download Complete!" if total_videos > 1 else "Download Complete!")

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
        # Wait for thread to finish before resetting
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.wait()
        self.reset_action_button()
        self.status_label.setText("Select a format to download")
        
        dialog = FormatSelectionDialog(info, self)
        if dialog.exec():
            # User selected something
            format_str = dialog.selected_format_id
            urls = dialog.selected_urls
            # Get playlist title if applicable
            playlist_title = info.get('title') if info.get('is_playlist') else None
            self.start_real_download(urls, format_str, playlist_title)
        else:
            self.status_label.setText("Download cancelled")

    def start_real_download(self, urls, format_str, playlist_title=None):
        path = "."
        proxy = None
        if self.settings_tab:
            p = self.settings_tab.path_input.text()
            if p: path = p
            px = self.settings_tab.proxy_input.text()
            if px: proxy = px

        # If it's a playlist and multiple items are selected, create a subfolder
        if playlist_title and len(urls) > 1:
            # Sanitize folder name
            safe_title = re.sub(r'[\\/*?:"<>|]', "_", playlist_title).strip()
            # Truncate very long titles to avoid path length issues
            if len(safe_title) > 150:
                safe_title = safe_title[:150]
            
            path = os.path.abspath(os.path.join(path, safe_title))
            if not os.path.exists(path):
                try:
                    os.makedirs(path, exist_ok=True)
                except Exception as e:
                    self.status_label.setText(f"Error creating directory: {e}")
                    # Fallback to original path if fail

        self.action_btn.setText("Cancel Download")
        self.action_btn.setEnabled(True)
        self.action_btn.setStyleSheet("background-color: #e74c3c;") # Red for cancel
        
        self.current_worker = DownloadWorker(urls, path, format_str, proxy)
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
