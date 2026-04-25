import sys
from PyQt5.QtWidgets import QApplication
from ui_view import GroundStationUI
from algorithm import RoutePlanner, compress_route
from comm_link import UDPComm

class MainController:
    def __init__(self):
        self.ui = GroundStationUI()
        self.planner = RoutePlanner()
        self.comm = UDPComm(local_port=8888, drone_ip="127.0.0.1", drone_port=8889)

        self.bind_signals()
        self.comm.start()
        self.ui.show()

    def bind_signals(self):
        self.ui.plan_btn.clicked.connect(self.handle_plan_route)
        self.ui.send_btn.clicked.connect(self.handle_send_route)
        
        self.comm.data_received.connect(self.handle_drone_data)
        self.comm.status_update.connect(self.ui.update_status_msg)

    def handle_plan_route(self):
        nofly_zones = self.ui.nofly_zones
        result = self.planner.plan_route(nofly_zones)
        
        # 处理不同返回格式的兼容性
        if len(result) == 5:
            route_list, return_start_index, checkpoint_indices, merged_route, merged_checkpoints = result
        elif len(result) == 3:
            route_list, return_start_index, checkpoint_indices = result
            merged_route = route_list
            merged_checkpoints = checkpoint_indices
        else:
            route_list, return_start_index = result
            checkpoint_indices = None
            merged_route = route_list
            merged_checkpoints = None
        
        # 基于检测状态进行航点合并
        detected_route = compress_route(merged_route, self.ui.detected_cells)

        # 兜底保障：航线最后必须回到起飞区
        if detected_route:
            start_point = self.ui.start_point
            if detected_route[-1] != start_point:
                if return_start_index is None:
                    return_start_index = len(detected_route) - 1
                detected_route = list(detected_route) + [start_point]
        
        # 使用状态优化后的路由
        self.ui.animate_path(detected_route, return_start_index=return_start_index, 
                           checkpoint_indices=merged_checkpoints,
                           original_route=route_list, original_checkpoints=checkpoint_indices)

    def handle_send_route(self):
        route_list = self.ui.route_list
        if not route_list or len(route_list) < 2:
            return
        route_str = "ROUTE:" + ",".join(route_list)
        self.comm.send_data(route_str)
        self.ui.set_grid_interaction(False)

    def handle_drone_data(self, data):
        try:
            if ":" in data:
                grid_id, animal_code = data.split(":")
                grid_id = grid_id.strip()
                animal_code = animal_code.strip()
                self.ui.update_grid_result(grid_id, animal_code)
                self.ui.update_plane_position(grid_id)
        except Exception as e:
            print(f"数据解析出错: {data}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    controller = MainController()
    sys.exit(app.exec_())
