import socket
import time
from PyQt5.QtCore import QThread, pyqtSignal

class UDPComm(QThread):
    # 定义两个信号，就像通信兵的两个对讲机频道
    # data_received 用来向主程序汇报：收到无人机数据了！
    # status_update 用来向主程序汇报：网络连上了/断开了！
    data_received = pyqtSignal(str) 
    status_update = pyqtSignal(str)
    arrival_received = pyqtSignal(str)
    report_received = pyqtSignal(str, str)
    status_received = pyqtSignal(str)
    reply_received = pyqtSignal(str)

    def __init__(self, local_port=8888, drone_ip="192.168.151.102", drone_port=8889):
        super().__init__()
        self.local_port = local_port
        self.drone_ip = drone_ip
        self.drone_port = drone_port
        
        self.sock = None
        self.is_running = True

    def run(self):
        """这是运行在后台的监听线程，死盯 UDP 端口"""
        try:
            # 开启 SO_REUSEADDR 允许重新绑定断开未释分的端口
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # 绑定所有的IP：绑定树莓派自己的端口，接收来自任意源端口的 UDP 数据
            self.sock.bind(('0.0.0.0', self.local_port)) 
            # 发射状态信号给 UI
            self.status_update.emit(f"UDP 监听已启动 (端口: {self.local_port})")
        except Exception as e:
            self.status_update.emit(f"UDP 启动失败: {e}")
            return

        while self.is_running:
            try:
                # 疯狂读取！榨干缓冲区，取消 socket 的 timeout 和循环内 sleep
                data, addr = self.sock.recvfrom(4096)
                try:
                    message = data.decode('utf-8', errors="replace").strip()
                except Exception:
                    message = ""
                    
                if message:
                    if message.startswith("STATUS:"):
                        payload = message.split(":", 1)[1].strip()
                        if payload:
                            self.status_received.emit(payload)
                        else:
                            self.data_received.emit(message)
                    elif message.startswith("REPLY:"):
                        payload = message.split(":", 1)[1].strip()
                        if payload:
                            self.reply_received.emit(payload)
                        else:
                            self.data_received.emit(message)
                    elif message.startswith("ARRIVED:"):
                        grid_id = message.split(":", 1)[1].strip()
                        if grid_id:
                            self.arrival_received.emit(grid_id)
                        else:
                            self.data_received.emit(message)
                    elif message.startswith("REPORT:"):
                        payload = message.split(":", 1)[1].strip()
                        if "@" in payload:
                            animal_code, grid_id = payload.split("@", 1)
                            animal_code = animal_code.strip()
                            grid_id = grid_id.strip()
                            if animal_code and grid_id:
                                self.report_received.emit(grid_id, animal_code)
                            else:
                                self.data_received.emit(message)
                        else:
                            self.data_received.emit(message)
                    else:
                        # 收到真实数据，立刻发射给主控
                        self.data_received.emit(message)
            except OSError:
                if not self.is_running:
                    break
            except Exception:
                pass
                
    def send_data(self, data_str):
        """主程序用来发送航线给飞机的接口"""
        if self.sock:
            try:
                # 编码成字节流发给无人机
                payload = data_str.encode('utf-8')
                self.sock.sendto(payload, (self.drone_ip, self.drone_port))
                print(f"[TX 发送成功] -> {self.drone_ip}:{self.drone_port} | 数据: {data_str}")
            except Exception as e:
                print(f"[TX 发送失败]: {e}")

    def stop(self):
        """安全退出机制"""
        self.is_running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.wait()
