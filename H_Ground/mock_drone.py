import socket
import time
import random

GS_IP = "127.0.0.1"
GS_PORT = 8888
LISTEN_PORT = 8889
START_POINT = "A9_B1"


def _parse_route(route_payload):
    entries = []
    for raw in route_payload.split(","):
        raw = raw.strip()
        if not raw:
            continue
        if ":" in raw:
            grid_id, tag = raw.split(":", 1)
            grid_id = grid_id.strip()
            tag = tag.strip().upper() if tag else "P"
        else:
            grid_id = raw
            tag = "P"
        if grid_id:
            entries.append((grid_id, tag))
    return entries


def _grid_to_xy(grid_id):
    try:
        col_part, row_part = grid_id.split("_", 1)
        x = int(col_part[1:]) - 1
        y = int(row_part[1:]) - 1
        return x, y
    except Exception:
        return 0, 0


def _estimate_travel_time(from_grid, to_grid):
    fx, fy = _grid_to_xy(from_grid)
    tx, ty = _grid_to_xy(to_grid)
    steps = abs(tx - fx) + abs(ty - fy)
    return 0.3 + steps * 0.25


def _allocate_animals(route_entries):
    patrol_grids = [gid for gid, tag in route_entries if gid != START_POINT and tag == "P"]
    if not patrol_grids:
        patrol_grids = [gid for gid, _ in route_entries if gid != START_POINT]

    animal_map = {gid: [0, 0, 0, 0, 0] for gid in patrol_grids}
    if not patrol_grids:
        return animal_map

    # 0:大象(4), 1:猴子(2), 2:孔雀(2), 3:野狼(2), 4:老虎(2)
    animal_pool = [0] * 4 + [1] * 2 + [2] * 2 + [3] * 2 + [4] * 2
    random.shuffle(animal_pool)

    for animal_idx in animal_pool:
        chosen_wp = random.choice(patrol_grids)
        animal_map[chosen_wp][animal_idx] += 1

    return animal_map


def _send_udp(sock, message):
    sock.sendto(message.encode("utf-8"), (GS_IP, GS_PORT))


def run_mock_drone():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", LISTEN_PORT))
    print("========================================")
    print("🚁 [SITL 虚拟飞控] 引擎启动 (12只动物已入库)")
    print("========================================")

    while True:
        data, addr = sock.recvfrom(2048)
        msg = data.decode("utf-8").strip()

        if not msg.startswith("ROUTE:"):
            continue

        route_payload = msg.replace("ROUTE:", "", 1)
        route_entries = _parse_route(route_payload)
        if not route_entries:
            continue

        print(f"\n[无线电] 接收到航线！共 {len(route_entries)} 个航点。")
        animal_map = _allocate_animals(route_entries)

        print("[飞控] 靶标已随机分布。电机解锁，准备起飞...\n")
        time.sleep(0.4)

        current_grid = START_POINT
        for grid_id, tag in route_entries:
            travel_time = _estimate_travel_time(current_grid, grid_id)
            if grid_id == START_POINT and current_grid == START_POINT:
                print(f"  -> [状态] 起飞区 {grid_id} 垂直起飞至安全高度...")
                time.sleep(0.3)
            else:
                print(f"  -> [飞行中] 前往目标点 {grid_id} ({tag}) ...")
                time.sleep(travel_time)

            _send_udp(sock, f"ARRIVED:{grid_id}")
            time.sleep(0.15)

            if grid_id != START_POINT:
                counts = animal_map.get(grid_id, [0, 0, 0, 0, 0])
                animals_str = "".join(map(str, counts))
                legacy_payload = f"{grid_id}:{animals_str}"
                _send_udp(sock, legacy_payload)
                if animals_str != "00000":
                    print(f"     🎯 [识别] 上报目标: {legacy_payload}")
                else:
                    print(f"     [识别] 区域安全，未发现动物。{legacy_payload}")

            current_grid = grid_id

        print("\n[飞控] 航线执行完毕！执行 RTL 直线返航降落...")
        time.sleep(0.6)
        _send_udp(sock, f"ARRIVED:{START_POINT}")
        time.sleep(0.2)
        print("  -> [返航] 已回到起飞区 A9_B1")
        print("[飞控] 降落锁定。等待下一次任务。\n")


if __name__ == "__main__":
    run_mock_drone()
