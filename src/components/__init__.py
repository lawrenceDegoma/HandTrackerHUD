"""
Components Package

This package contains specialized components for the Hand Tracker application:
- ui_components: Text rendering and UI utilities
- miniplayer: Spotify miniplayer interface
- window_capture: Window capturing and overlay functionality
- gesture_recognition: Hand gesture detection and recognition
- quad_manager: Quad creation, manipulation, and tracking
- volume_control: Volume gesture handling and Spotify volume control
"""

from .ui_components import TextRenderer, format_time
from .miniplayer import SpotifyMiniplayer, AlbumArtCache
from .window_capture import WindowCapture, FrameOverlay
from .gesture_recognition import GestureRecognizer, CloseGestureDetector
from .quad_manager import QuadManager
from .volume_control import VolumeController

__all__ = [
    'TextRenderer',
    'format_time', 
    'SpotifyMiniplayer',
    'AlbumArtCache',
    'WindowCapture',
    'FrameOverlay',
    'GestureRecognizer',
    'CloseGestureDetector',
    'QuadManager',
    'VolumeController'
]
