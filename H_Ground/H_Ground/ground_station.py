import sys
from PyQt5.QtWidgets import QApplication
from ui_view import GroundStationUI
from algorithm import RoutePlanner
from comm_link import UDPComm

class MainController:
    def __init__(self):
        self.ui = GroundStationUI()
        self.planner = RoutePlanner()
        self.comm = UDPComm(local_port=8888, drone_ip="192.168.1.100", drone_port=8889)

        self.bind_signals()
        self.comm.start()
        self.ui.show()

    def bind_signals(self):
        self.ui.plan_btn.clicked.connect(self.handle_plan_route)
        # 【新增】：绑定复位按钮到 UI 的 reset_ui 函数
        self.ui.reset_btn.clicked.connect(self.ui.reset_ui)
        
        self.comm.data_received.connect(self.handle_drone_data)
        self.comm.status_update.connect(self.ui.update_status_msg)

    def handle_plan_route(self):
        nofly_zones = self.ui.nofly_zones
        route_list = self.planner.plan_route(nofly_zones)
        self.ui.animate_path(route_list)
        route_str = "ROUTE:" + ",".join(route_list)
        self.comm.send_data(route_str)

    def handle_drone_data(self, data):
        try:
            if ":" in data:
                grid_id, animal_code = data.split(":")
                self.ui.update_grid_result(grid_id.strip(), animal_code.strip())
        except Exception as e:
            print(f"数据解析出错: {data}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    controller = MainController()
    sys.exit(app.exec_())
