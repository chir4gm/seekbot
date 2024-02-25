from ultralytics import YOLO
from openai import OpenAI
import threading
import time
import cv2
import IPython
from PIL import Image
import os
import sys
model = YOLO('yolov8l.pt')  
import openai
import requests
import os
openai.api_key = os.getenv('OPENAI_API_KEY')
VIDEO_URL = "http://172.16.120.29:8000/stream.mjpg"
SERVER_URL = "http://172.16.120.29:8000"

ROBOT_STATE = ""
ROBOT_X = 0
visible_classes = [] 
visible_classes_acc = threading.Condition()
# OpenAI prompt engineering code
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

def send_put_requests():
    while True:
        global ROBOT_STATE
        global ROBOT_X
        data = {
            'ROBOT_STATE': ROBOT_STATE,
            'ROBOT_X': int(ROBOT_X) 
        }
        response = requests.put(SERVER_URL, data=data)
        time.sleep(0.5)

 # Print server response
def api_calling(command): 
    global visible_classes
    prompt = f"""
    You are a LLM guiding a robot that with a camera.
    RESPOND WITH A SINGLE WORD!
    The robot's camera feed is fed through an Object Detection pipeline.
    Detected Objects:{visible_classes}
    This is what the user says they want to do or get:
    User Command:{command}
    From the user's command respond with a single item from the detected objects list
    If the user wants to stop the robot, respond with 'HALT'
    If the user wants to look for more items, respond with 'EXPLORE'
    If you are confused in any manner, respond with 'INVALID'
    Your response should be case-matching with the list. It can also be HALT, EXPLORE, INVALID
    RESPOND WITH A SINGLE CASE MATCHING WORD
    """
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model="gpt-3.5-turbo-1106",
        max_tokens=120
    )
    message = chat_completion.choices[0].message.content 
    global ROBOT_STATE
    global ROBOT_X
    ROBOT_STATE = message
    print(message)
    return chat_completion
read_counter = 0
frame_step = 10
names = model.names
read_counter = 0
def object_detection():
    global visible_classes
    global ROBOT_X
    read_counter = 0
    while True:
        results = model.predict(source=VIDEO_URL, verbose=False, stream=True, show=True)
        curr_cls = []
        for r in results:
            for boxes, c in zip(r.boxes.xyxy, r.boxes.cls):
                cls = names[int(c)]
                curr_cls.append(cls)
                if (ROBOT_STATE == cls):
                    print(boxes)
                    ROBOT_X = boxes[2] - boxes[0]
                    ROBOT_X /= 2
                    continue
            break
        visible_classes = curr_cls
        read_counter += 1
#object_detection()
obj_detect_thread = threading.Thread(target=object_detection, daemon=True)
put_req_thread = threading.Thread(target=send_put_requests, daemon=True)
obj_detect_thread.start()
put_req_thread.start()

try:
    while True:
        command = input("What would you like the robot to do?")
        print(visible_classes)
        if command.lower() == 'exit':
            break
        if len(command) != 0:
            api_calling(command)
except KeyboardInterrupt:
    print("Program terminated by user.")
    quit()