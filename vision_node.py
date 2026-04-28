#!/usr/bin/env python3
import rospy
import numpy as np
import cv2  # <-- 【核心修改】：已彻底移除 pyrealsense2，换成免驱之王 OpenCV
import socket
from std_msgs.msg import String, Bool
from ultralytics import YOLO

# ================= 核心遥测通信系统 =================
GS_IP = "198.162.151.102"
GS_PORT = 8888


def send_udp_telemetry(msg):
    """向上位机（高级地面站）回传状态数据"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(msg.encode('utf-8'), (GS_IP, GS_PORT))

        # 过滤掉频繁的心跳包打印，防止终端疯狂刷屏
        if not msg.startswith("STATUS:"):
            rospy.loginfo(f"[UDP TX] -> {msg}")

    except Exception as e:
        rospy.logerr(f"UDP 遥测发送失败: {e}")


def ping_cb(msg):
    # 只要听到 receiver 吹哨，立刻向地面站补发一次自己的存活证明
    send_udp_telemetry("STATUS:VISION_READY")


def start_vision_node():
    rospy.init_node('usb_cam_yolo_node', anonymous=True)

    # 建立与 FSM 通信的专属神经通道
    vision_pub = rospy.Publisher('/vision/animal_detect', String, queue_size=1)

    # 挂载一只“耳朵”，专门监听全局查岗广播
    rospy.Subscriber('/sys/ping', Bool, ping_cb)

    # ================= 1. 加载 TensorRT 引擎 =================
    rospy.loginfo("正在将 .engine 载入 Jetson 的 GPU...")
    model = YOLO("yolo_middle_best.engine", task="detect")

    # ================= 2. 初始化 OpenCV 下视相机 =================
    cam_index = 0  # 刚才查出来的 /dev/video0
    rospy.loginfo(f"正在唤醒下视 USB 相机 (设备号: /dev/video{cam_index})...")

    cap = cv2.VideoCapture(cam_index)

    # 强制分辨率 640x480，防止有的摄像头默认开 1080P 把算力卡死
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        rospy.logerr(f"无法打开 /dev/video{cam_index}！请检查相机硬件或连线。")
        return

    rospy.loginfo("下视相机启动成功！图像渲染已关闭，算力 100% 倾斜至推理引擎。")

    # 通知地面站视觉节点已彻底就绪
    send_udp_telemetry("STATUS:VISION_READY")

    # ================= 3. 定义绝对触发区 (ROI) =================
    center_x = 320
    center_y = 240

    # 200x200 像素 -> 对应 0.5m x 0.5m 物理网格
    ROI_HALF_SIZE = 100

    roi_x1 = center_x - ROI_HALF_SIZE
    roi_y1 = center_y - ROI_HALF_SIZE
    roi_x2 = center_x + ROI_HALF_SIZE
    roi_y2 = center_y + ROI_HALF_SIZE

    # 【核心修改】：帧率降为 15，减轻系统压力，完美契合飞控漂移反馈速度
    rate = rospy.Rate(15)

    try:
        while not rospy.is_shutdown():
            # 抓取一帧
            ret, frame = cap.read()
            if not ret:
                rospy.logwarn_throttle(2.0, "未能获取下视相机画面，检查硬件连接...")
                continue

            # ================= 4. TensorRT 推理 =================
            # OpenCV 读取的 frame 已经是 Numpy 数组且是 BGR 格式，直接喂给 YOLO 即可
            results = model.predict(frame, conf=0.4, verbose=False)

            for r in results:
                boxes = r.boxes
                for box in boxes:
                    cls_id = int(box.cls[0])
                    class_name = model.names[cls_id]

                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    animal_cx = (x1 + x2) / 2
                    animal_cy = (y1 + y2) / 2

                    # ================= 5. 核心：在不在准心区？ =================
                    if (roi_x1 < animal_cx < roi_x2) and (roi_y1 < animal_cy < roi_y2):
                        # 计算像素偏差 (带着正负号)
                        err_px = animal_cx - center_x
                        err_py = animal_cy - center_y

                        # 瞬间发送给 FSM 节点
                        msg_str = f"{class_name}:{err_px:.1f}:{err_py:.1f}"
                        vision_pub.publish(msg_str)

                        # 仅在终端打印极简日志
                        rospy.logwarn(f"[Vision] 锁定 {class_name} | 偏差(px): x={err_px:.1f}, y={err_py:.1f}")

            rate.sleep()

    finally:
        rospy.loginfo("关闭下视相机...")
        cap.release()


if __name__ == '__main__':
    try:
        start_vision_node()
    except rospy.ROSInterruptException:
        pass