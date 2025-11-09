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

    def draw_miniplayer_image(self, track_info, size=(300,120), volume=None):
        w, h = size  # width, height
        img = np.ones((h, w, 3), dtype=np.uint8) * 30
        # buttons are placed for width=300, height ~120
        cv2.circle(img, (50, 60), 25, (255,255,255), -1)
        cv2.circle(img, (150,60), 25, (255,255,255), -1)
        cv2.circle(img, (250,60), 25, (255,255,255), -1)
        ...
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
