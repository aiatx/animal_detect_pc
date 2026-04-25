import socket
import json


def get_coord(grid_code):
    """将网格代号 (如 A9_B1) 转换为 Jetson 底层的物理坐标 (X, Y)"""
    # 假设输入格式为 "A9_B1"
    parts = grid_code.split('_')
    col = int(parts[0][1])  # 从 'A9' 提取 9
    row = int(parts[1][1])  # 从 'B1' 提取 1

    # 核心数学映射：以 A9B1 为原点 (0,0)
    x = round((col - 9) * 0.5, 2)
    y = round((row - 1) * 0.5, 2)
    return x, y


def parse_and_save(data_str):
    """解析树莓派传来的字符串，转换坐标并生成 JSON"""
    if not data_str.startswith("ROUTE:"):
        print("收到非航线数据，忽略。")
        return

    route_str = data_str.replace("ROUTE:", "").strip()
    points = route_str.split(',')

    waypoints = []
    for pt in points:
        if not pt: continue

        # 拆分坐标和标签，比如 "A5_B3:T" -> ["A5_B3", "T"]
        parts = pt.split(':')
        grid_code = parts[0]
        tag = parts[1] if len(parts) > 1 else 'P'  # 没标签默认当做巡查 P

        try:
            # 瞬间完成坐标转换
            x, y = get_coord(grid_code)
            waypoints.append({
                "grid": grid_code,
                "x": x,
                "y": y,
                "z": 1.2,
                "task": tag
            })
        except Exception as e:
            print(f"解析坐标 {grid_code} 失败: {e}")

    # 落盘保存，供 fsm_patrol.py 随时读取
    with open("flight_mission.json", "w") as f:
        json.dump(waypoints, f, indent=4)

    print(f"\n[√] 坐标转换成功！共解析 {len(waypoints)} 个微步航点。")
    print(f"最后的降落点坐标确认: X={waypoints[-1]['x']}, Y={waypoints[-1]['y']}, 标签={waypoints[-1]['task']}")
    print(">> JSON 已更新，状态机节点可以起飞了！\n")


def start_udp_server():
    UDP_IP = "0.0.0.0"  # 监听 Jetson 上的所有网卡
    UDP_PORT = 8889  # 对应你树莓派发送的端口

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))

    print(f"=== Jetson 机载接收端已启动，死守端口 {UDP_PORT} ===")

    while True:
        data, addr = sock.recvfrom(4096)
        raw_str = data.decode('utf-8')
        print(f"收到地面站 {addr} 传来的路径包，正在疯狂解码...")
        parse_and_save(raw_str)


if __name__ == "__main__":
    start_udp_server()