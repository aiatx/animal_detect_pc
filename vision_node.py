#!/usr/bin/env python3
import rospy
import numpy as np
import pyrealsense2 as rs
import socket  # <-- 新增：用于 UDP 通信
from std_msgs.msg import String
from ultralytics import YOLO

# ================= 核心遥测通信系统 =================
GS_IP = "127.0.0.1"
GS_PORT = 8888


def send_udp_telemetry(msg):
    """向上位机（高级地面站）回传状态数据"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(msg.encode('utf-8'), (GS_IP, GS_PORT))
        # 视觉节点平时不发 UDP（发的是 ROS），只在初始化时发状态，所以打印出来没关系
        rospy.loginfo(f"[UDP TX] -> {msg}")
    except Exception as e:
        rospy.logerr(f"UDP 遥测发送失败: {e}")


def start_vision_node():
    rospy.init_node('realsense_yolo_node', anonymous=True)

    # 建立与 FSM 通信的专属神经通道
    vision_pub = rospy.Publisher('/vision/animal_detect', String, queue_size=1)

    # ================= 1. 加载 TensorRT 引擎 =================
    rospy.loginfo("正在将 .engine 载入 Jetson 的 GPU...")
    model = YOLO("yolo_middle_best.engine", task="detect")

    # ================= 2. 初始化 Intel RealSense =================
    rospy.loginfo("正在唤醒 Intel RealSense 深度相机 (Headless 模式)...")
    pipeline = rs.pipeline()
    config = rs.config()

    # 强制 640x480 @ 30fps，输出 BGR 格式直接喂给 YOLO
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

    try:
        pipeline.start(config)
        rospy.loginfo("相机启动成功！图像渲染已关闭，算力 100% 倾斜至推理引擎。")

        # 【握手协议核心】：通知地面站视觉节点已彻底就绪，随时可以打猎！
        send_udp_telemetry("STATUS:VISION_READY")

    except Exception as e:
        rospy.logerr(f"RealSense 启动失败，请检查连线！错误: {e}")
        return

    # ================= 3. 定义绝对触发区 (ROI) =================
    center_x = 320
    center_y = 240

    # 200x200 像素 -> 对应 0.5m x 0.5m 物理网格
    ROI_HALF_SIZE = 100

    roi_x1 = center_x - ROI_HALF_SIZE
    roi_y1 = center_y - ROI_HALF_SIZE
    roi_x2 = center_x + ROI_HALF_SIZE
    roi_y2 = center_y + ROI_HALF_SIZE

    rate = rospy.Rate(30)

    try:
        while not rospy.is_shutdown():
            frames = pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()
            if not color_frame:
                continue

            # 直接转成 NumPy 数组，零拷贝开销
            frame = np.asanyarray(color_frame.get_data())

            # ================= 4. TensorRT 推理 =================
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

                        # 瞬间发送给 FSM 节点！
                        msg_str = f"{class_name}:{err_px:.1f}:{err_py:.1f}"
                        vision_pub.publish(msg_str)

                        # 仅在终端打印极简日志
                        rospy.logwarn(f"[Vision] 锁定 {class_name} | 偏差(px): x={err_px:.1f}, y={err_py:.1f}")

            rate.sleep()

    finally:
        rospy.loginfo("关闭 RealSense 管道...")
        pipeline.stop()


if __name__ == '__main__':
    try:
        start_vision_node()
    except rospy.ROSInterruptException:
        pass