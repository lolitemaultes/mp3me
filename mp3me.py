#!/usr/bin/env python3
"""
YouTube Music Downloader
A PyQt6 application for searching and downloading music from YouTube Music.
Features:
- Search for artists and releases (albums & singles)
- Download individual songs, full albums, or entire artist discographies
- Display album and artist covers
- Manage download queue with progress

Created by lolitemaultes (Powered by yt-dlp)
"""

import os
import sys
import json
import time
import shutil
import random
import platform
import threading
import requests
import subprocess
import re
import logging
import hashlib
import uuid
import urllib.parse
from typing import List, Dict, Any, Optional
from ytmusicapi import YTMusic
from enum import Enum
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Union, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

# Suppress annoying Qt warnings in terminal
os.environ["QT_LOGGING_RULES"] = "*.debug=false;qt.qpa.*=false"

# PyQt6 imports
from PyQt6.QtCore import (Qt, QSize, QUrl, QThread, pyqtSignal, QObject, QMetaObject, Q_ARG,
                         QRunnable, QThreadPool, pyqtSlot, QTimer, QRect, QByteArray, QBuffer,
                         QEvent, QPoint, QPropertyAnimation, QEasingCurve)
from PyQt6.QtGui import (QIcon, QPixmap, QFont, QColor, QPalette, QImage,
                        QPainter, QBrush, QAction, QCursor, QGuiApplication,
                        QKeySequence, QShortcut, QLinearGradient)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QLabel, QPushButton, QLineEdit,
                            QTabWidget, QScrollArea, QProgressBar, QFileDialog,
                            QComboBox, QSpinBox, QMessageBox, QMenu, QSplitter,
                            QFrame, QGridLayout, QCheckBox, QListWidget,
                            QListWidgetItem, QSlider, QToolTip, QDialog, QGroupBox,
                            QRadioButton, QButtonGroup, QToolButton, QSystemTrayIcon,
                            QSizePolicy, QGraphicsOpacityEffect, QTableWidget,
                            QTableWidgetItem, QHeaderView, QTextEdit, QColorDialog,
                            QWizard, QWizardPage, QStackedWidget, QStyle,
                            QDialogButtonBox)

# Add qtawesome for better icons
try:
    import qtawesome as qta
    QTA_AVAILABLE = True
except ImportError:
    QTA_AVAILABLE = False

# Try to import mutagen - we'll handle its potential absence in the code
try:
    from mutagen.easyid3 import EasyID3
    from mutagen.id3 import ID3, APIC, ID3NoHeaderError, TIT2, TPE1, TALB, TRCK, TDRC, TCON
    from mutagen.flac import FLAC, Picture
    from mutagen.oggvorbis import OggVorbis
    from mutagen.mp4 import MP4, MP4Cover
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

# Constants
APP_NAME = "YouTube Music Downloader"
APP_VERSION = "1.2.0"
DEFAULT_THREADS = 3
DEFAULT_FORMAT = "mp3"
SUPPORTED_FORMATS = ["mp3", "flac", "wav", "ogg", "m4a"]
DEFAULT_ACCENT_COLOR = "#4d8ffd"
THUMBNAIL_SIZE = 150  # Size for album/artist thumbnails
SETTINGS_FILE = "ytmusic_downloader_settings.json"
MAX_CACHE_SIZE_MB = 500  # Maximum size for thumbnail cache in MB
MAX_RETRIES = 3  # Maximum number of retries for network operations
LOG_FILE = "ytmusic_downloader.log"

# Set up logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(APP_NAME)

# Define directory for settings and cache
if platform.system() == "Windows":
    APP_DATA_DIR = os.path.join(os.environ.get("APPDATA", ""), APP_NAME)
else:  # macOS and Linux
    APP_DATA_DIR = os.path.join(str(Path.home()), f".{APP_NAME.lower().replace(' ', '_')}")

# Create app data directory if it doesn't exist
os.makedirs(APP_DATA_DIR, exist_ok=True)
SETTINGS_FILE_PATH = os.path.join(APP_DATA_DIR, SETTINGS_FILE)
CACHE_DIR = os.path.join(APP_DATA_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
RESOURCES_DIR = os.path.join(APP_DATA_DIR, "resources")
os.makedirs(RESOURCES_DIR, exist_ok=True)


class DarkTheme:
    """Class to handle dark theme styling for the application"""

    @staticmethod
    def apply_to(app, accent_color=DEFAULT_ACCENT_COLOR):
        """Apply dark theme to the application"""
        try:
            # Look for custom style file first
            custom_style_path = os.path.join(APP_DATA_DIR, "custom_style.qss")
            style_file = custom_style_path if os.path.exists(custom_style_path) else os.path.join(APP_DATA_DIR, "style.qss")
            
            # Check if style file exists and create it if needed
            if not os.path.exists(style_file):
                DarkTheme._create_default_stylesheet(style_file)

            # Apply the stylesheet
            with open(style_file, "r") as f:
                style = f.read()
                style = DarkTheme._process_style(style, accent_color)
                app.setStyleSheet(style)
                
            logger.info("Dark theme applied successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error applying dark theme: {e}")
            return False

    @staticmethod
    def _process_style(style: str, accent_color: str) -> str:
        """Replace placeholder colors with the selected accent color."""
        base = QColor(accent_color)
        light = base.lighter(120).name()
        dark = base.darker(120).name()
        darker = base.darker(160).name()
        style = style.replace("{ACCENT_COLOR}", accent_color)
        style = style.replace("{ACCENT_LIGHT}", light)
        style = style.replace("{ACCENT_DARK}", dark)
        style = style.replace("{ACCENT_DARKER}", darker)
        return style
    
    @staticmethod
    def _create_default_stylesheet(file_path):
        """Create a default stylesheet if none exists."""
        style = """
        /* Modern Dark Theme */

        QMainWindow, QDialog, QWidget {
            background-color: #121212;
            color: #e0e0e0;
            font-family: "Segoe UI", Arial, sans-serif;
            font-size: 13px;
        }

        QFrame, QGroupBox {
            border: 1px solid #292929;
            border-radius: 8px;
            padding: 8px;
        }

        QTabWidget::pane {
            border: 1px solid #292929;
            padding: 10px;
            border-radius: 8px;
            background-color: #1a1a1a;
        }

        QTabBar::tab {
            background-color: #1e1e1e;
            color: #aaaaaa;
            padding: 8px 16px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }

        QTabBar::tab:selected {
            background-color: #272727;
            color: #ffffff;
            border-bottom: 2px solid {ACCENT_COLOR};
        }

        QPushButton {
            background-color: {ACCENT_COLOR};
            color: #ffffff;
            padding: 6px 12px;
            border-radius: 4px;
        }

        QPushButton:hover {
            background-color: {ACCENT_LIGHT};
        }

        QPushButton:pressed {
            background-color: {ACCENT_DARK};
        }

        QLineEdit, QComboBox, QTextEdit {
            background-color: #1e1e1e;
            color: #e0e0e0;
            border: 1px solid #3c3c3c;
            border-radius: 4px;
            padding: 4px 6px;
            selection-background-color: {ACCENT_COLOR};
        }

        QScrollBar:vertical, QScrollBar:horizontal {
            background: #1e1e1e;
            width: 8px;
            margin: 0px;
        }

        QScrollBar::handle {
            background: #444444;
            border-radius: 4px;
        }

        QScrollBar::handle:hover {
            background: {ACCENT_COLOR};
        }

        QProgressBar {
            background-color: #1e1e1e;
            border-radius: 4px;
            text-align: center;
            color: #ffffff;
        }

        QProgressBar::chunk {
            background-color: {ACCENT_COLOR};
            border-radius: 4px;
        }

        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border: 1px solid #3c3c3c;
            border-radius: 3px;
            background: #1e1e1e;
        }

        QCheckBox::indicator:checked {
            background: {ACCENT_COLOR};
            border-color: {ACCENT_COLOR};
        }

        QTableWidget {
            background-color: #121212;
            alternate-background-color: #1a1a1a;
            border: 1px solid #292929;
        }

        QTableWidget::item:selected {
            background-color: {ACCENT_COLOR};
            color: #ffffff;
        }
        """
        
        with open(file_path, "w") as f:
            f.write(style)
            
        logger.info(f"Created default stylesheet at: {file_path}")


class ContentType(Enum):
    """Enum for the different types of content that can be searched/downloaded."""
    SONG = "song"
    ALBUM = "album"
    ARTIST = "artist"
    PLAYLIST = "playlist"
    SINGLE = "single"
    RELEASE = "release"  # Combined type for albums and singles


@dataclass
class MusicItem:
    """Base class for music content items."""
    id: str
    title: str
    thumbnail_url: str
    type: ContentType
    url: str
    
    def __post_init__(self):
        # Cached thumbnail image
        self._thumbnail = None

    def get_thumbnail(self) -> QPixmap:
        """Get the thumbnail image, downloading it if necessary."""
        if self._thumbnail is None:
            self._thumbnail = download_thumbnail(self.thumbnail_url)
        return self._thumbnail


@dataclass
class Song(MusicItem):
    """Class representing a song."""
    artist: str = ""
    album: str = ""
    duration: str = ""
    track_number: int = 0
    year: str = ""
    genre: str = ""
    video_id: str = ""
    preview_url: str = ""
    selected: bool = True  # For track selection in the UI


@dataclass
class Release(MusicItem):
    """Class representing a release (album or single)."""
    artist: str = ""
    year: str = ""
    track_count: int = 0
    songs: List[Song] = None
    release_type: str = "album"  # 'album' or 'single'
    genre: str = ""
    
    def __post_init__(self):
        super().__post_init__()
        if self.songs is None:
            self.songs = []


@dataclass
class Artist(MusicItem):
    """Class representing an artist."""
    releases: List[Release] = None
    
    def __post_init__(self):
        super().__post_init__()
        if self.releases is None:
            self.releases = []


class DownloadStatus(Enum):
    """Enum for download status."""
    QUEUED = "Queued"
    DOWNLOADING = "Downloading"
    PROCESSING = "Processing Metadata"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    PENDING = "Pending Metadata"


@dataclass
class DownloadItem:
    """Class representing an item in the download queue."""
    item: Union[Song, Release, Artist]
    status: DownloadStatus = DownloadStatus.QUEUED
    progress: float = 0.0
    error_message: str = ""
    output_path: str = ""
    format: str = DEFAULT_FORMAT
    
    # For tracking individual song downloads within releases/artists
    current_song: Optional[Song] = None
    total_songs: int = 1
    completed_songs: int = 0
    quality: str = "high"


class NetworkManager:
    """Manages network connectivity and retries."""
    
    @staticmethod
    def is_connected():
        """Check if there is an active internet connection."""
        try:
            # Try to connect to a reliable server
            requests.get("https://www.google.com", timeout=3)
            return True
        except:
            return False
    
    @staticmethod
    def request_with_retry(url, method="get", max_retries=MAX_RETRIES, **kwargs):
        """Make a request with automatic retries."""
        retry_count = 0
        while retry_count < max_retries:
            try:
                if method.lower() == "post":
                    response = requests.post(url, **kwargs)
                else:
                    response = requests.get(url, **kwargs)
                
                if response.status_code == 200:
                    return response
                
                # If we got a response but it's not 200, increase retry count
                retry_count += 1
                
                # If it's a 429 (Too Many Requests), wait longer
                if response.status_code == 429:
                    time.sleep(5 * retry_count)
                else:
                    time.sleep(1 * retry_count)
                    
            except (requests.RequestException, ConnectionError) as e:
                logger.warning(f"Network error during request: {e}")
                retry_count += 1
                time.sleep(2 * retry_count)
        
        # If we get here, all retries failed
        raise ConnectionError(f"Failed to connect to {url} after {max_retries} retries")


class CacheManager:
    """Manages caching of thumbnails and other data."""
    
    @staticmethod
    def get_cache_size():
        """Get the current size of the cache in MB."""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(CACHE_DIR):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        return total_size / (1024 * 1024)  # Convert to MB
    
    @staticmethod
    def clear_old_cache_files(max_age_days=30):
        """Clear cache files older than max_age_days."""
        current_time = time.time()
        count = 0
        for file_name in os.listdir(CACHE_DIR):
            file_path = os.path.join(CACHE_DIR, file_name)
            if os.path.isfile(file_path):
                # If file is older than max_age_days
                if os.path.getmtime(file_path) < current_time - (max_age_days * 86400):
                    try:
                        os.remove(file_path)
                        count += 1
                    except Exception as e:
                        logger.error(f"Error removing old cache file {file_path}: {e}")
        
        logger.info(f"Removed {count} old cache files")
        return count
    
    @staticmethod
    def clean_cache_if_needed():
        """Clean the cache if it exceeds the maximum size."""
        cache_size = CacheManager.get_cache_size()
        if cache_size > MAX_CACHE_SIZE_MB:
            logger.info(f"Cache size ({cache_size:.2f}MB) exceeds limit, cleaning old files")
            
            # Try clearing old files first
            CacheManager.clear_old_cache_files()
            
            # If still over limit, remove files until under limit
            cache_size = CacheManager.get_cache_size()
            if cache_size > MAX_CACHE_SIZE_MB:
                files = [(f, os.path.getmtime(os.path.join(CACHE_DIR, f))) 
                        for f in os.listdir(CACHE_DIR) if os.path.isfile(os.path.join(CACHE_DIR, f))]
                
                # Sort by modification time (oldest first)
                files.sort(key=lambda x: x[1])
                
                # Delete oldest files until under limit
                for file_name, _ in files:
                    if cache_size <= MAX_CACHE_SIZE_MB:
                        break
                        
                    file_path = os.path.join(CACHE_DIR, file_name)
                    try:
                        file_size = os.path.getsize(file_path) / (1024 * 1024)  # Size in MB
                        os.remove(file_path)
                        cache_size -= file_size
                    except Exception as e:
                        logger.error(f"Error removing cache file {file_path}: {e}")
            
            logger.info(f"Cache cleaned, new size: {CacheManager.get_cache_size():.2f}MB")


class Signals(QObject):
    """Signals for communicating between threads."""
    search_complete = pyqtSignal(list)
    thumbnail_downloaded = pyqtSignal(str, QPixmap)
    download_progress = pyqtSignal(str, float, str)
    download_status_changed = pyqtSignal(str, DownloadStatus, str)
    error = pyqtSignal(str)
    network_status_changed = pyqtSignal(bool)
    metadata_fetched = pyqtSignal(str, object)
    task_completed = pyqtSignal(str, bool, str)


class Settings:
    """Class to manage application settings."""
    
    def __init__(self):
        self.download_dir = str(Path.home() / "Music")
        self.threads = DEFAULT_THREADS
        self.format = DEFAULT_FORMAT
        self.dark_mode = True
        self.audio_quality = "high"
        self.auto_rename = True
        self.use_album_folders = True
        self.normalize_audio = True
        self.max_cache_size = MAX_CACHE_SIZE_MB
        self.notify_on_complete = True
        self.check_duplicates = True
        self.accent_color = DEFAULT_ACCENT_COLOR
        self.preferred_language = "en"
        self.load()
    
    def load(self):
        """Load settings from file."""
        if os.path.exists(SETTINGS_FILE_PATH):
            try:
                with open(SETTINGS_FILE_PATH, 'r') as f:
                    settings = json.load(f)
                    
                self.download_dir = settings.get('download_dir', self.download_dir)
                self.threads = settings.get('threads', self.threads)
                self.format = settings.get('format', self.format)
                self.dark_mode = settings.get('dark_mode', self.dark_mode)
                self.audio_quality = settings.get('audio_quality', self.audio_quality)
                self.auto_rename = settings.get('auto_rename', self.auto_rename)
                self.use_album_folders = settings.get('use_album_folders', self.use_album_folders)
                self.normalize_audio = settings.get('normalize_audio', self.normalize_audio)
                self.max_cache_size = settings.get('max_cache_size', self.max_cache_size)
                self.notify_on_complete = settings.get('notify_on_complete', self.notify_on_complete)
                self.check_duplicates = settings.get('check_duplicates', self.check_duplicates)
                self.accent_color = settings.get('accent_color', self.accent_color)
                self.preferred_language = settings.get('preferred_language', self.preferred_language)
                
                # Validate the download directory
                if not os.path.exists(self.download_dir):
                    # If the specified directory doesn't exist, try to create it or fall back to Downloads
                    try:
                        os.makedirs(self.download_dir, exist_ok=True)
                    except:
                        self.download_dir = str(Path.home() / "Downloads")
                        os.makedirs(self.download_dir, exist_ok=True)
            except Exception as e:
                logger.error(f"Error loading settings: {e}")
                self._use_defaults()
        else:
            self._use_defaults()
    
    def _use_defaults(self):
        """Use default settings if loading fails."""
        # Use ~/Music as default, falling back to ~/Downloads if needed
        music_dir = str(Path.home() / "Music")
        if os.path.exists(music_dir) and os.path.isdir(music_dir):
            self.download_dir = music_dir
        else:
            # Fall back to Downloads
            self.download_dir = str(Path.home() / "Downloads")
            try:
                os.makedirs(self.download_dir, exist_ok=True)
            except:
                # If all else fails, use current directory
                self.download_dir = os.getcwd()
        self.accent_color = DEFAULT_ACCENT_COLOR
    
    def save(self):
        """Save settings to file."""
        settings = {
            'download_dir': self.download_dir,
            'threads': self.threads,
            'format': self.format,
            'dark_mode': self.dark_mode,
            'audio_quality': self.audio_quality,
            'auto_rename': self.auto_rename,
            'use_album_folders': self.use_album_folders,
            'normalize_audio': self.normalize_audio,
            'max_cache_size': self.max_cache_size,
            'notify_on_complete': self.notify_on_complete,
            'check_duplicates': self.check_duplicates,
            'accent_color': self.accent_color,
            'preferred_language': self.preferred_language
        }
        
        try:
            with open(SETTINGS_FILE_PATH, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving settings: {e}")


class DownloadManager:
    """Manages download queue and processes downloads."""
    
    def __init__(self, settings: Settings, signals: Signals):
        self.settings = settings
        self.signals = signals
        self.download_queue = {}  # Dictionary of downloads by ID
        self.active_downloads = set()  # Set of active download IDs
        # Executor used for high level download tasks (artists, releases, etc.)
        self.executor = ThreadPoolExecutor(max_workers=settings.threads)
        # Separate executor for individual song downloads to avoid blocking the
        # main executor when downloading multiple tracks concurrently
        self.song_executor = ThreadPoolExecutor(max_workers=settings.threads)
        self.lock = threading.Lock()  # Lock for thread-safe operations on shared data
        self.running = True  # Flag to control the download manager thread
        
        # Network monitor thread
        self.network_connected = True
        self.network_monitor_thread = threading.Thread(target=self._network_monitor_loop)
        self.network_monitor_thread.daemon = True
        self.network_monitor_thread.start()
        
        # Start the download manager thread
        self.manager_thread = threading.Thread(target=self._download_manager_loop)
        self.manager_thread.daemon = True
        self.manager_thread.start()

    def add_to_queue(self, item: Union[Song, Release, Artist], format_: str = None, quality: str = None) -> str:
        """Add an item to the download queue."""
        with self.lock:
            if format_ is None:
                format_ = self.settings.format
                
            if quality is None:
                quality = self.settings.audio_quality
            
            # Create download item
            download_id = f"{item.type.value}_{item.id}_{int(time.time())}"
            download_item = DownloadItem(
                item=item,
                status=DownloadStatus.QUEUED,
                format=format_,
                quality=quality
            )
            
            # For collections, set status to pending until we have metadata
            if item.type in [ContentType.ARTIST, ContentType.ALBUM, ContentType.RELEASE, ContentType.SINGLE]:
                # Check if we already have the songs list
                has_songs = False
                if item.type == ContentType.ARTIST and item.releases and any(release.songs for release in item.releases):
                    has_songs = True
                elif (item.type == ContentType.ALBUM or item.type == ContentType.RELEASE or item.type == ContentType.SINGLE) and hasattr(item, 'songs') and item.songs:
                    has_songs = True
                
                if not has_songs:
                    download_item.status = DownloadStatus.PENDING
            
            # For artists, albums, count total songs if available
            if item.type == ContentType.ARTIST:
                if item.releases:
                    download_item.total_songs = sum(len(release.songs) if release.songs else 1 for release in item.releases)
            elif item.type in [ContentType.ALBUM, ContentType.RELEASE, ContentType.SINGLE]:
                if item.songs:
                    # Filter for selected songs only
                    selected_songs = [song for song in item.songs if hasattr(song, 'selected') and song.selected]
                    download_item.total_songs = len(selected_songs) if selected_songs else len(item.songs)
            
            # Add to queue
            self.download_queue[download_id] = download_item
            
            # Notify about the new queued item
            self.signals.download_status_changed.emit(download_id, download_item.status, "")
            
            return download_id

    def cancel_download(self, download_id: str):
        """Cancel a download by its ID."""
        with self.lock:
            if download_id in self.download_queue:
                if download_id in self.active_downloads:
                    # Mark as cancelled (the download thread will handle cleanup)
                    self.download_queue[download_id].status = DownloadStatus.CANCELLED
                else:
                    # Remove from queue if not active
                    self.download_queue.pop(download_id)
                    self.signals.download_status_changed.emit(download_id, DownloadStatus.CANCELLED, "")

    def _network_monitor_loop(self):
        """Background thread that monitors network connectivity."""
        while self.running:
            connected = NetworkManager.is_connected()
            if connected != self.network_connected:
                self.network_connected = connected
                self.signals.network_status_changed.emit(connected)
                
                if connected:
                    logger.info("Network connection restored")
                else:
                    logger.warning("Network connection lost")
            
            # Check every 30 seconds
            time.sleep(30)

    def _download_manager_loop(self):
        """Background thread that manages the download queue."""
        while self.running:
            next_downloads = []
            
            # Check if network is connected
            if not self.network_connected:
                time.sleep(5)  # Wait and check again
                continue
                
            # Find queued downloads, up to the max thread count
            with self.lock:
                active_count = len(self.active_downloads)
                available_slots = self.settings.threads - active_count
                
                if available_slots > 0:
                    for download_id, item in self.download_queue.items():
                        if (item.status == DownloadStatus.QUEUED and 
                            download_id not in self.active_downloads and
                            len(next_downloads) < available_slots):
                            next_downloads.append(download_id)
                            self.active_downloads.add(download_id)
                        
                        # Also check for items with pending metadata
                        elif (item.status == DownloadStatus.PENDING and
                              download_id not in self.active_downloads):
                            # Start fetching metadata in a separate thread
                            self._start_metadata_fetch(download_id)
            
            # Start new downloads
            for download_id in next_downloads:
                self._start_download(download_id)
            
            # Sleep to avoid high CPU usage
            time.sleep(0.5)

    def _start_metadata_fetch(self, download_id: str):
        """Start fetching metadata for an item in a separate thread."""
        download_item = self.download_queue[download_id]
        
        # Submit the metadata fetch to the thread pool
        self.executor.submit(
            self._fetch_metadata_thread,
            download_id,
            download_item
        )

    def _fetch_metadata_thread(self, download_id: str, download_item: DownloadItem):
        """Thread function that fetches metadata."""
        try:
            item = download_item.item
            
            # Different fetch logic based on content type
            if item.type in [ContentType.ALBUM, ContentType.RELEASE, ContentType.SINGLE]:
                release_details = fetch_release_details(item.url, item.id)
                if release_details and 'songs' in release_details:
                    item.songs = release_details.get('songs', [])
                    item.year = release_details.get('year', '')
                    item.track_count = len(item.songs)
                    
                    # Set all songs as selected by default
                    for song in item.songs:
                        song.selected = True
                    
                    # Update total songs count
                    with self.lock:
                        if download_id in self.download_queue:
                            self.download_queue[download_id].total_songs = len(item.songs)
                            self.download_queue[download_id].status = DownloadStatus.QUEUED
                
            elif item.type == ContentType.ARTIST:
                artist_details = fetch_artist_details(item.url, item.id)
                if artist_details and 'releases' in artist_details:
                    item.releases = artist_details.get('releases', [])
                    
                    # Count total songs across all releases
                    total_songs = 0
                    for release in item.releases:
                        if release.songs:
                            total_songs += len(release.songs)
                        else:
                            # If we don't have song details, fetch them
                            try:
                                release_details = fetch_release_details(release.url, release.id)
                                if release_details and 'songs' in release_details:
                                    release.songs = release_details.get('songs', [])
                                    release.year = release_details.get('year', '')
                                    release.track_count = len(release.songs)
                                    
                                    # Set all songs as selected by default
                                    for song in release.songs:
                                        song.selected = True
                                        
                                    total_songs += len(release.songs)
                            except Exception:
                                # If we can't get song details, estimate 10 songs per release
                                total_songs += 10
                    
                    # Update total songs count
                    with self.lock:
                        if download_id in self.download_queue:
                            self.download_queue[download_id].total_songs = total_songs
                            self.download_queue[download_id].status = DownloadStatus.QUEUED
            
            # Emit signal with updated metadata
            self.signals.metadata_fetched.emit(download_id, item)
            
        except Exception as e:
            logger.error(f"Error fetching metadata: {e}")
            
            # Update status to FAILED
            with self.lock:
                if download_id in self.download_queue:
                    self.download_queue[download_id].status = DownloadStatus.FAILED
                    self.download_queue[download_id].error_message = str(e)
                    self.signals.download_status_changed.emit(
                        download_id, DownloadStatus.FAILED, str(e)
                    )

    def _start_download(self, download_id: str):
        """Start a download in a separate thread."""
        download_item = self.download_queue[download_id]
        download_item.status = DownloadStatus.DOWNLOADING
        self.signals.download_status_changed.emit(download_id, DownloadStatus.DOWNLOADING, "")
        
        # Submit the download to the thread pool
        self.executor.submit(
            self._download_thread,
            download_id,
            download_item
        )

    def _download_thread(self, download_id: str, download_item: DownloadItem):
        """Thread function that performs the actual download."""
        try:
            item = download_item.item
            
            # Different download logic based on content type
            if item.type == ContentType.SONG:
                self._download_song(download_id, download_item, item)
            elif item.type in [ContentType.ALBUM, ContentType.RELEASE, ContentType.SINGLE]:
                self._download_release(download_id, download_item, item)
            elif item.type == ContentType.ARTIST:
                self._download_artist(download_id, download_item, item)
        
        except Exception as e:
            # Handle any exceptions
            logger.error(f"Download error: {e}")
            with self.lock:
                if download_id in self.download_queue:
                    self.download_queue[download_id].status = DownloadStatus.FAILED
                    self.download_queue[download_id].error_message = str(e)
                    self.signals.download_status_changed.emit(
                        download_id, DownloadStatus.FAILED, str(e)
                    )
        
        finally:
            # Clean up
            with self.lock:
                if download_id in self.active_downloads:
                    self.active_downloads.remove(download_id)

    def _download_song(self, download_id: str, download_item: DownloadItem, song: Song):
        """Download a single song."""
        # Make sure the URL is valid
        if not song.url or "watch?v=song_" in song.url:
            if song.video_id:
                song.url = f"https://music.youtube.com/watch?v={song.video_id}"
            else:
                raise Exception(f"Invalid YouTube URL for {song.title}")

        # Ensure we have high quality album art
        if not song.thumbnail_url or "googleusercontent" in song.thumbnail_url:
            try:
                better = fetch_better_release_artwork(song.album or song.title, song.artist)
                if better:
                    song.thumbnail_url = better
            except Exception:
                pass
        
        # Update current song
        with self.lock:
            if download_id in self.download_queue:
                self.download_queue[download_id].current_song = song
        
        # Create output directory with optional organization
        if self.settings.use_album_folders and song.artist and song.album:
            artist_dir = sanitize_filename(song.artist)
            album_dir = sanitize_filename(song.album)
            output_dir = os.path.join(self.settings.download_dir, artist_dir, album_dir)
        elif self.settings.use_album_folders and song.artist:
            artist_dir = sanitize_filename(song.artist)
            output_dir = os.path.join(self.settings.download_dir, artist_dir, "Singles")
        else:
            output_dir = os.path.join(self.settings.download_dir, "Singles")
            
        os.makedirs(output_dir, exist_ok=True)
        
        # Determine track number and format it properly
        track_num = song.track_number
        if not track_num:
            track_num = 1
        
        # Create filename with optional auto-renaming
        if self.settings.auto_rename:
            # Use "Artist - Title" format
            base_filename = f"{sanitize_filename(song.artist)} - {sanitize_filename(song.title)}"
        else:
            # Just use the title, with optional track prefix
            track_prefix = f"{track_num:02d} - " if track_num else ""
            base_filename = f"{track_prefix}{sanitize_filename(song.title)}"
            
        filename = f"{base_filename}.{download_item.format}"
        output_path = os.path.join(output_dir, filename)
        
        # Set output path in download item
        with self.lock:
            if download_id in self.download_queue:
                self.download_queue[download_id].output_path = output_path
        
        # Check if the file already exists
        duplicate_found = False
        if self.settings.check_duplicates:
            duplicate_found = self._check_file_exists(song, output_dir, download_item.format)
        
        if duplicate_found or os.path.exists(output_path):
            # File already exists, treat as a completed download
            logger.info(f"Skipping download of {song.title} - file already exists")
            with self.lock:
                if download_id in self.download_queue:
                    item_type = self.download_queue[download_id].item.type
                    self.download_queue[download_id].completed_songs += 1
                    if item_type == ContentType.SONG:
                        self.download_queue[download_id].progress = 100.0
                        self.download_queue[download_id].status = DownloadStatus.COMPLETED
                        progress_value = 100.0
                        self.signals.download_status_changed.emit(download_id, DownloadStatus.COMPLETED, "")
                    else:
                        total = self.download_queue[download_id].total_songs
                        completed = self.download_queue[download_id].completed_songs
                        progress_value = (completed / total) * 100 if total else 0
                        self.download_queue[download_id].progress = progress_value
                    self.signals.download_progress.emit(download_id, progress_value, f"Already exists: {song.title}")
            return output_path
        
        # Check for cancellation
        with self.lock:
            if (download_id in self.download_queue and 
                self.download_queue[download_id].status == DownloadStatus.CANCELLED):
                self.signals.download_status_changed.emit(download_id, DownloadStatus.CANCELLED, "")
                return None
        
        # Download the song using yt-dlp
        yt_dlp_format = get_format_string(download_item.format, download_item.quality)
        
        # Before starting the download, ensure output directory exists
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
        except Exception as e:
            error_msg = f"Failed to create output directory: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

        # Create yt-dlp command with parameters for studio quality
        python_exe = sys.executable
        cmd = [
            python_exe,
            "-m",
            "yt_dlp",
            "-f", yt_dlp_format,
            "-o", output_path,
            "--extract-audio",
            "--audio-format", download_item.format,
            "--audio-quality", "0",
            "--embed-thumbnail",
            "--add-metadata",
            "--no-playlist", 
            "--ignore-errors",
            "--no-warnings",
            "--retries", "10",
            "--fragment-retries", "10",
            "--prefer-insecure",
            "--force-ipv4",
            "--throttled-rate", "100K",
            "--no-check-certificate",
        ]
        
        # Add additional parameters for better audio quality
        if download_item.format in ["mp3", "m4a"]:
            cmd.extend([
                "--postprocessor-args", "-ar 44100 -ac 2"
            ])
        
        # For FLAC, ensure best possible quality
        if download_item.format == "flac":
            cmd.extend([
                "--postprocessor-args", "-compression_level 12 -sample_fmt s16"
            ])
            
        # Add song URL
        cmd.append(song.url)
        
        # Print the command for debugging
        logger.debug(f"Running yt-dlp command: {' '.join(cmd)}")
        
        # Execute yt-dlp command with full Python path
        try:
            # Use a temporary directory for intermediate files to prevent corruption
            temp_dir = os.path.join(CACHE_DIR, f"temp_{uuid.uuid4().hex}")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Set working directory to temp
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                cwd=temp_dir
            )
            
            # Process output to track progress
            for line in process.stdout:
                # Print for debugging
                logger.debug(f"yt-dlp output: {line.strip()}")
                
                # Check for download percentage progress
                if '[download]' in line and '%' in line:
                    try:
                        progress_str = line.split('[download]')[1].split('%')[0].strip()
                        progress = float(progress_str)
                        
                        with self.lock:
                            if download_id in self.download_queue:
                                self.download_queue[download_id].progress = progress
                                self.signals.download_progress.emit(
                                    download_id, progress, f"Downloading: {song.title}"
                                )
                    except (ValueError, IndexError):
                        pass  # Ignore lines that don't contain progress info
                
                # Check for cancellation during download
                with self.lock:
                    if (download_id in self.download_queue and 
                        self.download_queue[download_id].status == DownloadStatus.CANCELLED):
                        process.terminate()
                        self.signals.download_status_changed.emit(download_id, DownloadStatus.CANCELLED, "")
                        return None
            
            # Wait for process to complete
            process.wait()
            
            # Check return code
            if process.returncode != 0:
                logger.error(f"yt-dlp error: return code {process.returncode}")
                if not os.path.exists(output_path):
                    # Try to get error details from the output
                    error_details = "Unknown error"
                    try:
                        # Try to parse error message from yt-dlp output
                        error_lines = []
                        with open(os.path.join(temp_dir, "log.txt"), 'r') as log_file:
                            error_lines = log_file.readlines()
                        if error_lines:
                            error_details = error_lines[-1].strip()
                    except:
                        pass
                    
                    raise Exception(f"yt-dlp error: return code {process.returncode} - {error_details}")
                # If file exists despite error code, continue
                logger.warning("File was created despite error, continuing...")
            
            # Clean up temp directory
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
                
        except Exception as e:
            error_msg = f"Download failed: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # Update metadata if the file was downloaded successfully
        if os.path.exists(output_path):
            try:
                with self.lock:
                    if download_id in self.download_queue:
                        self.download_queue[download_id].status = DownloadStatus.PROCESSING
                        self.signals.download_status_changed.emit(
                            download_id, DownloadStatus.PROCESSING, ""
                        )
                
                # Download thumbnail for embedding if needed
                thumbnail = download_thumbnail(song.thumbnail_url)
                if thumbnail:
                    thumbnail_data = save_pixmap_to_bytes(thumbnail)
                    
                    # Add metadata using mutagen if available
                    if MUTAGEN_AVAILABLE:
                        add_metadata(
                            output_path,
                            song.title,
                            song.artist,
                            song.album,
                            song.track_number,
                            song.year,
                            song.genre,
                            thumbnail_data
                        )
            except Exception as e:
                logger.warning(f"Metadata error (non-fatal): {str(e)}")
        
        # Mark as completed
        with self.lock:
            if download_id in self.download_queue:
                item_type = self.download_queue[download_id].item.type
                self.download_queue[download_id].completed_songs += 1

                if item_type == ContentType.SONG:
                    # Single track download
                    self.download_queue[download_id].progress = 100.0
                    self.download_queue[download_id].status = DownloadStatus.COMPLETED
                    self.signals.download_status_changed.emit(
                        download_id, DownloadStatus.COMPLETED, ""
                    )
                    progress_value = 100.0
                else:
                    total = self.download_queue[download_id].total_songs
                    completed = self.download_queue[download_id].completed_songs
                    progress_value = (completed / total) * 100 if total else 0
                    self.download_queue[download_id].progress = progress_value

                # Update progress message
                self.signals.download_progress.emit(
                    download_id, progress_value, f"Completed: {song.title}"
                )
        
        return output_path

    def _check_file_exists(self, song: Song, directory: str, format_: str) -> bool:
        """
        Check if a song already exists in the directory.
        Uses more flexible matching to detect duplicates.
        """
        # Don't check if the setting is disabled
        if not self.settings.check_duplicates:
            return False
            
        # Skip if no title or artist
        if not song.title or not song.artist:
            return False
            
        try:
            # Clean up the song title and artist for comparison
            title_clean = song.title.lower().strip()
            artist_clean = song.artist.lower().strip()
            
            # Remove common words and characters that might differ in filenames
            for char in ['(', ')', '[', ']', '{', '}', '-', '_', '.', ',', '\'', '"']:
                title_clean = title_clean.replace(char, ' ')
                artist_clean = artist_clean.replace(char, ' ')
                
            # Remove common extra words
            for word in ['official', 'video', 'audio', 'lyrics', 'ft', 'feat', 'remix', 'version']:
                title_clean = title_clean.replace(f" {word} ", ' ')
                title_clean = title_clean.replace(f" {word}.", ' ')
                
            # Split into words and remove common words
            title_words = [w for w in title_clean.split() if len(w) > 1]
            artist_words = [w for w in artist_clean.split() if len(w) > 1]
            
            # Get all files in the directory with the same extension
            for filename in os.listdir(directory):
                if filename.lower().endswith(f".{format_.lower()}"):
                    # Clean up the filename
                    file_clean = filename.lower().strip()
                    
                    # Remove extension
                    file_clean = file_clean[:-len(f".{format_.lower()}")]
                    
                    # Remove common characters
                    for char in ['(', ')', '[', ']', '{', '}', '-', '_', '.', ',', '\'', '"']:
                        file_clean = file_clean.replace(char, ' ')
                    
                    # Remove common extra words
                    for word in ['official', 'video', 'audio', 'lyrics', 'ft', 'feat', 'remix', 'version']:
                        file_clean = file_clean.replace(f" {word} ", ' ')
                        file_clean = file_clean.replace(f" {word}.", ' ')
                    
                    # Check if both title and artist are in the filename
                    title_match = all(word in file_clean for word in title_words)
                    artist_match = all(word in file_clean for word in artist_words)
                    
                    if title_match and artist_match:
                        logger.info(f"Duplicate found: {filename} matches {song.artist} - {song.title}")
                        return True
            
            return False
        
        except Exception as e:
            logger.error(f"Error checking for duplicates: {str(e)}")
            return False

    def _download_release(self, download_id: str, download_item: DownloadItem, release: Release):
        """Download a release (album or single)."""
        # Create output directory
        artist_dir = sanitize_filename(release.artist)
        release_dir = sanitize_filename(release.title)
        
        output_dir = os.path.join(self.settings.download_dir, artist_dir, release_dir)
        os.makedirs(output_dir, exist_ok=True)
        
        # Set output path in download item
        with self.lock:
            if download_id in self.download_queue:
                self.download_queue[download_id].output_path = output_dir
        
        # If we don't have the songs list yet, fetch release details
        if not release.songs or len(release.songs) == 0:
            try:
                # Fetch release details
                release_details = fetch_release_details(release.url, release.id)
                
                # Try to get better release artwork
                better_cover = fetch_better_release_artwork(release.title, release.artist)
                if better_cover:
                    release.thumbnail_url = better_cover
                    
                # Process songs...
                if release_details and 'songs' in release_details:
                    release.songs = release_details.get('songs', [])
                    
                    # Set all songs as selected by default
                    for song in release.songs:
                        song.selected = True
                    
                    # Update all songs to use the same high-quality album art
                    for song in release.songs:
                        song.thumbnail_url = release.thumbnail_url
                    
                    # Update total songs count
                    with self.lock:
                        if download_id in self.download_queue:
                            self.download_queue[download_id].total_songs = len(release.songs)
                else:
                    logger.warning(f"No songs found in release details for: {release.title}")
                    raise Exception("No songs found in release details")
                    
            except Exception as e:
                error_msg = f"Failed to fetch release details: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg)
        
        # Check if we have songs to download
        if not release.songs or len(release.songs) == 0:
            error_msg = f"No songs found in release: {release.title}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # Get only selected songs
        selected_songs = [song for song in release.songs if hasattr(song, 'selected') and song.selected]
        
        # If no songs are selected, default to all
        if not selected_songs:
            selected_songs = release.songs
        
        # Download each song using a separate executor to allow concurrency
        success_count = 0
        error_messages = []
        futures = {}

        for song in selected_songs:
            # Check for cancellation
            with self.lock:
                if (download_id in self.download_queue and
                    self.download_queue[download_id].status == DownloadStatus.CANCELLED):
                    self.signals.download_status_changed.emit(download_id, DownloadStatus.CANCELLED, "")
                    return

            # Ensure song has correct metadata
            if not song.album:
                song.album = release.title
            if not song.artist:
                song.artist = release.artist
            if not song.year:
                song.year = release.year

            # Fix placeholder URLs
            if "watch?v=song_" in song.url:
                if song.video_id:
                    song.url = f"https://music.youtube.com/watch?v={song.video_id}"
                else:
                    logger.warning(f"Skipping track with invalid URL: {song.title}")
                    continue

            with self.lock:
                if download_id in self.download_queue:
                    self.download_queue[download_id].current_song = song
                    completed = self.download_queue[download_id].completed_songs
                    total = self.download_queue[download_id].total_songs
                    overall_progress = (completed / total) * 100 if total > 0 else 0
                    self.signals.download_progress.emit(
                        download_id, overall_progress,
                        f"Downloading {completed+1}/{total}: {song.title}"
                    )

            logger.info(f"Downloading song: {song.title} (URL: {song.url})")
            futures[self.song_executor.submit(self._download_song, download_id, download_item, song)] = song

        for future in as_completed(futures):
            song = futures[future]
            try:
                output_path = future.result()
                if output_path:
                    success_count += 1
            except Exception as e:
                error_msg = f"Error downloading {song.title}: {str(e)}"
                logger.error(error_msg)
                error_messages.append(error_msg)
        
        # Update status based on results
        with self.lock:
            if download_id in self.download_queue:
                if success_count == 0:
                    self.download_queue[download_id].status = DownloadStatus.FAILED
                    self.download_queue[download_id].error_message = "\n".join(error_messages)
                    self.signals.download_status_changed.emit(
                        download_id, DownloadStatus.FAILED, 
                        f"Failed to download release: {release.title}"
                    )
                else:
                    self.download_queue[download_id].status = DownloadStatus.COMPLETED
                    self.signals.download_status_changed.emit(
                        download_id, DownloadStatus.COMPLETED, 
                        f"Downloaded {success_count}/{len(selected_songs)} songs"
                    )

    def _download_artist(self, download_id: str, download_item: DownloadItem, artist: Artist):
        """Download an artist's entire discography."""
        # Create output directory
        artist_dir = sanitize_filename(artist.title)
        output_dir = os.path.join(self.settings.download_dir, artist_dir)
        os.makedirs(output_dir, exist_ok=True)
        
        # Set output path in download item
        with self.lock:
            if download_id in self.download_queue:
                self.download_queue[download_id].output_path = output_dir
        
        # If we don't have the releases list yet, fetch artist details
        if not artist.releases or len(artist.releases) == 0:
            try:
                # Update status
                with self.lock:
                    if download_id in self.download_queue:
                        self.signals.download_progress.emit(
                            download_id, 0, f"Fetching artist details: {artist.title}"
                        )
                
                # Fetch artist details
                artist_details = fetch_artist_details(artist.url, artist.id)
                if artist_details and 'releases' in artist_details:
                    artist.releases = artist_details.get('releases', [])
                    
                    # Count total songs across all releases
                    total_songs = 0
                    for release in artist.releases:
                        if release.songs:
                            total_songs += len(release.songs)
                        else:
                            # If we don't have song details, fetch them
                            try:
                                release_details = fetch_release_details(release.url, release.id)
                                if release_details and 'songs' in release_details:
                                    release.songs = release_details.get('songs', [])
                                    release.year = release_details.get('year', '')
                                    release.track_count = len(release.songs)
                                    
                                    # Set all songs as selected by default
                                    for song in release.songs:
                                        song.selected = True
                                        
                                    total_songs += len(release.songs)
                            except:
                                # If we can't get song details, estimate 10 songs per release
                                total_songs += 10
                    
                    # Update total songs count
                    with self.lock:
                        if download_id in self.download_queue:
                            self.download_queue[download_id].total_songs = total_songs
                            self.download_queue[download_id].status = DownloadStatus.QUEUED
                
            except Exception as e:
                raise Exception(f"Failed to fetch artist details: {str(e)}")
        
        # Check if we have releases to download
        if not artist.releases or len(artist.releases) == 0:
            raise Exception(f"No releases found for artist: {artist.title}")
        
        # Download each release
        success_count = 0
        failed_releases = []
        
        for release in artist.releases:
            # Check for cancellation
            with self.lock:
                if (download_id in self.download_queue and 
                    self.download_queue[download_id].status == DownloadStatus.CANCELLED):
                    self.signals.download_status_changed.emit(download_id, DownloadStatus.CANCELLED, "")
                    return
            
            try:
                # Update status
                with self.lock:
                    if download_id in self.download_queue:
                        # Calculate overall progress
                        completed = self.download_queue[download_id].completed_songs
                        total = self.download_queue[download_id].total_songs
                        overall_progress = (completed / total) * 100 if total > 0 else 0
                        self.signals.download_progress.emit(
                            download_id, overall_progress, 
                            f"Downloading release {success_count+1}/{len(artist.releases)}: {release.title}"
                        )
                
                # Download the release
                self._download_release(download_id, download_item, release)
                success_count += 1
            
            except Exception as e:
                failed_releases.append(f"{release.title}: {str(e)}")
                continue
        
        # Update status based on results
        with self.lock:
            if download_id in self.download_queue:
                if success_count == 0:
                    self.download_queue[download_id].status = DownloadStatus.FAILED
                    self.download_queue[download_id].error_message = "\n".join(failed_releases)
                    self.signals.download_status_changed.emit(
                        download_id, DownloadStatus.FAILED, 
                        f"Failed to download any releases for: {artist.title}"
                    )
                else:
                    self.download_queue[download_id].status = DownloadStatus.COMPLETED
                    self.signals.download_status_changed.emit(
                        download_id, DownloadStatus.COMPLETED, 
                        f"Downloaded {success_count}/{len(artist.releases)} releases"
                    )

    def shutdown(self):
        """Shut down the download manager."""
        self.running = False
        # Cancel all active downloads
        with self.lock:
            for download_id in list(self.active_downloads):
                self.cancel_download(download_id)
        
        # Shutdown executors
        self.executor.shutdown(wait=False)
        self.song_executor.shutdown(wait=False)
        
        # Wait for manager thread to exit
        if self.manager_thread.is_alive():
            self.manager_thread.join(timeout=1.0)
        
        if self.network_monitor_thread.is_alive():
            self.network_monitor_thread.join(timeout=1.0)


class SearchWorker(QRunnable):
    """Worker for performing asynchronous YouTube Music searches."""
    
    def __init__(self, query: str, signals: Signals):
        super().__init__()
        self.query = query
        self.signals = signals
    
    @pyqtSlot()
    def run(self):
        """Perform the search."""
        try:
            # Create a task ID for this search
            task_id = f"search_{int(time.time())}"
            
            # Run the search
            results = search_youtube_music(self.query)
            
            # Emit the results
            self.signals.search_complete.emit(results)
            self.signals.task_completed.emit(task_id, True, f"Found {len(results)} results")
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            self.signals.error.emit(f"Search error: {str(e)}")
            self.signals.task_completed.emit("search", False, f"Search failed: {str(e)}")


class LoadingSpinner(QLabel):
    """Widget that shows an animated loading spinner."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dots_count = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_dots)
        self.timer.start(500)  # Update every 500 ms
        self._update_dots()
        
    def _update_dots(self):
        self.dots_count = (self.dots_count + 1) % 4
        dots = "." * self.dots_count
        self.setText(f"Loading{dots}")
        
    def showEvent(self, event):
        self.timer.start()
        super().showEvent(event)
        
    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)


class FeedbackMessage(QLabel):
    """Widget for showing temporary feedback messages."""
    
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hide()
        
        # Style based on type
        self.setStyleSheet("""
            #infoMessage {
                background-color: {ACCENT_COLOR};
                color: #ffffff;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            #errorMessage {
                background-color: #F44336;
                color: #ffffff;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            #warningMessage {
                background-color: #FF9800;
                color: #ffffff;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            #successMessage {
                background-color: #4CAF50;
                color: #ffffff;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
        """)
        
        # Set up animation
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0)
        self.setGraphicsEffect(self.opacity_effect)
        
        self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(300)
        self.fade_in_animation.setStartValue(0)
        self.fade_in_animation.setEndValue(1)
        self.fade_in_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self.fade_out_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out_animation.setDuration(300)
        self.fade_out_animation.setStartValue(1)
        self.fade_out_animation.setEndValue(0)
        self.fade_out_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self.fade_out_animation.finished.connect(self.hide)
        
        # Timer for auto-hide
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.start_fade_out)
    
    def show_message(self, message, message_type=INFO, duration=3000):
        """Show a message with specified type and duration."""
        # Set object name for style
        self.setObjectName(f"{message_type}Message")
        
        # Set text and show
        self.setText(message)
        self.adjustSize()
        self.show()
        
        # Start fade in
        self.fade_in_animation.start()
        
        # Set timer for auto-hide
        self.timer.start(duration)
    
    def start_fade_out(self):
        """Start the fade out animation."""
        self.fade_out_animation.start()


class TrackSelectionDialog(QDialog):
    """Dialog for selecting which tracks to download from a release."""
    
    def __init__(self, release, parent=None):
        super().__init__(parent)
        self.release = release
        self.setWindowTitle(f"Select Tracks to Download - {release.title}")
        self.setMinimumSize(850, 650)  # Larger minimum size for better usability
        
        # Apply the same style as the main window
        if hasattr(parent, 'settings') and parent.settings.dark_mode:
            self.setStyleSheet("""
                QDialog {
                    background-color: #121212;
                    color: #ffffff;
                }
            """)
        
        # Main layout with proper spacing
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(20)
        
        # ==================
        # Top section with album info
        # ==================
        top_section = QWidget()
        top_section.setObjectName("albumInfoSection")
        top_section.setStyleSheet("""
            #albumInfoSection {
                background-color: #1a1a1a;
                border-radius: 15px;
                padding: 5px;
            }
        """)
        top_layout = QHBoxLayout(top_section)
        top_layout.setContentsMargins(20, 20, 20, 20)
        top_layout.setSpacing(20)
        
        # Album artwork
        artwork_frame = QFrame()
        artwork_frame.setObjectName("artworkFrame")
        artwork_frame.setStyleSheet("""
            #artworkFrame {
                background-color: #242424;
                border-radius: 10px;
                padding: 5px;
            }
        """)
        artwork_frame.setFixedSize(150, 150)
        artwork_layout = QVBoxLayout(artwork_frame)
        artwork_layout.setContentsMargins(0, 0, 0, 0)
        
        # Album cover
        cover_label = QLabel()
        cover_label.setFixedSize(140, 140)
        cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_label.setStyleSheet("border-radius: 5px;")
        
        thumbnail = release.get_thumbnail()
        if thumbnail and not thumbnail.isNull():
            scaled_thumbnail = thumbnail.scaled(
                140, 140,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            cover_label.setPixmap(scaled_thumbnail)
        else:
            # Use a placeholder with icon if QTA is available
            if QTA_AVAILABLE:
                icon = qta.icon('fa5s.music', color='white')
                cover_label.setPixmap(icon.pixmap(80, 80))
            else:
                # Text fallback
                cover_label.setText("No Image")
        
        artwork_layout.addWidget(cover_label)
        top_layout.addWidget(artwork_frame)
        
        # Album info
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(10)
        
        # Title
        title_label = QLabel(release.title)
        title_label.setObjectName("albumTitle")
        title_label.setStyleSheet("""
            #albumTitle {
                font-size: 24px;
                font-weight: bold;
                color: #ffffff;
            }
        """)
        info_layout.addWidget(title_label)
        
        # Artist
        artist_label = QLabel(release.artist)
        artist_label.setObjectName("albumArtist")
        artist_label.setStyleSheet("""
            #albumArtist {
                font-size: 18px;
                color: #cccccc;
            }
        """)
        info_layout.addWidget(artist_label)
        
        # Details with bullet points
        details_widget = QWidget()
        details_layout = QHBoxLayout(details_widget)
        details_layout.setContentsMargins(0, 10, 0, 0)
        details_layout.setSpacing(15)
        
        details = []
        
        # Year
        if release.year:
            year_label = QLabel(f"<b>Year:</b> {release.year}")
            year_label.setStyleSheet("color: #aaaaaa;")
            details_layout.addWidget(year_label)
            
            # Add a bullet point
            if len(details) < 3:  # Don't add bullet after last item
                bullet = QLabel("•")
                bullet.setStyleSheet("color: #555555;")
                details_layout.addWidget(bullet)
        
        # Type
        type_text = "Album" if release.release_type == "album" else "Single"
        type_label = QLabel(f"<b>Type:</b> {type_text}")
        type_label.setStyleSheet("color: #aaaaaa;")
        details_layout.addWidget(type_label)
        
        # Add a bullet point
        bullet = QLabel("•")
        bullet.setStyleSheet("color: #555555;")
        details_layout.addWidget(bullet)
        
        # Tracks
        if release.track_count:
            tracks_text = "track" if release.track_count == 1 else "tracks"
            tracks_label = QLabel(f"<b>Tracks:</b> {release.track_count} {tracks_text}")
            tracks_label.setStyleSheet("color: #aaaaaa;")
            details_layout.addWidget(tracks_label)
        
        details_layout.addStretch(1)
        info_layout.addWidget(details_widget)
        
        info_layout.addStretch(1)
        top_layout.addWidget(info_widget, 1)
        
        main_layout.addWidget(top_section)
        
        # ==================
        # Tracks section
        # ==================
        tracks_section = QWidget()
        tracks_layout = QVBoxLayout(tracks_section)
        tracks_layout.setContentsMargins(0, 0, 0, 0)
        tracks_layout.setSpacing(15)
        
        # Section header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 0, 10, 0)
        
        tracks_header = QLabel("Select Tracks to Download")
        tracks_header.setObjectName("sectionHeader")
        tracks_header.setStyleSheet("""
            #sectionHeader {
                font-size: 18px;
                font-weight: bold;
                color: #ffffff;
            }
        """)
        header_layout.addWidget(tracks_header)
        
        # Selection buttons
        selection_layout = QHBoxLayout()
        selection_layout.setSpacing(10)
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.setObjectName("selectAllBtn")
        select_all_btn.setFixedWidth(100)
        select_all_btn.clicked.connect(self.select_all_tracks)
        if QTA_AVAILABLE:
            select_all_btn.setIcon(qta.icon('fa5s.check-square', color='white'))
        
        select_none_btn = QPushButton("Select None")
        select_none_btn.setObjectName("selectNoneBtn")
        select_none_btn.setFixedWidth(100)
        select_none_btn.clicked.connect(self.select_no_tracks)
        if QTA_AVAILABLE:
            select_none_btn.setIcon(qta.icon('fa5s.square', color='white'))
        
        selection_layout.addWidget(select_all_btn)
        selection_layout.addWidget(select_none_btn)
        
        header_layout.addLayout(selection_layout)
        tracks_layout.addLayout(header_layout)
        
        # Tracks table
        self.tracks_table = QTableWidget()
        self.tracks_table.setObjectName("tracksTable")
        self.tracks_table.setStyleSheet("""
            #tracksTable {
                background-color: #1a1a1a;
                border: none;
                border-radius: 10px;
                gridline-color: #2a2a2a;
                padding: 10px;
            }
            
            #tracksTable QHeaderView::section {
                background-color: #242424;
                color: #ffffff;
                padding: 10px;
                border: none;
                font-weight: bold;
            }
            
            #tracksTable::item {
                border-radius: 0px;
                padding: 8px;
                margin: 0px;
            }
            
            #tracksTable::item:selected {
                background-color: {ACCENT_COLOR};
                color: #ffffff;
            }
        """)
        
        # Configure table
        self.tracks_table.setColumnCount(5)  # Checkbox, Track #, Title, Duration, Artist
        self.tracks_table.setHorizontalHeaderLabels(["Select", "#", "Title", "Duration", "Artist"])
        self.tracks_table.horizontalHeader().setHighlightSections(False)
        self.tracks_table.setShowGrid(True)
        self.tracks_table.setAlternatingRowColors(True)
        
        # Better column sizing
        self.tracks_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.tracks_table.setColumnWidth(0, 70)  # Checkbox column
        
        self.tracks_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.tracks_table.setColumnWidth(1, 50)  # Track # column
        
        self.tracks_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Title stretches
        
        self.tracks_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.tracks_table.setColumnWidth(3, 100)  # Duration column
        
        self.tracks_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # Artist
        self.tracks_table.setColumnWidth(4, 150)  # Minimum width for artist
        
        # Set vertical header style - row numbers
        self.tracks_table.verticalHeader().setDefaultSectionSize(45)  # Taller rows
        
        # Populate tracks
        if release.songs:
            self.tracks_table.setRowCount(len(release.songs))
            
            for row, song in enumerate(release.songs):
                # Create checkbox in first column
                checkbox = QCheckBox()
                checkbox.setChecked(True)  # Default to selected
                
                checkbox_widget = QWidget()
                checkbox_layout = QHBoxLayout(checkbox_widget)
                checkbox_layout.setContentsMargins(5, 0, 0, 0)
                checkbox_layout.addWidget(checkbox)
                checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                
                self.tracks_table.setCellWidget(row, 0, checkbox_widget)
                
                # Set track number
                track_num_item = QTableWidgetItem(str(song.track_number) if song.track_number else "")
                track_num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tracks_table.setItem(row, 1, track_num_item)
                
                # Set title
                title_item = QTableWidgetItem(song.title)
                self.tracks_table.setItem(row, 2, title_item)
                
                # Set duration
                duration_item = QTableWidgetItem(song.duration)
                duration_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tracks_table.setItem(row, 3, duration_item)
                
                # Set artist (might be different for compilations)
                artist_item = QTableWidgetItem(song.artist if song.artist else release.artist)
                self.tracks_table.setItem(row, 4, artist_item)
                
                # Store song reference
                title_item.setData(Qt.ItemDataRole.UserRole, song)
        
        tracks_layout.addWidget(self.tracks_table)
        main_layout.addWidget(tracks_section, 1)  # Give tracks section more space
        
        # ==================
        # Button section
        # ==================
        button_section = QWidget()
        button_layout = QHBoxLayout(button_section)
        button_layout.setContentsMargins(0, 10, 0, 0)
        
        button_layout.addStretch(1)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.setFixedSize(140, 40)
        cancel_btn.clicked.connect(self.reject)
        if QTA_AVAILABLE:
            cancel_btn.setIcon(qta.icon('fa5s.times', color='white'))
        
        download_btn = QPushButton("Download Selected")
        download_btn.setObjectName("downloadBtn")
        download_btn.setFixedSize(200, 40)
        download_btn.clicked.connect(self.accept)
        if QTA_AVAILABLE:
            download_btn.setIcon(qta.icon('fa5s.download', color='white'))
        
        button_layout.addWidget(cancel_btn)
        button_layout.addSpacing(15)
        button_layout.addWidget(download_btn)
        
        main_layout.addWidget(button_section)
    
    def select_all_tracks(self):
        """Select all tracks."""
        for row in range(self.tracks_table.rowCount()):
            checkbox_widget = self.tracks_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(True)
    
    def select_no_tracks(self):
        """Deselect all tracks."""
        for row in range(self.tracks_table.rowCount()):
            checkbox_widget = self.tracks_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(False)
    
    def get_selected_tracks(self):
        """Get the selected tracks."""
        selected_songs = []
        
        for row in range(self.tracks_table.rowCount()):
            checkbox_widget = self.tracks_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    title_item = self.tracks_table.item(row, 2)
                    if title_item:
                        song = title_item.data(Qt.ItemDataRole.UserRole)
                        if song:
                            song.selected = True
                            selected_songs.append(song)
                        else:
                            # If song reference not found, get info from the table
                            track_num = self.tracks_table.item(row, 1).text()
                            title = title_item.text()
                            duration = self.tracks_table.item(row, 3).text()
                            artist = self.tracks_table.item(row, 4).text()
                            
                            # Create a new song
                            song = Song(
                                id=f"track_{row}",
                                title=title,
                                artist=artist,
                                album=self.release.title,
                                thumbnail_url=self.release.thumbnail_url,
                                type=ContentType.SONG,
                                url="",
                                duration=duration,
                                track_number=int(track_num) if track_num.isdigit() else 0,
                                selected=True
                            )
                            selected_songs.append(song)
                else:
                    # Mark unselected songs
                    title_item = self.tracks_table.item(row, 2)
                    if title_item:
                        song = title_item.data(Qt.ItemDataRole.UserRole)
                        if song:
                            song.selected = False
        
        return selected_songs


class SettingsDialog(QDialog):
    """Dialog for editing application settings."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.settings = parent.settings
        self.setWindowTitle("Settings")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # Download directory
        dir_group = QGroupBox("Download Directory")
        dir_layout = QHBoxLayout(dir_group)

        self.dir_input = QLineEdit(self.settings.download_dir)
        self.dir_input.setReadOnly(True)

        browse_button = QPushButton("Browse...")
        if QTA_AVAILABLE:
            browse_button.setIcon(qta.icon('fa5s.folder-open'))
        browse_button.clicked.connect(self.browse_download_dir)

        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(browse_button)

        # Threads
        threads_group = QGroupBox("Concurrent Downloads")
        threads_layout = QHBoxLayout(threads_group)

        threads_label = QLabel("Number of download threads:")
        self.threads_spinbox = QSpinBox()
        self.threads_spinbox.setMinimum(1)
        self.threads_spinbox.setMaximum(10)
        self.threads_spinbox.setValue(self.settings.threads)

        threads_layout.addWidget(threads_label)
        threads_layout.addWidget(self.threads_spinbox)

        # Format
        format_group = QGroupBox("Default Output Format")
        format_layout = QHBoxLayout(format_group)

        format_label = QLabel("Audio format:")
        self.format_combo = QComboBox()
        for fmt in SUPPORTED_FORMATS:
            self.format_combo.addItem(fmt)
        idx = self.format_combo.findText(self.settings.format)
        if idx >= 0:
            self.format_combo.setCurrentIndex(idx)

        format_layout.addWidget(format_label)
        format_layout.addWidget(self.format_combo)

        # Quality
        quality_group = QGroupBox("Default Audio Quality")
        quality_layout = QHBoxLayout(quality_group)

        quality_label = QLabel("Audio quality:")
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("High", "high")
        self.quality_combo.addItem("Medium", "medium")
        self.quality_combo.addItem("Low", "low")

        index = 0
        if self.settings.audio_quality == "medium":
            index = 1
        elif self.settings.audio_quality == "low":
            index = 2
        self.quality_combo.setCurrentIndex(index)

        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_combo)

        # Organization
        organization_group = QGroupBox("File Organization")
        organization_layout = QVBoxLayout(organization_group)

        self.auto_rename_checkbox = QCheckBox("Auto-rename files to 'Artist - Title' format")
        self.auto_rename_checkbox.setChecked(self.settings.auto_rename)

        self.use_album_folders_checkbox = QCheckBox("Organize by artist/album folders")
        self.use_album_folders_checkbox.setChecked(self.settings.use_album_folders)

        self.check_duplicates_checkbox = QCheckBox("Check for duplicate files before downloading")
        self.check_duplicates_checkbox.setChecked(self.settings.check_duplicates)

        organization_layout.addWidget(self.auto_rename_checkbox)
        organization_layout.addWidget(self.use_album_folders_checkbox)
        organization_layout.addWidget(self.check_duplicates_checkbox)

        # Processing
        processing_group = QGroupBox("Audio Processing")
        processing_layout = QVBoxLayout(processing_group)

        self.normalize_audio_checkbox = QCheckBox("Normalize audio volume")
        self.normalize_audio_checkbox.setChecked(self.settings.normalize_audio)

        processing_layout.addWidget(self.normalize_audio_checkbox)

        # Notifications
        notifications_group = QGroupBox("Notifications")
        notifications_layout = QVBoxLayout(notifications_group)

        self.notify_on_complete_checkbox = QCheckBox("Show notification when downloads complete")
        self.notify_on_complete_checkbox.setChecked(self.settings.notify_on_complete)

        notifications_layout.addWidget(self.notify_on_complete_checkbox)

        # Theme
        theme_group = QGroupBox("Theme")
        theme_layout = QHBoxLayout(theme_group)

        self.dark_mode_checkbox = QCheckBox("Dark Mode")
        self.dark_mode_checkbox.setChecked(self.settings.dark_mode)

        theme_layout.addWidget(self.dark_mode_checkbox)

        self.accent_button = QPushButton("Accent Color")
        self.accent_button.clicked.connect(self.choose_accent_color)
        self._update_accent_button()
        theme_layout.addWidget(self.accent_button)

        # Cache
        cache_group = QGroupBox("Cache")
        cache_layout = QVBoxLayout(cache_group)

        cache_size_layout = QHBoxLayout()
        self.cache_size_label = QLabel(f"Current cache size: {CacheManager.get_cache_size():.2f}MB")
        cache_size_layout.addWidget(self.cache_size_label)

        clear_cache_button = QPushButton("Clear Cache")
        if QTA_AVAILABLE:
            clear_cache_button.setIcon(qta.icon('fa5s.eraser'))
        clear_cache_button.clicked.connect(self.clear_cache)
        cache_size_layout.addWidget(clear_cache_button)

        cache_layout.addLayout(cache_size_layout)

        max_cache_layout = QHBoxLayout()
        max_cache_label = QLabel("Maximum cache size (MB):")
        self.max_cache_spinbox = QSpinBox()
        self.max_cache_spinbox.setMinimum(50)
        self.max_cache_spinbox.setMaximum(2000)
        self.max_cache_spinbox.setValue(self.settings.max_cache_size)
        max_cache_layout.addWidget(max_cache_label)
        max_cache_layout.addWidget(self.max_cache_spinbox)
        cache_layout.addLayout(max_cache_layout)

        # Credits
        credits_group = QGroupBox("About")
        credits_layout = QVBoxLayout(credits_group)

        credits_label = QLabel(f"{APP_NAME} v{APP_VERSION}")
        credits_label.setFont(QFont("", 12, QFont.Weight.Bold))
        powered_label = QLabel("Powered by yt-dlp and created by lolitemaultes")
        credits_layout.addWidget(credits_label)
        credits_layout.addWidget(powered_label)

        log_button = QPushButton("Open Log File")
        if QTA_AVAILABLE:
            log_button.setIcon(qta.icon('fa5s.file-alt'))
        log_button.clicked.connect(parent.open_log_file)
        credits_layout.addWidget(log_button)

        # Assemble layout
        layout.addWidget(dir_group)
        layout.addWidget(threads_group)
        layout.addWidget(format_group)
        layout.addWidget(quality_group)
        layout.addWidget(organization_group)
        layout.addWidget(processing_group)
        layout.addWidget(notifications_group)
        layout.addWidget(theme_group)
        layout.addWidget(cache_group)
        layout.addWidget(credits_group)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _update_accent_button(self):
        self.accent_button.setStyleSheet(f"background-color: {self.settings.accent_color}; color: white;")

    def browse_download_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Download Directory", self.settings.download_dir)
        if path:
            self.dir_input.setText(path)

    def choose_accent_color(self):
        color = QColorDialog.getColor(QColor(self.settings.accent_color), self, "Select Accent Color")
        if color.isValid():
            self.settings.accent_color = color.name()
            self._update_accent_button()
            self.parent.apply_theme()

    def clear_cache(self):
        try:
            files_count = len(os.listdir(CACHE_DIR))
            for f in os.listdir(CACHE_DIR):
                file_path = os.path.join(CACHE_DIR, f)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            self.cache_size_label.setText(f"Current cache size: {CacheManager.get_cache_size():.2f}MB")
            self.parent.status_bar.showMessage(f"Cleared {files_count} cache files")
            self.parent.feedback_message.show_message(f"Cleared {files_count} cache files", FeedbackMessage.SUCCESS)
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            self.parent.feedback_message.show_message(f"Error clearing cache: {str(e)}", FeedbackMessage.ERROR)

    def save_settings(self):
        new_threads = self.threads_spinbox.value()
        if new_threads != self.settings.threads:
            self.settings.threads = new_threads
            self.parent.threadpool.setMaxThreadCount(new_threads + 2)

        self.settings.download_dir = self.dir_input.text()
        self.settings.format = self.format_combo.currentText()
        self.settings.audio_quality = self.quality_combo.currentData()

        self.settings.auto_rename = self.auto_rename_checkbox.isChecked()
        self.settings.use_album_folders = self.use_album_folders_checkbox.isChecked()
        self.settings.check_duplicates = self.check_duplicates_checkbox.isChecked()

        self.settings.normalize_audio = self.normalize_audio_checkbox.isChecked()
        self.settings.notify_on_complete = self.notify_on_complete_checkbox.isChecked()
        self.settings.max_cache_size = self.max_cache_spinbox.value()

        old_dark = self.settings.dark_mode
        self.settings.dark_mode = self.dark_mode_checkbox.isChecked()

        self.settings.save()

        if old_dark != self.settings.dark_mode:
            self.parent.apply_theme()

        self.parent.status_bar.showMessage("Settings updated")
        self.parent.feedback_message.show_message("Settings updated", FeedbackMessage.SUCCESS)
        self.accept()


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        
        # Initialize signals
        self.signals = Signals()
        
        # Load settings
        self.settings = Settings()
        
        # Create thread pool for background tasks
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(self.settings.threads + 2)  # Extra threads for UI tasks
        
        # Initialize download manager
        self.download_manager = DownloadManager(self.settings, self.signals)

        # Settings dialog
        self.settings_dialog = SettingsDialog(self)

        # Flag to determine if a full exit was requested
        self.exit_requested = False
        
        # Initialize UI
        self.init_ui()
        
        # Connect signals
        self.connect_signals()
        
        # Apply theme
        self.apply_theme()
        
        # Check and clean cache
        CacheManager.clean_cache_if_needed()
        
        # Set up keyboard shortcuts
        self.setup_shortcuts()
        
        # Create system tray icon if QTA available
        if QTA_AVAILABLE:
            self.setup_tray_icon()
        
        # Initialize network status indicator
        self.network_connected = True
        self.update_network_indicator(True)

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle(APP_NAME)

        # Menu bar
        menubar = self.menuBar()
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings_dialog)
        menubar.addAction(settings_action)

        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about_dialog)
        menubar.addAction(about_action)
        
        # Set better minimum size to avoid cutoffs
        self.setMinimumSize(1100, 750)  # Increase from current 950, 650
        
        # Create central widget with better margins
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)
        
        # Create feedback message area
        self.feedback_message = FeedbackMessage()
        main_layout.addWidget(self.feedback_message)
        
        # Create search section
        search_section = QWidget()
        search_layout = QVBoxLayout(search_section)
        search_layout.setContentsMargins(0, 0, 0, 0)
        
        # Network status indicator and search controls
        search_bar_layout = QHBoxLayout()
        
        # Network status
        self.network_status = QLabel()
        self.network_status.setFixedSize(16, 16)
        search_bar_layout.addWidget(self.network_status)
        
        # Search bar with icon
        search_container = QFrame()
        search_container.setObjectName("searchContainer")
        search_container_layout = QHBoxLayout(search_container)
        search_container_layout.setContentsMargins(10, 0, 10, 0)
        search_container_layout.setSpacing(5)
        
        # Use qtawesome for the search icon if available
        search_icon = QLabel()
        if QTA_AVAILABLE:
            search_icon_pixmap = qta.icon('fa5s.search', color='white').pixmap(16, 16)
            search_icon.setPixmap(search_icon_pixmap)
        search_container_layout.addWidget(search_icon)
        
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchBox")
        self.search_input.setPlaceholderText("Search for artists, albums, or songs...")
        self.search_input.returnPressed.connect(self.perform_search)
        search_container_layout.addWidget(self.search_input)
        
        search_bar_layout.addWidget(search_container, 1)
        
        # Search button
        self.search_button = QPushButton("Search")
        self.search_button.setObjectName("searchButton")
        if QTA_AVAILABLE:
            self.search_button.setIcon(qta.icon('fa5s.search'))
        self.search_button.clicked.connect(self.perform_search)
        self.search_button.setToolTip("Search YouTube Music")
        search_bar_layout.addWidget(self.search_button)
        
        search_layout.addLayout(search_bar_layout)
        
        main_layout.addWidget(search_section)
        
        # Create main tab widget with custom styling
        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        
        # Create search results tab with nested tabs
        self.search_results_tab = QWidget()
        search_results_layout = QVBoxLayout(self.search_results_tab)
        search_results_layout.setContentsMargins(5, 5, 5, 5)
        search_results_layout.setSpacing(10)
        
        # Create nested tab widget for search results
        self.search_results_tabs = QTabWidget()
        search_results_layout.addWidget(self.search_results_tabs)
        
        # Create artists tab
        self.artists_tab = QWidget()
        artists_layout = QVBoxLayout(self.artists_tab)
        artists_layout.setContentsMargins(5, 5, 5, 5)
        artists_layout.setSpacing(10)
        
        self.artists_scroll = QScrollArea()
        self.artists_scroll.setWidgetResizable(True)
        self.artists_content = QWidget()
        self.artists_layout = QVBoxLayout(self.artists_content)
        self.artists_layout.setSpacing(10)
        self.artists_scroll.setWidget(self.artists_content)
        
        artists_layout.addWidget(self.artists_scroll)

        self.artists_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Create releases tab (albums + singles combined)
        self.releases_tab = QWidget()
        releases_layout = QVBoxLayout(self.releases_tab)
        releases_layout.setContentsMargins(5, 5, 5, 5)
        releases_layout.setSpacing(10)
        
        self.releases_scroll = QScrollArea()
        self.releases_scroll.setWidgetResizable(True)
        self.releases_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.releases_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.releases_content = QWidget()
        self.releases_content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.releases_layout = QVBoxLayout(self.releases_content)
        self.releases_layout.setSpacing(10)
        self.releases_layout.setContentsMargins(5, 5, 5, 5)
        self.releases_scroll.setWidget(self.releases_content)
        
        releases_layout.addWidget(self.releases_scroll)
        
        self.releases_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Add tabs to search results tab widget
        self.search_results_tabs.addTab(self.artists_tab, "Artists")
        self.search_results_tabs.addTab(self.releases_tab, "Releases")
        
        # Create downloads tab
        self.downloads_tab = QWidget()
        downloads_layout = QVBoxLayout(self.downloads_tab)
        downloads_layout.setContentsMargins(5, 5, 5, 5)
        downloads_layout.setSpacing(10)
        
        # Add download queue controls
        download_controls_layout = QHBoxLayout()
        
        # Download formats selector
        format_layout = QHBoxLayout()
        format_label = QLabel("Format:")
        self.format_combo = QComboBox()
        for fmt in SUPPORTED_FORMATS:
            self.format_combo.addItem(fmt)
        
        # Set the current format
        index = self.format_combo.findText(self.settings.format)
        if index >= 0:
            self.format_combo.setCurrentIndex(index)
        
        format_layout.addWidget(format_label)
        format_layout.addWidget(self.format_combo)
        download_controls_layout.addLayout(format_layout)
        
        # Quality selector
        quality_layout = QHBoxLayout()
        quality_label = QLabel("Quality:")
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("High", "high")
        self.quality_combo.addItem("Medium", "medium")
        self.quality_combo.addItem("Low", "low")
        
        # Set the current quality
        index = 0  # Default to high
        if self.settings.audio_quality == "medium":
            index = 1
        elif self.settings.audio_quality == "low":
            index = 2
        self.quality_combo.setCurrentIndex(index)
        
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_combo)
        download_controls_layout.addLayout(quality_layout)
        
        # Clear completed button
        self.clear_completed_button = QPushButton("Clear Completed")
        if QTA_AVAILABLE:
            self.clear_completed_button.setIcon(qta.icon('fa5s.trash'))
        self.clear_completed_button.clicked.connect(self.clear_completed_downloads)
        download_controls_layout.addWidget(self.clear_completed_button)
        
        # Cancel all button
        self.cancel_all_button = QPushButton("Cancel All")
        if QTA_AVAILABLE:
            self.cancel_all_button.setIcon(qta.icon('fa5s.times-circle'))
        self.cancel_all_button.clicked.connect(self.cancel_all_downloads)
        download_controls_layout.addWidget(self.cancel_all_button)
        
        # Download controls spacer
        download_controls_layout.addStretch(1)
        
        downloads_layout.addLayout(download_controls_layout)
        
        # Downloads scroll area
        self.downloads_scroll = QScrollArea()
        self.downloads_scroll.setWidgetResizable(True)
        self.downloads_content = QWidget()
        self.downloads_layout = QVBoxLayout(self.downloads_content)
        self.downloads_layout.setSpacing(10)
        self.downloads_scroll.setWidget(self.downloads_content)
        
        downloads_layout.addWidget(self.downloads_scroll)
        
        self.downloads_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Create library tab
        self.library_tab = QWidget()
        library_layout = QVBoxLayout(self.library_tab)
        library_layout.setContentsMargins(5, 5, 5, 5)
        library_layout.setSpacing(10)
        
        # Library scan button
        scan_layout = QHBoxLayout()
        scan_button = QPushButton("Scan Music Library")
        if QTA_AVAILABLE:
            scan_button.setIcon(qta.icon('fa5s.sync'))  # Changed from fa5s.refresh to fa5s.sync
        scan_button.clicked.connect(self.scan_music_library)
        scan_layout.addWidget(scan_button)
        scan_layout.addStretch(1)
        library_layout.addLayout(scan_layout)
        
        # Downloaded music table
        self.downloaded_table = QTableWidget()
        self.downloaded_table.setColumnCount(5)
        self.downloaded_table.setHorizontalHeaderLabels(["Title", "Artist", "Album", "Duration", "Path"])
        self.downloaded_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        library_layout.addWidget(self.downloaded_table)
        
        
        # Add tabs to the main tab widget
        self.tabs.addTab(self.search_results_tab, "Search Results")
        self.tabs.addTab(self.downloads_tab, "Downloads Queue")
        self.tabs.addTab(self.library_tab, "Library")
        
        main_layout.addWidget(self.tabs)
        
        # Set central widget
        self.setCentralWidget(central_widget)
        
        # Setup status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")
        
        # Show a welcome message in each search results tab
        self.create_welcome_messages()

    def create_welcome_messages(self):
        """Create welcome messages for the search tabs."""
        welcome_text = "<h2>Welcome to YouTube Music Downloader</h2><p>Enter a search term in the box above to find artists and releases.</p>"
        
        # Create separate instances for each tab
        artists_welcome = QLabel(welcome_text)
        artists_welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artists_layout.addWidget(artists_welcome)
        
        releases_welcome = QLabel(welcome_text)
        releases_welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.releases_layout.addWidget(releases_welcome)
        
        self.artists_layout.addStretch(1)
        self.releases_layout.addStretch(1)

    def connect_signals(self):
        """Connect signals to slots."""
        # Search signals
        self.signals.search_complete.connect(self.display_search_results)
        self.signals.error.connect(self.show_error)
        
        # Download signals
        self.signals.download_progress.connect(self.update_download_progress)
        self.signals.download_status_changed.connect(self.update_download_status)
        
        # Network status signal
        self.signals.network_status_changed.connect(self.update_network_indicator)
        
        # Metadata signal
        self.signals.metadata_fetched.connect(self.update_metadata)
        
        # Task completion signal
        self.signals.task_completed.connect(self.handle_task_completion)

    def setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        # Search shortcut (Ctrl+F)
        search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        search_shortcut.activated.connect(lambda: (self.search_input.setFocus(), self.search_input.selectAll()))
        
        # Download shortcut (Ctrl+D) - for selected item
        download_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        download_shortcut.activated.connect(self.download_selected)
        
        # Tab navigation (Ctrl+Tab, Ctrl+Shift+Tab)
        next_tab_shortcut = QShortcut(QKeySequence("Ctrl+Tab"), self)
        next_tab_shortcut.activated.connect(self.next_tab)
        
        prev_tab_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Tab"), self)
        prev_tab_shortcut.activated.connect(self.prev_tab)

    def setup_tray_icon(self):
        """Set up system tray icon if supported."""
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon(self)
            
            # Use qtawesome for icon
            if QTA_AVAILABLE:
                self.tray_icon.setIcon(qta.icon('fa5s.music', color='white'))
            else:
                # Use a standard icon
                self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
                
            # Create tray menu
            tray_menu = QMenu()

            # Show/hide action
            self.show_action = QAction("Hide" if self.isVisible() else "Show", self)
            self.show_action.triggered.connect(self.toggle_window)
            tray_menu.addAction(self.show_action)
            
            # Downloads status
            self.downloads_action = QAction("Downloads: 0 active", self)
            self.downloads_action.setEnabled(False)
            tray_menu.addAction(self.downloads_action)
            
            tray_menu.addSeparator()
            
            # Quit action
            quit_action = QAction("Quit", self)
            quit_action.triggered.connect(self.quit_application)
            tray_menu.addAction(quit_action)
            
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self.tray_icon_activated)
            
            # Show the tray icon
            self.tray_icon.show()
    
    def tray_icon_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_window()
    
    def toggle_window(self):
        """Toggle window visibility."""
        if self.isVisible():
            self.hide()
            if hasattr(self, "show_action"):
                self.show_action.setText("Show")
        else:
            self.show()
            self.activateWindow()
            if hasattr(self, "show_action"):
                self.show_action.setText("Hide")

    def quit_application(self):
        """Request application quit from the tray."""
        if self.download_manager.active_downloads:
            reply = QMessageBox.question(
                self,
                "Quit Application",
                "There are active downloads. Quit and cancel them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.exit_requested = True
        self.close()
        # Ensure the Qt event loop exits even if the window is hidden
        QApplication.instance().quit()

    def update_network_indicator(self, connected: bool):
        """Update the network status indicator."""
        self.network_connected = connected
        
        if connected:
            # Set green color for connected
            self.network_status.setStyleSheet("background-color: #4CAF50; border-radius: 8px;")
            self.network_status.setToolTip("Connected to network")
            self.status_bar.showMessage("Network connection detected", 3000)
        else:
            # Set red color for disconnected
            self.network_status.setStyleSheet("background-color: #F44336; border-radius: 8px;")
            self.network_status.setToolTip("No network connection")
            self.status_bar.showMessage("Network connection lost", 5000)
            self.show_error("Network connection lost. Downloads may be affected.")

    def perform_search(self):
        """Perform a search when the search button is clicked or Enter is pressed."""
        query = self.search_input.text().strip()
        if not query:
            self.feedback_message.show_message("Please enter a search term", FeedbackMessage.WARNING)
            return
        
        # Check network connection
        if not self.network_connected:
            self.feedback_message.show_message("No network connection. Please try again later.", FeedbackMessage.ERROR)
            return
        
        # Clear previous search results
        self.clear_layout(self.artists_layout)
        self.clear_layout(self.releases_layout)
        
        # Show loading indicator in each tab
        artists_loading = LoadingSpinner()
        artists_loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artists_layout.addWidget(artists_loading)
        
        releases_loading = LoadingSpinner()
        releases_loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.releases_layout.addWidget(releases_loading)
        
        # Switch to search results tab
        self.tabs.setCurrentIndex(0)
        
        # Create a search worker
        worker = SearchWorker(query, self.signals)
        
        # Execute the worker
        self.threadpool.start(worker)
        
        # Update status
        self.status_bar.showMessage(f"Searching for: {query}")
        self.feedback_message.show_message(f"Searching for '{query}'...", FeedbackMessage.INFO)

    def display_search_results(self, results):
        """Display the search results in separate tabs for artists and releases."""
        logger.info(f"Displaying {len(results)} search results")
        
        # Clear the layouts
        self.clear_layout(self.artists_layout)
        self.clear_layout(self.releases_layout)
        
        if not results:
            logger.warning("No results to display")
            # Show no results message in all tabs
            no_results_text = "No results found. Try a different search term."
            
            artists_no_results = QLabel(no_results_text)
            artists_no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.artists_layout.addWidget(artists_no_results)
            
            releases_no_results = QLabel(no_results_text)
            releases_no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.releases_layout.addWidget(releases_no_results)
            
            self.artists_layout.addStretch(1)
            self.releases_layout.addStretch(1)
            
            self.status_bar.showMessage("No results found")
            self.feedback_message.show_message("No results found. Try a different search term.", FeedbackMessage.WARNING)
            return
        
        # Group results by type
        artists = [r for r in results if r.type == ContentType.ARTIST]
        releases = [r for r in results if r.type in [ContentType.ALBUM, ContentType.SINGLE, ContentType.RELEASE]]
        
        logger.info(f"Categorized results: {len(artists)} artists, {len(releases)} releases")
        
        # Display artists
        if artists:
            for artist in artists:
                self.add_artist_item(artist, self.artists_layout)
        else:
            no_artists = QLabel("No artists found. Try a different search term.")
            no_artists.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.artists_layout.addWidget(no_artists)
        
        # Display releases (albums + singles)
        if releases:
            for release in releases:
                self.add_release_item(release, self.releases_layout)
        else:
            no_releases = QLabel("No releases found. Try a different search term.")
            no_releases.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.releases_layout.addWidget(no_releases)
        
        # Add stretch at the end of each layout
        self.artists_layout.addStretch(1)
        self.releases_layout.addStretch(1)
        
        # Select the appropriate tab based on results
        if artists and not releases:
            self.search_results_tabs.setCurrentIndex(0)  # Artists tab
        elif releases and not artists:
            self.search_results_tabs.setCurrentIndex(1)  # Releases tab
        else:
            # Choose tab with most results
            if len(artists) >= len(releases):
                self.search_results_tabs.setCurrentIndex(0)
            else:
                self.search_results_tabs.setCurrentIndex(1)
        
        # Update status
        total_results = len(artists) + len(releases)
        self.status_bar.showMessage(f"Found {total_results} results")
        self.feedback_message.show_message(f"Found {total_results} results", FeedbackMessage.SUCCESS)
    
    def add_artist_item(self, artist, parent_layout):
        """Add an artist search result item to the layout."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setObjectName("artistItem")
        frame.setStyleSheet("background-color: #1e1e1e; border-radius: 10px; padding: 10px;")
        
        # Use expanding size policy
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        frame.setMinimumHeight(180)
        
        # Store the item for later access
        frame.setProperty("item", artist)
        
        # Create layout - change to grid layout
        item_layout = QGridLayout(frame)
        item_layout.setContentsMargins(15, 15, 15, 15)
        item_layout.setSpacing(15)
        
        # Add thumbnail
        thumbnail_label = QLabel()
        thumbnail_label.setObjectName("thumbnailLabel")
        thumbnail_label.setStyleSheet("background-color: #242424; border-radius: 8px;")
        thumbnail_label.setFixedSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE)
        thumbnail_label.setScaledContents(True)
        thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center content
        
        # Get and set the thumbnail
        thumbnail = artist.get_thumbnail()
        if thumbnail and not thumbnail.isNull():
            scaled_thumbnail = thumbnail.scaled(
                THUMBNAIL_SIZE, THUMBNAIL_SIZE, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            thumbnail_label.setPixmap(scaled_thumbnail)
        else:
            # Use a placeholder with icon if QTA is available
            if QTA_AVAILABLE:
                icon = qta.icon('fa5s.user', color='white')
                thumbnail_label.setPixmap(icon.pixmap(64, 64))
            else:
                # Text fallback
                thumbnail_label.setText("No Image")
        
        # Add to layout at position row 0, column 0, spanning 2 rows, 1 column
        item_layout.addWidget(thumbnail_label, 0, 0, 2, 1)
        
        # Title and info
        info_layout = QVBoxLayout()
        
        title_label = QLabel(f"<h2>{artist.title}</h2>")
        title_label.setWordWrap(True)
        info_layout.addWidget(title_label)
        
        type_label = QLabel("Artist")
        type_label.setStyleSheet("color: #aaaaaa;")
        info_layout.addWidget(type_label)
        
        info_layout.addStretch(1)
        
        # Add info layout to grid at position row 0, column 1
        item_layout.addLayout(info_layout, 0, 1)
        
        # Button layout horizontally in row 1, column 1
        button_layout = QHBoxLayout()
        
        # Download button
        download_button = QPushButton("Download Discography")
        if QTA_AVAILABLE:
            download_button.setIcon(qta.icon('fa5s.download'))
        download_button.clicked.connect(lambda: self.download_item(artist))
        download_button.setMinimumWidth(150)
        button_layout.addWidget(download_button)
        
        # Format and quality selectors
        format_combo = QComboBox()
        for fmt in SUPPORTED_FORMATS:
            format_combo.addItem(fmt)
        
        # Set the current format
        index = format_combo.findText(self.settings.format)
        if index >= 0:
            format_combo.setCurrentIndex(index)
        
        format_combo.setFixedWidth(80)
        button_layout.addWidget(format_combo)
        
        quality_combo = QComboBox()
        quality_combo.addItem("High", "high")
        quality_combo.addItem("Medium", "medium")
        quality_combo.addItem("Low", "low")
        
        quality_combo.setFixedWidth(80)
        button_layout.addWidget(quality_combo)
        
        # Store combos in button properties
        download_button.setProperty("format_combo", format_combo)
        download_button.setProperty("quality_combo", quality_combo)
        
        # Add button layout to grid at position row 1, column 1
        item_layout.addLayout(button_layout, 1, 1)
        
        # Set column stretching - make the info column stretch
        item_layout.setColumnStretch(1, 1)
        
        # Add to parent layout
        parent_layout.addWidget(frame)
        
        # Add context menu
        frame.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        frame.customContextMenuRequested.connect(lambda pos, i=artist, f=frame: self.show_context_menu(pos, i, f))

    def add_release_item(self, release, parent_layout):
        """Add a release (album or single) search result item to the layout."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setObjectName("releaseItem")
        frame.setStyleSheet("background-color: #1e1e1e; border-radius: 10px; padding: 10px;")
        
        # This is crucial - ensure the frame uses all available width
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        frame.setMinimumHeight(180)
        
        # Store the item for later access
        frame.setProperty("item", release)
        
        # Create layout - change to QGridLayout for better control
        item_layout = QGridLayout(frame)
        item_layout.setContentsMargins(15, 15, 15, 15)
        item_layout.setSpacing(15)
        
        # Add thumbnail
        thumbnail_label = QLabel()
        thumbnail_label.setObjectName("thumbnailLabel")
        thumbnail_label.setStyleSheet("background-color: #242424; border-radius: 8px;")
        thumbnail_label.setFixedSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE)
        thumbnail_label.setScaledContents(True)
        
        # Get and set the thumbnail
        thumbnail = release.get_thumbnail()
        if thumbnail and not thumbnail.isNull():
            scaled_thumbnail = thumbnail.scaled(
                THUMBNAIL_SIZE, THUMBNAIL_SIZE, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            thumbnail_label.setPixmap(scaled_thumbnail)
        else:
            # Use a placeholder with icon if QTA is available
            if QTA_AVAILABLE:
                icon = qta.icon('fa5s.music', color='white')
                thumbnail_label.setPixmap(icon.pixmap(64, 64))
            else:
                # Text fallback
                thumbnail_label.setText("No Image")
                thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Add to layout at position row 0, column 0, spanning 2 rows, 1 column
        item_layout.addWidget(thumbnail_label, 0, 0, 2, 1)
        
        # Title and info
        info_layout = QVBoxLayout()
        
        # Use QLabel with word wrap and elided text
        title_label = QLabel(f"<h2>{release.title}</h2>")
        title_label.setWordWrap(True)
        info_layout.addWidget(title_label)
        
        artist_label = QLabel(f"<h3>{release.artist}</h3>")
        artist_label.setWordWrap(True)
        info_layout.addWidget(artist_label)
        
        # Release info
        info_parts = []
        
        # Release type (album/single)
        if release.type == ContentType.SINGLE:
            release_type = "Single"
            release.release_type = "single"
        else:
            release_type = "Album"
            release.release_type = "album"
        info_parts.append(release_type)
        
        # Year
        if release.year:
            info_parts.append(f"Released: {release.year}")
        
        # Tracks
        if release.track_count:
            track_text = "track" if release.track_count == 1 else "tracks"
            info_parts.append(f"{release.track_count} {track_text}")
        
        info_label = QLabel(" • ".join(info_parts))
        info_label.setStyleSheet("color: #aaaaaa;")
        info_layout.addWidget(info_label)
        
        info_layout.addStretch(1)
        
        # Add info layout to grid at position row 0, column 1
        item_layout.addLayout(info_layout, 0, 1)
        
        # Button layout horizontally in row 1, column 1
        button_layout = QHBoxLayout()
        
        # Download button
        download_button = QPushButton("Download")
        if QTA_AVAILABLE:
            download_button.setIcon(qta.icon('fa5s.download'))
        download_button.clicked.connect(lambda: self.download_item(release))
        download_button.setMinimumWidth(100)
        button_layout.addWidget(download_button)
        
        # Format and quality selectors
        format_combo = QComboBox()
        for fmt in SUPPORTED_FORMATS:
            format_combo.addItem(fmt)
        
        # Set the current format
        index = format_combo.findText(self.settings.format)
        if index >= 0:
            format_combo.setCurrentIndex(index)
        
        format_combo.setFixedWidth(80)
        button_layout.addWidget(format_combo)
        
        quality_combo = QComboBox()
        quality_combo.addItem("High", "high")
        quality_combo.addItem("Medium", "medium")
        quality_combo.addItem("Low", "low")
        
        quality_combo.setFixedWidth(80)
        button_layout.addWidget(quality_combo)
        
        # Store combos in button properties
        download_button.setProperty("format_combo", format_combo)
        download_button.setProperty("quality_combo", quality_combo)
        
        # Add button layout to grid at position row 1, column 1
        item_layout.addLayout(button_layout, 1, 1)
        
        # Set column stretching - make the info column stretch
        item_layout.setColumnStretch(1, 1)
        
        # Add to parent layout
        parent_layout.addWidget(frame)
        
        # Add context menu
        frame.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        frame.customContextMenuRequested.connect(lambda pos, i=release, f=frame: self.show_context_menu(pos, i, f))

    def show_context_menu(self, position, item, parent_widget):
        """Show context menu for a search result item."""
        menu = QMenu()
        
        # Download action
        download_action = QAction(f"Download {item.type.value}", self)
        if QTA_AVAILABLE:
            download_action.setIcon(qta.icon('fa5s.download'))
        download_action.triggered.connect(lambda: self.download_item(item))
        menu.addAction(download_action)
        
        # Copy link action
        copy_url_action = QAction("Copy URL", self)
        if QTA_AVAILABLE:
            copy_url_action.setIcon(qta.icon('fa5s.clipboard'))
        copy_url_action.triggered.connect(lambda: self.copy_url_to_clipboard(item.url))
        menu.addAction(copy_url_action)
        
        # Search for artist action (for releases)
        if item.type in [ContentType.ALBUM, ContentType.RELEASE, ContentType.SINGLE] and item.artist:
            search_artist_action = QAction(f"Search for artist: {item.artist}", self)
            if QTA_AVAILABLE:
                search_artist_action.setIcon(qta.icon('fa5s.search'))
            search_artist_action.triggered.connect(lambda: self.search_for_artist(item.artist))
            menu.addAction(search_artist_action)
        
        # Show the menu
        menu.exec(parent_widget.mapToGlobal(position))

    def copy_url_to_clipboard(self, url):
        """Copy URL to clipboard."""
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(url)
        self.feedback_message.show_message("URL copied to clipboard", FeedbackMessage.INFO)

    def search_for_artist(self, artist_name):
        """Search for an artist by name."""
        self.search_input.setText(artist_name)
        self.perform_search()

    def download_item(self, item):
        """Download an item with track selection for releases."""
        # Get the format and quality from the sender button if available
        sender = self.sender()
        format_ = self.settings.format
        quality = self.settings.audio_quality
        
        # If sender is a button, it might have format and quality combos
        if hasattr(sender, 'property'):
            format_combo = sender.property("format_combo")
            if format_combo is not None:
                format_ = format_combo.currentText()
                
            quality_combo = sender.property("quality_combo")
            if quality_combo is not None:
                quality = quality_combo.currentData()
        
        # For releases (albums/singles), show track selection dialog
        if item.type in [ContentType.ALBUM, ContentType.RELEASE, ContentType.SINGLE]:
            # First check if we have track details
            if not hasattr(item, 'songs') or not item.songs:
                # Need to fetch songs first
                self.fetch_release_details_for_download(item, format_, quality)
                return
            
            # Show track selection dialog
            dialog = TrackSelectionDialog(item, self)
            result = dialog.exec()
            
            if result == QDialog.DialogCode.Accepted:
                # Get selected tracks
                selected_tracks = dialog.get_selected_tracks()
                
                if not selected_tracks:
                    self.feedback_message.show_message("No tracks selected for download", FeedbackMessage.WARNING)
                    return
                
                # Update release songs with selected status
                for song in item.songs:
                    if song in selected_tracks:
                        song.selected = True
                    else:
                        song.selected = False
                
                # Add to download queue
                download_id = self.download_manager.add_to_queue(item, format_, quality)
                
                # Switch to downloads tab
                self.tabs.setCurrentIndex(1)
                
                # Update status
                self.status_bar.showMessage(f"Added to download queue: {item.title}")
                self.feedback_message.show_message(f"Added to download queue: {item.title}", FeedbackMessage.SUCCESS)
            
        else:
            # For other types, add directly to queue
            download_id = self.download_manager.add_to_queue(item, format_, quality)
            
            # Switch to downloads tab
            self.tabs.setCurrentIndex(1)
            
            # Update status
            self.status_bar.showMessage(f"Added to download queue: {item.title}")
            self.feedback_message.show_message(f"Added to download queue: {item.title}", FeedbackMessage.SUCCESS)

    def fetch_release_details_for_download(self, release, format_, quality):
        """Fetch release details before download."""
        # Show loading dialog
        loading_dialog = QDialog(self)
        loading_dialog.setWindowTitle("Loading")
        loading_dialog.setFixedSize(300, 100)
        loading_dialog.setObjectName("loadingDialog")
        
        layout = QVBoxLayout(loading_dialog)
        
        loading_label = QLabel(f"Fetching details for {release.title}...")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(loading_label)
        
        # Add spinner
        if QTA_AVAILABLE:
            spinner_label = QLabel()
            spinner_icon = qta.icon('fa5s.spinner', color='white', animation=qta.Spin(spinner_label))
            spinner_label.setPixmap(spinner_icon.pixmap(32, 32))
            spinner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(spinner_label)
        else:
            spinner = LoadingSpinner()
            layout.addWidget(spinner)
        
        # Create a thread to fetch release details
        class ReleaseFetcherThread(QThread):
            finished = pyqtSignal(object)
            error = pyqtSignal(str)
            
            def __init__(self, release):
                super().__init__()
                self.release = release
            
            def run(self):
                try:
                    details = fetch_release_details(self.release.url, self.release.id)
                    
                    if details and 'songs' in details:
                        self.release.songs = details.get('songs', [])
                        self.release.year = details.get('year', '')
                        self.release.track_count = len(self.release.songs)
                        
                        # Set all songs as selected by default
                        for song in self.release.songs:
                            song.selected = True
                    
                    self.finished.emit(self.release)
                    
                except Exception as e:
                    self.error.emit(str(e))
        
        # Show loading dialog without blocking
        loading_dialog.show()
        
        # Create thread
        self.release_fetch_thread = ReleaseFetcherThread(release)
        
        # Connect signals
        self.release_fetch_thread.finished.connect(
            lambda rel: self._on_release_details_fetched_for_download(rel, format_, quality, loading_dialog)
        )
        self.release_fetch_thread.error.connect(
            lambda err: self._on_release_details_error(err, loading_dialog)
        )
        
        # Start thread
        self.release_fetch_thread.start()

    def _on_release_details_fetched_for_download(self, release, format_, quality, dialog):
        """Handle release details fetching completion."""
        # Close the dialog
        dialog.accept()
        
        # Continue with download
        if release.songs:
            # Show track selection dialog
            track_dialog = TrackSelectionDialog(release, self)
            result = track_dialog.exec()
            
            if result == QDialog.DialogCode.Accepted:
                # Get selected tracks
                selected_tracks = track_dialog.get_selected_tracks()
                
                if not selected_tracks:
                    self.feedback_message.show_message("No tracks selected for download", FeedbackMessage.WARNING)
                    return
                
                # Update release songs with selected status
                for song in release.songs:
                    if song in selected_tracks:
                        song.selected = True
                    else:
                        song.selected = False
                
                # Add to download queue
                download_id = self.download_manager.add_to_queue(release, format_, quality)
                
                # Switch to downloads tab
                self.tabs.setCurrentIndex(1)
                
                # Update status
                self.status_bar.showMessage(f"Added to download queue: {release.title}")
                self.feedback_message.show_message(f"Added to download queue: {release.title}", FeedbackMessage.SUCCESS)
        else:
            self.feedback_message.show_message(f"No tracks found in {release.title}", FeedbackMessage.ERROR)

    def _on_release_details_error(self, error_msg, dialog):
        """Handle release details fetching error."""
        # Close the dialog
        dialog.accept()
        
        # Show error message
        self.feedback_message.show_message(f"Failed to fetch release details: {error_msg}", FeedbackMessage.ERROR)

    def download_selected(self):
        """Download the currently selected item."""
        # Determine the current tab and find selected items
        current_tab_index = self.search_results_tabs.currentIndex()
        if current_tab_index == 0:  # Artists tab
            for i in range(self.artists_layout.count()):
                widget = self.artists_layout.itemAt(i).widget()
                if isinstance(widget, QFrame) and widget.isActiveWindow():
                    item = widget.property("item")
                    if item:
                        self.download_item(item)
                        return
        elif current_tab_index == 1:  # Releases tab
            for i in range(self.releases_layout.count()):
                widget = self.releases_layout.itemAt(i).widget()
                if isinstance(widget, QFrame) and widget.isActiveWindow():
                    item = widget.property("item")
                    if item:
                        self.download_item(item)
                        return

    def update_metadata(self, download_id, item):
        """Update items with fetched metadata."""
        # Update the UI if needed - we're using threads now so this is safe
        pass

    def update_download_progress(self, download_id, progress, message):
        """Update the progress of a download."""
        # Find the download item widget
        download_widget = self.findChild(QWidget, f"download_{download_id}")
        if download_widget:
            # Find the progress bar
            progress_bar = download_widget.findChild(QProgressBar)
            if progress_bar:
                progress_bar.setValue(int(progress))
            
            # Find the message label
            message_label = download_widget.findChild(QLabel, "message")
            if message_label:
                message_label.setText(message)
            
            # Update the system tray information
            if hasattr(self, 'tray_icon') and hasattr(self, 'downloads_action'):
                active_count = len(self.download_manager.active_downloads)
                self.downloads_action.setText(f"Downloads: {active_count} active")

    def update_download_status(self, download_id, status, message):
        """Update the status of a download."""
        if status == DownloadStatus.QUEUED or status == DownloadStatus.PENDING:
            # Create a new download item widget
            self.create_download_widget(download_id)
        
        # Find the download item widget
        download_widget = self.findChild(QWidget, f"download_{download_id}")
        if download_widget:
            # Find the status label
            status_label = download_widget.findChild(QLabel, "status")
            if status_label:
                status_label.setText(status.value)
                
                # Set status color
                if status == DownloadStatus.COMPLETED:
                    status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
                    
                    # Show notification if enabled
                    if self.settings.notify_on_complete and hasattr(self, 'tray_icon'):
                        download_item = self.download_manager.download_queue.get(download_id)
                        if download_item:
                            title = f"Download Complete"
                            message = f"{download_item.item.title} has been downloaded."
                            self.tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)
                
                elif status == DownloadStatus.FAILED:
                    status_label.setStyleSheet("color: #F44336; font-weight: bold;")
                elif status == DownloadStatus.CANCELLED:
                    status_label.setStyleSheet("color: #FF9800; font-weight: bold;")
                else:
                    status_label.setStyleSheet("")
            
            # Find the message label
            message_label = download_widget.findChild(QLabel, "message")
            if message_label and message:
                message_label.setText(message)
            
            # Find cancel button and handle completed/failed states
            cancel_button = download_widget.findChild(QPushButton, "cancel")
            open_button = download_widget.findChild(QPushButton, "open")
            
            if status in [DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED]:
                if cancel_button:
                    cancel_button.setVisible(False)
                
                # Show open button for completed downloads
                if status == DownloadStatus.COMPLETED and open_button:
                    open_button.setVisible(True)
            
            # Update the widget style based on status
            if status == DownloadStatus.COMPLETED:
                download_widget.setStyleSheet("background-color: rgba(76, 175, 80, 0.1); border-radius: 5px;")
            elif status == DownloadStatus.FAILED:
                download_widget.setStyleSheet("background-color: rgba(244, 67, 54, 0.1); border-radius: 5px;")
            elif status == DownloadStatus.CANCELLED:
                download_widget.setStyleSheet("background-color: rgba(255, 152, 0, 0.1); border-radius: 5px;")
            elif status == DownloadStatus.DOWNLOADING:
                download_widget.setStyleSheet("background-color: rgba(77, 143, 253, 0.1); border-radius: 5px;")
            
            # Update the system tray information
            if hasattr(self, 'tray_icon') and hasattr(self, 'downloads_action'):
                active_count = len(self.download_manager.active_downloads)
                self.downloads_action.setText(f"Downloads: {active_count} active")

    def create_download_widget(self, download_id):
        """Create a widget for a download item."""
        # Get the download item
        download_item = self.download_manager.download_queue.get(download_id)
        if not download_item:
            return
        
        # Create frame
        frame = QFrame()
        frame.setObjectName(f"download_{download_id}")
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setFrameShadow(QFrame.Shadow.Raised)
        frame.setStyleSheet("border-radius: 5px;")
        
        # Create layout
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # Header layout
        header_layout = QHBoxLayout()
        
        # Get the item
        item = download_item.item
        
        # Item thumbnail
        thumbnail_label = QLabel()
        thumbnail_label.setStyleSheet("background-color: #1e2124; border-radius: 8px;")
        thumbnail = item.get_thumbnail()
        if thumbnail and not thumbnail.isNull():
            scaled_thumbnail = thumbnail.scaled(
                50, 50, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            thumbnail_label.setPixmap(scaled_thumbnail)
        
        thumbnail_label.setFixedSize(50, 50)
        header_layout.addWidget(thumbnail_label)
        
        # Title and info layout
        title_info_layout = QVBoxLayout()
        
        # Title label
        title_text = f"{item.type.value.title()}: {item.title}"
        if item.type in [ContentType.RELEASE, ContentType.ALBUM, ContentType.SINGLE]:
            title_text += f" - {item.artist}"
        
        title_label = QLabel(title_text)
        title_label.setFont(QFont("", 10, QFont.Weight.Bold))
        title_info_layout.addWidget(title_label)
        
        # Format and quality info
        format_quality_label = QLabel(f"Format: {download_item.format.upper()} • Quality: {download_item.quality.capitalize()}")
        title_info_layout.addWidget(format_quality_label)
        
        header_layout.addLayout(title_info_layout, 1)
        
        # Status label
        status_label = QLabel(download_item.status.value)
        status_label.setObjectName("status")
        status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(status_label)
        
        # Add header layout
        layout.addLayout(header_layout)
        
        # Progress bar
        progress_bar = QProgressBar()
        progress_bar.setMinimum(0)
        progress_bar.setMaximum(100)
        progress_bar.setValue(0)
        progress_bar.setTextVisible(True)
        layout.addWidget(progress_bar)
        
        # Message label
        message_label = QLabel("")
        message_label.setObjectName("message")
        layout.addWidget(message_label)
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        
        # Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("cancel")
        if QTA_AVAILABLE:
            cancel_button.setIcon(qta.icon('fa5s.times'))
        cancel_button.clicked.connect(lambda: self.download_manager.cancel_download(download_id))
        buttons_layout.addWidget(cancel_button)
        
        # Open folder button (initially hidden)
        open_button = QPushButton("Open Location")
        open_button.setObjectName("open")
        if QTA_AVAILABLE:
            open_button.setIcon(qta.icon('fa5s.folder-open'))
        open_button.setVisible(False)
        open_button.clicked.connect(lambda: self.open_download_location(download_id))
        buttons_layout.addWidget(open_button)
        
        # Add buttons layout
        layout.addLayout(buttons_layout)
        
        # Add to downloads layout
        self.downloads_layout.insertWidget(0, frame)
        
        # Update the system tray information
        if hasattr(self, 'tray_icon') and hasattr(self, 'downloads_action'):
            active_count = len(self.download_manager.active_downloads)
            self.downloads_action.setText(f"Downloads: {active_count} active")

    def open_download_location(self, download_id):
        """Open the folder containing a downloaded item."""
        # Get the download item
        download_item = self.download_manager.download_queue.get(download_id)
        if not download_item or not download_item.output_path:
            return
        
        # Get the output path
        path = download_item.output_path
        
        # If the path is a file, get its directory
        if os.path.isfile(path):
            path = os.path.dirname(path)
        
        # Open the folder in file explorer
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", path], check=True)
            else:  # Linux
                subprocess.run(["xdg-open", path], check=True)
        except Exception as e:
            logger.error(f"Failed to open folder: {str(e)}")
            self.feedback_message.show_message(f"Failed to open folder: {str(e)}", FeedbackMessage.ERROR)

    def clear_completed_downloads(self):
        """Clear completed downloads from the queue."""
        completed_widgets = []
        
        # Find completed download widgets
        for i in range(self.downloads_layout.count()):
            widget = self.downloads_layout.itemAt(i).widget()
            if widget and widget.objectName().startswith("download_"):
                status_label = widget.findChild(QLabel, "status")
                if status_label and status_label.text() in [DownloadStatus.COMPLETED.value, 
                                                          DownloadStatus.FAILED.value, 
                                                          DownloadStatus.CANCELLED.value]:
                    completed_widgets.append(widget)
        
        # Remove completed widgets
        for widget in completed_widgets:
            download_id = widget.objectName()[len("download_"):]
            
            # Remove from download manager queue
            with self.download_manager.lock:
                if download_id in self.download_manager.download_queue:
                    self.download_manager.download_queue.pop(download_id)
            
            # Remove widget
            widget.setParent(None)
            widget.deleteLater()
        
        # Update status
        self.status_bar.showMessage(f"Cleared {len(completed_widgets)} completed downloads")
        self.feedback_message.show_message(f"Cleared {len(completed_widgets)} completed downloads", FeedbackMessage.INFO)

    def cancel_all_downloads(self):
        """Cancel all active downloads."""
        with self.download_manager.lock:
            active_ids = list(self.download_manager.active_downloads)
            queued_ids = [id for id, item in self.download_manager.download_queue.items() 
                         if item.status == DownloadStatus.QUEUED and id not in active_ids]
            
            # Cancel active downloads
            for download_id in active_ids:
                self.download_manager.cancel_download(download_id)
            
            # Cancel queued downloads
            for download_id in queued_ids:
                self.download_manager.cancel_download(download_id)
        
        # Update status
        total_cancelled = len(active_ids) + len(queued_ids)
        self.status_bar.showMessage(f"Cancelled {total_cancelled} downloads")
        self.feedback_message.show_message(f"Cancelled {total_cancelled} downloads", FeedbackMessage.INFO)


    def apply_theme(self):
        """Apply the selected theme."""
        if self.settings.dark_mode:
            # Apply dark theme using QSS
            DarkTheme.apply_to(QApplication.instance(), self.settings.accent_color)
        else:
            # Use default light palette
            QApplication.instance().setStyleSheet("")
            self.setPalette(QApplication.style().standardPalette())

    def open_settings_dialog(self):
        """Show the settings dialog."""
        self.settings_dialog.exec()

    def show_about_dialog(self):
        """Display about information."""
        QMessageBox.about(self, f"{APP_NAME} v{APP_VERSION}",
                          f"{APP_NAME} v{APP_VERSION}\nPowered by yt-dlp and created by lolitemaultes")

    def scan_music_library(self):
        """Scan music library and display in the library tab."""
        # Get the music directory
        music_dir = self.settings.download_dir
        
        # Create a progress dialog
        progress_dialog = QMessageBox(self)
        progress_dialog.setWindowTitle("Scanning Music Library")
        progress_dialog.setText("Scanning music library...")
        progress_dialog.setStandardButtons(QMessageBox.StandardButton.Cancel)
        progress_dialog.show()
        QApplication.processEvents()
        
        # Start scanning in a background thread
        class LibraryScannerThread(QThread):
            finished = pyqtSignal(list)
            progress = pyqtSignal(int, int)
            error = pyqtSignal(str)
            
            def __init__(self, directory):
                super().__init__()
                self.directory = directory
                self.cancelled = False
            
            def run(self):
                try:
                    # Find music files
                    music_files = []
                    for root, dirs, files in os.walk(self.directory):
                        for file in files:
                            if self.cancelled:
                                return
                                
                            if file.lower().endswith(('.mp3', '.flac', '.wav', '.ogg', '.m4a')):
                                music_files.append(os.path.join(root, file))
                    
                    # Process files
                    music_data = []
                    for i, file_path in enumerate(music_files):
                        if self.cancelled:
                            return
                            
                        # Update progress every 10 files
                        if i % 10 == 0:
                            self.progress.emit(i, len(music_files))
                        
                        # Extract metadata
                        metadata = extract_file_metadata(file_path)
                        if metadata:
                            music_data.append(metadata)
                    
                    self.finished.emit(music_data)
                    
                except Exception as e:
                    self.error.emit(str(e))
        
        # Create scanner thread
        self.scanner_thread = LibraryScannerThread(music_dir)
        
        # Connect signals
        self.scanner_thread.finished.connect(lambda data: self._on_library_scan_finished(data, progress_dialog))
        self.scanner_thread.progress.connect(lambda i, total: progress_dialog.setText(f"Scanning music library... ({i}/{total})"))
        self.scanner_thread.error.connect(lambda err: self._on_library_scan_error(err, progress_dialog))
        
        # Connect cancel button
        progress_dialog.buttonClicked.connect(lambda: setattr(self.scanner_thread, 'cancelled', True))
        
        # Start thread
        self.scanner_thread.start()
        
    def _on_library_scan_finished(self, music_data, dialog):
        """Handle library scan completion."""
        # Close dialog
        dialog.accept()
        
        # Update library table
        self.update_library_table(music_data)
        
        # Show success message
        self.feedback_message.show_message(f"Found {len(music_data)} music files", FeedbackMessage.SUCCESS)
    
    def _on_library_scan_error(self, error_msg, dialog):
        """Handle library scan error."""
        # Close dialog
        dialog.accept()
        
        # Show error message
        self.feedback_message.show_message(f"Error scanning library: {error_msg}", FeedbackMessage.ERROR)

    def update_library_table(self, music_data):
        """Update the library table with scanned music data."""
        # Clear existing data
        self.downloaded_table.setRowCount(0)
        
        # Set up table
        self.downloaded_table.setRowCount(len(music_data))
        
        # Add data to table
        for row, data in enumerate(music_data):
            self.downloaded_table.setItem(row, 0, QTableWidgetItem(data.get('title', 'Unknown')))
            self.downloaded_table.setItem(row, 1, QTableWidgetItem(data.get('artist', 'Unknown')))
            self.downloaded_table.setItem(row, 2, QTableWidgetItem(data.get('album', 'Unknown')))
            self.downloaded_table.setItem(row, 3, QTableWidgetItem(data.get('duration', 'Unknown')))
            self.downloaded_table.setItem(row, 4, QTableWidgetItem(data.get('path', 'Unknown')))
        
        # Adjust columns
        self.downloaded_table.resizeColumnsToContents()
        
        # Add context menu to table
        self.downloaded_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.downloaded_table.customContextMenuRequested.connect(self.show_library_context_menu)

    def show_library_context_menu(self, position):
        """Show context menu for library items."""
        menu = QMenu()
        
        # Get selected row
        row = self.downloaded_table.rowAt(position.y())
        if row >= 0:
            # Play action
            play_action = QAction("Play", self)
            if QTA_AVAILABLE:
                play_action.setIcon(qta.icon('fa5s.play'))
            play_action.triggered.connect(lambda: self.play_library_item(row))
            menu.addAction(play_action)
            
            # Open folder action
            open_folder_action = QAction("Open Containing Folder", self)
            if QTA_AVAILABLE:
                open_folder_action.setIcon(qta.icon('fa5s.folder-open'))
            open_folder_action.triggered.connect(lambda: self.open_library_item_folder(row))
            menu.addAction(open_folder_action)
            
            # Show the menu
            menu.exec(self.downloaded_table.mapToGlobal(position))

    def play_library_item(self, row):
        """Play a library item."""
        path = self.downloaded_table.item(row, 4).text()
        if os.path.exists(path):
            try:
                if platform.system() == "Windows":
                    os.startfile(path)
                elif platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", path], check=True)
                else:  # Linux
                    subprocess.run(["xdg-open", path], check=True)
            except Exception as e:
                logger.error(f"Failed to play file: {str(e)}")
                self.feedback_message.show_message(f"Failed to play file: {str(e)}", FeedbackMessage.ERROR)
        else:
            self.feedback_message.show_message("File not found", FeedbackMessage.ERROR)

    def open_library_item_folder(self, row):
        """Open the folder containing a library item."""
        path = self.downloaded_table.item(row, 4).text()
        if os.path.exists(path):
            folder = os.path.dirname(path)
            try:
                if platform.system() == "Windows":
                    os.startfile(folder)
                elif platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", folder], check=True)
                else:  # Linux
                    subprocess.run(["xdg-open", folder], check=True)
            except Exception as e:
                logger.error(f"Failed to open folder: {str(e)}")
                self.feedback_message.show_message(f"Failed to open folder: {str(e)}", FeedbackMessage.ERROR)
        else:
            self.feedback_message.show_message("File not found", FeedbackMessage.ERROR)

    def open_log_file(self):
        """Open the application log file."""
        path = os.path.abspath(LOG_FILE)
        if os.path.exists(path):
            try:
                if platform.system() == "Windows":
                    os.startfile(path)
                elif platform.system() == "Darwin":
                    subprocess.run(["open", path], check=True)
                else:
                    subprocess.run(["xdg-open", path], check=True)
            except Exception as e:
                logger.error(f"Failed to open log file: {str(e)}")
                self.feedback_message.show_message(f"Failed to open log file: {str(e)}", FeedbackMessage.ERROR)
        else:
            self.feedback_message.show_message("Log file not found", FeedbackMessage.ERROR)


    def clear_layout(self, layout):
        """Clear all widgets from a layout."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                self.clear_layout(item.layout())

    def show_error(self, message):
        """Show an error message."""
        logger.error(message)
        QMessageBox.critical(self, "Error", message)
        self.feedback_message.show_message(message, FeedbackMessage.ERROR)

    def handle_task_completion(self, task_id, success, message):
        """Handle completion of background tasks."""
        if task_id.startswith("search_"):
            # Search completed
            if not success:
                self.feedback_message.show_message(f"Search failed: {message}", FeedbackMessage.ERROR)

    def next_tab(self):
        """Switch to the next tab."""
        current = self.tabs.currentIndex()
        if current < self.tabs.count() - 1:
            self.tabs.setCurrentIndex(current + 1)
        else:
            self.tabs.setCurrentIndex(0)

    def prev_tab(self):
        """Switch to the previous tab."""
        current = self.tabs.currentIndex()
        if current > 0:
            self.tabs.setCurrentIndex(current - 1)
        else:
            self.tabs.setCurrentIndex(self.tabs.count() - 1)
    def closeEvent(self, event):
        """Handle window close event."""
        # Bypass tray minimization if a full exit was requested
        if getattr(self, 'exit_requested', False):
            self.download_manager.shutdown()
            event.accept()
            return

        # If tray icon is enabled and window is being closed to tray
        if hasattr(self, 'tray_icon') and self.tray_icon.isVisible() and not QApplication.instance().isSavingSession():
            # Check if there are active downloads
            if self.download_manager.active_downloads:
                # Ask the user if they want to close or minimize to tray
                reply = QMessageBox.question(
                    self,
                    "Active Downloads",
                    "There are active downloads. What would you like to do?",
                    QMessageBox.StandardButton.Close | QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Minimize,
                    QMessageBox.StandardButton.Minimize,
                )

                if reply == QMessageBox.StandardButton.Close:
                    # Shutdown the download manager
                    self.download_manager.shutdown()

                    # Accept the event
                    event.accept()
                elif reply == QMessageBox.StandardButton.Minimize:
                    # Minimize to tray
                    self.hide()
                    if hasattr(self, 'show_action'):
                        self.show_action.setText('Show')
                    event.ignore()

                    # Show tray message if not already shown
                    if not hasattr(self, 'tray_message_shown'):
                        self.tray_icon.showMessage(
                            "YouTube Music Downloader",
                            "Application minimized to system tray. Downloads will continue in the background.",
                            QSystemTrayIcon.MessageIcon.Information,
                            3000,
                        )
                        self.tray_message_shown = True
                else:
                    # Cancel
                    event.ignore()
            else:
                # No active downloads, just minimize to tray
                self.hide()
                if hasattr(self, 'show_action'):
                    self.show_action.setText('Show')
                event.ignore()

                # Show tray message if not already shown
                if not hasattr(self, 'tray_message_shown'):
                    self.tray_icon.showMessage(
                        "YouTube Music Downloader",
                        "Application minimized to system tray.",
                        QSystemTrayIcon.MessageIcon.Information,
                        3000,
                    )
                    self.tray_message_shown = True
        else:
            # Shutdown the download manager
            self.download_manager.shutdown()

            # Accept the event
            event.accept()



# Utility functions

def create_default_icons():
    """Create default icons for the application if QtAwesome is not available."""
    global QTA_AVAILABLE
    # Create a resources directory if it doesn't exist
    if not os.path.exists(RESOURCES_DIR):
        try:
            os.makedirs(RESOURCES_DIR, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create resources directory: {e}")
            return

    # Create icons directory
    icons_dir = os.path.join(RESOURCES_DIR, "icons")
    if not os.path.exists(icons_dir):
        try:
            os.makedirs(icons_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create icons directory: {e}")
            return
            
    # If QtAwesome is available, we don't need default icons
    if QTA_AVAILABLE:
        logger.info("QtAwesome available, skipping default icon creation")
        return
        
    logger.info("Creating default icons")
    
    # Define icons we need as very simple pixmaps
    icons = {
        "cancel.png": (QPixmap(16, 16), QColor(255, 0, 0)),  # Red square for cancel
        "folder.png": (QPixmap(16, 16), QColor(0, 0, 255)),  # Blue square for folder
    }
    
    # Create simple square icons
    for filename, (pixmap, color) in icons.items():
        try:
            painter = QPainter(pixmap)
            painter.fillRect(0, 0, 16, 16, color)
            painter.end()
            
            icon_path = os.path.join(icons_dir, filename)
            pixmap.save(icon_path, "PNG")
            logger.debug(f"Created default icon: {icon_path}")
        except Exception as e:
            logger.error(f"Failed to create icon {filename}: {e}")


def extract_file_metadata(file_path):
    """Extract metadata from a music file."""
    if not os.path.exists(file_path):
        return None
    
    file_ext = os.path.splitext(file_path)[1].lower()
    
    metadata = {
        'path': file_path,
        'title': os.path.basename(file_path),
        'artist': 'Unknown',
        'album': 'Unknown',
        'duration': 'Unknown'
    }
    
    try:
        if MUTAGEN_AVAILABLE:
            if file_ext == '.mp3':
                audio = ID3(file_path)
                if 'TIT2' in audio:
                    metadata['title'] = str(audio['TIT2'])
                if 'TPE1' in audio:
                    metadata['artist'] = str(audio['TPE1'])
                if 'TALB' in audio:
                    metadata['album'] = str(audio['TALB'])
                
                # Get duration
                import mutagen.mp3
                mp3 = mutagen.mp3.MP3(file_path)
                if mp3.info.length:
                    mins = int(mp3.info.length // 60)
                    secs = int(mp3.info.length % 60)
                    metadata['duration'] = f"{mins}:{secs:02d}"
                
            elif file_ext == '.flac':
                audio = FLAC(file_path)
                if 'title' in audio:
                    metadata['title'] = str(audio['title'][0])
                if 'artist' in audio:
                    metadata['artist'] = str(audio['artist'][0])
                if 'album' in audio:
                    metadata['album'] = str(audio['album'][0])
                
                # Get duration
                if audio.info.length:
                    mins = int(audio.info.length // 60)
                    secs = int(audio.info.length % 60)
                    metadata['duration'] = f"{mins}:{secs:02d}"
                
            elif file_ext == '.ogg':
                audio = OggVorbis(file_path)
                if 'title' in audio:
                    metadata['title'] = str(audio['title'][0])
                if 'artist' in audio:
                    metadata['artist'] = str(audio['artist'][0])
                if 'album' in audio:
                    metadata['album'] = str(audio['album'][0])
                
                # Get duration
                if audio.info.length:
                    mins = int(audio.info.length // 60)
                    secs = int(audio.info.length % 60)
                    metadata['duration'] = f"{mins}:{secs:02d}"
                
            elif file_ext == '.m4a':
                audio = MP4(file_path)
                if '\xa9nam' in audio:
                    metadata['title'] = str(audio['\xa9nam'][0])
                if '\xa9ART' in audio:
                    metadata['artist'] = str(audio['\xa9ART'][0])
                if '\xa9alb' in audio:
                    metadata['album'] = str(audio['\xa9alb'][0])
                
                # Get duration
                if audio.info.length:
                    mins = int(audio.info.length // 60)
                    secs = int(audio.info.length % 60)
                    metadata['duration'] = f"{mins}:{secs:02d}"
        
        return metadata
    
    except Exception as e:
        logger.error(f"Error extracting metadata from {file_path}: {e}")
        return metadata


def sanitize_filename(filename):
    """Sanitize a filename by removing invalid characters."""
    if not filename:
        return "Unknown"
    
    # Replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove leading/trailing periods and spaces
    filename = filename.strip('. ')
    
    # Replace multiple spaces with a single space
    while '  ' in filename:
        filename = filename.replace('  ', ' ')
    
    # If the filename is empty after sanitization, use a default name
    if not filename:
        return "Unknown"
    
    return filename


def download_thumbnail(url):
    """Download a thumbnail image from a URL and return as QPixmap."""
    if not url:
        return QPixmap()
    
    try:
        # Check cache first
        cache_filename = os.path.join(CACHE_DIR, str(hashlib.md5(url.encode()).hexdigest()) + ".jpg")
        
        if os.path.exists(cache_filename):
            # Load from cache
            pixmap = QPixmap(cache_filename)
            if not pixmap.isNull():
                return pixmap
        
        # Download the image
        response = NetworkManager.request_with_retry(url, timeout=10)
        if response.status_code != 200:
            return QPixmap()
        
        # Create pixmap from image data
        pixmap = QPixmap()
        pixmap.loadFromData(response.content)
        
        if not pixmap.isNull():
            # Save to cache
            pixmap.save(cache_filename, "JPG")
            
            # Check and clean cache if needed
            CacheManager.clean_cache_if_needed()
            
            return pixmap
    except Exception as e:
        logger.error(f"Error downloading thumbnail: {e}")
    
    return QPixmap()


def save_pixmap_to_bytes(pixmap):
    """Convert a QPixmap to bytes."""
    if pixmap.isNull():
        return None
    
    # Use QByteArray instead of bytearray
    byte_array = QByteArray()
    buffer = QBuffer(byte_array)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "JPG")
    return byte_array.data()  # Return Python bytes object from QByteArray


def get_format_string(format_, quality="high"):
    """
    Get the yt-dlp format string with strict quality requirements for studio audio.
    Prioritizes official audio sources over video soundtracks.
    """
    # Base format focusing on official audio only, avoiding videos when possible
    base_format = "bestaudio[acodec!=opus]/bestaudio"
    
    # Quality tiers
    if quality == "high":
        # For high quality, require at least 256kbps when available
        if format_ == "mp3":
            return f"{base_format}[abr>=256]/bestaudio"
        elif format_ == "flac":
            return f"{base_format}[acodec=flac]/bestaudio"
        elif format_ == "wav":
            return f"{base_format}/bestaudio"
        elif format_ == "ogg":
            return f"{base_format}[acodec=vorbis]/bestaudio"
        elif format_ == "m4a":
            return f"bestaudio[ext=m4a][abr>=256]/{base_format}"
    elif quality == "medium":
        return f"{base_format}[abr>=192][abr<=256]/{base_format}"
    elif quality == "low":
        return f"{base_format}[abr>=128][abr<=192]/{base_format}"
    
    # Default fallback
    return base_format


def add_metadata(file_path, title, artist, album, track_number, year, genre, cover_data):
    """Add metadata to audio file using mutagen."""
    if not MUTAGEN_AVAILABLE:
        logger.warning("Mutagen not available. Skipping metadata.")
        return
    
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if ext == '.mp3':
            # ID3 (MP3) tags
            try:
                tags = ID3(file_path)
            except ID3NoHeaderError:
                tags = ID3()
            
            # Add basic metadata
            if title:
                tags["TIT2"] = TIT2(encoding=3, text=title)
            if artist:
                tags["TPE1"] = TPE1(encoding=3, text=artist)
            if album:
                tags["TALB"] = TALB(encoding=3, text=album)
            if track_number:
                tags["TRCK"] = TRCK(encoding=3, text=str(track_number))
            if year:
                tags["TDRC"] = TDRC(encoding=3, text=year)
            if genre:
                tags["TCON"] = TCON(encoding=3, text=genre)
            
            # Add cover art
            if cover_data:
                try:
                    # Ensure cover_data is bytes, not QByteArray
                    if not isinstance(cover_data, bytes):
                        cover_data = bytes(cover_data)
                    
                    tags["APIC"] = APIC(
                        encoding=3,
                        mime="image/jpeg",
                        type=3,  # Cover (front)
                        desc="Cover",
                        data=cover_data
                    )
                except Exception as e:
                    logger.warning(f"Failed to add cover art: {e}")
            
            tags.save(file_path)
            
        elif ext == '.flac':
            # FLAC tags
            audio = FLAC(file_path)
            
            # Add basic metadata
            if title:
                audio["TITLE"] = title
            if artist:
                audio["ARTIST"] = artist
            if album:
                audio["ALBUM"] = album
            if track_number:
                audio["TRACKNUMBER"] = str(track_number)
            if year:
                audio["DATE"] = year
            if genre:
                audio["GENRE"] = genre
            
            # Add cover art
            if cover_data:
                picture = Picture()
                picture.type = 3  # Cover (front)
                picture.mime = "image/jpeg"
                picture.desc = "Cover"
                picture.data = cover_data
                
                audio.add_picture(picture)
            
            audio.save()
            
        elif ext == '.ogg':
            # Ogg Vorbis tags
            audio = OggVorbis(file_path)
            
            # Add basic metadata
            if title:
                audio["TITLE"] = title
            if artist:
                audio["ARTIST"] = artist
            if album:
                audio["ALBUM"] = album
            if track_number:
                audio["TRACKNUMBER"] = str(track_number)
            if year:
                audio["DATE"] = year
            if genre:
                audio["GENRE"] = genre
            
            # Ogg doesn't support embedded covers through mutagen API
            
            audio.save()
            
        elif ext == '.m4a':
            # MP4 (AAC) tags
            audio = MP4(file_path)
            
            # Add basic metadata
            if title:
                audio["\xa9nam"] = [title]
            if artist:
                audio["\xa9ART"] = [artist]
            if album:
                audio["\xa9alb"] = [album]
            if track_number:
                audio["trkn"] = [(track_number, 0)]
            if year:
                audio["\xa9day"] = [year]
            if genre:
                audio["\xa9gen"] = [genre]
            
            # Add cover art
            if cover_data:
                audio["covr"] = [MP4Cover(cover_data, MP4Cover.FORMAT_JPEG)]
            
            audio.save()
    
    except Exception as e:
        logger.error(f"Error adding metadata: {e}")


def get_ytmusic():
    """Initialize and return a YTMusic client."""
    try:
        return YTMusic()
    except Exception as e:
        logger.error(f"Error initializing YTMusic API: {e}")
        raise


def extract_id_from_url(url: str) -> str:
    """Extract the YouTube ID from various URL formats."""
    # Extract video ID from watch URL
    video_match = re.search(r'watch\?v=([a-zA-Z0-9_-]+)', url)
    if video_match:
        return video_match.group(1)
    
    # Extract playlist ID
    playlist_match = re.search(r'list=([a-zA-Z0-9_-]+)', url)
    if playlist_match:
        return playlist_match.group(1)
    
    # Extract channel ID
    channel_match = re.search(r'channel/([a-zA-Z0-9_-]+)', url)
    if channel_match:
        return channel_match.group(1)
    
    # Extract browse ID (for albums)
    browse_match = re.search(r'browse/([a-zA-Z0-9_-]+)', url)
    if browse_match:
        return browse_match.group(1)
    
    # If we can't extract an ID, return the original ID
    return url


def format_duration(milliseconds: int) -> str:
    """Format milliseconds into a human-readable duration (MM:SS)."""
    if not milliseconds:
        return ""
    
    seconds = milliseconds // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    
    return f"{minutes}:{seconds:02d}"


def get_highest_res_thumbnail(thumbnails):
    """Get the highest resolution thumbnail URL from a list of thumbnails."""
    if not thumbnails:
        return ""
    
    # Sort thumbnails by width (descending) and take the first one
    sorted_thumbnails = sorted(thumbnails, key=lambda t: t.get('width', 0), reverse=True)
    return sorted_thumbnails[0]['url']


def search_youtube_music(query: str):
    """Search YouTube Music with preference for official releases and studio quality."""
    try:
        logger.info(f"Starting search with query: {query}")
        
        ytmusic = get_ytmusic()
        results = []
        
        # First, search for artists
        try:
            logger.info(f"Searching for artists matching: {query}")
            artist_results = ytmusic.search(query, filter="artists", limit=20)
            logger.info(f"Found {len(artist_results)} artist results")
            
            for artist in artist_results:
                if artist['category'] == 'Artists':
                    artist_obj = Artist(
                        id=artist['browseId'],
                        title=artist['artist'],
                        thumbnail_url=get_highest_res_thumbnail(artist['thumbnails']),
                        type=ContentType.ARTIST,
                        url=f"https://music.youtube.com/channel/{artist['browseId']}"
                    )
                    results.append(artist_obj)
        except Exception as e:
            logger.error(f"Error searching for artists: {e}")
        
        # Then, search for albums
        try:
            logger.info(f"Searching for albums matching: {query}")
            album_results = ytmusic.search(query, filter="albums", limit=20)
            logger.info(f"Found {len(album_results)} album results")
            
            for album in album_results:
                if album['category'] == 'Albums':
                    album_obj = Release(
                        id=album['browseId'],
                        title=album['title'],
                        artist=album['artists'][0]['name'] if album.get('artists') else "Various Artists",
                        thumbnail_url=get_highest_res_thumbnail(album['thumbnails']),
                        type=ContentType.RELEASE,
                        url=f"https://music.youtube.com/browse/{album['browseId']}",
                        year=album.get('year', ''),
                        release_type="album"
                    )
                    results.append(album_obj)
        except Exception as e:
            logger.error(f"Error searching for albums: {e}")
            
        # Search for singles
        try:
            logger.info(f"Searching for singles matching: {query}")
            single_results = ytmusic.search(query, filter="uploads", limit=10)  # Using uploads as a proxy for singles
            logger.info(f"Found {len(single_results)} potential single results")
            
            for single in single_results:
                if 'Single' in single.get('title', '') or 'EP' in single.get('title', ''):
                    single_obj = Release(
                        id=single.get('browseId', ''),
                        title=single.get('title', 'Unknown Single'),
                        artist=single.get('artists', [{'name': 'Unknown Artist'}])[0].get('name', 'Unknown Artist'),
                        thumbnail_url=get_highest_res_thumbnail(single.get('thumbnails', [])),
                        type=ContentType.RELEASE,
                        url=f"https://music.youtube.com/browse/{single.get('browseId', '')}",
                        release_type="single"
                    )
                    results.append(single_obj)
        except Exception as e:
            logger.error(f"Error searching for singles: {e}")
        
        logger.info(f"Found {len(results)} total results")
        return results
        
    except Exception as e:
        logger.error(f"Error searching YouTube Music: {e}")
        return []


def fetch_release_details(release_url, release_id):
    """
    Fetch details for a release (album or single) including its songs.
    
    Args:
        release_url: URL of the release
        release_id: ID of the release
        
    Returns:
        Dictionary with release details including songs list
    """
    try:
        logger.info(f"Fetching release details for: {release_id}")
        ytmusic = get_ytmusic()
        
        # Extract the proper ID if it's not already extracted
        release_id = extract_id_from_url(release_id)
        
        # Fetch release details
        release_details = ytmusic.get_album(release_id)
        
        # Extract release information
        release_title = release_details.get('title', 'Unknown Release')
        release_artist = release_details.get('artists', [{}])[0].get('name', 'Unknown Artist')
        release_year = release_details.get('year', '')
        release_type = "single" if "Single" in release_title or "EP" in release_title else "album"
        
        # Get release thumbnail
        release_thumbnail = ""
        if release_details.get('thumbnails'):
            release_thumbnail = get_highest_res_thumbnail(release_details.get('thumbnails', []))
        
        logger.info(f"Release info fetched: {release_title} by {release_artist} ({release_year})")
        logger.info(f"Found {len(release_details.get('tracks', []))} tracks")
        
        # Create song objects from tracks
        songs = []
        for i, track in enumerate(release_details.get('tracks', [])):
            try:
                # Some tracks might not have video IDs (podcast episodes, etc.)
                video_id = track.get('videoId', '')
                if not video_id:
                    video_id = f"song_{release_id}_{i}"  # Fallback ID
                
                # Get artist from track, or fall back to release artist
                artist_name = release_artist
                if track.get('artists') and len(track['artists']) > 0:
                    artist_name = track['artists'][0].get('name', release_artist)
                
                # Format duration properly
                duration = ""
                if 'duration_seconds' in track:
                    mins = track['duration_seconds'] // 60
                    secs = track['duration_seconds'] % 60
                    duration = f"{mins}:{secs:02d}"
                
                # Create song object
                song = Song(
                    id=video_id,
                    title=track.get('title', f"Track {i+1}"),
                    artist=artist_name,
                    album=release_title,
                    thumbnail_url=release_thumbnail,
                    type=ContentType.SONG,
                    url=f"https://music.youtube.com/watch?v={video_id}" if video_id and video_id != f"song_{release_id}_{i}" else release_url,
                    video_id=video_id if video_id != f"song_{release_id}_{i}" else "",
                    duration=duration,
                    track_number=i+1,
                    year=release_year,
                    genre="",  # No genre info available from the API
                    selected=True  # Default to selected
                )
                songs.append(song)
                logger.debug(f"Added track: {song.title}")
                
            except Exception as e:
                logger.error(f"Error creating track object: {str(e)}")
        
        return {
            "songs": songs,
            "year": release_year
        }
        
    except Exception as e:
        logger.error(f"Error fetching release details: {str(e)}")
        # Return empty result on error
        return {"songs": [], "year": ""}


def fetch_better_release_artwork(release_title, artist_name):
    """
    Attempt to fetch official release artwork from reliable sources.
    Falls back to YouTube thumbnail if not found.
    """
    try:
        # Build query for iTunes Search API
        query = f"{release_title} {artist_name}"
        params = {
            "term": query,
            "entity": "album",
            "limit": 5
        }

        response = NetworkManager.request_with_retry(
            "https://itunes.apple.com/search", params=params, timeout=10
        )
        if response.status_code != 200:
            return None

        results = response.json().get("results", [])
        release_lower = release_title.lower()
        artist_lower = artist_name.lower()

        for r in results:
            album = r.get("collectionName", "").lower()
            artist = r.get("artistName", "").lower()
            if release_lower in album and artist_lower in artist:
                artwork = r.get("artworkUrl100")
                if artwork:
                    return artwork.replace("100x100bb", "600x600bb")

        # Fallback to first result if nothing matches perfectly
        if results:
            artwork = results[0].get("artworkUrl100")
            if artwork:
                return artwork.replace("100x100bb", "600x600bb")

    except Exception as e:
        logger.warning(f"Failed to fetch better release art: {e}")

    return None


def fetch_artist_details(artist_url, artist_id):
    """
    Fetch details for an artist including their releases.
    
    Args:
        artist_url: URL of the artist
        artist_id: ID of the artist
        
    Returns:
        Dictionary with artist details including releases list
    """
    try:
        logger.info(f"Fetching artist details for: {artist_id}")
        ytmusic = get_ytmusic()
        
        # Extract the proper ID if it's not already extracted
        artist_id = extract_id_from_url(artist_id)
        
        # Fetch artist details
        artist_details = ytmusic.get_artist(artist_id)
        
        # Extract artist name and thumbnail
        artist_name = artist_details.get('name', 'Unknown Artist')
        artist_thumbnail = get_highest_res_thumbnail(artist_details.get('thumbnails', []))
        
        logger.info(f"Artist info fetched: {artist_name}")
        
        # Create release objects from the albums section
        releases = []
        
        # Check both "albums" and "singles" sections
        if 'albums' in artist_details and 'results' in artist_details['albums']:
            for section in artist_details['albums']['results']:
                # Create Release object
                release = Release(
                    id=section.get('browseId', f"album_{artist_id}_{len(releases)}"),
                    title=section.get('title', f"Album {len(releases)+1}"),
                    artist=artist_name,
                    thumbnail_url=get_highest_res_thumbnail(section.get('thumbnails', [])),
                    type=ContentType.RELEASE,
                    url=f"https://music.youtube.com/browse/{section.get('browseId')}",
                    year=section.get('year', ''),
                    release_type="album"
                )
                releases.append(release)
                logger.debug(f"Added album: {release.title}")
        
        # Also check singles if available
        if 'singles' in artist_details and 'results' in artist_details['singles']:
            for section in artist_details['singles']['results']:
                # Create Release object (singles are a type of release)
                release = Release(
                    id=section.get('browseId', f"album_{artist_id}_{len(releases)}"),
                    title=section.get('title', f"Single {len(releases)+1}"),
                    artist=artist_name,
                    thumbnail_url=get_highest_res_thumbnail(section.get('thumbnails', [])),
                    type=ContentType.RELEASE,
                    url=f"https://music.youtube.com/browse/{section.get('browseId')}",
                    year=section.get('year', ''),
                    release_type="single"
                )
                releases.append(release)
                logger.debug(f"Added single: {release.title}")
        
        logger.info(f"Found {len(releases)} releases")
        return {
            "releases": releases
        }
        
    except Exception as e:
        logger.error(f"Error fetching artist details: {str(e)}")
        # Return empty result on error
        return {"releases": []}


def main():
    """Main application entry point."""
    # Create QApplication FIRST
    app = QApplication(sys.argv)
    
    # Set application name and organization for settings
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("lolitemaultes")
    
    # Setup logging - doesn't use any Qt objects, so this is fine here
    try:
        logger.setLevel(logging.INFO)
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
        
        # Also add a console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logger.addHandler(console_handler)
        
        logger.info(f"Starting {APP_NAME} v{APP_VERSION}")
    except Exception as e:
        print(f"Error setting up logging: {e}")
    
    # Create default icons AFTER QApplication is initialized
    create_default_icons()
    
    # Load and apply stylesheet
    try:
        DarkTheme.apply_to(app, DEFAULT_ACCENT_COLOR)
    except Exception as e:
        logger.error(f"Error applying stylesheet: {e}")
    
    # Check for yt-dlp
    try:
        # First try direct command
        try:
            subprocess.run(
                ["yt-dlp", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            logger.info("yt-dlp found successfully!")
        except (subprocess.SubprocessError, FileNotFoundError):
            # Try python module approach as fallback
            result = subprocess.run(
                [sys.executable, "-m", "yt_dlp", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            if result.returncode != 0:
                raise FileNotFoundError("yt-dlp module not found")
            logger.info("yt-dlp module found successfully!")
    except Exception as e:
        # Show detailed error message
        error_message = (
            f"Error finding yt-dlp: {str(e)}\n\n"
            "yt-dlp is required for this application to work.\n\n"
            "Please make sure it's installed correctly:\n"
            "1. Install with: pip install yt-dlp\n"
            "2. Verify it's in the same Python environment as this app\n"
            "3. Try running 'yt-dlp --version' from command line\n\n"
            "You can continue, but downloads will not work until yt-dlp is available."
        )
        
        choice = QMessageBox.critical(
            None,
            "yt-dlp Detection Error",
            error_message,
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        
        if choice == QMessageBox.StandardButton.Cancel:
            return 1
    
    # Check for mutagen if not already available
    global MUTAGEN_AVAILABLE
    if not MUTAGEN_AVAILABLE:
        try:
            # Ask user if they want to install mutagen
            choice = QMessageBox.question(
                None,
                "Mutagen Not Found",
                "Mutagen library is not installed. This is required for proper metadata tagging of music files.\n\n"
                "Would you like to install it now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if choice == QMessageBox.StandardButton.Yes:
                try:
                    # Install mutagen
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install", "mutagen"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True
                    )
                    
                    # Try importing again
                    from mutagen.easyid3 import EasyID3
                    from mutagen.id3 import ID3, APIC, ID3NoHeaderError, TIT2, TPE1, TALB, TRCK, TDRC, TCON
                    from mutagen.flac import FLAC, Picture
                    from mutagen.oggvorbis import OggVorbis
                    from mutagen.mp4 import MP4, MP4Cover
                    
                    MUTAGEN_AVAILABLE = True
                    logger.info("Mutagen installed successfully")
                    
                    QMessageBox.information(
                        None,
                        "Mutagen Installed", 
                        "Mutagen has been installed successfully. Metadata tagging will be available."
                    )
                except Exception as e:
                    logger.error(f"Failed to install mutagen: {e}")
                    QMessageBox.warning(
                        None,
                        "Installation Failed",
                        f"Failed to install mutagen: {str(e)}\n\n"
                        "You can continue, but metadata tagging will be limited."
                    )
            else:
                # Show warning about missing mutagen
                QMessageBox.warning(
                    None,
                    "Limited Metadata Support",
                    "Without mutagen, metadata tagging will be limited.\n\n"
                    "You can install it later with: pip install mutagen"
                )
        except Exception as e:
            logger.error(f"Error handling mutagen installation: {e}")
        
    # Create and show the main window
    window = MainWindow()
    window.show()
    
    # Run the application
    return app.exec()

    # Create and show the main window
    window = MainWindow()
    window.show()
    
    # Run the application
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
