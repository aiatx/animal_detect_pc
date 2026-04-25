import socket
import time
import random

def run_mock_drone():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', 8889))
    print("========================================")
    print("🚁 [虚拟飞控 V2] 引擎启动 (12只动物已入库)")
    print("========================================")

    while True:
        data, addr = sock.recvfrom(2048)
        msg = data.decode('utf-8')
        
        if msg.startswith("ROUTE:"):
            route = msg.replace("ROUTE:", "").split(",")
            print(f"\n[无线电] 接收到航线！共 {len(route)} 个航点。")
            
            # --- 核心逻辑：实战沙盘预分配 ---
            valid_wps = [wp.split(':')[0] for wp in route if wp != 'A9_B1' and wp != 'A9_B1:P' and wp != 'A9_B1:L' and wp != 'A9_B1:T' and wp != 'A9_B1:R'] # 排除起飞区
            animal_map = {wp: [0, 0, 0, 0, 0] for wp in valid_wps}

            if valid_wps:
                # 0:大象(4), 1:猴子(2), 2:孔雀(2), 3:野狼(2), 4:老虎(2)
                # 总计 12 只动物，构成一个固定的池子
                animal_pool = [0]*4 + [1]*2 + [2]*2 + [3]*2 + [4]*2
                random.shuffle(animal_pool)
                
                # 将这12只动物随机“藏”在航线的格子里
                for animal_idx in animal_pool:
                    chosen_wp = random.choice(valid_wps)
                    animal_map[chosen_wp][animal_idx] += 1
            # ------------------------------

            print("[飞控] 靶标已随机分布。电机解锁，准备起飞...\n")
            time.sleep(0.4)

            for wp_full in route:
                wp = wp_full.split(':')[0]
                if wp == 'A9_B1':
                    print(f"  -> [状态] 正在起飞区 {wp_full} 爬升至安全高度...")
                    time.sleep(0.3)
                    continue

                print(f"  -> [飞行中] 全速前往目标点 {wp_full} ...")
                time.sleep(0.6) # 模拟飞行时间

                # 从预先分配好的沙盘里提取该格子的动物数量
                counts = animal_map.get(wp, [0, 0, 0, 0, 0])
                animals_str = "".join(map(str, counts))

                # 如果这个格子里面有动物，就汇报；没动物就报 00000
                feedback = f"{wp}:{animals_str}"
                sock.sendto(feedback.encode('utf-8'), ("127.0.0.1", 8888))

                if animals_str != "00000":
                    print(f"     📸 [摄像头] 发现目标！上传特征数据: {feedback}")
                else:
                    print(f"     [摄像头] 区域安全，未发现动物。{feedback}")

            print("\n[飞控] 航线执行完毕！执行 RTL 直线返航降落...")
            time.sleep(0.6)
            sock.sendto("A9_B1:00000".encode('utf-8'), ("127.0.0.1", 8888))
            print("  -> [返航] 已回到起飞区 A9_B1")
            time.sleep(0.4)
            print("[飞控] 降落锁定。等待下一次任务。\n")

if __name__ == "__main__":
    run_mock_drone()