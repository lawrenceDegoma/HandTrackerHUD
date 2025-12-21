"""
Hand Tracker

Main hand tracking system that coordinates gesture recognition,
quad management, and volume control through specialized components.
"""

import cv2
import mediapipe as mp
import time
from utils import get_current_track, toggle_play_pause, next_track, previous_track
from hand_tracker_components import GestureRecognizer, CloseGestureDetector, QuadManager, VolumeController


class HandTracker:
    """Main hand tracking system that coordinates all gesture recognition."""
    
    # Updated button positions for the new modern miniplayer (400x150) with button_spacing=45
    MINIPLAYER_BUTTONS = {
        "prev": (245, 75),    # Previous button (controls_x - button_spacing = 290 - 45)
        "play": (290, 75),    # Play/pause button (controls_x = 290) 
        "next": (335, 75)     # Next button (controls_x + button_spacing = 290 + 45)
    }
    MINIPLAYER_RADIUS = 18

    def __init__(self):
        self.mp_hands = mp.solutions.hands
        # Optimize MediaPipe settings for 60 FPS performance
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,        # Process video stream
            max_num_hands=2,                # Limit to 2 hands for performance
            min_detection_confidence=0.7,   # Higher confidence for faster processing
            min_tracking_confidence=0.5,    # Lower tracking confidence for speed
            model_complexity=0              # Use fastest model (0=lite, 1=full)
        )
        self.mp_drawing = mp.solutions.drawing_utils
        
        # Initialize specialized components
        self.gesture_recognizer = GestureRecognizer()
        self.close_gesture_detector = CloseGestureDetector()
        self.quad_manager = QuadManager()
        self.volume_controller = VolumeController()
        
        # Display and tracking settings
        self.tracing_enabled = False
        self.show_hand_skeleton = False  # Hand skeleton display off by default
        self.points = []
        
        # App management
        self.spawned_app = None  # name of app/miniplayer requested by voice or UI
        self.voice_enabled = True  # voice controls enabled by default
        
        # Track info caching
        self.last_track_info = None
        self.last_track_update = 0
        
        # Gesture state
        self.gesture_closed_window = False  # flag for main.py to detect gesture close

    # Properties for backward compatibility
    @property
    def quad_points(self):
        return self.quad_manager.quad_points
    
    @quad_points.setter
    def quad_points(self, value):
        self.quad_manager.quad_points = value
    
    @property
    def quad_active(self):
        return self.quad_manager.quad_active
    
    @quad_active.setter
    def quad_active(self, value):
        self.quad_manager.quad_active = value
    
    @property
    def all_app_quads(self):
        return self.quad_manager.all_app_quads
    
    @property
    def volume_gesture_enabled(self):
        return self.volume_controller.volume_gesture_enabled
    
    @volume_gesture_enabled.setter
    def volume_gesture_enabled(self, value):
        self.volume_controller.volume_gesture_enabled = value
    
    @property
    def current_volume(self):
        return self.volume_controller.current_volume

    def get_cached_track_info(self):
        """Get cached track info with rate limiting."""
        now = time.time()
        # Update every 1 second
        if now - self.last_track_update > 1:
            self.last_track_info = get_current_track()
            self.last_track_update = now
        return self.last_track_info

    def screen_to_miniplayer(self, pt, rect_points, miniplayer_size=(400, 150)):
        """Transform screen coordinates to miniplayer coordinates."""
        return self.gesture_recognizer.screen_to_miniplayer(pt, rect_points, miniplayer_size)

    def draw_window_in_rectangle(self, frame, rect_points, content_img):
        """Legacy method for drawing content in rectangle."""
        if content_img is None:
            return frame
        h, w, _ = content_img.shape
        import numpy as np
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

    def process_frame(self, frame):
        """Main frame processing method that coordinates all gesture recognition."""
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(frame_rgb)
        quad_points = []

        if results.multi_hand_landmarks:
            # Collect all pinch data from all hands for resize detection
            all_pinches = []
            
            for hand_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                if self.show_hand_skeleton:  # Only draw skeleton if enabled
                    self.mp_drawing.draw_landmarks(
                        frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS
                    )

                h, w, _ = frame.shape
                thumb_tip = hand_landmarks.landmark[4]
                index_tip = hand_landmarks.landmark[8]
                thumb_xy = (int(thumb_tip.x * w), int(thumb_tip.y * h))
                index_xy = (int(index_tip.x * w), int(index_tip.y * h))

                if self.show_hand_skeleton:  # Only draw finger dots if skeleton is enabled
                    cv2.circle(frame, thumb_xy, 8, (255, 0, 0), -1)
                    cv2.circle(frame, index_xy, 8, (0, 255, 0), -1)

                # Store pinch data for resize detection (include hand index)
                if self.gesture_recognizer.is_pinched(thumb_xy, index_xy):
                    pinch_center = ((thumb_xy[0] + index_xy[0]) // 2, (thumb_xy[1] + index_xy[1]) // 2)
                    all_pinches.append((hand_idx, hand_landmarks, thumb_xy, index_xy, pinch_center))

            # Handle resize gestures (two hands pinching opposite corners)
            self._handle_resize_gestures(all_pinches)

            # Process each hand for other gestures (but skip if resizing)
            for hand_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                h, w, _ = frame.shape
                thumb_tip = hand_landmarks.landmark[4]
                index_tip = hand_landmarks.landmark[8]
                thumb_xy = (int(thumb_tip.x * w), int(thumb_tip.y * h))
                index_xy = (int(index_tip.x * w), int(index_tip.y * h))

                # Check for close gesture
                if self.quad_manager.quad_points and len(self.quad_manager.quad_points) == 4:
                    if self.close_gesture_detector.check_close_gesture(hand_landmarks, self.quad_manager.quad_points, frame.shape):
                        # Close the window
                        self.quad_manager.quad_points = []
                        self.quad_manager.quad_active = False
                        self.spawned_app = None
                        self.gesture_closed_window = True
                        print("Window closed by gesture")
                        continue

                # Handle window dragging
                self._handle_dragging(thumb_xy, index_xy)

                # Collect quad points for new quad creation
                if not self.quad_manager.dragging_window and not self.quad_manager.resizing_window and self.gesture_recognizer.is_pinched(thumb_xy, index_xy):
                    quad_points.append(thumb_xy)
                    quad_points.append(index_xy)

                # Handle tracing if enabled
                if self.tracing_enabled:
                    index_tip = hand_landmarks.landmark[8]
                    x, y = int(index_tip.x * w), int(index_tip.y * h)
                    self.points.append((x, y))
                    cv2.circle(frame, (x, y), 5, (0, 0, 255), -1)

            # Handle quad creation
            self._handle_quad_creation(quad_points, frame)

        else:
            self.quad_manager.pinched_start_time = None

        # Draw tracing if enabled
        if self.tracing_enabled:
            for i in range(1, len(self.points)):
                cv2.line(frame, self.points[i - 1], self.points[i], (0, 255, 0), 2)

        # Create default quad if needed
        if self.spawned_app is not None and (not self.quad_manager.quad_points or len(self.quad_manager.quad_points) != 4):
            self.quad_manager.create_default_quad(frame.shape, self.spawned_app)

        # Handle volume gestures and button interactions
        if self.quad_manager.quad_active and len(self.quad_manager.quad_points) == 4:
            self._handle_volume_and_buttons(frame, results)

        # Draw debug quad
        frame = self.quad_manager.draw_debug_quad(frame, self.spawned_app)

        return frame

    def _handle_resize_gestures(self, all_pinches):
        """Handle two-hand resize gestures."""
        if len(all_pinches) == 2 and self.quad_manager.quad_points and len(self.quad_manager.quad_points) == 4:
            hand1_idx, hand1_landmarks, thumb1, index1, pinch1_center = all_pinches[0]
            hand2_idx, hand2_landmarks, thumb2, index2, pinch2_center = all_pinches[1]
            
            if not self.quad_manager.resizing_window:
                # Starting new resize
                corners_pinched = []
                for i, corner in enumerate(self.quad_manager.quad_points):
                    if self.gesture_recognizer.is_near_corner(pinch1_center, corner, threshold=50):
                        corners_pinched.append((i, hand1_idx, pinch1_center))
                    elif self.gesture_recognizer.is_near_corner(pinch2_center, corner, threshold=50):
                        corners_pinched.append((i, hand2_idx, pinch2_center))
                
                if len(corners_pinched) == 2:
                    corner1_idx, hand1_id, pos1 = corners_pinched[0]
                    corner2_idx, hand2_id, pos2 = corners_pinched[1]
                    
                    if self.quad_manager.are_opposite_corners(corner1_idx, corner2_idx):
                        # Start resizing
                        if self.quad_manager.dragging_window:
                            self.quad_manager.dragging_window = False
                            self.quad_manager.drag_corner_index = None
                            self.quad_manager.drag_offset = (0, 0)
                        
                        self.quad_manager.resizing_window = True
                        self.quad_manager.resize_corners = [corner1_idx, corner2_idx]
                        self.quad_manager.resize_hand_assignments = {
                            hand1_id: corner1_idx,
                            hand2_id: corner2_idx
                        }
            else:
                # Continue resizing
                if hand1_idx in self.quad_manager.resize_hand_assignments and hand2_idx in self.quad_manager.resize_hand_assignments:
                    corner1_idx = self.quad_manager.resize_hand_assignments[hand1_idx]
                    corner2_idx = self.quad_manager.resize_hand_assignments[hand2_idx]
                    
                    corner_positions = [
                        (corner1_idx, pinch1_center),
                        (corner2_idx, pinch2_center)
                    ]
                    self.quad_manager.update_quad_resize(corner_positions)
                else:
                    # Hand assignments lost - stop resizing
                    self.quad_manager.resizing_window = False
                    self.quad_manager.resize_corners = []
                    self.quad_manager.resize_hand_assignments = {}
        else:
            # Not enough pinches or no quad - stop resizing
            if self.quad_manager.resizing_window:
                self.quad_manager.resizing_window = False
                self.quad_manager.resize_corners = []
                self.quad_manager.resize_hand_assignments = {}

    def _handle_dragging(self, thumb_xy, index_xy):
        """Handle window dragging gestures."""
        if self.quad_manager.quad_points and len(self.quad_manager.quad_points) == 4 and not self.quad_manager.resizing_window:
            if self.gesture_recognizer.is_pinched(thumb_xy, index_xy):
                if not self.quad_manager.dragging_window:
                    # Check if pinch is near any corner
                    for i in [0, 1, 2, 3]:  # all corners
                        if (self.gesture_recognizer.is_near_corner(thumb_xy, self.quad_manager.quad_points[i]) or 
                            self.gesture_recognizer.is_near_corner(index_xy, self.quad_manager.quad_points[i])):
                            self.quad_manager.dragging_window = True
                            self.quad_manager.drag_corner_index = i
                            # Calculate offset from corner to pinch center
                            pinch_center = ((thumb_xy[0] + index_xy[0]) // 2, (thumb_xy[1] + index_xy[1]) // 2)
                            corner = self.quad_manager.quad_points[i]
                            self.quad_manager.drag_offset = (pinch_center[0] - corner[0], pinch_center[1] - corner[1])
                            break
                else:
                    # Continue dragging - move the quad
                    pinch_center = ((thumb_xy[0] + index_xy[0]) // 2, (thumb_xy[1] + index_xy[1]) // 2)
                    new_corner_pos = (pinch_center[0] - self.quad_manager.drag_offset[0], pinch_center[1] - self.quad_manager.drag_offset[1])
                    self.quad_manager.update_quad_position(new_corner_pos, self.quad_manager.drag_corner_index)
            else:
                # Not pinching - stop dragging
                if self.quad_manager.dragging_window:
                    self.quad_manager.dragging_window = False
                    self.quad_manager.drag_corner_index = None
                    self.quad_manager.drag_offset = (0, 0)

    def _handle_quad_creation(self, quad_points, frame):
        """Handle creation of new quads from pinch gestures."""
        if len(quad_points) == 4:
            # Allow creating multiple quads
            if self.quad_manager.pinched_start_time is None:
                self.quad_manager.pinched_start_time = time.time()

            live_rect = self.quad_manager.get_rectangle_from_points(quad_points)
            for i in range(4):
                cv2.line(frame, live_rect[i], live_rect[(i + 1) % 4], (0, 255, 255), 3)

            # If a spawn request exists, create new quad immediately 
            if self.spawned_app is not None:
                self.quad_manager.create_quad(live_rect, self.spawned_app)
                self.spawned_app = None  # Clear the request
                
            elif self.quad_manager.pinched_start_time is not None and time.time() - self.quad_manager.pinched_start_time >= 2.0:
                # Fallback: 2 second hold creates a default quad
                app_name = 'Spotify' if not self.voice_enabled else None
                self.quad_manager.create_quad(live_rect, app_name)
                
                # Auto-request Spotify if voice disabled
                if not self.voice_enabled and self.spawned_app is None:
                    self.spawned_app = 'Spotify'
        else:
            self.quad_manager.pinched_start_time = None

    def _handle_volume_and_buttons(self, frame, results):
        """Handle volume gestures and button interactions."""
        volume = None
        if self.volume_controller.volume_gesture_enabled and results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]
            h, w, _ = frame.shape
            thumb_tip = hand_landmarks.landmark[4]
            index_tip = hand_landmarks.landmark[8]
            thumb_xy = (int(thumb_tip.x * w), int(thumb_tip.y * h))
            index_xy = (int(index_tip.x * w), int(index_tip.y * h))
            
            volume = self.volume_controller.calculate_volume_from_pinch(thumb_xy, index_xy)

        # Store current volume for external renderer (AppManager)
        self.volume_controller.current_volume = volume

        # Handle button interactions
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                h, w, _ = frame.shape
                index_tip = hand_landmarks.landmark[8]
                index_xy = (int(index_tip.x * w), int(index_tip.y * h))
                miniplayer_xy = self.screen_to_miniplayer(index_xy, self.quad_manager.quad_points)

                for btn, center in self.MINIPLAYER_BUTTONS.items():
                    import math
                    dist = math.hypot(miniplayer_xy[0] - center[0], miniplayer_xy[1] - center[1])
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

    def toggle_quad(self):
        """Toggle the active state of all quads."""
        self.quad_manager.toggle_quad()

    def spawn_miniplayer(self, app_name: str = "Spotify"):
        """Request a miniplayer for an app."""
        self.spawned_app = app_name
        self.quad_manager.quad_active = True
        print(f"Spawn requested for: {app_name}")

    def get_all_app_regions(self):
        """Get all app quads formatted for AppManager multi-app rendering."""
        return self.quad_manager.get_all_app_regions()

    def __del__(self):
        """Cleanup when the HandTracker is destroyed."""
        if hasattr(self, 'volume_controller'):
            self.volume_controller.cleanup()
