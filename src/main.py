import cv2
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
    tracker = HandTracker()
    app_manager = AppManager()

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

        # fetch cached track info once per loop
        track_info = tracker.get_cached_track_info()

        # debug overlay: show spawn/app/quad state
        try:
            debug_lines = [
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

        elif key == ord('q'):
            tracker.toggle_quad()
            print("Quad toggled")

    # stop voice listener and cleanup
    stop_event.set()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
