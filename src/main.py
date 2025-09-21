import cv2
from handtracker import HandTracker

def main():
    cap = cv2.VideoCapture(0)
    tracker = HandTracker()

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break

        frame = cv2.flip(frame, 1)

        frame = tracker.process_frame(frame)
        cv2.imshow('Hand Tracker', frame)

        key = cv2.waitKey(10) & 0xFF
        # 'Esc' to exit
        if key == 27:  
            break

        elif key == ord('c'):
            tracker.points.clear()

        # 't' for tracing
        elif key == ord('t'):
            tracker.tracing_enabled = not tracker.tracing_enabled
        
        elif key == ord('q'):
            tracker.toggle_quad()
            print("Quad toggled")

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
