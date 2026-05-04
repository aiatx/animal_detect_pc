#!/usr/bin/env python3
import cv2
import numpy as np


def nothing(x):
    pass


def main():
    # 1. 初始化相机 (默认 /dev/video0)
    cam_index = 0
    cap = cv2.VideoCapture(cam_index)

    if not cap.isOpened():
        print(f"错误: 无法打开相机 /dev/video{cam_index}")
        return

    # 2. 创建调试窗口
    window_name = "Exposure Debugger"
    cv2.namedWindow(window_name)

    # 3. 创建滑动条
    # 注意：不同相机的范围不同，通常手动模式下曝光值在 1-500 左右，或者 -10 到 -1
    cv2.createTrackbar("Auto_Exp", window_name, 1, 3, nothing)  # 1:手动, 3:自动
    cv2.createTrackbar("Exposure", window_name, 100, 500, nothing)
    cv2.createTrackbar("Gain", window_name, 0, 255, nothing)

    print("--- 调试说明 ---")
    print("1. 拖动滑动条观察画面变化")
    print("2. 画面不闪烁且动物纹理清晰为佳")
    print("3. 按 'q' 键退出并查看最终参数")

    while True:
        # 获取当前滑动条的值
        auto_exp = cv2.getTrackbarPos("Auto_Exp", window_name)
        exp_val = cv2.getTrackbarPos("Exposure", window_name)
        gain_val = cv2.getTrackbarPos("Gain", window_name)

        # 应用设置到相机
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, auto_exp)
        if auto_exp == 1:  # 仅在手动模式下设置曝光
            cap.set(cv2.CAP_PROP_EXPOSURE, exp_val)
        cap.set(cv2.CAP_PROP_GAIN, gain_val)

        # 读取画面
        ret, frame = cap.read()
        if not ret:
            break

        # 在画面上实时标注参数
        info = f"AutoExp: {auto_exp} | Exp: {exp_val} | Gain: {gain_val}"
        cv2.putText(frame, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.imshow(window_name, frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            print(f"\n最终调试参数建议:")
            print(f"CAP_PROP_AUTO_EXPOSURE: {auto_exp}")
            print(f"CAP_PROP_EXPOSURE: {exp_val}")
            print(f"CAP_PROP_GAIN: {gain_val}")
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()