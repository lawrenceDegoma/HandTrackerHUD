import cv2
import mediapipe as mp
import math
import time
import numpy as np
from utils import (
    toggle_play_pause,
    next_track,
    previous_track,
    get_current_track,
    set_volume,
)
import threading
import queue


class HandTracker:
    MINIPLAYER_BUTTONS = {"prev": (50, 60), "play": (150, 60), "next": (250, 60)}
    MINIPLAYER_RADIUS = 25

    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands()
        self.mp_drawing = mp.solutions.drawing_utils
        self.tracing_enabled = False
        self.points = []
        self.quad_points = []
        self.quad_active = True
        self.pinched_start_time = None
        self.last_track_info = None
        self.last_track_update = 0
        self.volume_gesture_enabled = False
        self.last_volume_set = 0
        self.current_volume = None
        self.spawned_app = None  # name of app/miniplayer requested by voice or UI
        self.voice_enabled = True  # voice controls enabled by default
        
        # Window dragging state
        self.dragging_window = False
        self.drag_corner_index = None  # which corner (0-3) is being dragged
        self.drag_offset = (0, 0)  # offset from corner to pinch point
        
        # Close gesture state
        self.close_gesture_start_pos = None
        self.close_gesture_start_time = None
        self.close_gesture_threshold = 17  # degrees to rotate wrist
        self.gesture_closed_window = False  # flag for main.py to detect gesture close
        self.close_gesture_start_angle = None

        # Volume worker: non-blocking updates to Spotify
        self._volume_queue = queue.Queue()
        self._volume_worker_stop = threading.Event()
        self._volume_worker_thread = threading.Thread(
            target=self._volume_worker, daemon=True
        )
        self._volume_worker_thread.start()

    def get_cached_track_info(self):
        now = time.time()
        # Update every 1 second
        if now - self.last_track_update > 1:
            self.last_track_info = get_current_track()
            self.last_track_update = now
        return self.last_track_info

    def screen_to_miniplayer(self, pt, rect_points, miniplayer_size=(300, 120)):
        src_pts = np.float32(rect_points)
        width, height = miniplayer_size
        dst_pts = np.float32(
            [
                [0, 0],
                [width, 0],
                [width, height],
                [0, height],
            ]
        )
        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
        pt_homog = np.array([[pt]], dtype=np.float32)
        pt_transformed = cv2.perspectiveTransform(pt_homog, matrix)
        x, y = pt_transformed[0][0]
        return int(x), int(y)

    def is_near_corner(self, point, corner, threshold=50):
        """Check if a point is near a corner of the quad."""
        x1, y1 = point
        x2, y2 = corner
        return math.hypot(x2 - x1, y2 - y1) < threshold

    def update_quad_position(self, new_corner_pos, corner_index):
        """Update quad position by moving one corner and adjusting the rectangle."""
        if not self.quad_points or len(self.quad_points) != 4:
            return
        
        # Get current quad as rectangle (maintain rectangular shape)
        old_corner = self.quad_points[corner_index]
        dx = new_corner_pos[0] - old_corner[0]
        dy = new_corner_pos[1] - old_corner[1]
        
        # Move the entire rectangle by the delta
        new_quad = []
        for corner in self.quad_points:
            new_quad.append((corner[0] + dx, corner[1] + dy))
        
        self.quad_points = new_quad

    def get_wrist_angle(self, hand_landmarks):
        """Calculate the angle of the wrist based on hand orientation."""
        # Use wrist (0) and middle finger base (9) to determine hand orientation
        wrist = hand_landmarks.landmark[0]
        middle_base = hand_landmarks.landmark[9]
        
        dx = middle_base.x - wrist.x
        dy = middle_base.y - wrist.y
        
        # Calculate angle in degrees
        angle = math.degrees(math.atan2(dy, dx))
        return angle

    def check_close_gesture(self, hand_landmarks, frame_shape):
        """Check for wrist rotation gesture from top-right corner."""
        if not self.quad_points or len(self.quad_points) != 4:
            return False
            
        h, w, _ = frame_shape
        index_tip = hand_landmarks.landmark[8]
        
        # Position of index finger
        finger_x = int(index_tip.x * w)
        finger_y = int(index_tip.y * h)
        current_pos = (finger_x, finger_y)
        
        # Check if near top-right corner of quad
        top_right_corner = self.quad_points[1]
        is_near = self.is_near_corner(current_pos, top_right_corner, threshold=150)
        
        if not is_near:
            self.close_gesture_start_pos = None
            self.close_gesture_start_time = None
            self.close_gesture_start_angle = None
            return False
        
        # Get current wrist angle
        current_angle = self.get_wrist_angle(hand_landmarks)
        
        # Start tracking when hand is positioned at corner
        if self.close_gesture_start_angle is None:
            self.close_gesture_start_angle = current_angle
            self.close_gesture_start_pos = current_pos
            self.close_gesture_start_time = time.time()
            return False
        
        # Check rotation amount
        angle_diff = abs(current_angle - self.close_gesture_start_angle)
        # Handle angle wraparound (e.g., -170 to 170 is 20 degrees, not 340)
        if angle_diff > 180:
            angle_diff = 360 - angle_diff
            
        # If rotated enough, close the window
        if angle_diff >= self.close_gesture_threshold:
            self.close_gesture_start_pos = None
            self.close_gesture_start_time = None
            self.close_gesture_start_angle = None
            return True
            
        return False

    def is_pinched(self, thumb_tip, index_tip, threshold=100):
        x1, y1 = thumb_tip
        x2, y2 = index_tip
        return math.hypot(x2 - x1, y2 - y1) < threshold

    def get_rectangle_from_points(self, points):
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        left, right = min(xs), max(xs)
        top, bottom = min(ys), max(ys)
        return [(left, top), (right, top), (right, bottom), (left, bottom)]

    def draw_window_in_rectangle(self, frame, rect_points, content_img):
        if content_img is None:
            return frame
        h, w, _ = content_img.shape
        src_pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst_pts = np.float32(rect_points)
        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
        warped = cv2.warpPerspective(
            content_img, matrix, (frame.shape[1], frame.shape[0])
        )
        mask = np.zeros_like(frame, dtype=np.uint8)
        cv2.fillConvexPoly(mask, np.int32(dst_pts), (255, 255, 255))
        frame = cv2.bitwise_and(frame, cv2.bitwise_not(mask))
        frame = cv2.add(frame, warped)
        return frame

    def _enqueue_volume(self, volume: int):
        """Enqueue a volume request. The worker collapses multiple pending requests to the latest value."""
        try:
            # put latest volume into queue without blocking
            self._volume_queue.put_nowait(int(volume))
        except queue.Full:
            # if full (unlikely) replace by draining and adding
            with self._volume_queue.mutex:
                self._volume_queue.queue.clear()
            self._volume_queue.put(int(volume))

    def _volume_worker(self):
        """Worker thread: take latest volume requests, collapse them, and call set_volume() with rate limiting."""
        min_interval = 0.5  # seconds between actual API calls
        last_call = 0
        while not self._volume_worker_stop.is_set():
            try:
                # block until at least one value is available
                vol = self._volume_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            # drain queue to get the latest requested volume
            latest = vol
            try:
                while True:
                    latest = self._volume_queue.get_nowait()
            except queue.Empty:
                pass
            # rate limit
            now = time.time()
            wait = max(0, min_interval - (now - last_call))
            if wait > 0:
                time.sleep(wait)
            try:
                set_volume(latest)
            except Exception:
                # swallow exceptions to avoid crashing worker
                pass
            last_call = time.time()

    def process_frame(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(frame_rgb)
        quad_points = []

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                self.mp_drawing.draw_landmarks(
                    frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS
                )

                h, w, _ = frame.shape
                thumb_tip = hand_landmarks.landmark[4]
                index_tip = hand_landmarks.landmark[8]
                thumb_xy = (int(thumb_tip.x * w), int(thumb_tip.y * h))
                index_xy = (int(index_tip.x * w), int(index_tip.y * h))

                cv2.circle(frame, thumb_xy, 8, (255, 0, 0), -1)
                cv2.circle(frame, index_xy, 8, (0, 255, 0), -1)

                # Check for close gesture (two-finger swipe left from top-right)
                if self.quad_points and len(self.quad_points) == 4:
                    if self.check_close_gesture(hand_landmarks, frame.shape):
                        # Close the window
                        self.quad_points = []
                        self.quad_active = False
                        self.spawned_app = None
                        # Set a flag that main.py can use to notify AppManager
                        self.gesture_closed_window = True
                        print("Window closed by gesture")
                        continue  # Skip other gesture processing for this hand

                # Check for window dragging if quad exists
                if self.quad_points and len(self.quad_points) == 4:
                    if self.is_pinched(thumb_xy, index_xy):
                        if not self.dragging_window:
                            # Check if pinch is near any corner (only top corners for dragging)
                            for i in [0, 1]:  # top-left and top-right corners
                                if self.is_near_corner(thumb_xy, self.quad_points[i]) or self.is_near_corner(index_xy, self.quad_points[i]):
                                    self.dragging_window = True
                                    self.drag_corner_index = i
                                    # Calculate offset from corner to pinch center
                                    pinch_center = ((thumb_xy[0] + index_xy[0]) // 2, (thumb_xy[1] + index_xy[1]) // 2)
                                    corner = self.quad_points[i]
                                    self.drag_offset = (pinch_center[0] - corner[0], pinch_center[1] - corner[1])
                                    break
                        else:
                            # Continue dragging - move the quad
                            pinch_center = ((thumb_xy[0] + index_xy[0]) // 2, (thumb_xy[1] + index_xy[1]) // 2)
                            new_corner_pos = (pinch_center[0] - self.drag_offset[0], pinch_center[1] - self.drag_offset[1])
                            self.update_quad_position(new_corner_pos, self.drag_corner_index)
                    else:
                        # Not pinching - stop dragging
                        if self.dragging_window:
                            self.dragging_window = False
                            self.drag_corner_index = None
                            self.drag_offset = (0, 0)

                # Only collect quad points if not dragging and no existing quad
                if not self.dragging_window and self.is_pinched(thumb_xy, index_xy):
                    quad_points.append(thumb_xy)
                    quad_points.append(index_xy)

                if self.tracing_enabled:
                    h, w, _ = frame.shape
                    index_tip = hand_landmarks.landmark[8]
                    x, y = int(index_tip.x * w), int(index_tip.y * h)
                    self.points.append((x, y))
                    cv2.circle(frame, (x, y), 5, (0, 0, 255), -1)

            if len(quad_points) == 4:
                # Only process pinch quad creation if no existing quad is set
                if not self.quad_points or len(self.quad_points) != 4:
                    if self.pinched_start_time is None:
                        self.pinched_start_time = time.time()

                    live_rect = self.get_rectangle_from_points(quad_points)
                    for i in range(4):
                        cv2.line(
                            frame, live_rect[i], live_rect[(i + 1) % 4], (0, 255, 255), 3
                        )

                    # If a spawn request exists, detach immediately regardless of voice_enabled.
                    if self.spawned_app is not None:
                        self.quad_points = live_rect
                        self.quad_active = True
                    elif not self.quad_points or len(self.quad_points) != 4:
                        # Only allow creating a new quad if none exists yet.
                        # Fallback behavior: if not spawning via request, require 2s hold to detach.
                        if self.pinched_start_time is not None and time.time() - self.pinched_start_time >= 2.0:
                            self.quad_points = live_rect
                            self.quad_active = True
                            # If voice controls are disabled, auto-request a Spotify miniplayer so
                            # the main loop / AppManager will spawn it without needing voice input.
                            if not self.voice_enabled and self.spawned_app is None:
                                self.spawned_app = 'Spotify'
                else:
                    # Reset pinch timer if quad already exists - don't process new pinches
                    self.pinched_start_time = None
            else:
                self.pinched_start_time = None

        else:
            self.pinched_start_time = None

        if self.tracing_enabled:
            for i in range(1, len(self.points)):
                cv2.line(frame, self.points[i - 1], self.points[i], (0, 255, 0), 2)

        # If a miniplayer was requested but no quad has been captured yet, create
        # a sane default rectangle centered in the frame so the app can be drawn.
        if self.spawned_app is not None and (not self.quad_points or len(self.quad_points) != 4):
            h, w, _ = frame.shape
            # default size: 40% width, 25% height, clamped to the frame
            box_w = int(w * 0.4)
            box_h = int(h * 0.25)
            box_w = max(100, min(box_w, w - 40))
            box_h = max(80, min(box_h, h - 40))
            cx, cy = w // 2, h // 2
            left = cx - box_w // 2
            right = cx + box_w // 2
            top = cy - box_h // 2
            bottom = cy + box_h // 2
            self.quad_points = [(left, top), (right, top), (right, bottom), (left, bottom)]
            self.quad_active = True

        if self.quad_active and len(self.quad_points) == 4:
            volume = None
            if self.volume_gesture_enabled and results.multi_hand_landmarks:
                hand_landmarks = results.multi_hand_landmarks[0]
                h, w, _ = frame.shape
                thumb_tip = hand_landmarks.landmark[4]
                index_tip = hand_landmarks.landmark[8]
                x1, y1 = int(thumb_tip.x * w), int(thumb_tip.y * h)
                x2, y2 = int(index_tip.x * w), int(index_tip.y * h)
                pinch_dist = math.hypot(x2 - x1, y2 - y1)

                min_dist, max_dist = 20, 200
                volume = int(
                    np.clip(
                        (pinch_dist - min_dist) / (max_dist - min_dist) * 100, 0, 100
                    )
                )

                if abs(volume - self.last_volume_set) > 2:
                    # enqueue instead of blocking
                    self._enqueue_volume(volume)
                    self.last_volume_set = volume

            # store current volume for external renderer (AppManager)
            self.current_volume = volume

            # --- debug: draw a visible rectangle and label when a miniplayer is requested ---
            if self.spawned_app is not None and self.quad_points and len(self.quad_points) == 4:
                try:
                    pts = np.array(self.quad_points, dtype=np.int32).reshape((-1, 1, 2))
                    cv2.polylines(frame, [pts], isClosed=True, color=(0, 128, 255), thickness=4)
                    tl_x, tl_y = self.quad_points[0]
                    # label background
                    cv2.rectangle(frame, (tl_x, max(0, tl_y - 28)), (tl_x + 140, tl_y), (0, 128, 255), -1)
                    cv2.putText(
                        frame,
                        f"{self.spawned_app}",
                        (tl_x + 6, tl_y - 6),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 255, 255),
                        2,
                    )
                except Exception:
                    pass

            # removed draw_miniplayer — rendering handled by AppManager in main
            # keep button detection logic here (miniplayer coordinate mapping)
            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    h, w, _ = frame.shape
                    index_tip = hand_landmarks.landmark[8]
                    index_xy = (int(index_tip.x * w), int(index_tip.y * h))
                    miniplayer_xy = self.screen_to_miniplayer(
                        index_xy, self.quad_points
                    )

                    for btn, center in self.MINIPLAYER_BUTTONS.items():
                        dist = math.hypot(
                            miniplayer_xy[0] - center[0], miniplayer_xy[1] - center[1]
                        )
                        if dist < self.MINIPLAYER_RADIUS:
                            if not hasattr(self, "last_btn_time"):
                                self.last_btn_time = 0
                            if time.time() - self.last_btn_time > 1:
                                if btn == "prev":
                                    previous_track()
                                elif btn == "play":
                                    toggle_play_pause()
                                elif btn == "next":
                                    next_track()
                                self.last_btn_time = time.time()
        return frame

    def toggle_quad(self):
        self.quad_active = not self.quad_active
        if not self.quad_active:
            self.quad_points = []

    def spawn_miniplayer(self, app_name: str = "Spotify"):
        """Request a miniplayer for an app. This sets state — the main loop will draw the miniplayer when a quad exists."""
        self.spawned_app = app_name
        self.quad_active = True
        # Keep existing quad_points if present; user can form the quad first
        print(f"Spawn requested for: {app_name}")
