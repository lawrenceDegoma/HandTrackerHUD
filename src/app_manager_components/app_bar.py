"""
App Bar Component

Provides a visual interface for selecting and dragging apps to spawn windows
without requiring voice commands. Shows available apps as draggable icons.
"""

import cv2
import numpy as np
import time
import os


class AppBar:
    """Visual app bar for drag-and-drop app spawning."""
    
    def __init__(self, position="bottom", height=80):
        self.position = position  # "top", "bottom", "left", "right"
        self.height = height
        self.width = 300  # Will be adjusted based on screen
        self.visible = True
        
        # Available apps
        self.apps = {
            "Spotify": {
                "color": (30, 215, 96),  # Spotify green
                "icon": "♪",
                "text_color": (255, 255, 255)
            },
            "Maps": {
                "color": (66, 133, 244),  # Google blue
                "icon": "📍", 
                "text_color": (255, 255, 255)
            },
            "Weather": {
                "color": (255, 149, 0),  # Orange
                "icon": "🌤",
                "text_color": (255, 255, 255)
            }
        }
        
        self.app_rects = {}  # Will store clickable rectangles for each app
        self.dragging_app = None
        self.drag_start_pos = None
        self.drag_current_pos = None
        
        # Load Spotify PNG icon
        self.spotify_img = self._load_image("spotify.png", size=50)
        
    def _load_image(self, filename, size=50):
        """Load an image from the public folder and resize it."""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # app_bar.py is in src/app_manager_components, so go up two levels to reach project root
            project_root = os.path.dirname(os.path.dirname(current_dir))
            path = os.path.join(project_root, "public", filename)
            if os.path.exists(path):
                img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
                if img is not None:
                    return cv2.resize(img, (size, size))
            print(f"Could not find {path}")
        except Exception as e:
            print(f"Could not load {filename}: {e}")
        return None

    def _overlay_image(self, frame, img, cx, cy):
        """Overlay img centered at (cx, cy) on frame, respecting alpha."""
        h, w = img.shape[:2]
        x1, y1 = cx - w // 2, cy - h // 2
        x2, y2 = x1 + w, y1 + h
        # Clamp to frame bounds
        if x1 < 0 or y1 < 0 or x2 > frame.shape[1] or y2 > frame.shape[0]:
            return
        if img.shape[2] == 4:  # RGBA
            alpha = img[:, :, 3:] / 255.0
            frame[y1:y2, x1:x2] = (alpha * img[:, :, :3] + (1 - alpha) * frame[y1:y2, x1:x2]).astype(np.uint8)
        else:
            frame[y1:y2, x1:x2] = img

    def calculate_layout(self, frame_shape):
        """Calculate app bar layout based on frame size."""
        frame_height, frame_width = frame_shape[:2]
        
        if self.position == "bottom":
            self.bar_rect = (0, frame_height - self.height, frame_width, frame_height)
        elif self.position == "top":
            self.bar_rect = (0, 0, frame_width, self.height)
        
        # Calculate app icon positions
        app_width = 80
        app_spacing = 20
        total_apps_width = len(self.apps) * app_width + (len(self.apps) - 1) * app_spacing
        start_x = (frame_width - total_apps_width) // 2
        
        self.app_rects = {}
        for i, app_name in enumerate(self.apps.keys()):
            x = start_x + i * (app_width + app_spacing)
            y = self.bar_rect[1] + 10
            self.app_rects[app_name] = (x, y, x + app_width, y + 60)
    
    def draw(self, frame):
        """Draw the app bar on the frame."""
        if not self.visible:
            return frame
            
        self.calculate_layout(frame.shape)
        
        # Draw semi-transparent background bar
        overlay = frame.copy()
        cv2.rectangle(overlay, (self.bar_rect[0], self.bar_rect[1]), 
                     (self.bar_rect[2], self.bar_rect[3]), (40, 40, 40), -1)
        frame = cv2.addWeighted(frame, 0.7, overlay, 0.3, 0)
        
        # Draw app icons
        for app_name, app_info in self.apps.items():
            if app_name in self.app_rects:
                x1, y1, x2, y2 = self.app_rects[app_name]
                
                # Skip if this app is being dragged
                if self.dragging_app == app_name:
                    continue
                
                # Draw app background
                cv2.rectangle(frame, (x1, y1), (x2, y2), app_info["color"], -1)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (200, 200, 200), 2)
                
                # Draw app icon/text
                if app_name == "Spotify" and self.spotify_img is not None:
                    cx = x1 + (x2 - x1) // 2
                    cy = y1 + (y2 - y1) // 2
                    self._overlay_image(frame, self.spotify_img, cx, cy)
                else:
                    icon_text = app_info["icon"]
                    text_size = cv2.getTextSize(icon_text, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 2)[0]
                    text_x = x1 + (x2 - x1 - text_size[0]) // 2
                    text_y = y1 + (y2 - y1 + text_size[1]) // 2
                    cv2.putText(frame, icon_text, (text_x, text_y), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1.5, app_info["text_color"], 2)
                
                # Draw app name
                name_size = cv2.getTextSize(app_name, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
                name_x = x1 + (x2 - x1 - name_size[0]) // 2
                name_y = y2 + 15
                cv2.putText(frame, app_name, (name_x, name_y), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # Draw dragging app if active
        if self.dragging_app and self.drag_current_pos:
            self._draw_dragging_app(frame)
        
        return frame
    
    def _draw_dragging_app(self, frame):
        """Draw the app being dragged."""
        if not self.dragging_app or not self.drag_current_pos:
            return
            
        app_info = self.apps[self.dragging_app]
        x, y = self.drag_current_pos
        
        # Draw semi-transparent dragging icon
        app_size = 60
        x1, y1 = x - app_size//2, y - app_size//2
        x2, y2 = x + app_size//2, y + app_size//2
        
        # Draw with some transparency
        overlay = frame.copy()
        cv2.rectangle(overlay, (x1, y1), (x2, y2), app_info["color"], -1)
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (255, 255, 255), 2)
        frame = cv2.addWeighted(frame, 0.7, overlay, 0.3, 0)
        
        # Draw icon
        if self.dragging_app == "Spotify" and self.spotify_img is not None:
            self._overlay_image(frame, self.spotify_img, x, y)
        else:
            icon_text = app_info["icon"]
            text_size = cv2.getTextSize(icon_text, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)[0]
            text_x = x - text_size[0] // 2
            text_y = y + text_size[1] // 2
            cv2.putText(frame, icon_text, (text_x, text_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, app_info["text_color"], 2)
    
    def handle_click(self, x, y):
        """Handle mouse/touch click on app bar."""
        if not self.visible:
            return None
            
        # Check if click is within any app rectangle
        for app_name, rect in self.app_rects.items():
            x1, y1, x2, y2 = rect
            if x1 <= x <= x2 and y1 <= y <= y2:
                self.dragging_app = app_name
                self.drag_start_pos = (x, y)
                self.drag_current_pos = (x, y)
                return app_name
        return None
    
    def handle_drag(self, x, y):
        """Handle dragging motion."""
        if self.dragging_app:
            self.drag_current_pos = (x, y)
    
    def handle_release(self, x, y, frame_shape):
        """Handle drag release and return spawn information if valid."""
        if not self.dragging_app:
            return None
            
        app_name = self.dragging_app
        
        # Check if released outside of app bar area
        bar_y1, bar_y2 = self.bar_rect[1], self.bar_rect[3]
        if not (bar_y1 <= y <= bar_y2):
            # Valid drop location - use pinch release point as top-right corner
            # Default window size: 300x200 pixels
            default_width, default_height = 300, 200
            frame_height, frame_width = frame_shape[:2]
            
            # Top-right corner is at the pinch release point
            right, top = x, y
            left = right - default_width
            bottom = top + default_height
            
            # Ensure bounds are valid (don't go negative or beyond screen)
            left = max(0, left)
            top = max(0, top)
            right = min(frame_width, right)
            bottom = min(frame_height, bottom)
            
            # Make sure we still have a valid rectangle
            if right > left and bottom > top:
                # Create quad points (top-left, top-right, bottom-right, bottom-left)
                quad_points = [
                    (left, top),
                    (right, top), 
                    (right, bottom),
                    (left, bottom)
                ]
                
                print(f"DEBUG: Spawning {app_name} at release point ({x}, {y})")
                print(f"DEBUG: Quad points: {quad_points}")
            else:
                print(f"DEBUG: Invalid quad bounds - skipping spawn")
                # Reset drag state
                self.dragging_app = None
                self.drag_start_pos = None
                self.drag_current_pos = None
                return None
            
            # Reset drag state
            self.dragging_app = None
            self.drag_start_pos = None
            self.drag_current_pos = None
            
            return {
                "app_name": app_name,
                "quad_points": quad_points
            }
        
        # Reset drag state if dropped back on app bar
        self.dragging_app = None
        self.drag_start_pos = None
        self.drag_current_pos = None
        return None
    
    def toggle_visibility(self):
        """Toggle app bar visibility."""
        self.visible = not self.visible
    
    def is_point_in_bar(self, x, y):
        """Check if point is within the app bar area."""
        if not self.visible or not hasattr(self, 'bar_rect'):
            return False
        return (self.bar_rect[0] <= x <= self.bar_rect[2] and 
                self.bar_rect[1] <= y <= self.bar_rect[3])
