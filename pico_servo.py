
from machine import Pin, PWM
import sys

# Servo connections
pan = PWM(Pin(16))    # Physical pin 21
tilt = PWM(Pin(17))   # Physical pin 22

pan.freq(50)
tilt.freq(50)

# Initial safe movement limits
MIN_ANGLE = 45
MAX_ANGLE = 135

def set_angle(servo, angle):
    angle = max(MIN_ANGLE, min(MAX_ANGLE, angle))

    # Approximately 1000–2000 microseconds
    pulse_us = 1000 + (angle / 180) * 1000

    servo.duty_ns(int(pulse_us * 1000))

def move_servos(pan_angle, tilt_angle):
    set_angle(pan, pan_angle)
    set_angle(tilt, tilt_angle)

# Start centered
move_servos(90, 90)

while True:
    line = sys.stdin.readline().strip()

    try:
        values = line.split(",")

        if len(values) == 2:
            pan_angle = int(values[0])
            tilt_angle = int(values[1])

            move_servos(pan_angle, tilt_angle)

    except (ValueError, TypeError):
        pass
