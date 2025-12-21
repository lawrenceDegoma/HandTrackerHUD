"""
Window Capture and Overlay Utilities

This module handles capturing windows from other applications and overlaying
content onto video frames with perspective transformations.
"""

import cv2
import numpy as np
import Quartz


class WindowCapture:
    """Handles window capturing from macOS applications."""
    
    def capture_window(self, window_title):
        """Capture a window by its title or owner name."""
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


class FrameOverlay:
    """Handles overlaying content onto video frames with transformations."""
    
    def warp_and_overlay(self, frame, content_img, dst_pts, opacity=1.0):
        """Warp content image to fit destination points and overlay on frame."""
        if content_img is None:
            return frame
        
        h, w, _ = content_img.shape
        src_pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst_pts_f = np.float32(dst_pts)
        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts_f)
        warped = cv2.warpPerspective(content_img, matrix, (frame.shape[1], frame.shape[0]))
        mask = np.zeros_like(frame, dtype=np.uint8)
        cv2.fillConvexPoly(mask, np.int32(dst_pts_f), (255, 255, 255))
        
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
