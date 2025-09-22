import cv2
import mediapipe as mp
import math
import time
import numpy as np
from utils import toggle_play_pause, next_track, previous_track, get_current_track

class HandTracker:
    MINIPLAYER_BUTTONS = {
    "prev":  (50, 60),
    "play":  (150, 60),
    "next":  (250, 60)
    }
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

    def get_cached_track_info(self):
        now = time.time()
        if now - self.last_track_update > 1:  # Update every 1 second
            self.last_track_info = get_current_track()
            self.last_track_update = now
        return self.last_track_info

    def draw_miniplayer(self, frame, rect_points, track_info=None):
        # Warp a blank image to the rectangle
        h, w = 120, 300  # Miniplayer size
        miniplayer_img = np.ones((h, w, 3), dtype=np.uint8) * 30  # Dark background

        # Draw buttons
        cv2.circle(miniplayer_img, (50, 60), 25, (255, 255, 255), -1)  # Prev
        cv2.circle(miniplayer_img, (150, 60), 25, (255, 255, 255), -1) # Play/Pause
        cv2.circle(miniplayer_img, (250, 60), 25, (255, 255, 255), -1) # Next

        # Draw track info if available
        if track_info:
            cv2.putText(miniplayer_img, track_info['name'], (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
            cv2.putText(miniplayer_img, track_info['artist'], (10, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), 1)

        # Warp to rectangle
        src_pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst_pts = np.float32(rect_points)
        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
        warped = cv2.warpPerspective(miniplayer_img, matrix, (frame.shape[1], frame.shape[0]))
        mask = np.zeros_like(frame, dtype=np.uint8)
        cv2.fillConvexPoly(mask, np.int32(dst_pts), (255, 255, 255))
        frame = cv2.bitwise_and(frame, cv2.bitwise_not(mask))
        frame = cv2.add(frame, warped)
        return frame
    
    def screen_to_miniplayer(self, pt, rect_points, miniplayer_size=(120, 300)):
        src_pts = np.float32(rect_points)
        dst_pts = np.float32([[0, 0], [miniplayer_size[1], 0], [miniplayer_size[1], miniplayer_size[0]], [0, miniplayer_size[0]]])
        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
        pt_homog = np.array([[pt]], dtype=np.float32)
        pt_transformed = cv2.perspectiveTransform(pt_homog, matrix)
        x, y = pt_transformed[0][0]
        return int(x), int(y)

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
        warped = cv2.warpPerspective(content_img, matrix, (frame.shape[1], frame.shape[0]))
        mask = np.zeros_like(frame, dtype=np.uint8)
        cv2.fillConvexPoly(mask, np.int32(dst_pts), (255, 255, 255))
        frame = cv2.bitwise_and(frame, cv2.bitwise_not(mask))
        frame = cv2.add(frame, warped)
        return frame

    def process_frame(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(frame_rgb)
        quad_points = []

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                self.mp_drawing.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)

                h, w, _ = frame.shape
                thumb_tip = hand_landmarks.landmark[4]
                index_tip = hand_landmarks.landmark[8]
                thumb_xy = (int(thumb_tip.x * w), int(thumb_tip.y * h))
                index_xy = (int(index_tip.x * w), int(index_tip.y * h))

                cv2.circle(frame, thumb_xy, 8, (255, 0, 0), -1)
                cv2.circle(frame, index_xy, 8, (0, 255, 0), -1)

                if self.is_pinched(thumb_xy, index_xy):
                    quad_points.append(thumb_xy)
                    quad_points.append(index_xy)

                if self.tracing_enabled:
                    h, w, _ = frame.shape
                    index_tip = hand_landmarks.landmark[8]
                    x, y = int(index_tip.x * w), int(index_tip.y * h)
                    self.points.append((x, y))
                    cv2.circle(frame, (x, y), 5, (0, 0, 255), -1)
            
            if len(quad_points) == 4:
                if self.pinched_start_time is None:
                    self.pinched_start_time = time.time()

                live_rect = self.get_rectangle_from_points(quad_points)
                for i in range(4):
                    cv2.line(frame, live_rect[i], live_rect[(i+1)%4], (0, 255, 255), 3)
                
                if time.time() - self.pinched_start_time >= 3.0:
                    self.quad_points = live_rect
                    self.quad_active = True
            else:
                self.pinched_start_time = None

        else:
            self.pinched_start_time = None

        if self.tracing_enabled:
            for i in range(1, len(self.points)):
                cv2.line(frame, self.points[i - 1], self.points[i], (0, 255, 0), 2)

        if self.quad_active and len(self.quad_points) == 4:
            track_info = self.get_cached_track_info()
            frame = self.draw_miniplayer(frame, self.quad_points, track_info)

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    h, w, _ = frame.shape
                    index_tip = hand_landmarks.landmark[8]
                    index_xy = (int(index_tip.x * w), int(index_tip.y * h))
                    miniplayer_xy = self.screen_to_miniplayer(index_xy, self.quad_points)

                    for btn, center in self.MINIPLAYER_BUTTONS.items():
                        dist = math.hypot(miniplayer_xy[0] - center[0], miniplayer_xy[1] - center[1])
                        if dist < self.MINIPLAYER_RADIUS:
                            if not hasattr(self, 'last_btn_time'):
                                self.last_btn_time = 0
                            if time.time() - self.last_btn_time > 1:
                                if btn == "prev":
                                    previous_track()
                                elif btn == "play":
                                    toggle_play_pause()  # Add pause toggle logic if desired
                                elif btn == "next":
                                    next_track()
                                self.last_btn_time = time.time()
        return frame
    
    def toggle_quad(self):
        self.quad_active = not self.quad_active
        if not self.quad_active:
            self.quad_points = []