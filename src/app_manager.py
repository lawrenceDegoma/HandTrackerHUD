import cv2
import numpy as np
import Quartz
import math
from utils import get_current_track, toggle_play_pause, next_track, previous_track

class AppManager:
    def __init__(self):
        self.current_app = None

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

    def _warp_and_overlay(self, frame, content_img, dst_pts):
        if content_img is None:
            return frame
        h, w, _ = content_img.shape
        src_pts = np.float32([[0,0],[w,0],[w,h],[0,h]])
        dst_pts_f = np.float32(dst_pts)
        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts_f)
        warped = cv2.warpPerspective(content_img, matrix, (frame.shape[1], frame.shape[0]))
        mask = np.zeros_like(frame, dtype=np.uint8)
        cv2.fillConvexPoly(mask, np.int32(dst_pts_f), (255,255,255))
        frame = cv2.bitwise_and(frame, cv2.bitwise_not(mask))
        frame = cv2.add(frame, warped)
        return frame

    def draw_miniplayer_image(self, track_info, size=(400, 150), volume=None):
        """Draw a miniplayer with track info and controls."""
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
        
        # Draw album artwork placeholder with modern style
        cv2.rectangle(img, (album_x, album_y), (album_x + album_size, album_y + album_size), (60, 60, 60), -1)
        cv2.rectangle(img, (album_x + 2, album_y + 2), (album_x + album_size - 2, album_y + album_size - 2), (80, 80, 80), 2)
        
        # Add music note icon in album area
        center_x, center_y = album_x + album_size // 2, album_y + album_size // 2
        cv2.circle(img, (center_x, center_y), 20, (150, 150, 150), -1)
        cv2.putText(img, "♪", (center_x - 8, center_y + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (220, 220, 220), 2)
        
        # Track info area (middle section)
        info_x = album_x + album_size + 20
        info_width = w - info_x - 120  # Leave space for controls on right
        
        # Track title
        if track_info and 'name' in track_info:
            title = track_info['name'][:25] + "..." if len(track_info['name']) > 25 else track_info['name']
        else:
            title = "No track playing"
        
        # Artist name
        if track_info and 'artist' in track_info:
            artist = track_info['artist'][:30] + "..." if len(track_info['artist']) > 30 else track_info['artist']
        else:
            artist = "Unknown artist"
        
        # Draw track info with modern typography
        cv2.putText(img, title, (info_x, album_y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(img, artist, (info_x, album_y + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        
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
        
        return img

    def draw_app_in_rect(self, frame, rect_points, volume=None, track_info=None):
        if self.current_app is None:
            return frame
        # if spotify, draw miniplayer with track info
        if self.current_app.lower() == 'spotify':
            # prefer cached track_info passed in to avoid network calls per-frame
            if track_info is None:
                track_info = get_current_track()
            mini = self.draw_miniplayer_image(track_info, volume=volume)
            return self._warp_and_overlay(frame, mini, rect_points)
        # otherwise try to capture window by owner name or title
        win = self.capture_window(self.current_app)
        if win is not None:
            return self._warp_and_overlay(frame, win, rect_points)
        # fallback: draw placeholder miniplayer
        mini = self.draw_miniplayer_image({'name': self.current_app, 'artist': ''}, volume=volume)
        return self._warp_and_overlay(frame, mini, rect_points)
