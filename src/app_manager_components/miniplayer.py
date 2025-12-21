"""
Spotify Miniplayer Renderer

This module handles rendering the Spotify miniplayer interface with
album artwork, track information, controls, and progress display.
"""

import cv2
import numpy as np
import requests
import time
from .ui_components import TextRenderer, format_time


class AlbumArtCache:
    """Manages caching of album artwork to avoid repeated downloads."""
    
    def __init__(self):
        self.cache = {}
    
    def get_album_artwork(self, album_art_url, size=(130, 130)):
        """Download and cache album artwork from Spotify URL."""
        if not album_art_url:
            return None
            
        # Check cache first
        cache_key = f"{album_art_url}_{size[0]}x{size[1]}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            # Download image
            response = requests.get(album_art_url, timeout=5)
            response.raise_for_status()
            
            # Convert to OpenCV format
            image_array = np.frombuffer(response.content, np.uint8)
            img = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            
            if img is not None:
                # Resize to fit album area
                img = cv2.resize(img, size, interpolation=cv2.INTER_AREA)
                
                # Cache the result
                self.cache[cache_key] = img
                
                return img
                
        except Exception as e:
            print(f"Error downloading album artwork: {e}")
            return None
        
        return None


class SpotifyMiniplayer:
    """Renders the Spotify miniplayer interface."""
    
    def __init__(self):
        self.text_renderer = TextRenderer()
        self.album_art_cache = AlbumArtCache()
    
    def draw_miniplayer_image(self, track_info, size=(400, 150), volume=None, opacity=1.0):
        """Draw a miniplayer with track info and controls.
        
        Args:
            track_info: Dictionary containing track information
            size: Tuple of (width, height) for the miniplayer
            volume: Current volume level (0-100)
            opacity: Opacity value between 0.0 (fully transparent) and 1.0 (fully opaque)
        """
        w, h = size  # width, height
        
        # Create background with gradient
        img = np.ones((h, w, 3), dtype=np.uint8) * 20  # Dark background
        
        # Add subtle gradient background
        for y in range(h):
            intensity = int(20 + (y / h) * 15)  # Gradient from 20 to 35
            img[y, :] = [intensity, intensity, intensity]
        
        # Add rounded corner effect (simple version)
        corner_radius = 15
        cv2.rectangle(img, (0, 0), (w, corner_radius), (0, 0, 0), -1)
        cv2.rectangle(img, (0, h-corner_radius), (w, h), (0, 0, 0), -1)
        cv2.rectangle(img, (0, 0), (corner_radius, h), (0, 0, 0), -1)
        cv2.rectangle(img, (w-corner_radius, 0), (w, h), (0, 0, 0), -1)
        
        # Draw album artwork
        self._draw_album_artwork(img, track_info, h)
        
        # Draw track information
        self._draw_track_info(img, track_info, h, w)
        
        # Draw progress bar
        self._draw_progress_bar(img, track_info, h, w)
        
        # Draw control buttons
        self._draw_control_buttons(img, w, h)
        
        # Draw volume indicator
        if volume is not None:
            self._draw_volume_indicator(img, volume, w, h)
        
        # Apply opacity if specified
        if opacity < 1.0:
            opacity = max(0.0, min(1.0, opacity))  # Clamp between 0.0 and 1.0
            img = img.astype(np.float32)
            img = img * opacity
            img = img.astype(np.uint8)
        
        return img
    
    def _draw_album_artwork(self, img, track_info, h):
        """Draw album artwork on the left side of the miniplayer."""
        album_size = h - 20  # Leave 10px margin on top/bottom
        album_x, album_y = 10, 10
        
        # Try to get real album artwork
        album_art = None
        if track_info and 'album_art' in track_info:
            album_art = self.album_art_cache.get_album_artwork(track_info['album_art'], (album_size, album_size))
        
        if album_art is not None:
            # Draw the actual album artwork
            img[album_y:album_y + album_size, album_x:album_x + album_size] = album_art
            
            # Add a subtle border
            cv2.rectangle(img, (album_x, album_y), (album_x + album_size, album_y + album_size), (80, 80, 80), 2)
        else:
            # Fallback to placeholder with modern style
            cv2.rectangle(img, (album_x, album_y), (album_x + album_size, album_y + album_size), (60, 60, 60), -1)
            cv2.rectangle(img, (album_x + 2, album_y + 2), (album_x + album_size - 2, album_y + album_size - 2), (80, 80, 80), 2)
            
            # Add music note icon in album area
            center_x, center_y = album_x + album_size // 2, album_y + album_size // 2
            cv2.circle(img, (center_x, center_y), 20, (150, 150, 150), -1)
            cv2.putText(img, "♪", (center_x - 8, center_y + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (220, 220, 220), 2)
    
    def _draw_track_info(self, img, track_info, h, w):
        """Draw track title and artist information."""
        album_size = h - 20
        info_x = 10 + album_size + 20  # After album artwork + margin
        info_width = w - info_x - 40  # Leave space for controls on right
        
        # Track title
        if track_info and 'name' in track_info:
            clean_name = self.text_renderer.clean_text_for_display(track_info['name'])
            title = clean_name
        else:
            title = "No track playing"
        
        # Artist name
        if track_info and 'artist' in track_info:
            clean_artist = self.text_renderer.clean_text_for_display(track_info['artist'])
            artist = clean_artist
        else:
            artist = "Unknown artist"
        
        # Draw track info with scrolling text
        title_max_width = info_width - 10  # Leave some padding
        artist_max_width = info_width - 10
        
        # Use scrolling text for title and artist
        album_y = 10
        self.text_renderer.draw_scrolling_text(img, title, "title", info_x, album_y + 25, title_max_width, 0.6, (255, 255, 255), 2)
        self.text_renderer.draw_scrolling_text(img, artist, "artist", info_x, album_y + 50, artist_max_width, 0.5, (180, 180, 180), 1)
    
    def _draw_progress_bar(self, img, track_info, h, w):
        """Draw the progress bar and time indicators."""
        album_size = h - 20
        info_x = 10 + album_size + 20
        info_width = w - info_x - 40
        progress_y = 10 + album_size // 2 + 35  # Position below track info
        progress_width = info_width - 20  # Leave some margin
        
        # Calculate real progress and times
        current_time = 0
        total_time = 180  # Default 3:00 if no track info
        progress = 0.0
        
        if track_info:
            # Get progress from track_info if available
            if 'progress_ms' in track_info and 'duration_ms' in track_info:
                current_time = track_info['progress_ms'] // 1000  # Convert to seconds
                total_time = track_info['duration_ms'] // 1000
                if total_time > 0:
                    progress = min(current_time / total_time, 1.0)
            elif 'progress_percentage' in track_info:
                progress = track_info['progress_percentage'] / 100.0
                current_time = int(progress * total_time)
        
        # Background progress bar
        cv2.rectangle(img, (info_x, progress_y), (info_x + progress_width, progress_y + 4), (60, 60, 60), -1)
        
        # Filled progress
        filled_width = int(progress_width * progress)
        if filled_width > 0:
            cv2.rectangle(img, (info_x, progress_y), (info_x + filled_width, progress_y + 4), (30, 215, 96), -1)  # Spotify green
        
        # Time indicators with real values
        current_time_str = format_time(current_time)
        total_time_str = format_time(total_time)
        
        cv2.putText(img, current_time_str, (info_x, progress_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
        cv2.putText(img, total_time_str, (info_x + progress_width - 25, progress_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
    
    def _draw_control_buttons(self, img, w, h):
        """Draw the previous, play/pause, and next control buttons."""
        controls_x = w - 110
        button_y = h // 2
        button_spacing = 45
        button_radius = 15
        
        # Previous button
        prev_x = controls_x - button_spacing
        cv2.circle(img, (prev_x, button_y), button_radius, (70, 70, 70), -1)
        cv2.circle(img, (prev_x, button_y), button_radius - 1, (90, 90, 90), 2)
        # Previous icon (triangles)
        cv2.line(img, (prev_x - 5, button_y), (prev_x - 2, button_y - 5), (220, 220, 220), 2)
        cv2.line(img, (prev_x - 5, button_y), (prev_x - 2, button_y + 5), (220, 220, 220), 2)
        cv2.line(img, (prev_x + 1, button_y), (prev_x + 4, button_y - 5), (220, 220, 220), 2)
        cv2.line(img, (prev_x + 1, button_y), (prev_x + 4, button_y + 5), (220, 220, 220), 2)
        
        # Play/Pause button (larger)
        play_radius = 18
        cv2.circle(img, (controls_x, button_y), play_radius, (30, 215, 96), -1)  # Spotify green
        cv2.circle(img, (controls_x, button_y), play_radius - 1, (40, 230, 110), 2)
        # Play icon (triangle)
        triangle_points = np.array([[controls_x - 6, button_y - 8], [controls_x - 6, button_y + 8], [controls_x + 6, button_y]], np.int32)
        cv2.fillPoly(img, [triangle_points], (255, 255, 255))
        
        # Next button
        next_x = controls_x + button_spacing
        cv2.circle(img, (next_x, button_y), button_radius, (70, 70, 70), -1)
        cv2.circle(img, (next_x, button_y), button_radius - 1, (90, 90, 90), 2)
        # Next icon (triangles)
        cv2.line(img, (next_x + 5, button_y), (next_x + 2, button_y - 5), (220, 220, 220), 2)
        cv2.line(img, (next_x + 5, button_y), (next_x + 2, button_y + 5), (220, 220, 220), 2)
        cv2.line(img, (next_x - 1, button_y), (next_x - 4, button_y - 5), (220, 220, 220), 2)
        cv2.line(img, (next_x - 1, button_y), (next_x - 4, button_y + 5), (220, 220, 220), 2)
    
    def _draw_volume_indicator(self, img, volume, w, h):
        """Draw the volume indicator in the bottom right."""
        vol_x = w - 60
        vol_y = h - 25
        vol_width = 50
        vol_height = 6
        
        # Volume background
        cv2.rectangle(img, (vol_x, vol_y), (vol_x + vol_width, vol_y + vol_height), (60, 60, 60), -1)
        
        # Volume fill
        vol_fill = int(vol_width * (volume / 100))
        if volume > 70:
            vol_color = (50, 50, 255)  # Red for high volume
        elif volume > 30:
            vol_color = (50, 200, 255)  # Orange for medium
        else:
            vol_color = (50, 255, 50)  # Green for low
        
        cv2.rectangle(img, (vol_x, vol_y), (vol_x + vol_fill, vol_y + vol_height), vol_color, -1)
        
        # Volume icon
        cv2.putText(img, "♪", (vol_x - 15, vol_y + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)
        
        # Volume percentage
        cv2.putText(img, f"{volume}%", (vol_x + 5, vol_y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (200, 200, 200), 1)
