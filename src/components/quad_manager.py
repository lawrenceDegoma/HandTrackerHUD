"""
Quad Management

This module handles quad creation, manipulation, resizing, dragging,
and tracking of multiple application windows.
"""

import cv2
import numpy as np
import time


class QuadManager:
    """Manages quad creation, manipulation, and tracking."""
    
    def __init__(self):
        self.quad_points = []
        self.all_app_quads = []  # List of {quad_points: [...], app: 'Spotify'} for multiple windows
        self.quad_active = True
        self.pinched_start_time = None
        
        # Window dragging state
        self.dragging_window = False
        self.drag_corner_index = None  # which corner (0-3) is being dragged
        self.drag_offset = (0, 0)  # offset from corner to pinch point
        
        # Window resizing state
        self.resizing_window = False
        self.resize_corners = []  # list of corner indices being pinched
        self.resize_initial_positions = []  # initial positions of pinched corners
        self.resize_hand_assignments = {}  # maps hand_id to corner_index
    
    def get_rectangle_from_points(self, points):
        """Convert pinch points to a rectangle."""
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        left, right = min(xs), max(xs)
        top, bottom = min(ys), max(ys)
        return [(left, top), (right, top), (right, bottom), (left, bottom)]
    
    def are_opposite_corners(self, corner1, corner2):
        """Check if two corners are opposite (diagonal) to each other."""
        # Corners: 0=top-left, 1=top-right, 2=bottom-right, 3=bottom-left
        opposite_pairs = [(0, 2), (1, 3)]  # (top-left, bottom-right), (top-right, bottom-left)
        return (corner1, corner2) in opposite_pairs or (corner2, corner1) in opposite_pairs
    
    def update_quad_resize(self, corner_positions):
        """Update quad size by moving opposite corners."""
        if not self.quad_points or len(self.quad_points) != 4 or len(corner_positions) != 2:
            return
        
        corner1_idx, corner1_pos = corner_positions[0]
        corner2_idx, corner2_pos = corner_positions[1]
        
        # Update the quad points with new corner positions
        new_quad = list(self.quad_points)
        new_quad[corner1_idx] = corner1_pos
        new_quad[corner2_idx] = corner2_pos
        
        # For opposite corners, we need to update the other two corners to maintain rectangle shape
        if self.are_opposite_corners(corner1_idx, corner2_idx):
            if corner1_idx == 0 and corner2_idx == 2:  # top-left and bottom-right
                new_quad[1] = (corner2_pos[0], corner1_pos[1])  # top-right
                new_quad[3] = (corner1_pos[0], corner2_pos[1])  # bottom-left
            elif corner1_idx == 1 and corner2_idx == 3:  # top-right and bottom-left
                new_quad[0] = (corner2_pos[0], corner1_pos[1])  # top-left
                new_quad[2] = (corner1_pos[0], corner2_pos[1])  # bottom-right
            elif corner1_idx == 2 and corner2_idx == 0:  # bottom-right and top-left
                new_quad[1] = (corner1_pos[0], corner2_pos[1])  # top-right
                new_quad[3] = (corner2_pos[0], corner1_pos[1])  # bottom-left
            elif corner1_idx == 3 and corner2_idx == 1:  # bottom-left and top-right
                new_quad[0] = (corner1_pos[0], corner2_pos[1])  # top-left
                new_quad[2] = (corner2_pos[0], corner1_pos[1])  # bottom-right
        
        self.quad_points = new_quad
    
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
    
    def create_quad(self, points, app_name=None):
        """Create a new quad and add it to the list."""
        new_quad = {
            'quad_points': points,
            'app': app_name
        }
        self.all_app_quads.append(new_quad)
        
        # Set as current active quad for backward compatibility
        self.quad_points = points
        self.quad_active = True
        print(f"Created new quad for {app_name}")
        return len(self.all_app_quads) - 1  # Return index
    
    def create_default_quad(self, frame_shape, app_name=None):
        """Create a default centered quad when no quad has been captured yet."""
        h, w, _ = frame_shape
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
        return self.quad_points
    
    def toggle_quad(self):
        """Toggle the active state of all quads."""
        self.quad_active = not self.quad_active
        if not self.quad_active:
            self.quad_points = []
    
    def get_all_app_regions(self):
        """Get all app quads formatted for AppManager multi-app rendering."""
        if not self.all_app_quads:
            return []
        
        app_regions = []
        for quad_data in self.all_app_quads:
            if quad_data['app'] and len(quad_data['quad_points']) == 4:
                app_regions.append({
                    'app_id': quad_data['app'].lower(),
                    'rect_points': quad_data['quad_points'],
                    'opacity': 0.9
                })
        
        return app_regions
    
    def draw_debug_quad(self, frame, spawned_app):
        """Draw debug rectangle and label when a miniplayer is requested."""
        if spawned_app is not None and self.quad_points and len(self.quad_points) == 4:
            try:
                pts = np.array(self.quad_points, dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [pts], isClosed=True, color=(0, 128, 255), thickness=4)
                tl_x, tl_y = self.quad_points[0]
                # label background
                cv2.rectangle(frame, (tl_x, max(0, tl_y - 28)), (tl_x + 140, tl_y), (0, 128, 255), -1)
                cv2.putText(
                    frame,
                    f"{spawned_app}",
                    (tl_x + 6, tl_y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2,
                )
            except Exception:
                pass
        return frame
