#!/usr/bin/env python3
import socket
import json
import rospy
from std_msgs.msg import Bool

# 高级地面站的 IP 和端口 (你需要确保这里和你的实际情况一致)
GS_IP = "127.0.0.1"
GS_PORT = 8888


def send_udp_telemetry(msg):
    """向上位机（高级地面站）回传握手与状态数据"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(msg.encode('utf-8'), (GS_IP, GS_PORT))
        rospy.loginfo(f"[UDP TX] -> {msg}")
    except Exception as e:
        rospy.logerr(f"UDP 遥测发送失败: {e}")


def get_coord(grid_code):
    """将网格代号 (如 A9_B1) 转换为 Jetson 底层的物理坐标 (X, Y)"""
    parts = grid_code.split('_')
    col = int(parts[0][1])
    row = int(parts[1][1])

    # 核心数学映射：以 A9B1 为原点 (0,0)
    x = round((col - 9) * 0.5, 2)
    y = round((row - 1) * 0.5, 2)
    return x, y


def parse_and_save(data_str):
    """解析树莓派传来的字符串，转换坐标并生成 JSON"""
    route_str = data_str.replace("ROUTE:", "").strip()
    points = route_str.split(',')

    waypoints = []
    for pt in points:
        if not pt: continue

        parts = pt.split(':')
        grid_code = parts[0]
        tag = parts[1] if len(parts) > 1 else 'P'

        try:
            x, y = get_coord(grid_code)
            waypoints.append({
                "grid": grid_code,
                "x": x,
                "y": y,
                "z": 1.2,
                "task": tag
            })
        except Exception as e:
            rospy.logerr(f"解析坐标 {grid_code} 失败: {e}")

    # 落盘保存，供 fsm_patrol.py 读取
    with open("flight_mission.json", "w") as f:
        json.dump(waypoints, f, indent=4)

    rospy.loginfo(f"√ 坐标转换成功！共解析 {len(waypoints)} 个微步航点。")
    rospy.loginfo(f"最后的降落点坐标确认: X={waypoints[-1]['x']}, Y={waypoints[-1]['y']}, 标签={waypoints[-1]['task']}")

    # 【握手协议核心 1】：通知地面站航线已存好
    send_udp_telemetry("REPLY:MISSION_SAVED")


def start_udp_server():
    # 1. 初始化 ROS 节点
    rospy.init_node('receiver_node', anonymous=True)

    # 2. 注册起飞指令广播大喇叭
    takeoff_pub = rospy.Publisher('/fsm/takeoff_cmd', Bool, queue_size=1)

    UDP_IP = "0.0.0.0"
    UDP_PORT = 8889

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))

    # 设置超时，让 ROS 的 is_shutdown() 能够及时响应 Ctrl+C 退出
    sock.settimeout(1.0)

    # 【握手协议核心 2】：报告节点就绪
    send_udp_telemetry("STATUS:RECEIVER_READY")
    rospy.loginfo(f"=== Jetson 机载接收端已启动，死守端口 {UDP_PORT} ===")

    while not rospy.is_shutdown():
        try:
            data, addr = sock.recvfrom(4096)
            raw_str = data.decode('utf-8').strip()

            # 【握手协议核心 3】：权限分发 (收到起飞指令)
            if raw_str == "CMD:TAKEOFF":
                rospy.logwarn(">>> 收到地面站【起飞】授权指令！立刻广播给 FSM！ <<<")
                takeoff_pub.publish(True)

            # 处理航线数据
            elif raw_str.startswith("ROUTE:"):
                rospy.loginfo(f"收到地面站 {addr} 传来的路径包，正在疯狂解码...")
                parse_and_save(raw_str)

            else:
                rospy.logwarn(f"收到未知格式数据: {raw_str}")

        except socket.timeout:
            # 超时是正常的，继续下一轮循环等待
            continue
        except Exception as e:
            rospy.logerr(f"接收数据异常: {e}")


if __name__ == "__main__":
    try:
        start_udp_server()
    except rospy.ROSInterruptException:
        pass