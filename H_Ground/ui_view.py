import math
from PyQt5.QtWidgets import QMainWindow, QWidget, QGridLayout, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy
from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtGui import QFont, QPainter, QPen, QColor, QPolygonF

class PathRenderer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.path_points = []
        self.offset_px = 8  # 双车道偏移像素
        self.return_start_index = None
        self.plane_pos = None
        self.plane_text = "✈"
        self.plane_font_size = 18
        self.plane_offset = QPointF(12, -12)
        self.plane_color = QColor(244, 81, 30, 230)

        # 去程：冷色调（亮蓝色） + 实线
        self.outbound_pen = QPen(QColor(30, 136, 229, 200), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        
        # 重复访问（橙色） + 虚线
        self.repeat_pen = QPen(QColor(255, 111, 0, 210), 3, Qt.DashLine, Qt.RoundCap, Qt.RoundJoin)
        
        # 返程：暖色调（紫色） + 粗虚线
        self.rtl_pen = QPen(QColor(123, 31, 162, 210), 4, Qt.DashLine, Qt.RoundCap, Qt.RoundJoin)
        
        # 长线模式：用于跨越多个格子的连续航段
        self.skip_arrows = set()  # 需要跳过绘制箭头的线段索引

    def clear(self):
        self.path_points.clear()
        self.skip_arrows.clear()
        self.update()

    def set_return_start_index(self, index):
        self.return_start_index = index
        self.update()

    def set_points(self, points, skip_arrows_indices=None):
        """设置路径点
        
        参数：
            points: QPointF列表
            skip_arrows_indices: 不需要绘制箭头的线段索引集合
        """
        self.path_points = list(points)
        self.skip_arrows = set(skip_arrows_indices or [])
        self.update()

    def add_point(self, point):
        self.path_points.append(point)
        self.update()

    def set_plane_position(self, pos):
        if pos is None:
            self.plane_pos = None
            self.update()
            return
        self.plane_pos = QPointF(pos)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if len(self.path_points) >= 2:
            points = self.path_points
            visited_points = set()
            if points:
                visited_points.add(self._point_key(points[0]))

            for i in range(len(points) - 1):
                p1 = points[i]
                p2 = points[i + 1]
                dx = p2.x() - p1.x()
                dy = p2.y() - p1.y()
                length = math.hypot(dx, dy)
                if length == 0:
                    continue

                end_key = self._point_key(p2)
                is_return_phase = self.return_start_index is not None and i >= self.return_start_index
                is_repeat = (end_key in visited_points) if not is_return_phase else False
                if not is_return_phase:
                    visited_points.add(end_key)

                # 计算法向量用于双车道偏移
                nx = -dy / length
                ny = dx / length
                off_x = nx * self.offset_px
                off_y = ny * self.offset_px

                new_p1 = QPointF(p1.x() + off_x, p1.y() + off_y)
                new_p2 = QPointF(p2.x() + off_x, p2.y() + off_y)

                # 选择笔触
                if is_return_phase:
                    pen = self.rtl_pen  # 返程：紫色粗虚线
                else:
                    pen = self.repeat_pen if is_repeat else self.outbound_pen  # 去程或重复

                painter.setPen(pen)
                painter.setBrush(pen.color())
                painter.drawLine(new_p1, new_p2)
                
                # 只在需要的位置绘制箭头（跳过长线段）
                if i not in self.skip_arrows:
                    self.draw_arrow(painter, new_p1, new_p2)

        if self.plane_pos is not None:
            self._draw_plane(painter, self.plane_pos)

    def _point_key(self, point):
        return (int(round(point.x())), int(round(point.y())))

    def draw_arrow(self, painter, p1, p2):
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        length = math.hypot(dx, dy)
        if length == 0:
            return

        angle = math.atan2(dy, dx)
        arrow_back = min(16.0, length * 0.3)
        arrow_size = min(10.0, length * 0.2)
        end_p = QPointF(p2.x() - math.cos(angle) * arrow_back,
                        p2.y() - math.sin(angle) * arrow_back)

        p3 = QPointF(end_p.x() - arrow_size * math.cos(angle - math.pi / 6),
                     end_p.y() - arrow_size * math.sin(angle - math.pi / 6))
        p4 = QPointF(end_p.x() - arrow_size * math.cos(angle + math.pi / 6),
                     end_p.y() - arrow_size * math.sin(angle + math.pi / 6))

        painter.drawPolygon(QPolygonF([end_p, p3, p4]))

    def _draw_plane(self, painter, pos):
        painter.setPen(self.plane_color)
        font = QFont("Segoe UI Emoji", self.plane_font_size)
        font.setBold(True)
        painter.setFont(font)
        draw_pos = QPointF(pos.x() + self.plane_offset.x(), pos.y() + self.plane_offset.y())
        painter.drawText(draw_pos, self.plane_text)

class GroundStationUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.grid_widgets = {}
        self.grid_data = {}
        self.nofly_zones = set()
        self.detected_cells = set()
        self.grid_interaction_enabled = True
        self.nofly_locked = False  # 禁飞区锁定状态
        self.columns = [f'A{i}' for i in range(1, 10)]
        self.rows = [f'B{i}' for i in range(1, 8)]
        self.start_point = 'A9_B1'
        self.animal_names = ["大象", "猴子", "孔雀", "野狼", "老虎"]
        self.manual_mode = False
        self.return_start_index = None
        self.cell_size_m = 0.5
        self.plane_grid_id = None
        
        # 保存路由状态，用于自适应刷新
        self.current_step = 0
        self.route_list = []
        
        self.initUI()

    def initUI(self):
        self.setWindowTitle('无人机地面站控制系统 v2.0')
        self.resize(1280, 720)
        
        # 现代化配色方案
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f8f9fa, stop:1 #e9ecef);
            }
            QLabel {
                color: #2c3e50;
                font-family: 'Microsoft YaHei UI', 'Segoe UI', sans-serif;
            }
        """)

        main_layout = QHBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 左侧网格容器
        grid_container = QVBoxLayout()
        grid_container.setSpacing(8)
        
        # 网格标题
        grid_title = QLabel("飞行区域网格")
        grid_title.setFont(QFont('Microsoft YaHei UI', 16, QFont.Bold))
        grid_title.setStyleSheet("""
            color: #1a73e8;
            padding: 10px;
            background-color: white;
            border-radius: 8px;
            border: 2px solid #e3f2fd;
        """)
        grid_title.setAlignment(Qt.AlignCenter)
        grid_container.addWidget(grid_title)
        
        # 网格布局
        grid_layout = QGridLayout()
        grid_layout.setSpacing(6)
        grid_layout.setContentsMargins(10, 10, 10, 10)
        
        # 现代化样式
        self.style_normal = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f8f9fa);
                color: #495057;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                font-weight: bold;
                padding: 5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #e3f2fd, stop:1 #bbdefb);
                border: 2px solid #90caf9;
            }
        """
        
        self.style_takeoff = """
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #fff3cd, stop:1 #ffc107);
            color: #856404;
            font-weight: bold;
            border: 3px solid #ffb300;
            border-radius: 8px;
            font-size: 13px;
        """
        
        self.style_nofly = """
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #f8d7da, stop:1 #f44336);
            color: #721c24;
            font-weight: bold;
            border: 3px solid #c62828;
            border-radius: 8px;
            font-size: 12px;
        """
        
        self.style_route = """
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #cfe2ff, stop:1 #2196f3);
            color: #004085;
            border: 3px solid #1976d2;
            border-radius: 8px;
            font-weight: bold;
        """
        
        self.style_done = """
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #d4edda, stop:1 #4caf50);
            color: #155724;
            font-weight: bold;
            border: 3px solid #388e3c;
            border-radius: 8px;
            font-size: 12px;
        """

        for y_idx, row_name in enumerate(reversed(self.rows)):
            lbl = QLabel(row_name)
            lbl.setStyleSheet("""
                color: #1976d2;
                font-weight: bold;
                font-size: 16px;
                padding: 5px;
            """)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid_layout.addWidget(lbl, y_idx, 0)
            
            for x_idx, col_name in enumerate(self.columns):
                grid_id = f"{col_name}_{row_name}"
                btn = QPushButton()
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                btn.setMinimumSize(75, 55)
                btn.setFont(QFont('Consolas', 12, QFont.Bold))
                btn.setCursor(Qt.PointingHandCursor)
                
                if grid_id == self.start_point:
                    btn.setText("起飞区")
                    btn.setStyleSheet(self.style_takeoff)
                    btn.clicked.connect(lambda checked, gid=grid_id: self.handle_grid_click(gid))
                else:
                    self.grid_data[grid_id] = "00000"
                    btn.setText(self.grid_data[grid_id])
                    btn.setStyleSheet(self.style_normal)
                    btn.clicked.connect(lambda checked, gid=grid_id: self.handle_grid_click(gid))
                
                grid_layout.addWidget(btn, y_idx, x_idx + 1)
                self.grid_widgets[grid_id] = btn

        for x_idx, col_name in enumerate(self.columns):
            lbl = QLabel(col_name)
            lbl.setStyleSheet("""
                color: #1976d2;
                font-weight: bold;
                font-size: 16px;
                padding: 5px;
            """)
            lbl.setAlignment(Qt.AlignCenter)
            grid_layout.addWidget(lbl, 7, x_idx + 1)

        grid_container.addLayout(grid_layout)
        
        # 右侧控制面板
        side_panel = QVBoxLayout()
        side_panel.setSpacing(12)
        side_panel.setContentsMargins(10, 10, 10, 10)
        
        # 状态面板
        status_panel = QWidget()
        status_panel.setStyleSheet("""
            background-color: white;
            border-radius: 10px;
            border: 2px solid #e3f2fd;
        """)
        status_layout = QVBoxLayout(status_panel)
        status_layout.setContentsMargins(15, 15, 15, 15)
        
        self.status_lbl = QLabel("通信状态: 待连接...")
        self.status_lbl.setFont(QFont('Microsoft YaHei UI', 11))
        self.status_lbl.setStyleSheet("""
            color: #1976d2;
            padding: 8px;
            background-color: #e3f2fd;
            border-radius: 6px;
        """)
        status_layout.addWidget(self.status_lbl)

        self.info_label = QLabel("禁飞区数: 0\n航点总数: 0")
        self.info_label.setFont(QFont('Microsoft YaHei UI', 11))
        self.info_label.setStyleSheet("""
            color: #2e7d32;
            padding: 8px;
            background-color: #f1f8e9;
            border-radius: 6px;
            margin-top: 8px;
        """)
        status_layout.addWidget(self.info_label)
        
        side_panel.addWidget(status_panel)
        
        # 统计面板
        stat_panel = QWidget()
        stat_panel.setStyleSheet("""
            background-color: white;
            border-radius: 10px;
            border: 2px solid #fff3e0;
        """)
        stat_layout = QVBoxLayout(stat_panel)
        stat_layout.setContentsMargins(15, 15, 15, 15)
        
        stat_title = QLabel("🦁 动物数量统计")
        stat_title.setFont(QFont('Microsoft YaHei UI', 14, QFont.Bold))
        stat_title.setStyleSheet("""
            color: #e65100;
            padding: 8px;
            background-color: #fff3e0;
            border-radius: 6px;
        """)
        stat_layout.addWidget(stat_title)

        self.stat_labels = {}
        animal_icons = ["🐘", "🐵", "🦚", "🐺", "🐯"]
        for i, name in enumerate(self.animal_names):
            lbl = QLabel(f"{animal_icons[i]} {name}: 0")
            lbl.setFont(QFont('Microsoft YaHei UI', 12))
            lbl.setStyleSheet("""
                color: #424242;
                padding: 6px;
                margin: 2px;
                background-color: #fafafa;
                border-radius: 4px;
            """)
            stat_layout.addWidget(lbl)
            self.stat_labels[name] = lbl
        
        side_panel.addWidget(stat_panel)
        side_panel.addStretch()

        # 控制按钮组
        btn_style_base = """
            QPushButton {
                color: white;
                font-weight: bold;
                border-radius: 8px;
                font-size: 14px;
                padding: 10px;
                font-family: 'Microsoft YaHei UI', sans-serif;
            }
            QPushButton:hover {
                transform: scale(1.05);
            }
            QPushButton:pressed {
                transform: scale(0.95);
            }
            QPushButton:disabled {
                background-color: #bdbdbd;
                color: #757575;
            }
        """

        self.manual_btn = QPushButton("🎯 手动规划")
        self.manual_btn.setCheckable(True)
        self.manual_btn.setFixedHeight(45)
        self.manual_btn.setStyleSheet(btn_style_base + """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #78909c, stop:1 #546e7a);
            }
            QPushButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #26a69a, stop:1 #00897b);
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #90a4ae, stop:1 #607d8b);
            }
        """)
        self.manual_btn.toggled.connect(self.set_manual_mode)
        side_panel.addWidget(self.manual_btn)

        self.plan_btn = QPushButton("🚁 自动规划")
        self.plan_btn.setFixedHeight(50)
        self.plan_btn.setStyleSheet(btn_style_base + """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #42a5f5, stop:1 #1976d2);
                font-size: 15px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #64b5f6, stop:1 #2196f3);
            }
        """)
        side_panel.addWidget(self.plan_btn)

        self.send_btn = QPushButton("✈️ 发送/起飞")
        self.send_btn.setFixedHeight(50)
        self.send_btn.setEnabled(False)
        self.send_btn.setStyleSheet(btn_style_base + """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #66bb6a, stop:1 #43a047);
                font-size: 15px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #81c784, stop:1 #4caf50);
            }
        """)
        side_panel.addWidget(self.send_btn)

        self.reset_all_btn = QPushButton("🔄 全局复位")
        self.reset_all_btn.setFixedHeight(42)
        self.reset_all_btn.setStyleSheet(btn_style_base + """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #78909c, stop:1 #546e7a);
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #90a4ae, stop:1 #607d8b);
            }
        """)
        side_panel.addWidget(self.reset_all_btn)

        main_layout.addLayout(grid_container, 5)
        main_layout.addLayout(side_panel, 2)

        self.central_widget = QWidget()
        self.central_widget.setLayout(main_layout)
        self.setCentralWidget(self.central_widget)

        self.overlay = PathRenderer(self.central_widget)

        self.reset_all_btn.clicked.connect(self.reset_all)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'overlay') and self.centralWidget():
            self.overlay.resize(self.centralWidget().size())
            # 窗口大小改变时，重新把算好的坐标喂给画板
            self.recalculate_route_points()

    def recalculate_route_points(self):
        """核心修复：在安全的时候计算坐标，并只存结果"""
        if not hasattr(self, 'route_list') or not self.route_list:
            return
        points = []
        for i in range(self.current_step):
            gid = self.route_list[i]
            btn = self.grid_widgets[gid]
            pos = btn.mapTo(self.central_widget, btn.rect().center())
            points.append(QPointF(pos.x(), pos.y()))
        skip_arrows = getattr(self, 'skip_arrows', None)
        self.overlay.set_points(points, skip_arrows_indices=skip_arrows)
        self._refresh_plane_overlay()

    def calculate_totals(self):
        totals = [0, 0, 0, 0, 0]
        for gid, txt in self.grid_data.items():
            if len(txt) == 5 and txt.isdigit():
                for i in range(5):
                    totals[i] += int(txt[i])
        for i, name in enumerate(self.animal_names):
            self.stat_labels[name].setText(f"{name}: {totals[i]}")

    def update_info_label(self, prefix=None):
        distance_m = self._route_distance_m(self.route_list)
        distance_text = f"航线距离: {distance_m:.2f} m"
        if prefix:
            self.info_label.setText(
                f"禁飞区数: {len(self.nofly_zones)}\n"
                f"{prefix}航点数: {len(self.route_list)}\n"
                f"{distance_text}"
            )
        else:
            self.info_label.setText(
                f"禁飞区数: {len(self.nofly_zones)}\n"
                f"航点总数: {len(self.route_list)}\n"
                f"{distance_text}"
            )

    def _grid_id_to_coord(self, grid_id):
        col_name, row_name = grid_id.split('_', 1)
        x = self.columns.index(col_name)
        y = self.rows.index(row_name)
        return x, y

    def _route_distance_m(self, route_list):
        if not route_list or len(route_list) < 2:
            return 0.0
        total_steps = 0
        for i in range(1, len(route_list)):
            x1, y1 = self._grid_id_to_coord(route_list[i - 1])
            x2, y2 = self._grid_id_to_coord(route_list[i])
            total_steps += abs(x2 - x1) + abs(y2 - y1)
        return total_steps * self.cell_size_m

    def handle_grid_click(self, grid_id):
        if not self.grid_interaction_enabled:
            return
        if self.manual_mode:
            self.add_manual_waypoint(grid_id)
        else:
            # 直接点击设置禁飞区，只有在未锁定时才能修改
            if not self.nofly_locked:
                self.toggle_nofly(grid_id)

    def set_grid_interaction(self, enabled):
        self.grid_interaction_enabled = enabled
        for btn in self.grid_widgets.values():
            btn.setEnabled(enabled)

    def toggle_nofly(self, grid_id):
        btn = self.grid_widgets[grid_id]
        if grid_id in self.nofly_zones:
            self.nofly_zones.remove(grid_id)
            btn.setText(self.grid_data.get(grid_id, "00000"))
            btn.setStyleSheet(self.style_done if grid_id in self.detected_cells else self.style_normal)
        else:
            self.nofly_zones.add(grid_id)
            btn.setText(self.grid_data.get(grid_id, "00000"))
            btn.setStyleSheet(self.style_nofly)
            
        self.update_info_label()
        self.calculate_totals()

    def refresh_grid_styles(self):
        for gid, btn in self.grid_widgets.items():
            if gid == self.start_point:
                btn.setText("起飞区")
                btn.setStyleSheet(self.style_takeoff)
                continue

            if gid in self.nofly_zones:
                btn.setText(self.grid_data.get(gid, "00000"))
                btn.setStyleSheet(self.style_nofly)
                continue

            btn.setText(self.grid_data.get(gid, "00000"))
            if gid in self.detected_cells:
                btn.setStyleSheet(self.style_done)
            else:
                btn.setStyleSheet(self.style_normal)

    def set_nofly_mode(self, enabled):
        """设置禁飞区模式"""
        self.nofly_mode = enabled
        if enabled:
            # 进入禁飞区设置模式时，如果已锁定则禁用按钮
            if self.nofly_locked:
                self.nofly_btn.setChecked(False)
                self.nofly_mode = False
                return
            # 禁用其他模式
            self.manual_btn.setEnabled(False)
            self.plan_btn.setEnabled(False)
        else:
            # 退出禁飞区设置模式
            self.manual_btn.setEnabled(True)
            self.plan_btn.setEnabled(not self.manual_mode)

    def reset_all(self):
        if hasattr(self, 'timer'):
            self.timer.stop()

        self.manual_btn.blockSignals(True)
        self.manual_btn.setChecked(False)
        self.manual_btn.blockSignals(False)
        self.manual_mode = False

        self.nofly_zones.clear()
        self.detected_cells.clear()
        for gid in self.grid_widgets:
            if gid != self.start_point:
                self.grid_data[gid] = "00000"

        self.route_list = []
        self.current_step = 0
        self.return_start_index = None
        self.skip_arrows = set()
        self.plane_grid_id = None
        self.nofly_locked = False  # 重置禁飞区锁定状态
        self.overlay.set_return_start_index(None)
        self.overlay.clear()
        self.overlay.set_plane_position(None)

        self.plan_btn.setEnabled(True)
        self.send_btn.setEnabled(False)
        self.set_grid_interaction(True)
        self.refresh_grid_styles()
        self.calculate_totals()
        self.update_info_label()

    def update_status_msg(self, msg):
        self.status_lbl.setText(f"通信状态:\n{msg}")

    def _normalize_animal_code(self, animal_code):
        digits = "".join([ch for ch in animal_code if ch.isdigit()])
        if len(digits) >= 5:
            return digits[:5]
        return digits.rjust(5, "0")

    def update_grid_result(self, gid, animal_code):
        if gid in self.grid_widgets:
            # Prevent double counting for revisits/return trips once the cell is confirmed.
            if gid in self.detected_cells and self.grid_data.get(gid, "00000") != "00000":
                return
            btn = self.grid_widgets[gid]
            normalized = self._normalize_animal_code(animal_code)
            self.grid_data[gid] = normalized
            self.detected_cells.add(gid)
            btn.setText(normalized)
            if gid in self.nofly_zones:
                btn.setStyleSheet(self.style_nofly)
            else:
                btn.setStyleSheet(self.style_done)
            self.calculate_totals()

    def update_plane_position(self, grid_id):
        if grid_id not in self.grid_widgets:
            return
        self.plane_grid_id = grid_id

        btn = self.grid_widgets[grid_id]
        pos = btn.mapTo(self.central_widget, btn.rect().center())
        self.overlay.set_plane_position(QPointF(pos.x(), pos.y()))

    def _refresh_plane_overlay(self):
        if not self.plane_grid_id:
            return
        if self.plane_grid_id not in self.grid_widgets:
            return
        btn = self.grid_widgets[self.plane_grid_id]
        pos = btn.mapTo(self.central_widget, btn.rect().center())
        self.overlay.set_plane_position(QPointF(pos.x(), pos.y()))

    def animate_path(self, route_list, animate=True, prefix="规划成功! ", return_start_index=None, 
                     checkpoint_indices=None, original_route=None, original_checkpoints=None):
        self.route_list = route_list
        self.original_route = original_route or route_list
        self.current_step = 0
        self.checkpoint_indices = checkpoint_indices or list(range(len(route_list)))
        self.send_btn.setEnabled(len(route_list) > 1)
        self.refresh_grid_styles()
        self.update_info_label(prefix=prefix)
        self.return_start_index = return_start_index
        self.overlay.set_return_start_index(return_start_index)
        
        # 锁定禁飞区：开始生成航线后不允许修改
        self.nofly_locked = True
        
        # 计算需要跳过箭头的线段（长线跨越合并点）
        skip_arrows = self._calculate_skip_arrows(self.original_route, route_list)
        self.skip_arrows = skip_arrows

        if not animate:
            self._render_route_points(route_list, skip_arrows)
            return

        self.plan_btn.setEnabled(False)
        self.overlay.clear()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.draw_next_step)
        self.timer.start(150)
    
    def _calculate_skip_arrows(self, original_route, merged_route):
        """计算哪些线段需要跳过箭头（长线段）
        
        返回线段索引集合，这些线段跨越了被合并的点。
        """
        if not original_route or original_route == merged_route:
            return set()
        
        skip_arrows = set()
        
        # 构建原始路线的索引映射
        orig_indices = {}
        for i, gid in enumerate(merged_route):
            # 在原始路线中找这个点
            try:
                orig_idx = original_route.index(gid)
                orig_indices[i] = orig_idx
            except ValueError:
                orig_indices[i] = -1
        
        # 检查合并路线中的相邻点在原始路线中是否相邻
        for i in range(len(merged_route) - 1):
            orig_i = orig_indices.get(i, -1)
            orig_next = orig_indices.get(i + 1, -1)
            
            # 如果两个点在原始路线中不相邻，说明有点被合并了
            if orig_i >= 0 and orig_next >= 0 and orig_next != orig_i + 1:
                # 这是一条长线段，跳过其箭头
                skip_arrows.add(i)
        
        return skip_arrows

    def draw_next_step(self):
        if self.current_step < len(self.route_list):
            grid_id = self.route_list[self.current_step]
            btn = self.grid_widgets[grid_id]
            
            self._apply_route_style(grid_id)
            
            # 在这里算好坐标，丢给画板，这样画板就不会去违规查内存了
            pos = btn.mapTo(self.central_widget, btn.rect().center())
            self.overlay.add_point(QPointF(pos.x(), pos.y()))
            
            self.current_step += 1
        else:
            self.timer.stop()
            self.plan_btn.setEnabled(True)

    def _apply_route_style(self, grid_id):
        if grid_id == self.start_point:
            return
        if grid_id in self.nofly_zones or grid_id in self.detected_cells:
            return
        self.grid_widgets[grid_id].setStyleSheet(self.style_route)

    def _render_route_points(self, route_list, skip_arrows=None):
        points = []
        for gid in route_list:
            btn = self.grid_widgets[gid]
            self._apply_route_style(gid)
            pos = btn.mapTo(self.central_widget, btn.rect().center())
            points.append(QPointF(pos.x(), pos.y()))
        self.current_step = len(route_list)
        # 传递skip_arrows给PathRenderer
        self.overlay.set_points(points, skip_arrows_indices=skip_arrows)

    def set_manual_mode(self, enabled):
        self.manual_mode = enabled
        self.plan_btn.setEnabled(not enabled)
        if enabled:
            # 清空当前航线
            if hasattr(self, 'timer'):
                self.timer.stop()
            self.return_start_index = None
            self.overlay.set_return_start_index(None)
            self.route_list = [self.start_point]
            self.current_step = 1
            self.send_btn.setEnabled(False)
            self.set_grid_interaction(True)
            self.refresh_grid_styles()
            self._render_route_points(self.route_list)
            self.update_info_label(prefix="手动 ")

    def add_manual_waypoint(self, grid_id):
        """手动添加航点，支持格子状态追踪
        
        逻辑：
        - 手动模式下操作员有最高权限
        - 每个航点都继承其格子的检测状态
        - 已检查的格子将参与合并算法
        """
        # 在手动模式下，操作员拥有最高权限，可以点击任何格子包括起飞区
        if not self.manual_mode and grid_id == self.start_point:
            return
        
        if not self.route_list:
            self.route_list = [self.start_point]
        
        self.route_list.append(grid_id)
        self._render_route_points(self.route_list)
        self.update_info_label(prefix="手动 ")
        self.send_btn.setEnabled(len(self.route_list) > 1)
        
        # 标记这个航点的检测状态（用于后续的合并算法）
        # 如果该格子已经被检测过，它将被标记为"已检查"状态
        # 这样在合并算法中就能识别并合并这些已检查的中间点
