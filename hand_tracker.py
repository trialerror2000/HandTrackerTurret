
import cv2
import mediapipe as mp
import serial
import time

# ---------------- CONFIGURATION ----------------

PORT = "COM9"             # Your Pico COM port
CAMERA_INDEX = 1          # Replace with your external webcam index

PAN_CENTER = 90
TILT_CENTER = 90

PAN_RANGE = 35
TILT_RANGE = 30

# Change to -1 if an axis moves in the wrong direction
PAN_SIGN = 1
TILT_SIGN = 1

MIN_ANGLE = 45
MAX_ANGLE = 135

SMOOTHING = 0.20
DEAD_ZONE = 0.035

# -----------------------------------------------

# Connect to Pico
pico = serial.Serial(PORT, 115200, timeout=1)
time.sleep(2)

# Open external webcam
cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

if not cap.isOpened():
    pico.close()
    raise RuntimeError("External webcam not found")

# Webcam resolution
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# MediaPipe setup
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    model_complexity=0,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6
)

# Current servo positions
pan_now = float(PAN_CENTER)
tilt_now = float(TILT_CENTER)

last_sent = None
last_seen = time.monotonic()

def clamp(value):
    return max(MIN_ANGLE, min(MAX_ANGLE, value))

def apply_dead_zone(value):
    if abs(value) < DEAD_ZONE:
        return 0.0

    return value

def send_angles(pan_angle, tilt_angle):
    global last_sent

    command = (int(pan_angle), int(tilt_angle))

    if command != last_sent:
        message = f"{command[0]},{command[1]}\n"
        pico.write(message.encode())
        last_sent = command

try:
    # Start at center
    send_angles(PAN_CENTER, TILT_CENTER)

    while True:

        ret, frame = cap.read()

        if not ret:
            print("Camera frame unavailable")
            break

        # Mirror the preview
        frame = cv2.flip(frame, 1)

        height, width = frame.shape[:2]

        center_x = width / 2
        center_y = height / 2

        # Convert BGR to RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect hand
        results = hands.process(rgb)

        # Draw reference centre
        cv2.drawMarker(
            frame,
            (int(center_x), int(center_y)),
            (255, 255, 255),
            cv2.MARKER_CROSS,
            20,
            2
        )

        if results.multi_hand_landmarks:

            hand = results.multi_hand_landmarks[0]
            lm = hand.landmark

            # Palm center using landmarks 5 and 17
            hand_x = (lm[5].x + lm[17].x) / 2
            hand_y = (lm[5].y + lm[17].y) / 2

            # Convert normalized coordinates into pixels
            hand_x *= width
            hand_y *= height

            # Calculate normalized position errors
            error_x = (hand_x - center_x) / (width / 2)
            error_y = (center_y - hand_y) / (height / 2)

            # Ignore small movements around centre
            error_x = apply_dead_zone(error_x)
            error_y = apply_dead_zone(error_y)

            # Calculate target angles
            target_pan = (
                PAN_CENTER + PAN_SIGN * error_x * PAN_RANGE
            )

            target_tilt = (
                TILT_CENTER + TILT_SIGN * error_y * TILT_RANGE
            )

            target_pan = clamp(target_pan)
            target_tilt = clamp(target_tilt)

            # Smooth the servo movement
            pan_now += SMOOTHING * (target_pan - pan_now)
            tilt_now += SMOOTHING * (target_tilt - tilt_now)

            pan_cmd = round(pan_now)
            tilt_cmd = round(tilt_now)

            send_angles(pan_cmd, tilt_cmd)

            last_seen = time.monotonic()

            # Draw hand landmarks
            mp_draw.draw_landmarks(
                frame,
                hand,
                mp_hands.HAND_CONNECTIONS
            )

            # Draw palm centre
            px = int(hand_x)
            py = int(hand_y)

            cv2.circle(
                frame, (px, py), 8,
                (0, 255, 255), -1
            )

            cv2.line(
                frame,
                (int(center_x), int(center_y)),
                (px, py),
                (255, 0, 0), 2
            )

            cv2.putText(
                frame,
                f"Pan: {pan_cmd} Tilt: {tilt_cmd}",
                (15, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (0, 255, 0), 2
            )

        else:
            # Recenter after the hand has been absent for 1 second
            if time.monotonic() - last_seen > 1.0:

                pan_now += SMOOTHING * (
                    PAN_CENTER - pan_now
                )

                tilt_now += SMOOTHING * (
                    TILT_CENTER - tilt_now
                )

                send_angles(round(pan_now), round(tilt_now))

        cv2.putText(
            frame,
            "Press Q to quit",
            (15, height - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6, (255, 255, 255), 2
        )

        cv2.imshow("Hand Tracking Turret", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    # Return to neutral position
    try:
        pico.write(b"90,90\n")
        time.sleep(0.2)
        pico.close()
    except serial.SerialException:
        pass

    cap.release()
    hands.close()
    cv2.destroyAllWindows()
