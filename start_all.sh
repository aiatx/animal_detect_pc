#!/bin/bash

echo "🚀 准备召唤多终端分布式控制台..."

# 1. 赋予串口权限 (在当前主终端运行即可)
# sudo chmod 777 /dev/ttyTHS0

# 2. 召唤终端 A：MAVROS 飞控心跳
# gnome-terminal --title="MAVROS_飞控" -- bash -c "roslaunch mavros px4.launch; exec bash"
# sleep 4

# 3. 召唤终端 B：激光雷达与 SLAM (这两个可以放一起，或者再拆开)
# gnome-terminal --title="LIO_SLAM" -- bash -c "roslaunch livox_ros_driver2 msg_MID360.launch & sleep 3; roslaunch # faster_lio rflysim.launch; exec bash"
# sleep 4

# 4. 召唤终端 C：地面站通信接收大爷
gnome-terminal --title="UDP_Receiver" -- bash -c "python3 receiver.py; exec bash"
sleep 2

# 5. 召唤终端 D：视觉大脑 (占用算力最高，单独一个窗口盯着)
gnome-terminal --title="YOLO_Vision" -- bash -c "python3 vision_node.py; exec bash"
sleep 4

# 6. 召唤终端 E：飞控状态机主逻辑
gnome-terminal --title="FSM_大脑" -- bash -c "python3 fsm_patrol.py; exec bash"

echo "✅ 所有终端均已就绪！请在各自的窗口中查看运行日志。"