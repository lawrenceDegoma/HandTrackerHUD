import cv2
import time
from handtracker import HandTracker
from utils import get_current_track, toggle_play_pause, next_track, previous_track
from voice_control import start_voice_listener
from app_manager import AppManager
import queue


def main():
    _ = get_current_track()

    # start voice listener (background thread)
    cmd_queue = queue.Queue()
    stop_event = start_voice_listener(cmd_queue)

    cap = cv2.VideoCapture(0)
    
    # Optimize camera settings for 60 FPS performance
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)    # Set width to 1280 (720p)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)   # Set height to 720 (720p)
    cap.set(cv2.CAP_PROP_FPS, 60)             # Set to 60 FPS for high performance
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))  # Use MJPEG codec
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)    # Enable auto exposure
    cap.set(cv2.CAP_PROP_BRIGHTNESS, 0.5)     # Adjust brightness (0.0 to 1.0)
    cap.set(cv2.CAP_PROP_CONTRAST, 0.5)       # Adjust contrast (0.0 to 1.0)
    cap.set(cv2.CAP_PROP_SATURATION, 0.5)     # Adjust saturation (0.0 to 1.0)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)       # Reduce buffer size for lower latency
    
    # Print actual camera settings achieved
    actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"Camera settings: {int(actual_width)}x{int(actual_height)} @ {actual_fps}fps")
    
    tracker = HandTracker()
    app_manager = AppManager()

    # Performance monitoring for 60 FPS
    fps_counter = 0
    fps_start_time = time.time()
    last_fps_display = 0

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break

        frame = cv2.flip(frame, 1)

        # handle voice commands (non-blocking) if voice is enabled
        cmd = None
        if tracker.voice_enabled:
            try:
                cmd = cmd_queue.get_nowait()
            except queue.Empty:
                cmd = None

        # Only dispatch real voice commands to AppManager. When voice is disabled,
        # we will later bridge tracker.spawned_app to app_manager.spawn_app directly.
        if cmd is not None:
            app_manager.handle_command(cmd, tracker=tracker)

        frame = tracker.process_frame(frame)

        # If tracker requested a spawn but AppManager hasn't been notified, notify it now
        if tracker.spawned_app and not app_manager.current_app:
            # Call spawn_app directly to avoid routing through voice command parsing
            app_manager.spawn_app(tracker.spawned_app)
            # clear one-shot request
            tracker.spawned_app = None
        
        # Check if window was closed by gesture
        if hasattr(tracker, 'gesture_closed_window') and tracker.gesture_closed_window:
            app_manager.close_app()
            tracker.gesture_closed_window = False

        # Only fetch track info when we actually have a Spotify miniplayer active
        track_info = None
        if tracker.quad_active and len(tracker.quad_points) == 4 and app_manager.current_app == 'Spotify':
            track_info = tracker.get_cached_track_info()

        # Performance monitoring for 60 FPS
        fps_counter += 1
        current_time = time.time()
        if current_time - fps_start_time >= 1.0:  # Update every second
            current_fps = fps_counter / (current_time - fps_start_time)
            last_fps_display = current_fps
            fps_counter = 0
            fps_start_time = current_time

        # debug overlay: show spawn/app/quad state and FPS
        try:
            debug_lines = [
                f"FPS: {last_fps_display:.1f}",
                f"Voice: {'ON' if tracker.voice_enabled else 'OFF'} (Say 'Hey computer')",
                f"spawned_app: {tracker.spawned_app}",
                f"app_manager: {app_manager.current_app}",
                f"quad_pts: {len(tracker.quad_points)}",
                f"quad_active: {tracker.quad_active}",
            ]
            y = 20
            for line in debug_lines:
                cv2.putText(frame, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                y += 18
        except Exception:
            pass

        # if an app is spawned, draw it in the quad
        if tracker.quad_active and len(tracker.quad_points) == 4 and app_manager.current_app:
            frame = app_manager.draw_app_in_rect(frame, tracker.quad_points, volume=tracker.current_volume, track_info=track_info)

        cv2.imshow('Hand Tracker', frame)

        key = cv2.waitKey(10) & 0xFF
        # 'Esc' to exit
        if key == 27:
            break

        elif key == ord('c'):
            tracker.points.clear()

        elif key == ord('v'):
            tracker.volume_gesture_enabled = not tracker.volume_gesture_enabled
            print("Volume gesture mode:", tracker.volume_gesture_enabled)

        elif key == ord('h'):
            tracker.show_hand_skeleton = not tracker.show_hand_skeleton
            print("Hand skeleton display:", tracker.show_hand_skeleton)

        # toggle voice listener with 'm'
        elif key == ord('m'):
            tracker.voice_enabled = not tracker.voice_enabled
            print("Voice enabled:", tracker.voice_enabled)
            if tracker.voice_enabled:
                # ensure listener running
                if stop_event.is_set():
                    stop_event = start_voice_listener(cmd_queue)
            else:
                # mute listener
                stop_event.set()

        # 't' for tracing
        elif key == ord('t'):
            tracker.tracing_enabled = not tracker.tracing_enabled

        # 'f' to cycle frame rate (30 -> 60 -> 120 -> 30)
        elif key == ord('f'):
            current_fps = int(cap.get(cv2.CAP_PROP_FPS))
            if current_fps <= 30:
                cap.set(cv2.CAP_PROP_FPS, 60)
                print("Switched to 60 FPS")
            elif current_fps <= 60:
                cap.set(cv2.CAP_PROP_FPS, 120)
                print("Switched to 120 FPS")
            else:
                cap.set(cv2.CAP_PROP_FPS, 30)
                print("Switched to 30 FPS")
            actual_fps = cap.get(cv2.CAP_PROP_FPS)
            print(f"Actual FPS: {actual_fps}")

        # 'r' to cycle resolution (720p -> 1080p -> 480p -> 720p)
        elif key == ord('r'):
            current_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            current_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            if current_width == 1280 and current_height == 720:  # 720p -> 1080p
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
                print("Switched to 1080p")
            elif current_width == 1920 and current_height == 1080:  # 1080p -> 480p
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                print("Switched to 480p")
            else:  # 480p or other -> 720p
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                print("Switched to 720p")
                
            # Print actual resolution achieved
            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"Actual resolution: {actual_w}x{actual_h}")

        # 'b' to adjust brightness
        elif key == ord('b'):
            current_brightness = cap.get(cv2.CAP_PROP_BRIGHTNESS)
            new_brightness = (current_brightness + 0.1) % 1.0
            cap.set(cv2.CAP_PROP_BRIGHTNESS, new_brightness)
            print(f"Brightness: {new_brightness:.1f}")

        # 'n' to adjust contrast  
        elif key == ord('n'):
            current_contrast = cap.get(cv2.CAP_PROP_CONTRAST)
            new_contrast = (current_contrast + 0.1) % 1.0
            cap.set(cv2.CAP_PROP_CONTRAST, new_contrast)
            print(f"Contrast: {new_contrast:.1f}")

        elif key == ord('q'):
            tracker.toggle_quad()
            print("Quad toggled")

    # stop voice listener and cleanup
    stop_event.set()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
