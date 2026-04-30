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

                # 【极其关键的一步】：必须释放 8889 端口！
                # 否则一会 receiver.py 启动时会报 "Address already in use" 错误！
                sock.close()
                time.sleep(0.5)

                # 4. 执行 Launch 文件
                # 注意：你现在还没建包没关系，到时候建好了把这里的路径替换掉就行
                launch_cmd = "bash -c 'source /opt/ros/noetic/setup.bash && source /home/nvidia/catkin_ws/devel/setup.bash && roslaunch your_package your_launch_file.launch'"

                print(f"执行命令: {launch_cmd}")

                # Popen 会在后台把整个 ROS 系统拉起来，然后这个 Python 脚本就可以功成身退了
                subprocess.Popen(launch_cmd, shell=True)

                sys.exit(0)  # 退出引导程序，将舞台交给真正的飞控节点

        except socket.timeout:
            continue
        except Exception as e:
            print(f"引导程序异常: {e}")
            time.sleep(1)


if __name__ == "__main__":
    main()