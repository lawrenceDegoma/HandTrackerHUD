"""
Volume Control

This module handles volume gesture recognition and background
Spotify volume control with rate limiting.
"""

import threading
import queue
import time
import math
import numpy as np


class VolumeController:
    """Handles volume gesture recognition and Spotify volume control."""
    
    def __init__(self):
        self.volume_gesture_enabled = False
        self.last_volume_set = 0
        self.current_volume = None
        
        # Volume worker: non-blocking updates to Spotify
        self._volume_queue = queue.Queue()
        self._volume_worker_stop = threading.Event()
        self._volume_worker_thread = threading.Thread(
            target=self._volume_worker, daemon=True
        )
        self._volume_worker_thread.start()
    
    def calculate_volume_from_pinch(self, thumb_xy, index_xy):
        """Calculate volume level from pinch distance."""
        if not self.volume_gesture_enabled:
            return None
            
        pinch_dist = math.hypot(index_xy[0] - thumb_xy[0], index_xy[1] - thumb_xy[1])
        
        min_dist, max_dist = 20, 200
        volume = int(
            np.clip(
                (pinch_dist - min_dist) / (max_dist - min_dist) * 100, 0, 100
            )
        )
        
        # Only update if there's a significant change
        if abs(volume - self.last_volume_set) > 2:
            self._enqueue_volume(volume)
            self.last_volume_set = volume
        
        return volume
    
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
        from utils import set_volume
        
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
    
    def cleanup(self):
        """Stop the volume worker thread."""
        self._volume_worker_stop.set()
        if self._volume_worker_thread.is_alive():
            self._volume_worker_thread.join(timeout=1)
