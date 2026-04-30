#!/usr/bin/env python3
import socket
import subprocess
import time
import sys

# 地面站的 IP 和端口
GS_IP = "192.168.151.100"
GS_PORT = 8888
# 本机监听的端口 (和你们后续 receiver 用的端口保持一致)
LOCAL_PORT = 8889


def main():
    # 1. 建立 UDP Socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", LOCAL_PORT))
    sock.settimeout(1.0)  # 1秒超时，方便循环

    print("🚀 机载引导程序已启动，正在等待地面站发射指令...")

    while True:
        try:
            # 2. 疯狂向地面站发送“我还活着，还没起飞”的信号
            heartbeat_msg = "STATUS:BOOT_WAITING"
            sock.sendto(heartbeat_msg.encode('utf-8'), (GS_IP, GS_PORT))

            # 3. 听地面站的指令
            data, addr = sock.recvfrom(1024)
            cmd = data.decode('utf-8').strip()

            if cmd == "CMD:LAUNCH":
                print("🎯 收到地面站启动指令！准备起爆 ROS 系统！")

                # 释放端口，让 receiver.py 能接管
                sock.close()
                time.sleep(0.5)

                launch_cmd = "bash -c 'source /opt/ros/noetic/setup.bash && source /home/nvidia/catkin_ws/devel/setup.bash && roslaunch animal_detect start_all.launch'"

                print(f"执行命令: {launch_cmd}")

                # 【终极修复】：用 os.system 阻塞式运行！
                # 这样引导程序会一直“撑着”不退出，欺骗 systemd 大管家它还在上班。
                # roslaunch 就能在它撑起的保护伞下完美运行！
                import os
                os.system(launch_cmd)

                # 一旦 roslaunch 因为意外崩溃退出，这里再退出，
                # 触发 systemd 的 Restart=on-failure，5秒后又会自动开始监听地面站指令！
                sys.exit(0)

        except socket.timeout:
            continue
        except Exception as e:
            print(f"引导程序异常: {e}")
            time.sleep(1)


if __name__ == "__main__":
    main()