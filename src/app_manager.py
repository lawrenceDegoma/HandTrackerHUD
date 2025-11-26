import cv2
import numpy as np
import Quartz
import math
import requests
from io import BytesIO
import unicodedata
import time
from utils import get_current_track, toggle_play_pause, next_track, previous_track

class AppManager:
    def __init__(self):
        self.current_app = None
        self.album_art_cache = {}  # Cache for album artwork
        self.scroll_state = {}  # Track scrolling state for each text field

    def spawn_app(self, name: str):
        self.current_app = name
        print(f"AppManager: spawned {name}")

    def close_app(self):
        print(f"AppManager: closed {self.current_app}")
        self.current_app = None

    def handle_command(self, cmd: str, tracker=None):
        """Handle a voice command string and act on tracker or Spotify."""
        text = (cmd or "").lower().strip()
        print(f"AppManager handling command: {text}")

        # If there is no text (or empty) but tracker requested a spawn, use that; otherwise default to Spotify.
        if text == "":
            if tracker is not None and getattr(tracker, 'spawned_app', None):
                name = tracker.spawned_app
            else:
                name = 'Spotify'
            self.spawn_app(name)
            if tracker is not None:
                tracker.spawn_miniplayer(name)
            return

        # support generic open/spawn with optional target; default to Spotify
        if text.startswith('open') or text.startswith('spawn'):
            parts = text.split()
            # if user only said 'open' or 'spawn', default to Spotify
            if len(parts) == 1:
                name = 'Spotify'
            else:
                # e.g. 'open spotify' or 'spawn youtube'
                name = ' '.join(parts[1:]).strip().title()
            self.spawn_app(name)
            if tracker is not None:
                tracker.spawn_miniplayer(name)
            return

        if "close spotify" in text or "hide spotify" in text:
            self.close_app()
            if tracker is not None:
                tracker.spawned_app = None
                tracker.toggle_quad()
        elif "play" in text and "pause" not in text:
            toggle_play_pause()
        elif "pause" in text:
            toggle_play_pause()
        elif "next" in text:
            next_track()
        elif "previous" in text or "prev" in text:
            previous_track()
        elif "volume mode" in text or "volume gesture" in text:
            if tracker is not None:
                tracker.volume_gesture_enabled = not tracker.volume_gesture_enabled
                print("Volume gesture mode:", tracker.volume_gesture_enabled)
        else:
            print("AppManager: unrecognized command")

    def get_album_artwork(self, album_art_url, size=(130, 130)):
        """Download and cache album artwork from Spotify URL."""
        if not album_art_url:
            return None
            
        # Check cache first
        cache_key = f"{album_art_url}_{size[0]}x{size[1]}"
        if cache_key in self.album_art_cache:
            return self.album_art_cache[cache_key]
        
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
                self.album_art_cache[cache_key] = img
                
                return img
                
        except Exception as e:
            print(f"Error downloading album artwork: {e}")
            return None
        
        return None

    def clean_text_for_display(self, text):
        """Clean text to handle Unicode characters properly for OpenCV display."""
        if not text:
            return ""
        
        # Replace common problematic Unicode characters
        replacements = {
            '\u2019': "'",  # Right single quotation mark
            '\u2018': "'",  # Left single quotation mark
            '\u201c': '"',  # Left double quotation mark
            '\u201d': '"',  # Right double quotation mark
            '\u2013': '-',  # En dash
            '\u2014': '-',  # Em dash
            '\u2026': '...',  # Horizontal ellipsis
            '\u00e9': 'e',  # é
            '\u00e8': 'e',  # è
            '\u00ea': 'e',  # ê
            '\u00e1': 'a',  # á
            '\u00e0': 'a',  # à
            '\u00f1': 'n',  # ñ
            '\u00fc': 'u',  # ü
            '\u00f6': 'o',  # ö
            '\u00e4': 'a',  # ä
        }
        
        # Apply replacements
        for unicode_char, replacement in replacements.items():
            text = text.replace(unicode_char, replacement)
        
        # Normalize Unicode characters and remove any remaining non-ASCII characters
        try:
            # Normalize to decomposed form, then remove combining characters
            text = unicodedata.normalize('NFKD', text)
            # Keep only ASCII characters
            text = text.encode('ascii', 'ignore').decode('ascii')
        except Exception:
            # Fallback: remove any non-printable characters
            text = ''.join(char for char in text if ord(char) < 128 and char.isprintable())
        
        return text

    def get_scrolling_text(self, text, field_name, max_width, font_scale=0.6):
        """Handle horizontal scrolling text for long titles/artists."""
        if not text:
            return text, 0
        
        # Calculate text width
        (text_width, text_height), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 2)
        
        # If text fits within the available space, no scrolling needed
        if text_width <= max_width:
            # Reset scroll state if text fits
            if field_name in self.scroll_state:
                del self.scroll_state[field_name]
            return text, 0
        
        # Initialize scroll state for this field if not exists
        if field_name not in self.scroll_state:
            self.scroll_state[field_name] = {
                'start_time': time.time(),
                'text': text,
                'pause_start': 0,
                'pause_end': 2.0,  # Pause at start for 2 seconds
                'scroll_speed': 30,  # pixels per second
                'text_width': text_width,
                'max_width': max_width
            }
        
        state = self.scroll_state[field_name]
        current_time = time.time()
        elapsed_time = current_time - state['start_time']
        
        # If text changed, reset the scroll state
        if state['text'] != text:
            state['start_time'] = current_time
            state['text'] = text
            state['text_width'] = text_width
            state['pause_start'] = 0
            state['pause_end'] = 2.0
            elapsed_time = 0
        
        # Phase 1: Pause at start (show beginning of text)
        if elapsed_time <= state['pause_end']:
            return text, 0
        
        # Phase 2: Scroll from right to left
        scroll_duration = (state['text_width'] - state['max_width'] + 40) / state['scroll_speed']  # +40 for spacing
        scroll_phase_end = state['pause_end'] + scroll_duration
        
        if elapsed_time <= scroll_phase_end:
            # Calculate scroll offset
            scroll_progress = (elapsed_time - state['pause_end']) / scroll_duration
            scroll_offset = -int(scroll_progress * (state['text_width'] - state['max_width'] + 40))
            return text, scroll_offset
        
        # Phase 3: Pause at end (show end of text)
        pause_at_end = 1.5
        if elapsed_time <= scroll_phase_end + pause_at_end:
            scroll_offset = -(state['text_width'] - state['max_width'] + 40)
            return text, scroll_offset
        
        # Phase 4: Reset and start over
        state['start_time'] = current_time
        return text, 0

    def draw_scrolling_text(self, img, text, field_name, x, y, max_width, font_scale, color, thickness=2):
        """Draw text with horizontal scrolling if it's too long."""
        display_text, scroll_offset = self.get_scrolling_text(text, field_name, max_width, font_scale)
        
        if scroll_offset == 0:
            # No scrolling needed or at start position
            cv2.putText(img, display_text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
        else:
            # Create a temporary image for the scrolling text
            temp_img = np.zeros_like(img)
            
            # Draw text with offset on temporary image
            text_x = x + scroll_offset
            cv2.putText(temp_img, display_text, (text_x, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
            
            # Create a mask for the clipping region
            mask = np.zeros(img.shape[:2], dtype=np.uint8)
            cv2.rectangle(mask, (x, y-25), (x+max_width, y+5), 255, -1)
            
            # Apply the mask to the temporary image
            temp_img_masked = cv2.bitwise_and(temp_img, temp_img, mask=mask)
            
            # Clear the text area on the original image
            img_mask_inv = cv2.bitwise_not(mask)
            img_cleared = cv2.bitwise_and(img, img, mask=img_mask_inv)
            
            # Combine the cleared original with the masked text
            img[:] = cv2.add(img_cleared, temp_img_masked)
        
        return img

    def capture_window(self, window_title):
        try:
            window_list = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID
            )
        except Exception:
            return None
        for window in window_list:
            owner = window.get('kCGWindowOwnerName', '')
            name = window.get('kCGWindowName', '')
            if owner == window_title or name == window_title:
                bounds = window.get('kCGWindowBounds')
                if not bounds:
                    continue
                x, y, w, h = int(bounds['X']), int(bounds['Y']), int(bounds['Width']), int(bounds['Height'])
                image = Quartz.CGWindowListCreateImage(
                    Quartz.CGRectMake(x, y, w, h),
                    Quartz.kCGWindowListOptionIncludingWindow,
                    window['kCGWindowNumber'],
                    Quartz.kCGWindowImageDefault,
                )
                if image:
                    width = Quartz.CGImageGetWidth(image)
                    height = Quartz.CGImageGetHeight(image)
                    bytes_per_row = Quartz.CGImageGetBytesPerRow(image)
                    data_provider = Quartz.CGImageGetDataProvider(image)
                    data = Quartz.CGDataProviderCopyData(data_provider)
                    arr = np.frombuffer(data, dtype=np.uint8)
                    arr = arr.reshape((height, bytes_per_row // 4, 4))
                    img = arr[:, :w, :3][:, :, ::-1].copy()
                    return img
        return None

    def _warp_and_overlay(self, frame, content_img, dst_pts, opacity=1.0):
        if content_img is None:
            return frame
        h, w, _ = content_img.shape
        src_pts = np.float32([[0,0],[w,0],[w,h],[0,h]])
        dst_pts_f = np.float32(dst_pts)
        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts_f)
        warped = cv2.warpPerspective(content_img, matrix, (frame.shape[1], frame.shape[0]))
        mask = np.zeros_like(frame, dtype=np.uint8)
        cv2.fillConvexPoly(mask, np.int32(dst_pts_f), (255,255,255))
        
        # Apply opacity blending if specified
        if opacity < 1.0:
            # Create the region where we'll blend
            masked_frame = cv2.bitwise_and(frame, cv2.bitwise_not(mask))
            masked_warped = cv2.bitwise_and(warped, mask)
            
            # Apply opacity to the warped content
            masked_warped = masked_warped.astype(np.float32) * opacity
            masked_warped = masked_warped.astype(np.uint8)
            
            # Get the background in the warped region
            background_region = cv2.bitwise_and(frame, mask)
            background_region = background_region.astype(np.float32) * (1.0 - opacity)
            background_region = background_region.astype(np.uint8)
            
            # Combine background and foreground with opacity
            blended_region = cv2.add(masked_warped, background_region)
            frame = cv2.add(masked_frame, blended_region)
        else:
            # Original behavior for full opacity
            frame = cv2.bitwise_and(frame, cv2.bitwise_not(mask))
            frame = cv2.add(frame, warped)
        
        return frame

    def draw_miniplayer_image(self, track_info, size=(400, 150), volume=None, opacity=1.0):
        """Draw a miniplayer with track info and controls.
        
        Args:
            opacity (float): Opacity value between 0.0 (fully transparent) and 1.0 (fully opaque)
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
        
        # Album artwork area (left side)
        album_size = h - 20  # Leave 10px margin on top/bottom
        album_x, album_y = 10, 10
        
        # Try to get real album artwork
        album_art = None
        if track_info and 'album_art' in track_info:
            album_art = self.get_album_artwork(track_info['album_art'], (album_size, album_size))
        
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
        
        # Track info area (middle section)
        info_x = album_x + album_size + 20
        info_width = w - info_x - 40  # Leave space for controls on right
        
        # Track title
        if track_info and 'name' in track_info:
            clean_name = self.clean_text_for_display(track_info['name'])
            title = clean_name  # Don't truncate, let scrolling handle it
        else:
            title = "No track playing"
        
        # Artist name
        if track_info and 'artist' in track_info:
            clean_artist = self.clean_text_for_display(track_info['artist'])
            artist = clean_artist  # Don't truncate, let scrolling handle it
        else:
            artist = "Unknown artist"
        
        # Draw track info with scrolling text
        title_max_width = info_width - 10 # Leave some padding
        artist_max_width = info_width - 10
        
        # Use scrolling text for title and artist
        self.draw_scrolling_text(img, title, "title", info_x, album_y + 25, title_max_width, 0.6, (255, 255, 255), 2)
        self.draw_scrolling_text(img, artist, "artist", info_x, album_y + 50, artist_max_width, 0.5, (180, 180, 180), 1)
        
        # Progress bar with real-time calculation
        progress_y = album_y + 70
        progress_width = info_width - 20
        
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
        
        # Format time strings
        def format_time(seconds):
            mins = seconds // 60
            secs = seconds % 60
            return f"{mins}:{secs:02d}"
        
        current_time_str = format_time(current_time)
        total_time_str = format_time(total_time)
        
        # Time indicators with real values
        cv2.putText(img, current_time_str, (info_x, progress_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
        cv2.putText(img, total_time_str, (info_x + progress_width - 25, progress_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
        
        # Control buttons (right side) - modern circular buttons
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
        cv2.line(img, (next_x - 4, button_y), (next_x - 1, button_y - 5), (220, 220, 220), 2)
        cv2.line(img, (next_x - 4, button_y), (next_x - 1, button_y + 5), (220, 220, 220), 2)
        cv2.line(img, (next_x + 2, button_y), (next_x + 5, button_y - 5), (220, 220, 220), 2)
        cv2.line(img, (next_x + 2, button_y), (next_x + 5, button_y + 5), (220, 220, 220), 2)
        
        # Volume indicator (bottom right)
        if volume is not None:
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
        
        # Apply opacity if specified
        if opacity < 1.0:
            # Create alpha channel and blend with transparent background
            opacity = max(0.0, min(1.0, opacity))  # Clamp between 0.0 and 1.0
            img = img.astype(np.float32)
            img = img * opacity
            img = img.astype(np.uint8)
        
        return img

    def draw_app_in_rect(self, frame, rect_points, volume=None, track_info=None, opacity=0.8):
        if self.current_app is None:
            return frame
        # if spotify, draw miniplayer with track info
        if self.current_app.lower() == 'spotify':
            # prefer cached track_info passed in to avoid network calls per-frame
            if track_info is None:
                track_info = get_current_track()
            mini = self.draw_miniplayer_image(track_info, volume=volume, opacity=opacity)
            return self._warp_and_overlay(frame, mini, rect_points, opacity=opacity)
        # otherwise try to capture window by owner name or title
        win = self.capture_window(self.current_app)
        if win is not None:
            return self._warp_and_overlay(frame, win, rect_points, opacity=opacity)
        # fallback: draw placeholder miniplayer
        mini = self.draw_miniplayer_image({'name': self.current_app, 'artist': ''}, volume=volume, opacity=opacity)
        return self._warp_and_overlay(frame, mini, rect_points, opacity=opacity)
