#!/usr/bin/python3

# This is the same as mjpeg_server.py, but uses the h/w MJPEG encoder.
import threading
import io
import logging
import socketserver
from http import server
from threading import Condition
import libcamera
import urllib
from src import motor as motor_module
from src import distance_sensor as distance_sensor_module
import time
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput


ROBOT_STATE = "HALT"
ROBOT_X = 0 
PAGE = """\
<html>
<head>
<title>picamera2 MJPEG streaming demo</title>
</head>
<body>
<h1>Picamera2 MJPEG Streaming Demo</h1>
<img src="stream.mjpg" width="640" height="480" />
</body>
</html>
"""


class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()
    def do_PUT(self):
            content_length = int(self.headers['Content-Length'])
            put_data = self.rfile.read(content_length).decode("utf-8")

            data = urllib.parse.parse_qs(put_data)

            print("Received data:", data)
            global ROBOT_STATE
            global ROBOT_X
            if 'ROBOT_STATE' in data.keys():
                ROBOT_STATE = data['ROBOT_STATE'][0]
            if 'ROBOT_X' in data.keys():
                ROBOT_X = data['ROBOT_X'][0]
            print(data)
            self.send_response(200)
            self.end_headers()
            response_message = "PUT request processed successfully."
            self.wfile.write(response_message.encode())
CENTER_X = 65
def motor_control():
    motor1 = motor_module.Motor({
        "pins": {
            "speed": 13,
            "control1": 5,
            "control2": 6
        }
    })

    motor2 = motor_module.Motor({
        "pins": {
            "speed": 12,
            "control1": 7,
            "control2": 8
        }
    })
    distance_sensor1 = distance_sensor_module.DistanceSensor({
        "pins": {
            "echo": 23,
            "trigger": 24
        }
    })

    distance_sensor2 = distance_sensor_module.DistanceSensor({
        "pins": {
            "echo": 17,
            "trigger": 27
        }
    })
    while True:
        try:
            if (ROBOT_STATE == 'INVALID' or ROBOT_STATE == 'HALT'):
                motor1.stop()
                motor2.stop()
            elif (ROBOT_STATE == 'EXPLORE'):
                motor1.forward(0.6)
                motor2.stop()
            elif (ROBOT_X - CENTER_X <= 5):
                motor2.forward(0.8*0.9)
                motor1.forward(0.8)
            elif (CENTER_X - ROBOT_X <= 5):
                motor1.forward(0.8*0.9)
                motor2.forward(0.8)
            elif (distance_sensor1.distance <= 0.1 or distance_sensor2.distance <= 0.1):
                motor1.stop()
                motor2.stop()
        except e:
            print(e)
            print("Motor control failed!")

motor_t = threading.Thread(target=motor_control, daemon=True)
motor_t.start()
class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


picam2 = Picamera2()
server_config = picam2.create_video_configuration(main={"size": (640, 480)})
server_config["transform"] = libcamera.Transform(vflip=1)
picam2.configure(server_config)
output = StreamingOutput()
picam2.start_recording(MJPEGEncoder(), FileOutput(output))


try:
    address = ('', 8000)
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()
    motor_control()
finally:
    picam2.stop_recording()
