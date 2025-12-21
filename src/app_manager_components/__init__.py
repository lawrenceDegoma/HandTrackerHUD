"""
App Manager Components Package

Specialized components for UI rendering, media player interface, and window management.
"""

from .ui_components import TextRenderer
from .miniplayer import SpotifyMiniplayer, AlbumArtCache
from .window_capture import WindowCapture, FrameOverlay

__all__ = [
    'TextRenderer',
    'SpotifyMiniplayer',
    'AlbumArtCache',
    'WindowCapture',
    'FrameOverlay'
]
