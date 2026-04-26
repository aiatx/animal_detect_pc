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
    """向上位机（高级地面站）回传数据"""
    GS_IP = "127.0.0.1"
    GS_PORT = 8888
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(msg.encode('utf-8'), (GS_IP, GS_PORT))
        # 恢复调试打印，让你能看到发给地面站了啥
        rospy.loginfo(f"[UDP 发送] -> {msg}")
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

    # 核心逻辑：只有开启了视觉神经且处于悬停检查时，才处理识别结果
    if vision_enabled and fsm_state == STATE_HOVER_CHECK:
        try:
            parts = msg.data.split(':')
            animal_name = parts[0]
            err_px = float(parts[1])
            err_py = float(parts[2])

            if animal_name not in detected_animals:
                rospy.logwarn(f"!!! 视觉锁定: 在 {current_grid_code} 发现 {animal_name}，执行平滑对齐 !!!")
                detected_animals.add(animal_name)

                # 像素到物理距离映射
                offset_x = -err_py * 0.0025
                offset_y = -err_px * 0.0025

                drift_target_x = current_pos.pose.position.x + offset_x
                drift_target_y = current_pos.pose.position.y + offset_y

                # 【核心回传 1】：向地面站汇报发现了什么，在哪发现的
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
        rospy.loginfo(f"成功加载航点文件！共包含 {len(mission_wps)} 个航点。")
    except:
        rospy.logerr("缺少 flight_mission.json 文件，请检查 UDP 接收节点是否正常运行！")
        return

    rospy.loginfo("等待飞控连接...")
    while not rospy.is_shutdown() and not current_state.connected:
        rate.sleep()
    rospy.loginfo("飞控已连接！准备接管控制权...")

    pose = PoseStamped()
    for _ in range(100):
        local_pos_pub.publish(pose)
        rate.sleep()

    wp_index = 0
    TOLERANCE = 0.15  # 稍微收紧精度，保证变色准时

    rospy.loginfo("========== 飞行状态机正式启动 ==========")

    while not rospy.is_shutdown():
        # 0. 待机与解锁
        if fsm_state == STATE_IDLE:
            if current_state.mode != "OFFBOARD":
                set_mode_client(custom_mode="OFFBOARD")
            elif not current_state.armed:
                arming_client(True)
            else:
                rospy.loginfo(">> [状态切换] 已解锁，开始垂直起飞至 Z=1.2m")
                fsm_state = STATE_TAKEOFF

        # 1. 起飞
        elif fsm_state == STATE_TAKEOFF:
            pose.pose.position.x = 0
            pose.pose.position.y = 0
            pose.pose.position.z = 1.2
            if abs(current_pos.pose.position.z - 1.2) < TOLERANCE:
                rospy.loginfo(">> [状态切换] 到达起飞高度，切入巡航网络")
                fsm_state = STATE_PATROL

        # 2. 闭眼巡航
        elif fsm_state == STATE_PATROL:
            if wp_index >= len(mission_wps): break
            target = mission_wps[wp_index]
            current_task = target.get("task", "P")
            current_grid_code = target["grid"]

            speed = 4.0 if current_task in ["T", "R", "L"] else 2.0
            # 巡航途中不开启视觉，节省算力，防止误触
            vision_enabled = False

            step = speed * dt
            dx, dy = target["x"] - pose.pose.position.x, target["y"] - pose.pose.position.y
            dist = math.sqrt(dx ** 2 + dy ** 2)

            if dist > step:
                pose.pose.position.x += (dx / dist) * step
                pose.pose.position.y += (dy / dist) * step
            else:
                pose.pose.position.x, pose.pose.position.y = target["x"], target["y"]

            # 判断是否到达目标点中心
            if get_distance(current_pos.pose.position.x, current_pos.pose.position.y, 1.2, target["x"], target["y"],
                            1.2) < TOLERANCE:

                rospy.loginfo(f"√ 到达航点: {target['grid']} [任务类型: {current_task}]")

                # 【核心回传 2】：告诉地面站，“我已经飞到了这个格子”，让它变色！
                send_udp_telemetry(f"ARRIVED:{target['grid']}")

                if current_task == "L":
                    rospy.loginfo(">> [触发降落] 识别到终点标记 L，彻底关闭视觉，准备退避！")
                    vision_enabled = False
                    fsm_state = STATE_RETREAT
                elif current_task == "P":
                    # 进入悬停检查，显式开启视觉神经
                    rospy.loginfo(">> [状态切换] 进入步进悬停 (0.8s)，视觉神经已开启。")
                    vision_enabled = True
                    hover_start_time = time.time()
                    fsm_state = STATE_HOVER_CHECK
                else:
                    # T 或 R 任务，直接去下一点
                    wp_index += 1

        # 5. 步进悬停检查 (0.8s)
        elif fsm_state == STATE_HOVER_CHECK:
            # 保持坐标在格子中心
            target = mission_wps[wp_index]
            pose.pose.position.x, pose.pose.position.y = target["x"], target["y"]

            if time.time() - hover_start_time > 0.8:
                # 时间到没发现目标，关闭视觉去下一处
                rospy.loginfo(f"-> {target['grid']} 无目标，闭眼全速前往下一网格。")
                vision_enabled = False
                wp_index += 1
                fsm_state = STATE_PATROL

        # 6. 平滑漂移对齐 (3.0s)
        elif fsm_state == STATE_DRIFT_ALIGN:
            pose.pose.position.x, pose.pose.position.y = drift_target_x, drift_target_y
            if time.time() - drift_start_time > 3.0:
                rospy.loginfo(">> [对齐展示完毕] 目标已锁定，切回巡航状态。")
                vision_enabled = False  # 展示结束，关闭视觉去下一处
                wp_index += 1
                fsm_state = STATE_PATROL

        # 3. 降落前退避
        elif fsm_state == STATE_RETREAT:
            pose.pose.position.x, pose.pose.position.y = 0.0, 1.2
            if get_distance(current_pos.pose.position.x, current_pos.pose.position.y, 1.2, 0, 1.2, 1.2) < TOLERANCE:
                rospy.loginfo(">> [退避完成] 准备进入 45 度斜线降落。")
                fsm_state = STATE_LANDING

        # 4. 45度斜降
        elif fsm_state == STATE_LANDING:
            pose.pose.position.x, pose.pose.position.y, pose.pose.position.z = 0, 0, 0
            if current_pos.pose.position.z < 0.1:
                rospy.logwarn(">> [着陆成功] 触发 AUTO.LAND 断桨！任务圆满结束。")
                set_mode_client(custom_mode="AUTO.LAND")
                break

        local_pos_pub.publish(pose)
        rate.sleep()


if __name__ == '__main__':
    try:
        main_loop()
    except rospy.ROSInterruptException:
        pass