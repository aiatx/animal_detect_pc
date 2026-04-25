#!/usr/bin/env python3
import rospy
import math
import json
import time
import socket
from geometry_msgs.msg import PoseStamped
from mavros_msgs.srv import CommandBool, SetMode
from mavros_msgs.msg import State
from std_msgs.msg import String

# ================= 全局变量与状态枚举 =================
current_state = State()
current_pos = PoseStamped()

STATE_IDLE = 0
STATE_TAKEOFF = 1
STATE_PATROL = 2
STATE_RETREAT = 3
STATE_LANDING = 4
STATE_HOVER_CHECK = 5
STATE_DRIFT_ALIGN = 6

fsm_state = STATE_IDLE

# 视觉与追踪全局变量
vision_enabled = False
detected_animals = set()
current_grid_code = "UNKNOWN"

# 悬停与漂移计时/坐标
hover_start_time = 0
drift_target_x = 0.0
drift_target_y = 0.0
drift_start_time = 0


# ================= 核心遥测通信系统 =================
def send_udp_telemetry(msg):
    GS_IP = "127.0.0.1"
    GS_PORT = 8888
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(msg.encode('utf-8'), (GS_IP, GS_PORT))
    except Exception as e:
        rospy.logerr(f"UDP 遥测发送失败: {e}")


# ================= 回调函数 =================
def state_cb(msg):
    global current_state
    current_state = msg


def pos_cb(msg):
    global current_pos
    current_pos = msg


def vision_cb(msg):
    global fsm_state, detected_animals, current_grid_code, vision_enabled
    global drift_target_x, drift_target_y, drift_start_time

    # 只有在 vision_enabled 开启且处于悬停检查阶段才接受视觉信号
    if vision_enabled and fsm_state == STATE_HOVER_CHECK:
        try:
            parts = msg.data.split(':')
            animal_name = parts[0]
            err_px = float(parts[1])
            err_py = float(parts[2])

            if animal_name not in detected_animals:
                rospy.logwarn(f"!!! 锁定 {animal_name}，执行平滑对齐 !!!")
                detected_animals.add(animal_name)

                # 像素到物理距离映射 (1px ≈ 0.0025m)
                offset_x = -err_py * 0.0025
                offset_y = -err_px * 0.0025

                drift_target_x = current_pos.pose.position.x + offset_x
                drift_target_y = current_pos.pose.position.y + offset_y

                send_udp_telemetry(f"REPORT:{animal_name}@{current_grid_code}")

                drift_start_time = time.time()
                fsm_state = STATE_DRIFT_ALIGN
        except:
            pass


def get_distance(p1_x, p1_y, p1_z, p2_x, p2_y, p2_z):
    return math.sqrt((p1_x - p2_x) ** 2 + (p1_y - p2_y) ** 2 + (p1_z - p2_z) ** 2)


# ================= 核心状态机主循环 =================
def main_loop():
    global fsm_state, vision_enabled, current_grid_code, hover_start_time
    rospy.init_node('fsm_patrol_node', anonymous=True)

    rospy.Subscriber("mavros/state", State, state_cb)
    rospy.Subscriber("mavros/local_position/pose", PoseStamped, pos_cb)
    rospy.Subscriber("/vision/animal_detect", String, vision_cb)
    local_pos_pub = rospy.Publisher("mavros/setpoint_position/local", PoseStamped, queue_size=10)

    arming_client = rospy.ServiceProxy("mavros/cmd/arming", CommandBool)
    set_mode_client = rospy.ServiceProxy("mavros/set_mode", SetMode)

    rate = rospy.Rate(20.0)
    dt = 1.0 / 20.0

    try:
        with open("flight_mission.json", "r") as f:
            mission_wps = json.load(f)
    except:
        rospy.logerr("缺少航点文件！")
        return

    while not rospy.is_shutdown() and not current_state.connected:
        rate.sleep()

    pose = PoseStamped()
    for _ in range(100):
        local_pos_pub.publish(pose)
        rate.sleep()

    wp_index = 0
    TOLERANCE = 0.2

    while not rospy.is_shutdown():
        # 0. 待机与解锁
        if fsm_state == STATE_IDLE:
            if current_state.mode != "OFFBOARD":
                set_mode_client(custom_mode="OFFBOARD")
            elif not current_state.armed:
                arming_client(True)
            else:
                fsm_state = STATE_TAKEOFF

        # 1. 起飞
        elif fsm_state == STATE_TAKEOFF:
            pose.pose.position.z = 1.2
            if abs(current_pos.pose.position.z - 1.2) < TOLERANCE:
                fsm_state = STATE_PATROL

        # 2. 闭眼巡航
        elif fsm_state == STATE_PATROL:
            if wp_index >= len(mission_wps): break
            target = mission_wps[wp_index]
            current_task = target.get("task", "P")
            current_grid_code = target["grid"]

            # 航段初设：T/R/L 禁视，P 可视（但需进入 HOVER_CHECK 才真正检测）
            speed = 4.0 if current_task in ["T", "R", "L"] else 2.0
            vision_enabled = True if current_task == "P" else False

            step = speed * dt
            dx, dy = target["x"] - pose.pose.position.x, target["y"] - pose.pose.position.y
            dist = math.sqrt(dx ** 2 + dy ** 2)

            if dist > step:
                pose.pose.position.x += (dx / dist) * step
                pose.pose.position.y += (dy / dist) * step
            else:
                pose.pose.position.x, pose.pose.position.y = target["x"], target["y"]

            if get_distance(current_pos.pose.position.x, current_pos.pose.position.y, 1.2, target["x"], target["y"],
                            1.2) < TOLERANCE:
                send_udp_telemetry(f"ARRIVED:{target['grid']}")

                # --- 状态切换逻辑加固 ---
                if current_task == "L":
                    vision_enabled = False  # 强制关闭视觉，准备降落
                    fsm_state = STATE_RETREAT
                elif current_task == "P":
                    vision_enabled = True  # 显式开启视觉，准备检查
                    hover_start_time = time.time()
                    fsm_state = STATE_HOVER_CHECK
                else:
                    vision_enabled = False  # T 或 R 任务，继续关闭视觉
                    wp_index += 1

        # 5. 步进悬停检查 (0.8s)
        elif fsm_state == STATE_HOVER_CHECK:
            if time.time() - hover_start_time > 0.8:
                wp_index += 1
                vision_enabled = False  # 检查结束，前往下一点途中关闭视觉
                fsm_state = STATE_PATROL

        # 6. 平滑漂移对齐 (3.0s)
        elif fsm_state == STATE_DRIFT_ALIGN:
            pose.pose.position.x, pose.pose.position.y = drift_target_x, drift_target_y
            if time.time() - drift_start_time > 3.0:
                wp_index += 1
                vision_enabled = False  # 漂移结束，前往下一点途中关闭视觉
                fsm_state = STATE_PATROL

        # 3. 降落前退避
        elif fsm_state == STATE_RETREAT:
            pose.pose.position.x, pose.pose.position.y = 0.0, 1.2
            if get_distance(current_pos.pose.position.x, current_pos.pose.position.y, 1.2, 0, 1.2, 1.2) < TOLERANCE:
                fsm_state = STATE_LANDING

        # 4. 45度斜降
        elif fsm_state == STATE_LANDING:
            pose.pose.position.x, pose.pose.position.y, pose.pose.position.z = 0, 0, 0
            if current_pos.pose.position.z < 0.1:
                set_mode_client(custom_mode="AUTO.LAND")
                break

        local_pos_pub.publish(pose)
        rate.sleep()


if __name__ == '__main__':
    main_loop()