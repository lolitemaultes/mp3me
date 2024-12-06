import sys
import re
import os
import json
import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass
from urllib.parse import quote_plus, urlparse
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QProgressBar, QFileDialog, QMessageBox, QTabWidget,
    QComboBox, QSpinBox, QCheckBox, QGridLayout, QScrollArea, QFrame, QListWidget,
    QGroupBox, QStyle, QStyleFactory, QToolTip, QSystemTrayIcon, QMenu, QListWidgetItem,
    QDialog, QRadioButton, QButtonGroup, QSlider, QTextEdit, QAction, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer, QSettings, QUrl
from PyQt5.QtGui import QPalette, QColor, QFont, QIcon, QPixmap
import yt_dlp

# Modern style inspired by m3u8me
STYLE_SHEET = """
QMainWindow, QDialog {
    background-color: #1e1e1e;
    color: #ffffff;
}

QLabel {
    color: #ffffff;
}

QPushButton {
    background-color: #2fd492;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
    min-width: 100px;
    margin: 2px;
}

QPushButton:hover {
    background-color: #25a270;
}

QPushButton:pressed {
    background-color: #1c8159;
}

QPushButton:disabled {
    background-color: #383838;
    color: #888888;
}

QLineEdit {
    padding: 8px;
    border-radius: 6px;
    border: 1px solid #3d3d3d;
    background-color: #333333;
    color: white;
    selection-background-color: #4285f4;
    margin: 2px;
}

QProgressBar {
    border: none;
    border-radius: 4px;
    background-color: #333333;
    height: 20px;
    text-align: center;
    color: white;
    margin: 2px;
}

QProgressBar::chunk {
    border-radius: 4px;
    background-color: #2fd492;
}

QGroupBox {
    border: 1px solid #3d3d3d;
    border-radius: 8px;
    margin-top: 1em;
    padding: 15px;
    background-color: #2a2a2a;
    color: white;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QWidget#downloads_widget {
    background-color: #1e1e1e;
}

QListWidget {
    background-color: #2a2a2a;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    color: white;
}

QListWidget::item {
    padding: 8px;
    border-radius: 4px;
    color: white;
}

QListWidget::item:selected {
    background-color: #2fd492;
    color: white;
}

QListWidget::item:hover {
    background-color: #383838;
}

QComboBox {
    padding: 6px;
    border-radius: 6px;
    border: 1px solid #3d3d3d;
    background-color: #333333;
    color: white;
    min-width: 100px;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
    background-color: #2fd492;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}

QCheckBox {
    color: white;
}

QTextEdit {
    background-color: #2a2a2a;
    color: white;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
}

QScrollBar:vertical {
    border: none;
    background-color: #2a2a2a;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #4a4a4a;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}
"""

class PlaylistSelectionDialog(QDialog):
    def __init__(self, playlist_info, parent=None):
        super().__init__(parent)
        self.playlist_info = playlist_info
        self.selected_tracks = []
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Select Playlist Tracks")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Info label with playlist details
        info_layout = QVBoxLayout()
        title_label = QLabel(f"Playlist: {self.playlist_info.get('title', 'Unknown')}")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2fd492; margin-bottom: 10px;")
        
        details_label = QLabel(f"Tracks found: {len(self.playlist_info.get('entries', []))}")
        details_label.setStyleSheet("font-size: 12px; color: #888888;")
        
        info_layout.addWidget(title_label)
        info_layout.addWidget(details_label)
        layout.addLayout(info_layout)
        
        # Track list with custom styling
        list_container = QGroupBox("Tracks")
        list_container.setStyleSheet("""
            QGroupBox {
                background-color: #2a2a2a;
                border-radius: 8px;
                padding: 15px;
                margin-top: 10px;
            }
            QGroupBox::title {
                color: white;
                padding: 5px;
            }
        """)
        list_layout = QVBoxLayout(list_container)
        
        self.track_list = QListWidget()
        self.track_list.setStyleSheet("""
            QListWidget {
                background-color: #333333;
                border: none;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                background-color: #2d2d2d;
                border-radius: 4px;
                margin: 2px;
                padding: 8px;
                min-height: 20px;
            }
            QListWidget::item:selected {
                background-color: #2fd492;
            }
            QListWidget::item:hover {
                background-color: #383838;
            }
        """)
        
        # Process entries
        entries = self.playlist_info.get('entries', [])
        if isinstance(entries, list):
            for i, entry in enumerate(entries, 1):
                if entry:
                    # Get track info
                    title = entry.get('title', '')
                    duration = entry.get('duration')
                    duration_str = self._format_duration(duration) if duration else "Unknown length"
                    
                    # Create item with duration
                    item = QListWidgetItem(f"{i:02d}. {title} ({duration_str})")
                    item.setData(Qt.UserRole, {
                        'url': entry.get('url', '') or entry.get('webpage_url', ''),
                        'title': title
                    })
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Checked)
                    self.track_list.addItem(item)
        
        list_layout.addWidget(self.track_list)
        layout.addWidget(list_container)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all)
        select_all_btn.setMinimumWidth(120)
        
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self.deselect_all)
        deselect_all_btn.setMinimumWidth(120)
        
        download_btn = QPushButton("Download Selected")
        download_btn.clicked.connect(self.accept)
        download_btn.setMinimumWidth(150)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("background-color: #d32f2f;")
        cancel_btn.setMinimumWidth(120)
        
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(deselect_all_btn)
        button_layout.addStretch()
        button_layout.addWidget(download_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)

    def _format_duration(self, duration):
        if not duration:
            return "Unknown"
        mins = int(duration) // 60
        secs = int(duration) % 60
        return f"{mins}:{secs:02d}"

    def select_all(self):
        for i in range(self.track_list.count()):
            self.track_list.item(i).setCheckState(Qt.Checked)

    def deselect_all(self):
        for i in range(self.track_list.count()):
            self.track_list.item(i).setCheckState(Qt.Unchecked)

    def get_selected_tracks(self):
        selected = []
        for i in range(self.track_list.count()):
            item = self.track_list.item(i)
            if item.checkState() == Qt.Checked:
                track_data = item.data(Qt.UserRole)
                selected.append({
                    'url': track_data['url'],
                    'title': track_data['title'],
                    'index': i + 1
                })
        return selected

class SearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_data = None
        self.search_thread = None
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Search Music")
        self.setMinimumWidth(900)
        self.setMinimumHeight(700)
        layout = QVBoxLayout(self)
        
        # Search options
        search_group = QGroupBox("Search")
        search_layout = QVBoxLayout()
        
        # Search type
        type_layout = QHBoxLayout()
        self.type_group = QButtonGroup(self)
        
        for search_type in ["Songs"]:
            radio = QRadioButton(search_type)
            if search_type == "Songs":
                radio.setChecked(True)
            self.type_group.addButton(radio)
            type_layout.addWidget(radio)
        
        search_layout.addLayout(type_layout)
        
        # Search input
        input_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter song name, artist, etc...")
        self.search_input.returnPressed.connect(self.perform_search)
        
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.perform_search)
        
        input_layout.addWidget(self.search_input)
        input_layout.addWidget(self.search_btn)
        
        search_layout.addLayout(input_layout)
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)
        
        # Results
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout()
        
        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self.accept)
        
        results_layout.addWidget(self.results_list)
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        # Download options
        options_group = QGroupBox("Download Options")
        options_layout = QGridLayout()
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(['mp3', 'wav', 'm4a', 'flac'])
        options_layout.addWidget(QLabel("Format:"), 0, 0)
        options_layout.addWidget(self.format_combo, 0, 1)
        
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(['320k', '256k', '192k', '128k'])
        options_layout.addWidget(QLabel("Quality:"), 0, 2)
        options_layout.addWidget(self.quality_combo, 0, 3)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Status label
        self.status_label = QLabel("Enter a search term above")
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.download_btn = QPushButton("Download Selected")
        self.download_btn.clicked.connect(self.accept)
        self.download_btn.setEnabled(False)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("background-color: #d32f2f;")
        
        button_layout.addStretch()
        button_layout.addWidget(self.download_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

    def accept(self):
        selected_items = self.results_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select an item to download")
            return
            
        selected_item = selected_items[0]
        result_data = selected_item.data(Qt.UserRole)
        
        if result_data.get('type') == 'playlist':
            # Handle playlist selection
            try:
                with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                    playlist_info = ydl.extract_info(result_data['url'], download=False)
                    
                dialog = PlaylistSelectionDialog(playlist_info, self)
                if dialog.exec_() == QDialog.Accepted:
                    self.selected_data = {
                        'type': 'playlist',
                        'tracks': dialog.get_selected_tracks(),
                        'title': result_data['title'],
                        'format': self.format_combo.currentText(),
                        'quality': self.quality_combo.currentText()
                    }
                    super().accept()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to fetch playlist: {str(e)}")
        else:
            # Handle single song
            self.selected_data = {
                'type': 'song',
                'url': result_data['url'],
                'title': result_data['title'],
                'format': self.format_combo.currentText(),
                'quality': self.quality_combo.currentText()
            }
            super().accept()

    def perform_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
            
        self.search_btn.setEnabled(False)
        self.status_label.setText("Searching...")
        self.results_list.clear()
        
        search_type = "song"
        for radio in self.type_group.buttons():
            if radio.isChecked():
                search_type = radio.text().lower().rstrip('s')
                break
        
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.stop()
            
        self.search_thread = SearchThread(query, search_type)
        self.search_thread.result_ready.connect(self.add_result)
        self.search_thread.search_complete.connect(self.search_complete)
        self.search_thread.error.connect(self.show_error)
        self.search_thread.start()

    def add_result(self, result):
        item = QListWidgetItem()
        if result.get('type') == 'playlist':
            text = f"🎵 {result['title']} ({result['count']} tracks)"
        else:
            text = f"🎵 {result['title']} - {result['duration']}"
        item.setText(text)
        item.setData(Qt.UserRole, result)
        self.results_list.addItem(item)
        self.download_btn.setEnabled(True)

    def search_complete(self, total_results):
        self.search_btn.setEnabled(True)
        self.status_label.setText(f"Found {total_results} results")
        self.status_label.setStyleSheet("color: #2fd492;")

    def show_error(self, error):
        self.status_label.setText(f"Error: {error}")
        self.status_label.setStyleSheet("color: #ff5252;")
        self.search_btn.setEnabled(True)

class SearchThread(QThread):
    result_ready = pyqtSignal(dict)
    search_complete = pyqtSignal(int)
    error = pyqtSignal(str)
    
    def __init__(self, query, search_type='song'):
        super().__init__()
        self.query = query
        self.search_type = search_type
        self.is_running = True
        
    def stop(self):
        self.is_running = False
        
    def run(self):
        try:
            # Handle direct URLs immediately
            if self.query.startswith(('http://', 'https://')):
                self._handle_direct_url()
                return

            # Different handling for playlist vs song search
            if self.search_type == 'playlist':
                self._search_playlists()
            else:
                self._search_songs()

        except Exception as e:
            self.error.emit(str(e))

    def _search_songs(self):
        """Dedicated song search method"""
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'no_warnings': True,
            'ignoreerrors': True
        }

        search_query = f"ytsearch10:{self.query}"

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = ydl.extract_info(search_query, download=False)
                
                if not results or 'entries' not in results:
                    self.error.emit("No songs found")
                    return

                found_count = 0
                for entry in results['entries']:
                    if not entry or not self.is_running:
                        continue

                    url = entry.get('url') or entry.get('webpage_url', '')
                    if not url:
                        continue

                    # Only process if it's not a playlist
                    if not entry.get('playlist_id') and 'list=' not in url:
                        duration = entry.get('duration')
                        if duration and duration > 0:
                            result = {
                                'title': entry.get('title', 'Unknown'),
                                'url': url,
                                'duration': self._format_duration(duration),
                                'type': 'song',
                                'artist': entry.get('artist', '') or entry.get('uploader', '')
                            }
                            self.result_ready.emit(result)
                            found_count += 1

                if found_count > 0:
                    self.search_complete.emit(found_count)
                else:
                    self.error.emit("No songs found matching your search")

        except Exception as e:
            self.error.emit(f"Search error: {str(e)}")

    def _handle_direct_url(self):
        """Handle direct URL input"""
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': 'in_playlist',
                'no_warnings': True
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.query, download=False)
                
                if info.get('_type') == 'playlist' or 'entries' in info:
                    # It's a playlist
                    entries = info.get('entries', [])
                    valid_entries = [e for e in entries if e]
                    result = {
                        'title': info.get('title', 'Unknown Playlist'),
                        'url': self.query,
                        'type': 'playlist',
                        'count': len(valid_entries),
                        'creator': info.get('uploader', 'Unknown')
                    }
                else:
                    # It's a single song
                    result = {
                        'title': info.get('title', 'Unknown'),
                        'url': self.query,
                        'duration': self._format_duration(info.get('duration')),
                        'type': 'song',
                        'artist': info.get('artist', '') or info.get('uploader', '')
                    }
                self.result_ready.emit(result)
                self.search_complete.emit(1)
                    
        except Exception as e:
            self.error.emit(f"Error processing URL: {str(e)}")

    def _format_duration(self, duration):
        if not duration:
            return "Unknown"
        mins = int(duration) // 60
        secs = int(duration) % 60
        return f"{mins}:{secs:02d}"
            
    def _handle_direct_url(self):
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': 'in_playlist',
                'skip_download': True,
                'no_warnings': True
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.query, download=False)
                
                if 'entries' in info:
                    valid_entries = [e for e in info['entries'] if e]
                    result = {
                        'title': info.get('title', 'Unknown Playlist'),
                        'url': self.query,
                        'type': 'playlist',
                        'count': len(valid_entries),
                        'creator': info.get('uploader', 'Unknown'),
                        'description': info.get('description', '')[:100]
                    }
                else:
                    result = {
                        'title': info.get('title', 'Unknown'),
                        'url': self.query,
                        'duration': self._format_duration(info.get('duration')),
                        'type': 'song',
                        'artist': info.get('artist', '') or info.get('uploader', '')
                    }
                self.result_ready.emit(result)
                self.search_complete.emit(1)
                    
        except Exception as e:
            self.error.emit(f"Error processing URL: {str(e)}")

class DownloadWidget(QFrame):
    def __init__(self, url, title, parent=None, playlist_data=None):
        super().__init__(parent)
        self.url = url
        self.title = title
        self.playlist_data = playlist_data
        self.init_ui()
        
        # Apply shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

        # Set style
        self.setStyleSheet("""
            DownloadWidget {
                background-color: #2d2d2d;
                border-radius: 8px;
                padding: 12px;
                margin: 8px 4px;
            }
        """)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Title and info layout
        info_layout = QVBoxLayout()
        
        # Title with playlist info if applicable
        if self.playlist_data:
            title_text = f"Playlist: {self.playlist_data['title']}"
        else:
            title_text = self.title
            
        self.title_label = QLabel(title_text)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        
        self.status_label = QLabel("Waiting to start...")
        self.status_label.setStyleSheet("color: #888888;")
        
        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.status_label)
        
        # Progress section
        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar, stretch=1)
        
        # Control buttons
        button_layout = QHBoxLayout()
        self.retry_btn = QPushButton("Retry")
        self.retry_btn.setVisible(False)
        self.retry_btn.setFixedWidth(80)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setProperty("cancel", True)
        self.cancel_btn.setFixedWidth(80)
        self.cancel_btn.setStyleSheet("background-color: #d32f2f;")
        
        button_layout.addStretch()
        button_layout.addWidget(self.retry_btn)
        button_layout.addWidget(self.cancel_btn)
        
        # Add all to main layout
        layout.addLayout(info_layout)
        layout.addLayout(progress_layout)
        layout.addLayout(button_layout)

    def update_status(self, status, color="#2fd492"):
        self.status_label.setText(status)
        self.status_label.setStyleSheet(f"color: {color};")

    def update_progress(self, progress):
        self.progress_bar.setValue(int(progress))
        # Update progress bar color based on progress
        if progress < 30:
            color = "#ff5252"
        elif progress < 70:
            color = "#ffd740"
        else:
            color = "#2fd492"
            
        self.progress_bar.setStyleSheet(f"""
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 2px;
            }}
        """)

    def show_error(self, error_msg):
        self.error_details.setVisible(True)
        self.error_details.setText(error_msg)
        self.retry_btn.setVisible(True)

class DownloadThread(QThread):
    progress = pyqtSignal(str, float, str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str, str)
    
    def __init__(self, url, save_path, format_option='mp3', quality='320k', playlist_data=None):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self.format_option = format_option
        self.quality = quality
        self.playlist_data = playlist_data
        self.is_running = True
        self.current_track = 0
        self.total_tracks = 0
        self.current_track_progress = 0

    def progress_hook(self, d):
        """Progress hook for single file downloads"""
        if not self.is_running:
            raise Exception("Download cancelled")
            
        try:
            if d['status'] == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                
                if total:
                    progress = (downloaded / total) * 100
                    speed = d.get('speed', 0)
                    if speed:
                        speed_str = f"{speed/1024/1024:.1f} MB/s"
                        eta = d.get('eta', 0)
                        eta_str = f"{eta} seconds" if eta else "N/A"
                        status = f"Downloading... {speed_str} ETA: {eta_str}"
                    else:
                        status = "Downloading..."
                    
                    self.progress.emit(self.url, progress, status)
                    
            elif d['status'] == 'finished':
                self.progress.emit(self.url, 100, "Processing audio...")
                
        except Exception:
            self.progress.emit(self.url, 0, "Downloading...")
        
    def run(self):
        try:
            format_info = {
                'mp3': {'format': 'mp3', 'quality': self.quality.replace('k', '')},
                'wav': {'format': 'wav'},
                'm4a': {'format': 'm4a', 'quality': '0'},
                'flac': {'format': 'flac'}
            }.get(self.format_option, {'format': 'mp3', 'quality': '320'})

            if self.playlist_data:
                self._handle_playlist_download(format_info)
            else:
                self._handle_single_download(format_info)

        except Exception as e:
            self.error.emit(self.url, str(e))

    def _get_progress_hook(self, track_number, total_tracks):
        def progress_hook(d):
            if not self.is_running:
                raise Exception("Download cancelled")
                
            try:
                if d['status'] == 'downloading':
                    # Calculate progress for current track
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                    
                    if total:
                        self.current_track_progress = (downloaded / total) * 100
                        # Calculate overall progress
                        track_weight = 100.0 / total_tracks
                        overall_progress = ((track_number - 1) * track_weight) + (self.current_track_progress * track_weight / 100)
                        
                        speed = d.get('speed', 0)
                        if speed:
                            speed_str = f"{speed/1024/1024:.1f} MB/s"
                            status = f"Track {track_number}/{total_tracks} • {speed_str}"
                        else:
                            status = f"Track {track_number}/{total_tracks}"
                        
                        self.progress.emit(self.url, overall_progress, status)
                
                elif d['status'] == 'finished':
                    # Track finished downloading, now processing
                    overall_progress = (track_number / total_tracks) * 100
                    self.progress.emit(self.url, overall_progress, f"Processing track {track_number}/{total_tracks}")
                    
            except Exception:
                # If there's an error calculating progress, just show track number
                self.progress.emit(self.url, 
                                 (track_number / total_tracks) * 100,
                                 f"Downloading track {track_number}/{total_tracks}")
                
        return progress_hook

    def _handle_single_download(self, format_info):
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(self.save_path, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': format_info['format'],
                'preferredquality': format_info.get('quality', None),
            }],
            'progress_hooks': [self.progress_hook],  # Add the progress hook here
            'quiet': True,
            'no_warnings': True
        }
    
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self.progress.emit(self.url, 0, "Starting download...")
                ydl.download([self.url])
        
            if self.is_running:
                self.finished.emit(self.url)
        except Exception as e:
            raise Exception(f"Download failed: {str(e)}")
    
    def _handle_playlist_download(self, format_info):
        try:
            # Create playlist directory
            safe_title = "".join(c for c in self.playlist_data['title'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
            playlist_dir = os.path.join(self.save_path, safe_title)
            os.makedirs(playlist_dir, exist_ok=True)
    
            total_tracks = len(self.playlist_data['tracks'])
            self.total_tracks = total_tracks  # Store total tracks count
            failed_tracks = []
    
            # Initial progress update
            self.progress.emit(self.url, 0, f"Starting playlist download (0/{total_tracks})")
    
            for index, track in enumerate(self.playlist_data['tracks'], 1):
                if not self.is_running:
                    raise Exception("Download cancelled")
    
                self.current_track = index  # Update current track number
                track_url = track['url']
    
                # Configure yt-dlp options
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(playlist_dir, f"{index:02d}. %(title)s.%(ext)s"),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': format_info['format'],
                        'preferredquality': format_info.get('quality', None),
                    }],
                    'progress_hooks': [lambda d: self._get_progress_hook(index, total_tracks)(d)],
                    'quiet': True,
                    'no_warnings': True
                }
    
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([track_url])
                except Exception as e:
                    failed_tracks.append((index, str(e)))
                    continue
    
            # Final status update
            if failed_tracks:
                msg = f"Completed {total_tracks - len(failed_tracks)}/{total_tracks} tracks"
                self.progress.emit(self.url, 100, msg)
            else:
                self.progress.emit(self.url, 100, f"Playlist complete ({total_tracks} tracks)")
    
            self.finished.emit(self.url)
    
        except Exception as e:
            raise Exception(f"Playlist download failed: {str(e)}")
            
    def stop(self):
        self.is_running = False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("mp3me")
        self.setMinimumSize(900, 700)
        self.downloads = {}
        self.save_path = None
        self.init_ui()
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Logo container
        logo_container = QWidget()
        logo_container.setObjectName("logo_container")
        logo_container.setFixedHeight(120)
        logo_layout = QHBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 10, 0, 10)
        
        logo_label = QLabel()
        try:
            # First try the direct path
            logo_path = "Resources/mp3me/mp3me.png"
            if not os.path.exists(logo_path):
                # If not found, try the resource path
                logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), logo_path)
                if not os.path.exists(logo_path):
                    # If still not found, try one directory up
                    logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), logo_path)
            
            if os.path.exists(logo_path):
                logo_pixmap = QPixmap(logo_path)
                scaled_pixmap = logo_pixmap.scaled(480, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(scaled_pixmap)
            else:
                raise FileNotFoundError("Logo file not found")
        except Exception as e:
            print(f"Error loading logo: {str(e)}")
            logo_label.setText("MP3ME")
            logo_label.setStyleSheet("font-size: 32px; font-weight: bold; color: #2fd492;")
        
        logo_label.setAlignment(Qt.AlignCenter)
        logo_layout.addStretch()
        logo_layout.addWidget(logo_label)
        logo_layout.addStretch()
        
        layout.addWidget(logo_container)
        
        # URL input section
        url_group = QGroupBox("Quick Download")
        url_layout = QHBoxLayout()
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter URL (video or playlist)")
        self.url_input.returnPressed.connect(self.process_url)
        
        url_download_btn = QPushButton("Download")
        url_download_btn.clicked.connect(self.process_url)
        
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(url_download_btn)
        
        url_group.setLayout(url_layout)
        layout.addWidget(url_group)
        
        # Control buttons
        control_group = QGroupBox()
        button_layout = QHBoxLayout()
        
        search_btn = QPushButton("Search Music")
        search_btn.clicked.connect(self.show_search)
        
        self.start_all_btn = QPushButton("Start All")
        self.start_all_btn.clicked.connect(self.start_all_downloads)
        self.start_all_btn.setEnabled(False)
        
        self.stop_all_btn = QPushButton("Stop All")
        self.stop_all_btn.clicked.connect(self.stop_all_downloads)
        self.stop_all_btn.setEnabled(False)
        
        self.clear_btn = QPushButton("Clear Completed")
        self.clear_btn.clicked.connect(self.clear_completed)
        
        button_layout.addWidget(search_btn)
        button_layout.addWidget(self.start_all_btn)
        button_layout.addWidget(self.stop_all_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addStretch()
        
        control_group.setLayout(button_layout)
        layout.addWidget(control_group)
        
        # Downloads area
        downloads_group = QGroupBox("Downloads")
        downloads_layout = QVBoxLayout()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.downloads_widget = QWidget()
        self.downloads_widget.setObjectName("downloads_widget")  # For styling
        self.downloads_layout = QVBoxLayout(self.downloads_widget)
        self.downloads_layout.addStretch()
        
        scroll.setWidget(self.downloads_widget)
        downloads_layout.addWidget(scroll)
        
        downloads_group.setLayout(downloads_layout)
        layout.addWidget(downloads_group)
        
        # Status bar
        self.statusBar().showMessage("Ready")
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.statusBar().addPermanentWidget(self.progress_bar)

    def process_url(self):
        url = self.url_input.text().strip()
        if not url:
            return
            
        if not url.startswith(('http://', 'https://')):
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid URL")
            return
            
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'skip_download': True,
                'no_warnings': True,
                'extract_flat': 'in_playlist'  # Make sure we get playlist info
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    raise Exception("Could not fetch information")
                    
                # Handle playlist URL
                if 'entries' in info:
                    # Make sure we have valid entries
                    valid_entries = [e for e in info['entries'] if e]
                    if not valid_entries:
                        raise Exception("No valid tracks found in playlist")
                        
                    info['entries'] = valid_entries  # Update entries to only valid ones
                    dialog = PlaylistSelectionDialog(info, self)
                    if dialog.exec_() == QDialog.Accepted:
                        selected_tracks = dialog.get_selected_tracks()
                        if selected_tracks:
                            self.add_download(
                                url,
                                info.get('title', 'Unknown Playlist'),
                                playlist_data={
                                    'title': info.get('title', 'Unknown Playlist'),
                                    'tracks': selected_tracks
                                }
                            )
                # Handle single video URL
                else:
                    self.add_download(url, info.get('title', 'Unknown'))
                    
                self.url_input.clear()
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error processing URL: {str(e)}")

    def show_search(self):
        dialog = SearchDialog(self)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_data:
            if dialog.selected_data['type'] == 'playlist':
                for track in dialog.selected_data['tracks']:
                    self.add_download(
                        track['url'],
                        f"{track['index']}. {track['title']}",
                        format_option=dialog.selected_data['format'],
                        quality=dialog.selected_data['quality'],
                        playlist_data={'title': dialog.selected_data['title']}
                    )
            else:
                self.add_download(
                    dialog.selected_data['url'],
                    dialog.selected_data['title'],
                    format_option=dialog.selected_data['format'],
                    quality=dialog.selected_data['quality']
                )

    def add_download(self, url, title, format_option='mp3', quality='320k', playlist_data=None):
        if url in self.downloads:
            QMessageBox.warning(
                self,
                "Duplicate URL",
                "This URL is already in the download queue!",
                QMessageBox.Ok
            )
            return

        download_widget = DownloadWidget(url, title, playlist_data=playlist_data)
        download_widget.cancel_btn.clicked.connect(lambda: self.remove_download(url))
        download_widget.retry_btn.clicked.connect(lambda: self.retry_download(url))
        
        self.downloads_layout.insertWidget(
            self.downloads_layout.count() - 1,
            download_widget
        )
        
        self.downloads[url] = {
            'widget': download_widget,
            'thread': None,
            'format': format_option,
            'quality': quality,
            'playlist_data': playlist_data
        }

        self.start_all_btn.setEnabled(True)
        self.update_status()

    def start_all_downloads(self):
        if not self.downloads:
            return
            
        if not self.save_path:
            self.save_path = QFileDialog.getExistingDirectory(
                self,
                "Select Save Directory",
                str(Path.home() / 'Music'),
                QFileDialog.ShowDirsOnly
            )
            
            if not self.save_path:
                return

        self.start_all_btn.setEnabled(False)
        self.stop_all_btn.setEnabled(True)
        
        for url in list(self.downloads.keys()):
            if not self.downloads[url]['thread']:
                self.start_download(url)

    def start_download(self, identifier):
        if identifier not in self.downloads:
            return
            
        download = self.downloads[identifier]
        
        if download.get('is_playlist'):
            thread = PlaylistDownloadThread(
                download['tracks'],
                self.save_path,
                identifier,
                download['format'],
                download['quality']
            )
        else:
            thread = DownloadThread(
                identifier,
                self.save_path,
                download['format'],
                download['quality']
            )
        
        thread.progress.connect(lambda u, p, s: self.update_progress(u, p, s))
        thread.finished.connect(self.download_finished)
        thread.error.connect(self.download_error)
        
        download['thread'] = thread
        download['widget'].status_label.setText("Starting download...")
        thread.start()

    def stop_all_downloads(self):
        for download in self.downloads.values():
            if download['thread'] and download['thread'].isRunning():
                download['thread'].stop()
                download['widget'].update_status("Stopped", "#ff5252")
                
        self.stop_all_btn.setEnabled(False)
        self.start_all_btn.setEnabled(True)
        self.update_status()

    def remove_download(self, url):
        if url not in self.downloads:
            return
            
        download = self.downloads[url]
        if download['thread'] and download['thread'].isRunning():
            download['thread'].stop()
            
        download['widget'].deleteLater()
        del self.downloads[url]
        
        if not self.downloads:
            self.start_all_btn.setEnabled(False)
            self.stop_all_btn.setEnabled(False)
            
        self.update_status()

    def retry_download(self, url):
        if url not in self.downloads:
            return
            
        download = self.downloads[url]
        download['widget'].error_details.setVisible(False)
        download['widget'].retry_btn.setVisible(False)
        self.start_download(url)

    def update_progress(self, url, progress, status):
        if url not in self.downloads:
            return
            
        download = self.downloads[url]
        download['widget'].progress_bar.setValue(int(progress))
        download['widget'].update_status(status)
        
        # Update progress bar color based on progress
        if progress < 30:
            color = "#ff5252"  # Red for early progress
        elif progress < 70:
            color = "#ffd740"  # Yellow for mid progress
        else:
            color = "#2fd492"  # Green for near completion
            
        download['widget'].progress_bar.setStyleSheet(
            f"""
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 2px;
            }}
            """
        )
        
        self.update_status()

    def download_finished(self, url):
        if url not in self.downloads:
            return
            
        download = self.downloads[url]
        download['thread'] = None
        download['widget'].progress_bar.setValue(100)
        download['widget'].update_status("Download complete!", "#2fd492")
        
        self.update_status()
        
        if not any(d['thread'] and d['thread'].isRunning() for d in self.downloads.values()):
            self.stop_all_btn.setEnabled(False)
            QMessageBox.information(
                self,
                "Downloads Complete",
                "All downloads have completed successfully!",
                QMessageBox.Ok
            )

    def download_error(self, url, error):
        if url not in self.downloads:
            return
            
        download = self.downloads[url]
        download['thread'] = None
        download['widget'].update_status("Error", "#ff5252")
        download['widget'].show_error(error)
        
        self.update_status()

    def clear_completed(self):
        urls_to_remove = []
        for url, download in self.downloads.items():
            if not download['thread'] or not download['thread'].isRunning():
                urls_to_remove.append(url)
                
        if not urls_to_remove:
            return
            
        for url in urls_to_remove:
            self.remove_download(url)

    def update_status(self):
        total = len(self.downloads)
        active = sum(1 for d in self.downloads.values() if d['thread'] and d['thread'].isRunning())
        completed = sum(1 for d in self.downloads.values() if d['widget'].progress_bar.value() == 100)
        
        self.statusBar().showMessage(
            f"Total: {total} | Active: {active} | Completed: {completed}"
        )
        
        if total > 0:
            progress = sum(d['widget'].progress_bar.value() for d in self.downloads.values()) / total
            self.progress_bar.setValue(int(progress))
        else:
            self.progress_bar.setValue(0)

def main():
    # Enable high DPI support
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE_SHEET)
    
    try:
        window = MainWindow()
        window.show()
        sys.exit(app.exec_())
        
    except Exception as e:
        QMessageBox.critical(
            None,
            "Fatal Error",
            f"An unexpected error occurred:\n\n{str(e)}\n\nThe application will now close.",
            QMessageBox.Ok
        )
        sys.exit(1)

if __name__ == "__main__":
    try:
        # Check for yt-dlp and try to update it
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                      capture_output=True)
    except:
        pass
        
    # Check for FFmpeg
    if not shutil.which('ffmpeg'):
        QMessageBox.critical(
            None,
            "FFmpeg Not Found",
            "FFmpeg is required but not found. Please install FFmpeg to continue.",
            QMessageBox.Ok
        )
        sys.exit(1)
        
    main()
