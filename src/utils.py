import cv2

def draw_landmarks(image, hand_landmarks, connections):
    for connection in connections:
        start = hand_landmarks.landmark[connection[0]]
        end = hand_landmarks.landmark[connection[1]]
        start_point = (int(start.x * image.shape[1]), int(start.y * image.shape[0]))
        end_point = (int(end.x * image.shape[1]), int(end.y * image.shape[0]))
        cv2.line(image, start_point, end_point, (0, 255, 0), 2)

def process_frame(frame, hands):
    results = hands.process(frame)
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            draw_landmarks(frame, hand_landmarks, HAND_CONNECTIONS)
    return frame

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),  # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),  # Index
    (0, 9), (9, 10), (10, 11), (11, 12),  # Middle
    (0, 13), (13, 14), (14, 15), (15, 16),  # Ring
    (0, 17), (17, 18), (18, 19), (19, 20)   # Pinky
]
