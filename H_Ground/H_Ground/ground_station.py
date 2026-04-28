import sys
import random
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from ui_view import GroundStationUI
from algorithm import RoutePlanner
from comm_link import UDPComm

class MainController:
    def __init__(self):
        self.ui = GroundStationUI()
        self.planner = RoutePlanner()
        self.comm = UDPComm(local_port=8888, drone_ip="198.162.151.102", drone_port=8889)

        self.bind_signals()
        self.comm.start()
        self._start_ping_timer()
        self.ui.show()

    def _start_ping_timer(self):
        self.ping_timer = QTimer()
        self.ping_timer.setSingleShot(True)
        self.ping_timer.timeout.connect(self._send_ping)
        self._schedule_ping()

    def _schedule_ping(self):
        interval_ms = random.randint(1000, 2000)
        self.ping_timer.start(interval_ms)

    def _send_ping(self):
        try:
            if self.comm and self.comm.isRunning():
                self.comm.send_data("CMD:PING")
        finally:
            self._schedule_ping()

    def bind_signals(self):
        self.ui.plan_btn.clicked.connect(self.handle_plan_route)
        # 【新增】：绑定复位按钮到 UI 的 reset_ui 函数
        self.ui.reset_btn.clicked.connect(self.ui.reset_ui)
        
        self.comm.data_received.connect(self.handle_drone_data)
        self.comm.arrival_received.connect(self.handle_drone_arrival)
        self.comm.report_received.connect(self.handle_drone_report)
        self.comm.status_update.connect(self.ui.update_status_msg)

    def handle_plan_route(self):
        nofly_zones = self.ui.nofly_zones
        route_list = self.planner.plan_route(nofly_zones)
        self.ui.animate_path(route_list)
        route_str = "ROUTE:" + ",".join(route_list)
        self.comm.send_data(route_str)

    def handle_drone_data(self, data):
        try:
            if data.startswith("ARRIVED:"):
                grid_id = data.split(":", 1)[1].strip()
                if grid_id:
                    self.handle_drone_arrival(grid_id)
                return
            if data.startswith("REPORT:"):
                payload = data.split(":", 1)[1].strip()
                if "@" in payload:
                    animal_code, grid_id = payload.split("@", 1)
                    self.handle_drone_report(grid_id.strip(), animal_code.strip())
                return
            if ":" in data:
                grid_id, animal_code = data.split(":", 1)
                self.handle_drone_report(grid_id.strip(), animal_code.strip())
        except Exception as e:
            print(f"数据解析出错: {data}")

    def handle_drone_report(self, grid_id, animal_code):
        self.ui.update_grid_result(grid_id, animal_code)

    def handle_drone_arrival(self, grid_id):
        self.ui.update_status_msg(f"无人机已抵达 {grid_id}")
        if hasattr(self.ui, "update_grid_arrival"):
            self.ui.update_grid_arrival(grid_id)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    controller = MainController()
    sys.exit(app.exec_())
