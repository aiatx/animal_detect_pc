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
STATE_PATROL = 2  # 包含了巡查(P)、穿梭(T)、返航(R)逻辑
STATE_DRAWING = 3  # 发现动物悬停画圈
STATE_RETREAT = 4  # 降落前退避 1.2m
STATE_LANDING = 5  # 45度斜线下砸

fsm_state = STATE_IDLE

# 视觉系统的状态锁与记忆小本本
vision_enabled = False
detected_animals = set()
draw_start_time = 0
current_grid_code = "UNKNOWN"  # 记录当前所在的网格，用于战报回传


# ================= 回调函数与通信函数 =================
def state_cb(msg):
    global current_state
    current_state = msg


def pos_cb(msg):
    global current_pos
    current_pos = msg


def report_to_ground_station(animal, grid):
    """把战报用 UDP 发回高级地面站"""
    GS_IP = "127.0.0.1"  # 默认发往本地 IP
    GS_PORT = 8888  # 适配你们的高级地面站监听端口

    msg = f"REPORT:{animal}@{grid}"
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(msg.encode('utf-8'), (GS_IP, GS_PORT))
        rospy.loginfo(f"已向高级地面站发送战报: {msg}")
    except Exception as e:
        rospy.logerr(f"战报发送失败: {e}")


def vision_cb(msg):
    global fsm_state, draw_start_time, detected_animals, vision_enabled, current_grid_code
    animal_name = msg.data

    # 触发悬停的三个硬性条件：1.允许视觉 2.正在巡航 3.第一次遇见
    if vision_enabled and fsm_state == STATE_PATROL and (animal_name not in detected_animals):
        rospy.logwarn(f"!!! 真实视觉预警：在 {current_grid_code} 发现 {animal_name}，紧急悬停 !!!")

        detected_animals.add(animal_name)

        # 瞬间打断状态
        draw_start_time = time.time()
        fsm_state = STATE_DRAWING

        # 呼叫地面站
        report_to_ground_station(animal_name, current_grid_code)


def get_distance(p1_x, p1_y, p1_z, p2_x, p2_y, p2_z):
    return math.sqrt((p1_x - p2_x) ** 2 + (p1_y - p2_y) ** 2 + (p1_z - p2_z) ** 2)


# ================= 核心状态机主循环 =================
def main_loop():
    global fsm_state, vision_enabled, current_grid_code
    rospy.init_node('fsm_patrol_node', anonymous=True)

    rospy.Subscriber("mavros/state", State, state_cb)
    rospy.Subscriber("mavros/local_position/pose", PoseStamped, pos_cb)
    rospy.Subscriber("/vision/animal_detect", String, vision_cb)

    local_pos_pub = rospy.Publisher("mavros/setpoint_position/local", PoseStamped, queue_size=10)

    arming_client = rospy.ServiceProxy("mavros/cmd/arming", CommandBool)
    set_mode_client = rospy.ServiceProxy("mavros/set_mode", SetMode)

    RATE_HZ = 20.0
    rate = rospy.Rate(RATE_HZ)
    dt = 1.0 / RATE_HZ

    # 1. 加载接收端翻译好的 JSON 航点
    try:
        with open("flight_mission.json", "r") as f:
            mission_wps = json.load(f)
        rospy.loginfo(f"成功加载 JSON！共 {len(mission_wps)} 个航点。")
    except Exception as e:
        rospy.logerr("找不到 flight_mission.json！请检查接收节点是否正常运行。")
        return

    # 飞控连通性检查
    while not rospy.is_shutdown() and not current_state.connected:
        rate.sleep()
    rospy.loginfo("飞控已连接！准备接管控制权...")

    # 发送心跳包抢占 OFFBOARD
    pose = PoseStamped()
    for _ in range(100):
        local_pos_pub.publish(pose)
        rate.sleep()

    wp_index = 0
    TOLERANCE = 0.2

    rospy.loginfo("========== 状态机启动 ==========")

    while not rospy.is_shutdown():

        # ------------------------------------------
        # 状态 0: 待机并解锁
        # ------------------------------------------
        if fsm_state == STATE_IDLE:
            if current_state.mode != "OFFBOARD":
                set_mode_client(custom_mode="OFFBOARD")
            elif not current_state.armed:
                arming_client(True)
            else:
                rospy.loginfo(">> [起飞] 目标高度 Z=1.2m")
                fsm_state = STATE_TAKEOFF

        # ------------------------------------------
        # 状态 1: 直上起飞
        # ------------------------------------------
        elif fsm_state == STATE_TAKEOFF:
            pose.pose.position.x = 0
            pose.pose.position.y = 0
            pose.pose.position.z = 1.2

            if get_distance(current_pos.pose.position.x, current_pos.pose.position.y, current_pos.pose.position.z, 0, 0,
                            1.2) < TOLERANCE:
                rospy.loginfo(">> [进入巡航网络]")
                fsm_state = STATE_PATROL

        # ------------------------------------------
        # 状态 2: 智能网络巡航
        # ------------------------------------------
        elif fsm_state == STATE_PATROL:
            if wp_index >= len(mission_wps):
                rospy.logerr("警告：航点越界。")
                break

            target = mission_wps[wp_index]
            current_task = target.get("task", "P")
            current_grid_code = target["grid"]  # 实时更新当前网格，供视觉回调使用

            # 【动态变速箱与视觉开关锁】
            if current_task == "P":
                current_speed = 2.0
                vision_enabled = True
            elif current_task in ["T", "R", "L"]:
                current_speed = 4.0
                vision_enabled = False

            STEP_DIST = current_speed * dt

            # 【平滑胡萝卜引导法】
            if fsm_state == STATE_PATROL:
                dx = target["x"] - pose.pose.position.x
                dy = target["y"] - pose.pose.position.y
                dist = math.sqrt(dx ** 2 + dy ** 2)

                if dist > STEP_DIST:
                    pose.pose.position.x += (dx / dist) * STEP_DIST
                    pose.pose.position.y += (dy / dist) * STEP_DIST
                else:
                    pose.pose.position.x = target["x"]
                    pose.pose.position.y = target["y"]

                real_dist = get_distance(current_pos.pose.position.x, current_pos.pose.position.y, 1.2, target["x"],
                                         target["y"], 1.2)
                if real_dist < TOLERANCE:
                    rospy.loginfo(f"√ 到达 {target['grid']} [标签:{current_task}]")

                    if current_task == "L":
                        rospy.loginfo(">> [全场最后一点到达！触发退避动作]")
                        fsm_state = STATE_RETREAT
                    else:
                        wp_index += 1

        # ------------------------------------------
        # 状态 3: 绘制轮廓 (悬停打断)
        # ------------------------------------------
        elif fsm_state == STATE_DRAWING:
            elapsed = time.time() - draw_start_time
            if elapsed < 3.0:
                pass
            else:
                rospy.loginfo(">> [画图完毕，恢复高速巡航]")
                fsm_state = STATE_PATROL

        # ------------------------------------------
        # 状态 4: 降落前退避
        # ------------------------------------------
        elif fsm_state == STATE_RETREAT:
            target_x, target_y, target_z = 0.0, 1.2, 1.2

            dx = target_x - pose.pose.position.x
            dy = target_y - pose.pose.position.y
            dist = math.sqrt(dx ** 2 + dy ** 2)

            RETREAT_SPEED = 2.0 * dt
            if dist > RETREAT_SPEED:
                pose.pose.position.x += (dx / dist) * RETREAT_SPEED
                pose.pose.position.y += (dy / dist) * RETREAT_SPEED
            else:
                pose.pose.position.x = target_x
                pose.pose.position.y = target_y

            real_dist = get_distance(current_pos.pose.position.x, current_pos.pose.position.y, 1.2, target_x, target_y,
                                     target_z)
            if real_dist < TOLERANCE:
                rospy.loginfo(">> [退避完成！执行 45度斜线 LANDING]")
                fsm_state = STATE_LANDING

        # ------------------------------------------
        # 状态 5: 45度斜降
        # ------------------------------------------
        elif fsm_state == STATE_LANDING:
            target_x, target_y, target_z = 0.0, 0.0, 0.0

            dx = target_x - pose.pose.position.x
            dy = target_y - pose.pose.position.y
            dz = target_z - pose.pose.position.z
            dist = math.sqrt(dx ** 2 + dy ** 2 + dz ** 2)

            LAND_SPEED = 0.5 * dt

            if dist > LAND_SPEED:
                pose.pose.position.x += (dx / dist) * LAND_SPEED
                pose.pose.position.y += (dy / dist) * LAND_SPEED
                pose.pose.position.z += (dz / dist) * LAND_SPEED
            else:
                rospy.loginfo(">> [着陆完成！切入硬件 AUTO.LAND 彻底断桨]")
                set_mode_client(custom_mode="AUTO.LAND")
                break

        local_pos_pub.publish(pose)
        rate.sleep()


if __name__ == '__main__':
    try:
        main_loop()
    except rospy.ROSInterruptException:
        pass