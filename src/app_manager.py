"""
Application Manager

Main application management system that coordinates app spawning,
command handling, and rendering through specialized components.
"""

from utils import get_current_track
from components import SpotifyMiniplayer, WindowCapture, FrameOverlay


class AppManager:
    """Manages application lifecycle and rendering coordination."""
    
    def __init__(self):
        self.current_app = None
        
        # Initialize specialized components
        self.spotify_player = SpotifyMiniplayer()
        self.window_capture = WindowCapture()
        self.frame_overlay = FrameOverlay()

    def spawn_app(self, name: str):
        """Spawn a new application."""
        self.current_app = name
        print(f"AppManager: spawned {name}")

    def close_app(self):
        """Close the current application."""
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
            from utils import toggle_play_pause
            toggle_play_pause()
        elif "pause" in text:
            from utils import toggle_play_pause
            toggle_play_pause()
        elif "next" in text:
            from utils import next_track
            next_track()
        elif "previous" in text or "prev" in text:
            from utils import previous_track
            previous_track()
        elif "volume mode" in text or "volume gesture" in text:
            if tracker is not None:
                tracker.volume_gesture_enabled = not tracker.volume_gesture_enabled
                print("Volume gesture mode:", tracker.volume_gesture_enabled)
        else:
            print("AppManager: unrecognized command")

    def draw_app_in_rect(self, frame, rect_points, volume=None, track_info=None, opacity=0.8):
        """Draw the current app in a specified rectangle on the frame."""
        if self.current_app is None:
            return frame
        
        # if spotify, draw miniplayer with track info
        if self.current_app.lower() == 'spotify':
            # prefer cached track_info passed in to avoid network calls per-frame
            if track_info is None:
                track_info = get_current_track()
            mini = self.spotify_player.draw_miniplayer_image(track_info, volume=volume, opacity=opacity)
            return self.frame_overlay.warp_and_overlay(frame, mini, rect_points, opacity=opacity)
        
        # otherwise try to capture window by owner name or title
        win = self.window_capture.capture_window(self.current_app)
        if win is not None:
            return self.frame_overlay.warp_and_overlay(frame, win, rect_points, opacity=opacity)
        
        # fallback: draw placeholder miniplayer
        mini = self.spotify_player.draw_miniplayer_image({'name': self.current_app, 'artist': ''}, volume=volume, opacity=opacity)
        return self.frame_overlay.warp_and_overlay(frame, mini, rect_points, opacity=opacity)
