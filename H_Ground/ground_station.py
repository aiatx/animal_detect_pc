import sys
import random
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from ui_view import GroundStationUI
from algorithm import RoutePlanner, compress_route
from comm_link import UDPComm

class MainController:
    def __init__(self):
        self.ui = GroundStationUI()
        self.planner = RoutePlanner()
        self.comm = UDPComm(local_port=8888, drone_ip="192.168.151.102", drone_port=8889)
        self._reset_handshake_state()

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

    def _reset_handshake_state(self):
        self.flight_started = False
        self._handshake_logged = {
            "receiver_ready": False,
            "fsm_ready": False,
            "route_sent": False,
            "mission_saved": False,
            "mission_loaded": False,
            "takeoff_sent": False,
            "takeoff_success": False
        }

    def _log_once(self, key, message):
        if self._handshake_logged.get(key):
            return False
        self._handshake_logged[key] = True
        if hasattr(self.ui, "append_log"):
            self.ui.append_log(message)
        return True

    def _mark_takeoff_success(self):
        if not self._handshake_logged.get("takeoff_sent"):
            return
        if self._handshake_logged.get("takeoff_success"):
            return
        self._handshake_logged["takeoff_success"] = True
        self.flight_started = True
        if hasattr(self.ui, "append_log"):
            self.ui.append_log("起飞成功")

    def bind_signals(self):
        self.ui.plan_btn.clicked.connect(self.handle_plan_route)
        self.ui.send_btn.clicked.connect(self.handle_send_route)
        self.ui.takeoff_btn.clicked.connect(self.handle_takeoff_authorize)
        if hasattr(self.ui, "pause_btn"):
            self.ui.pause_btn.clicked.connect(self.handle_emergency_pause)
        
        self.ui.apply_ip_btn.clicked.connect(self.handle_apply_ip)

        self.comm.data_received.connect(self.handle_drone_data)
        self.comm.arrival_received.connect(self.handle_drone_arrival)
        self.comm.report_received.connect(self.handle_alarm_report)
        self.comm.status_received.connect(self.handle_drone_status)
        self.comm.reply_received.connect(self.handle_drone_reply)
        self.comm.status_update.connect(self.ui.update_status_msg)

    def handle_apply_ip(self):
        new_ip = self.ui.ip_input.text().strip()
        old_ip = getattr(self.comm, "drone_ip", "")
        old_send_port = getattr(self.comm, "drone_port", 0)
        old_recv_port = getattr(self.comm, "local_port", 0)
        
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
        self.comm.report_received.connect(self.handle_alarm_report)
        self.comm.status_received.connect(self.handle_drone_status)
        self.comm.reply_received.connect(self.handle_drone_reply)
        self.comm.status_update.connect(self.ui.update_status_msg)
        
        # 4. Start again
        self.comm.start()
        self._reset_handshake_state()
        if hasattr(self.ui, "append_log"):
            if (old_ip != new_ip) or (old_send_port != new_send_port) or (old_recv_port != new_recv_port):
                self.ui.append_log(
                    f"通信：网络配置变化 (本地端口 {old_recv_port} -> {new_recv_port}, "
                    f"目标 {old_ip}:{old_send_port} -> {new_ip}:{new_send_port})"
                )
            self.ui.append_log("通信：网络配置应用成功")

    def handle_plan_route(self):
        nofly_zones = self.ui.nofly_zones
        if hasattr(self.ui, "append_log"):
            self.ui.append_log("按钮：自动规划")
            self.ui.append_log("任务：自动规划开始")
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
        if hasattr(self.ui, "append_log"):
            self.ui.append_log(f"任务：自动规划完成，航点数 {len(detected_route or [])}")

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
        if hasattr(self.ui, "append_log"):
            self.ui.append_log("航线已发送，等待 receiver 保存")
        self._handshake_logged["route_sent"] = True
            
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
        if hasattr(self.ui, "update_mission_status"):
            self.ui.update_mission_status("等待机载端确认", log=False)
        if hasattr(self.ui, "set_takeoff_enabled"):
            self.ui.set_takeoff_enabled(False)

    def handle_drone_data(self, data):
        try:
            if data.startswith("STATUS:"):
                payload = data.split(":", 1)[1].strip()
                if payload:
                    self.handle_drone_status(payload)
                return
            if data.startswith("REPLY:"):
                payload = data.split(":", 1)[1].strip()
                if payload:
                    self.handle_drone_reply(payload)
                return
            if data.startswith("ARRIVED:"):
                grid_id = data.split(":", 1)[1].strip()
                if grid_id:
                    self.handle_drone_arrival(grid_id)
                return
            if data.startswith("REPORT:"):
                payload = data.split(":", 1)[1].strip()
                if "@" in payload:
                    animal_code, grid_id = payload.split("@", 1)
                    self.handle_alarm_report(grid_id.strip(), animal_code.strip())
                return
            if ":" in data:
                grid_id, animal_code = data.split(":", 1)
                grid_id = grid_id.strip()
                animal_code = animal_code.strip()
                self.handle_legacy_report(grid_id, animal_code)
        except Exception as e:
            print(f"数据解析出错: {data}")

    def handle_alarm_report(self, grid_id, animal_code):
        self.ui.update_grid_result(grid_id, animal_code)
        if hasattr(self.ui, "update_grid_alarm"):
            self.ui.update_grid_alarm(grid_id)
        self._mark_takeoff_success()
        if hasattr(self.ui, "append_log"):
            self.ui.append_log(f"[识别] {grid_id} 上报 {animal_code}")
        if hasattr(self.ui, "update_plane_position"):
            self.ui.update_plane_position(grid_id)

    def handle_legacy_report(self, grid_id, animal_code):
        self.ui.update_grid_result(grid_id, animal_code)
        self._mark_takeoff_success()
        if hasattr(self.ui, "append_log"):
            self.ui.append_log(f"[识别] {grid_id} 上报 {animal_code}")
        if hasattr(self.ui, "update_plane_position"):
            self.ui.update_plane_position(grid_id)

    def handle_drone_arrival(self, grid_id):
        if hasattr(self.ui, "update_mission_status"):
            self.ui.update_mission_status(f"无人机已抵达 {grid_id}", log=False)
        self._mark_takeoff_success()
        if hasattr(self.ui, "append_log"):
            self.ui.append_log(f"[遥测] 无人机抵达 {grid_id}")
        if hasattr(self.ui, "update_grid_arrival"):
            self.ui.update_grid_arrival(grid_id)
        if hasattr(self.ui, "update_plane_position"):
            self.ui.update_plane_position(grid_id)

    def handle_drone_status(self, status):
        status_key = status.strip().upper()
        mapping = {
            "VISION_READY": "VISION",
            "RECEIVER_READY": "RECEIVER",
            "FSM_READY": "FSM"
        }
        node_labels = {
            "VISION": "视觉节点",
            "RECEIVER": "接收节点",
            "FSM": "飞控大脑"
        }
        if status_key == "HOVERING":
            if hasattr(self.ui, "set_emergency_alert"):
                self.ui.set_emergency_alert(True)
            if hasattr(self.ui, "update_mission_status"):
                self.ui.update_mission_status("已紧急刹车，坐标锁定", log=False)
            if hasattr(self.ui, "append_log"):
                self.ui.append_log("[警告] 已紧急刹车，坐标锁定")
            if hasattr(self.ui, "set_takeoff_enabled"):
                self.ui.set_takeoff_enabled(False)
            return
        
        node_key = mapping.get(status_key)
        if node_key and hasattr(self.ui, "set_node_ready"):
            self.ui.set_node_ready(node_key, True)
            if not self.flight_started:
                if node_key == "RECEIVER":
                    self._log_once("receiver_ready", "接收节点已就绪")
                elif node_key == "FSM":
                    self._log_once("fsm_ready", "飞控大脑已就绪")
            return
        if status_key.startswith("VISION") or status_key.startswith("RECEIVER") or status_key.startswith("FSM"):
            return
        task_status_map = {
            "MISSION_RUNNING": "任务执行中",
            "MISSION_START": "任务执行中",
            "EXECUTING": "任务执行中",
            "RETURN_HOME": "返航",
            "RETURNING": "返航中",
            "LANDING": "降落",
            "GLOBAL_RESET": "全局复位",
            "MISSION_FINISHED": "任务完成",
            "MISSION_DONE": "任务完成",
            "MISSION_COMPLETE": "任务完成"
        }
        task_status = task_status_map.get(status_key)
        if task_status:
            if status_key in ("MISSION_RUNNING", "MISSION_START", "EXECUTING"):
                self._mark_takeoff_success()
            if hasattr(self.ui, "update_mission_status"):
                self.ui.update_mission_status(task_status, log=False)
            if hasattr(self.ui, "append_log") and status_key not in ("MISSION_RUNNING", "MISSION_START", "EXECUTING"):
                self.ui.append_log(f"[任务] {task_status}")
            if status_key == "GLOBAL_RESET":
                self._reset_handshake_state()

    def handle_drone_reply(self, reply):
        reply_key = reply.strip().upper()
        if reply_key == "MISSION_SAVED":
            if hasattr(self.ui, "update_mission_status"):
                self.ui.update_mission_status("无人机已接收并保存航线", log=False)
            if hasattr(self.ui, "set_takeoff_enabled"):
                self.ui.set_takeoff_enabled(False)
            self._log_once("mission_saved", "receiver 已保存航线")
        elif reply_key == "MISSION_LOADED":
            if hasattr(self.ui, "update_mission_status"):
                self.ui.update_mission_status("无人机状态机已成功加载航线，准许起飞", log=False)
            if hasattr(self.ui, "set_takeoff_enabled"):
                self.ui.set_takeoff_enabled(True)
            self._log_once("mission_loaded", "FSM 已加载航线，等待起飞授权")
        else:
            if hasattr(self.ui, "update_mission_status"):
                self.ui.update_mission_status(f"未知回复: {reply}", log=False)
            if hasattr(self.ui, "append_log"):
                self.ui.append_log(f"[警告] 未知回复: {reply}")

    def handle_takeoff_authorize(self):
        if hasattr(self.ui, "append_log"):
            self.ui.append_log("已发送起飞指令 CMD:TAKEOFF")
        self.comm.send_data("CMD:TAKEOFF")
        self._handshake_logged["takeoff_sent"] = True
        if hasattr(self.ui, "set_takeoff_enabled"):
            self.ui.set_takeoff_enabled(False)
        if hasattr(self.ui, "update_mission_status"):
            self.ui.update_mission_status("已发送起飞授权", log=False)

    def handle_emergency_pause(self):
        if hasattr(self.ui, "append_log"):
            self.ui.append_log("[警告] 已发送紧急刹车指令")
        self.comm.send_data("CMD:PAUSE")
        if hasattr(self.ui, "update_mission_status"):
            self.ui.update_mission_status("已发送紧急刹车指令", log=False)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    controller = MainController()
    sys.exit(app.exec_())
