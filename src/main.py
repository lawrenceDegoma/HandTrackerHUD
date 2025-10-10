import cv2
from handtracker import HandTracker
from utils import get_current_track, toggle_play_pause, next_track, previous_track
from voice_control import start_voice_listener
import queue


def main():
    _ = get_current_track()

    # start voice listener (background thread)
    cmd_queue = queue.Queue()
    stop_event = start_voice_listener(cmd_queue)

    cap = cv2.VideoCapture(0)
    tracker = HandTracker()

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

        if cmd:
            print("Voice command:", cmd)
            if "open spotify" in cmd or "spawn spotify" in cmd or "open spotify window" in cmd:
                tracker.spawn_miniplayer("Spotify")
            elif "close spotify" in cmd or "hide spotify" in cmd:
                tracker.spawned_app = None
                tracker.toggle_quad()
            elif "play" in cmd and "pause" not in cmd:
                toggle_play_pause()
            elif "pause" in cmd:
                toggle_play_pause()
            elif "next" in cmd:
                next_track()
            elif "previous" in cmd or "prev" in cmd:
                previous_track()
            elif "volume mode" in cmd or "volume gesture" in cmd:
                tracker.volume_gesture_enabled = not tracker.volume_gesture_enabled
                print("Volume gesture mode:", tracker.volume_gesture_enabled)

        frame = tracker.process_frame(frame)
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
