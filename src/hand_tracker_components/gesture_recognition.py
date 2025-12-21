"""
Gesture Recognition

This module handles detection and recognition of hand gestures including
pinch detection, wrist rotation, and coordinate transformations.
"""

import cv2
import math
import numpy as np


class GestureRecognizer:
    """Handles hand gesture recognition and coordinate transformations."""
    
    def __init__(self):
        pass
    
    def is_pinched(self, thumb_tip, index_tip, threshold=50):
        """Check if thumb and index finger are pinched together."""
        x1, y1 = thumb_tip
        x2, y2 = index_tip
        return math.hypot(x2 - x1, y2 - y1) < threshold
    
    def is_near_corner(self, point, corner, threshold=50):
        """Check if a point is near a corner of the quad."""
        x1, y1 = point
        x2, y2 = corner
        return math.hypot(x2 - x1, y2 - y1) < threshold
    
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
    
    def screen_to_miniplayer(self, pt, rect_points, miniplayer_size=(400, 150)):
        """Transform screen coordinates to miniplayer coordinates."""
        src_pts = np.float32(rect_points)
        width, height = miniplayer_size
        dst_pts = np.float32([
            [0, 0],
            [width, 0],
            [width, height],
            [0, height],
        ])
        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
        pt_homog = np.array([[pt]], dtype=np.float32)
        pt_transformed = cv2.perspectiveTransform(pt_homog, matrix)
        x, y = pt_transformed[0][0]
        return int(x), int(y)


class CloseGestureDetector:
    """Detects wrist rotation gesture for closing windows."""
    
    def __init__(self, rotation_threshold=17):
        self.rotation_threshold = rotation_threshold
        self.gesture_start_pos = None
        self.gesture_start_time = None
        self.gesture_start_angle = None
    
    def check_close_gesture(self, hand_landmarks, quad_points, frame_shape):
        """Check for wrist rotation gesture from top-right corner."""
        if not quad_points or len(quad_points) != 4:
            return False
            
        h, w, _ = frame_shape
        index_tip = hand_landmarks.landmark[8]
        
        # Position of index finger
        finger_x = int(index_tip.x * w)
        finger_y = int(index_tip.y * h)
        current_pos = (finger_x, finger_y)
        
        # Check if near top-right corner of quad
        top_right_corner = quad_points[1]
        gesture_recognizer = GestureRecognizer()
        is_near = gesture_recognizer.is_near_corner(current_pos, top_right_corner, threshold=150)
        
        if not is_near:
            self.gesture_start_pos = None
            self.gesture_start_time = None
            self.gesture_start_angle = None
            return False
        
        # Get current wrist angle
        current_angle = gesture_recognizer.get_wrist_angle(hand_landmarks)
        
        # Start tracking when hand is positioned at corner
        if self.gesture_start_angle is None:
            self.gesture_start_angle = current_angle
            self.gesture_start_pos = current_pos
            import time
            self.gesture_start_time = time.time()
            return False
        
        # Check rotation amount
        angle_diff = abs(current_angle - self.gesture_start_angle)
        # Handle angle wraparound (e.g., -170 to 170 is 20 degrees, not 340)
        if angle_diff > 180:
            angle_diff = 360 - angle_diff
            
        # If rotated enough, close the window
        if angle_diff >= self.rotation_threshold:
            self.gesture_start_pos = None
            self.gesture_start_time = None
            self.gesture_start_angle = None
            return True
            
        return False
