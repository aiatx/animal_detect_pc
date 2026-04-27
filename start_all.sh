#!/bin/bash

echo "🚀 [1/4] 开启串口权限 (可能需要输入密码)..."
sudo chmod 777 /dev/ttyTHS0

# 启动 MAVROS (放入后台)
echo "🚀 [2/4] 启动 MAVROS..."
roslaunch mavros px4.launch &
sleep 5  # 等待飞控心跳建立

# 启动激光雷达和 LIO SLAM
echo "🚀 [3/4] 启动 Livox 雷达与 Faster-LIO..."
roslaunch livox_ros_driver2 msg_MID360.launch &
sleep 3
roslaunch faster_lio rflysim.launch &
sleep 5  # 等待点云地图初始化

# 启动我们自己手写的 Python 核心节点
echo "🚀 [4/4] 启动高层逻辑大脑 (Receiver, Vision, FSM)..."
python3 receiver.py &
sleep 2
python3 vision_node.py &
sleep 5
python3 fsm_patrol.py &

echo "=================================================="
echo "✅ 所有系统均已上线！飞机已准备好接受地面站指令。"
echo "🛑 退出程序：请直接按 Ctrl + C，系统将自动清理所有节点。"
echo "=================================================="

# 【灵魂代码】捕获 Ctrl+C (SIGINT)，一键杀掉本脚本启动的所有后台子进程
trap "echo '收到停止指令，正在全军撤退...'; kill 0" SIGINT

# 挂起主线程，死等后台任务
wait