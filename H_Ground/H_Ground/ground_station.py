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
        
        self.ui.apply_ip_btn.clicked.connect(self.handle_apply_ip)

        self.comm.data_received.connect(self.handle_drone_data)
        self.comm.arrival_received.connect(self.handle_drone_arrival)
        self.comm.report_received.connect(self.handle_drone_report)
        self.comm.status_update.connect(self.ui.update_status_msg)

    def handle_apply_ip(self):
        new_ip = self.ui.ip_input.text().strip()
        
        try:
            new_send_port = int(self.ui.port_send_input.text().strip())
        except ValueError:
            new_send_port = 8889
            
        try:
            new_recv_port = int(self.ui.port_recv_input.text().strip())
        except ValueError:
            new_recv_port = 8888
            
        # 1. Stop old communication
        self.comm.stop()
        self.comm.wait()
        
        # 2. Re-instantiate
        self.comm = UDPComm(local_port=new_recv_port, drone_ip=new_ip, drone_port=new_send_port)
        
        # 3. Re-bind
        self.comm.data_received.connect(self.handle_drone_data)
        self.comm.arrival_received.connect(self.handle_drone_arrival)
        self.comm.report_received.connect(self.handle_drone_report)
        self.comm.status_update.connect(self.ui.update_status_msg)
        
        # 4. Start again
        self.comm.start()

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
            
        # 1. 计算正确的返航点(R)起始索引：最后一个出现的新网格(P)的下一个点
        temp_visited = set()
        last_p_idx = -1
        # 最后一点起飞点(准备降落)不参与判定
        for i in range(len(route_list) - 1):
            wp = route_list[i]
            if wp not in temp_visited:
                last_p_idx = i
                temp_visited.add(wp)
                
        # 超过此索引的全部是纯返航过程
        return_start_idx = last_p_idx + 1 if last_p_idx != -1 else len(route_list)
            
        # 2. 根据规则生成带有 Tag 的航点字符串
        tagged_route = []
        visited = set()
        
        for i, wp in enumerate(route_list):
            if i == len(route_list) - 1:
                # 最后一个点一定是起点 A9_B1，并且打上 L 标签
                tagged_route.append(f"{wp}:L")
            else:
                # 如果这个网格是返航路径上的
                if i >= return_start_idx:
                    tagged_route.append(f"{wp}:R")
                else:
                    if wp not in visited:
                        tagged_route.append(f"{wp}:P")
                        visited.add(wp)
                    else:
                        tagged_route.append(f"{wp}:T")
        
        route_str = "ROUTE:" + ",".join(tagged_route)
        self.comm.send_data(route_str)
        self.ui.set_grid_interaction(False)

    def handle_drone_data(self, data):
        try:
            if ":" in data:
                grid_id, animal_code = data.split(":")
                grid_id = grid_id.strip()
                animal_code = animal_code.strip()
                self.handle_drone_report(grid_id, animal_code)
        except Exception as e:
            print(f"数据解析出错: {data}")

    def handle_drone_report(self, grid_id, animal_code):
        self.ui.update_grid_result(grid_id, animal_code)
        if hasattr(self.ui, "update_plane_position"):
            self.ui.update_plane_position(grid_id)

    def handle_drone_arrival(self, grid_id):
        self.ui.update_status_msg(f"无人机已抵达 {grid_id}")
        if hasattr(self.ui, "update_plane_position"):
            self.ui.update_plane_position(grid_id)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    controller = MainController()
    sys.exit(app.exec_())
