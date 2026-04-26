#!/usr/bin/env python3
import rospy
import math
import json
import time
import socket
import os  # <-- 新增：用于检查文件是否存在
from geometry_msgs.msg import PoseStamped
from mavros_msgs.srv import CommandBool, SetMode
from mavros_msgs.msg import State
from std_msgs.msg import String, Bool  # <-- Bool 用于接收起飞和刹车指令

# ================= 全局变量与状态枚举 =================
current_state = State()
current_pos = PoseStamped()

# 【新增】前置等待状态与紧急状态
STATE_WAIT_MISSION = -2
STATE_WAIT_TAKEOFF = -1

STATE_IDLE = 0
STATE_TAKEOFF = 1
STATE_PATROL = 2
STATE_RETREAT = 3
STATE_LANDING = 4
STATE_HOVER_CHECK = 5
STATE_DRIFT_ALIGN = 6
STATE_PAUSE = 99  # <-- 【新增】紧急悬停死锁状态

# 初始状态设为等待航线
fsm_state = STATE_WAIT_MISSION

# 视觉与追踪全局变量
vision_enabled = False
detected_animals = set()
current_grid_code = "UNKNOWN"

# 悬停与漂移计时/坐标
hover_start_time = 0
drift_target_x = 0.0
drift_target_y = 0.0
drift_start_time = 0

# 起飞授权锁与紧急刹车锁
takeoff_cmd_received = False
lock_x, lock_y, lock_z = 0.0, 0.0, 0.0  # 用于保存紧急刹车时的空间快照


# ================= 核心遥测通信系统 =================
def send_udp_telemetry(msg):
    GS_IP = "127.0.0.1"
    GS_PORT = 8888
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(msg.encode('utf-8'), (GS_IP, GS_PORT))
        rospy.loginfo(f"[UDP TX] -> {msg}")
    except Exception as e:
        rospy.logerr(f"UDP 遥测发送失败: {e}")


# ================= 回调函数 =================
def state_cb(msg):
    global current_state
    current_state = msg


def pos_cb(msg):
    global current_pos
    current_pos = msg


def takeoff_cb(msg):
    """接收来自 receiver 节点的起飞授权"""
    global takeoff_cmd_received
    if msg.data:
        takeoff_cmd_received = True


def pause_cb(msg):
    """【新增】接收来自 receiver 的紧急刹车指令"""
    global fsm_state, lock_x, lock_y, lock_z, vision_enabled
    # 只有在非暂停状态下收到 True 才执行刹车，防止重复触发
    if msg.data and fsm_state != STATE_PAUSE:
        rospy.logerr("!!! 触发紧急刹车！立刻拍下空间坐标快照 !!!")
        # 拍下坐标快照 (死死钉在这个位置)
        lock_x = current_pos.pose.position.x
        lock_y = current_pos.pose.position.y
        lock_z = current_pos.pose.position.z

        # 强行切断视觉神经，防止此时动物乱入改变状态
        vision_enabled = False

        # 强行切入 99 号死锁状态
        fsm_state = STATE_PAUSE
        send_udp_telemetry("STATUS:HOVERING")


def vision_cb(msg):
    global fsm_state, detected_animals, current_grid_code, vision_enabled
    global drift_target_x, drift_target_y, drift_start_time

    if vision_enabled and fsm_state == STATE_HOVER_CHECK:
        try:
            parts = msg.data.split(':')
            animal_name = parts[0]
            err_px = float(parts[1])
            err_py = float(parts[2])

            if animal_name not in detected_animals:
                rospy.logwarn(f"!!! 发现新目标: {animal_name}，执行漂移对齐 !!!")
                detected_animals.add(animal_name)

                # 物理映射
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


# ================= 主循环 =================
def main_loop():
    global fsm_state, vision_enabled, current_grid_code, hover_start_time
    global takeoff_cmd_received, lock_x, lock_y, lock_z
    rospy.init_node('fsm_patrol_node', anonymous=True)

    rospy.Subscriber("mavros/state", State, state_cb)
    rospy.Subscriber("mavros/local_position/pose", PoseStamped, pos_cb)
    rospy.Subscriber("/vision/animal_detect", String, vision_cb)

    rospy.Subscriber("/fsm/takeoff_cmd", Bool, takeoff_cb)
    # 【新增】订阅紧急悬停话题
    rospy.Subscriber("/fsm/pause_cmd", Bool, pause_cb)

    local_pos_pub = rospy.Publisher("mavros/setpoint_position/local", PoseStamped, queue_size=10)

    arming_client = rospy.ServiceProxy("mavros/cmd/arming", CommandBool)
    set_mode_client = rospy.ServiceProxy("mavros/set_mode", SetMode)

    rate = rospy.Rate(20.0)
    dt = 1.0 / 20.0

    send_udp_telemetry("STATUS:FSM_READY")

    mission_wps = []

    rospy.loginfo("等待飞控连接...")
    while not rospy.is_shutdown() and not current_state.connected:
        rate.sleep()
    rospy.loginfo("飞控已连接！建立心跳包...")

    pose = PoseStamped()
    for _ in range(100):
        local_pos_pub.publish(pose)
        rate.sleep()

    wp_index = 0
    TOLERANCE = 0.15

    rospy.loginfo("========== 状态机心跳启动 ==========")

    while not rospy.is_shutdown():

        # 99. 【新增】紧急悬停死锁
        if fsm_state == STATE_PAUSE:
            pose.pose.position.x = lock_x
            pose.pose.position.y = lock_y
            pose.pose.position.z = lock_z
            rospy.loginfo_throttle(2.0, "[紧急悬停] 坐标已死锁！请检查飞机状态，需手动重启节点以恢复。")

        # -2. 等待航线文件
        elif fsm_state == STATE_WAIT_MISSION:
            if os.path.exists("flight_mission.json"):
                try:
                    with open("flight_mission.json", "r") as f:
                        mission_wps = json.load(f)
                    rospy.loginfo(f"√ 成功加载航点文件！共包含 {len(mission_wps)} 个航点。")

                    send_udp_telemetry("REPLY:MISSION_LOADED")
                    fsm_state = STATE_WAIT_TAKEOFF
                except Exception as e:
                    rospy.logerr_throttle(2.0, f"读取 JSON 失败，可能文件写入中... 错误: {e}")
            else:
                rospy.loginfo_throttle(2.0, "[待机中] 死等 flight_mission.json 诞生...")

        # -1. 等待起飞授权
        elif fsm_state == STATE_WAIT_TAKEOFF:
            rospy.loginfo_throttle(2.0, "[待命] 航线已装载，等待地面站下发【起飞指令】...")
            if takeoff_cmd_received:
                rospy.logwarn(">>> 收到起飞指令，进入解锁起飞序列！ <<<")
                fsm_state = STATE_IDLE

        # 0. 待机与解锁
        elif fsm_state == STATE_IDLE:
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

        # 2. 巡航
        elif fsm_state == STATE_PATROL:
            if wp_index >= len(mission_wps): break
            target = mission_wps[wp_index]
            current_task = target.get("task", "P")
            current_grid_code = target["grid"]

            speed = 2.0 if current_task in ["T", "R", "L"] else 2.0
            vision_enabled = False

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
                if current_task == "L":
                    vision_enabled = False
                    fsm_state = STATE_RETREAT
                elif current_task == "P":
                    vision_enabled = True
                    hover_start_time = time.time()
                    fsm_state = STATE_HOVER_CHECK  # 去检查
                else:
                    wp_index += 1

        # 5. 悬停检测 (核心：多兽逻辑的循环入口)
        elif fsm_state == STATE_HOVER_CHECK:
            target = mission_wps[wp_index]
            pose.pose.position.x, pose.pose.position.y = target["x"], target["y"]

            if time.time() - hover_start_time > 0.8:
                rospy.loginfo(f"格子 {target['grid']} 扫描完毕，去下一处。")
                vision_enabled = False
                wp_index += 1
                fsm_state = STATE_PATROL

        # 6. 平滑对齐
        elif fsm_state == STATE_DRIFT_ALIGN:
            pose.pose.position.x, pose.pose.position.y = drift_target_x, drift_target_y
            if time.time() - drift_start_time > 3.0:
                rospy.loginfo(">> 展示完毕，回中心检测是否有遗漏目标...")
                hover_start_time = time.time()
                fsm_state = STATE_HOVER_CHECK

        # 3. 退避
        elif fsm_state == STATE_RETREAT:
            pose.pose.position.x, pose.pose.position.y = 0.0, 1.2
            if get_distance(current_pos.pose.position.x, current_pos.pose.position.y, 1.2, 0, 1.2, 1.2) < TOLERANCE:
                fsm_state = STATE_LANDING

        # 4. 降落
        elif fsm_state == STATE_LANDING:
            pose.pose.position.x, pose.pose.position.y, pose.pose.position.z = 0, 0, 0
            if current_pos.pose.position.z < 0.1:
                set_mode_client(custom_mode="AUTO.LAND")
                break

        local_pos_pub.publish(pose)
        rate.sleep()


if __name__ == '__main__':
    try:
        main_loop()
    except rospy.ROSInterruptException:
        pass