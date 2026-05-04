#!/usr/bin/env python3
import rospy
import numpy as np
import cv2
import socket
import math
from std_msgs.msg import String, Bool
from ultralytics import YOLO

# ================= 核心遥测通信系统 =================
GS_IP = "192.168.151.101"
GS_PORT = 8888


def send_udp_telemetry(msg):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(msg.encode('utf-8'), (GS_IP, GS_PORT))
        if not msg.startswith("STATUS:"):
            rospy.loginfo(f"[UDP TX] -> {msg}")
    except Exception as e:
        rospy.logerr(f"UDP 遥测发送失败: {e}")


def ping_cb(msg):
    send_udp_telemetry("STATUS:VISION_READY")


def start_vision_node():
    rospy.init_node('usb_cam_yolo_node', anonymous=True)
    vision_pub = rospy.Publisher('/vision/animal_detect', String, queue_size=1)
    rospy.Subscriber('/sys/ping', Bool, ping_cb)

    # ================= 1. 加载 TensorRT 引擎 =================
    rospy.loginfo("正在载入 TensorRT 引擎...")
    ENGINE_PATH = "/home/nvidia/catkin_ws/src/animal_detect/models/best26_map0.72.engine"
    model = YOLO(ENGINE_PATH, task="detect")

    # ================= 2. 初始化相机并应用调试参数 =================
    cam_index = 0
    cap = cv2.VideoCapture(cam_index)

    # 设置分辨率
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # 【根据调试截图修改】：
    # 1. 开启自动模式 (根据截图，3 是你最清晰的状态)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 3)

    # 2. 设置增益 (根据截图，56 是你最清晰的状态)
    # 增益高可以提高暗部细节，但也可能引入噪声，56 是个很稳的中间值
    cap.set(cv2.CAP_PROP_GAIN, 56)

    # 注意：在 Auto_Exp=3 模式下，手动设置 CAP_PROP_EXPOSURE 通常无效，所以这里不再设置

    if not cap.isOpened():
        rospy.logerr(f"无法打开 /dev/video{cam_index}！")
        return

    rospy.loginfo(f"下视相机启动成功！已应用调试参数 (AutoExp:3, Gain:56)。")
    send_udp_telemetry("STATUS:VISION_READY")

    # ================= 3. 定义判准参数 =================
    center_x = 320
    center_y = 240
    TRIGGER_RADIUS = 80
    CONFIRM_FRAMES = 3
    detection_counts = {}

    rate = rospy.Rate(15)

    try:
        while not rospy.is_shutdown():
            ret, frame = cap.read()
            if not ret:
                rospy.logwarn_throttle(2.0, "未能获取相机画面...")
                continue

            # ================= 4. YOLO 推理 =================
            results = model.predict(frame, conf=0.35, verbose=False)
            seen_this_frame = set()

            for r in results:
                boxes = r.boxes
                for box in boxes:
                    cls_id = int(box.cls[0])
                    class_name = model.names[cls_id]
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    animal_cx = (x1 + x2) / 2
                    animal_cy = (y1 + y2) / 2

                    err_px = animal_cx - center_x
                    err_py = animal_cy - center_y
                    dist_to_center = math.sqrt(err_px ** 2 + err_py ** 2)

                    if dist_to_center < TRIGGER_RADIUS:
                        seen_this_frame.add(class_name)
                        count = detection_counts.get(class_name, 0)
                        if count >= 0:
                            detection_counts[class_name] = count + 1

                        if detection_counts[class_name] >= CONFIRM_FRAMES:
                            msg_str = f"{class_name}:{err_px:.1f}:{err_py:.1f}"
                            vision_pub.publish(msg_str)
                            rospy.logwarn(f"🎯 [锁定确认] {class_name}")
                            detection_counts[class_name] = -20
                    else:
                        detection_counts[class_name] = 0

            for name in list(detection_counts.keys()):
                if name not in seen_this_frame:
                    if detection_counts[name] > 0:
                        detection_counts[name] = 0
                    elif detection_counts[name] < 0:
                        detection_counts[name] += 1

            rate.sleep()

    finally:
        cap.release()


if __name__ == '__main__':
    try:
        start_vision_node()
    except rospy.ROSInterruptException:
        pass