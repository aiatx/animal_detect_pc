import math
from PyQt5.QtWidgets import QMainWindow, QWidget, QGridLayout, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy
from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtGui import QFont, QPainter, QPen, QColor, QPolygonF

class PathOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        # 核心修改：这里不再存格子的 ID，而是直接存算好的纯粹物理坐标 (QPointF)
        # 这样 paintEvent 就不需要去查其他组件的几何数据了，彻底避开段错误
        self.points = []        

    def paintEvent(self, event):
        if len(self.points) < 2:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing) 
        
        pen = QPen(QColor(229, 57, 53, 200), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QColor(229, 57, 53, 200))
        
        offset_val = 8 

        for i in range(len(self.points) - 1):
            # 直接拿现成的纯坐标，绝不去碰 UI 组件
            p1 = self.points[i]
            p2 = self.points[i+1]
            
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            off_x, off_y = 0, 0
            if abs(dx) > abs(dy): 
                if dx > 0: off_y = offset_val   
                else:      off_y = -offset_val  
            else: 
                if dy > 0: off_x = offset_val   
                else:      off_x = -offset_val  
                
            new_p1 = QPointF(p1.x() + off_x, p1.y() + off_y)
            new_p2 = QPointF(p2.x() + off_x, p2.y() + off_y)
            
            painter.drawLine(new_p1, new_p2)
            self.draw_arrow(painter, new_p1, new_p2)

    def draw_arrow(self, painter, p1, p2):
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        angle = math.atan2(dy, dx)
        arrow_size = 12
        end_p = QPointF(p2.x() - math.cos(angle) * 16, p2.y() - math.sin(angle) * 16)
        
        p3 = QPointF(end_p.x() - arrow_size * math.cos(angle - math.pi / 6),
                     end_p.y() - arrow_size * math.sin(angle - math.pi / 6))
        p4 = QPointF(end_p.x() - arrow_size * math.cos(angle + math.pi / 6),
                     end_p.y() - arrow_size * math.sin(angle + math.pi / 6))
        
        painter.drawPolygon(QPolygonF([end_p, p3, p4]))

class GroundStationUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.grid_widgets = {}
        self.nofly_zones = []
        self.columns = [f'A{i}' for i in range(1, 10)]
        self.rows = [f'B{i}' for i in range(1, 8)]
        self.start_point = 'A9_B1'
        self.animal_names = ["大象", "猴子", "孔雀", "野狼", "老虎"]
        
        # 保存路由状态，用于自适应刷新
        self.current_step = 0
        self.route_list = []
        
        self.initUI()

    def initUI(self):
        self.setWindowTitle('电赛H题 - 战术地面站 (高稳自适应版)')
        self.resize(1024, 600)
        self.setStyleSheet("background-color: #F5F7FA; color: #333333;")

        main_layout = QHBoxLayout()
        grid_container = QGridLayout()
        grid_container.setSpacing(4)
        
        self.style_normal = "QPushButton { background-color: #FFFFFF; color: #000000; border: 1px solid #B0BEC5; border-radius: 4px; }"
        self.style_takeoff = "background-color: #FFE082; color: #B78103; font-weight: bold; border: 2px solid #FFCA28; border-radius: 4px;"
        self.style_nofly = "background-color: #FFCDD2; color: #C62828; font-weight: bold; border: 2px solid #EF5350; border-radius: 4px;"
        self.style_route = "background-color: #FFFFFF; color: #000000; border: 2px solid #E53935; border-radius: 4px;" 
        self.style_done = "background-color: #C8E6C9; color: #2E7D32; font-weight: bold; border: 2px solid #66BB6A; border-radius: 4px;"

        for y_idx, row_name in enumerate(reversed(self.rows)):
            lbl = QLabel(row_name)
            lbl.setStyleSheet("color: #455A64; font-weight: bold; font-size: 14px;")
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid_container.addWidget(lbl, y_idx, 0)
            
            for x_idx, col_name in enumerate(self.columns):
                grid_id = f"{col_name}_{row_name}"
                btn = QPushButton("00000")
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                btn.setMinimumSize(60, 45) 
                btn.setFont(QFont('Consolas', 11, QFont.Bold)) 
                
                if grid_id == self.start_point:
                    btn.setText("起飞区")
                    btn.setStyleSheet(self.style_takeoff)
                    btn.setEnabled(False)
                else:
                    btn.setStyleSheet(self.style_normal)
                    btn.clicked.connect(lambda checked, gid=grid_id: self.toggle_nofly(gid))
                
                grid_container.addWidget(btn, y_idx, x_idx + 1)
                self.grid_widgets[grid_id] = btn

        for x_idx, col_name in enumerate(self.columns):
            lbl = QLabel(col_name)
            lbl.setStyleSheet("color: #455A64; font-weight: bold; font-size: 14px;")
            lbl.setAlignment(Qt.AlignCenter)
            grid_container.addWidget(lbl, 7, x_idx + 1)

        side_panel = QVBoxLayout()
        side_panel.setContentsMargins(20, 10, 10, 10)
        
        self.status_lbl = QLabel("通信状态: 待连接...")
        self.status_lbl.setFont(QFont('微软雅黑', 11))
        self.status_lbl.setStyleSheet("color: #1565C0; margin-bottom: 5px;")
        side_panel.addWidget(self.status_lbl)

        self.info_label = QLabel("禁飞区数: 0\n航点总数: 0")
        self.info_label.setFont(QFont('微软雅黑', 11))
        self.info_label.setStyleSheet("color: #2E7D32;")
        side_panel.addWidget(self.info_label)
        
        stat_title = QLabel("动物数量汇总")
        stat_title.setFont(QFont('微软雅黑', 14, QFont.Bold))
        stat_title.setStyleSheet("color: #37474F; margin-top: 15px;")
        side_panel.addWidget(stat_title)

        self.stat_labels = {}
        for name in self.animal_names:
            lbl = QLabel(f"{name}: 0")
            lbl.setFont(QFont('微软雅黑', 13))
            lbl.setStyleSheet("color: #546E7A; margin-left: 5px;")
            side_panel.addWidget(lbl)
            self.stat_labels[name] = lbl
            
        side_panel.addStretch()

        self.reset_btn = QPushButton("清空复位")
        self.reset_btn.setFixedHeight(45)
        self.reset_btn.setStyleSheet("background-color: #EF5350; color: white; font-weight: bold; border-radius: 6px; font-size: 15px; margin-bottom: 10px;")
        side_panel.addWidget(self.reset_btn)

        self.plan_btn = QPushButton("规划航线")
        self.plan_btn.setFixedHeight(45)
        self.plan_btn.setStyleSheet("background-color: #42A5F5; color: white; font-weight: bold; border-radius: 6px; font-size: 15px;")
        side_panel.addWidget(self.plan_btn)

        main_layout.addLayout(grid_container, 4)
        main_layout.addLayout(side_panel, 1)

        self.central_widget = QWidget()
        self.central_widget.setLayout(main_layout)
        self.setCentralWidget(self.central_widget)

        # 这里只需传父组件，不再传 self
        self.overlay = PathOverlay(self.central_widget)

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
        self.overlay.points.clear()
        for i in range(self.current_step):
            gid = self.route_list[i]
            btn = self.grid_widgets[gid]
            pos = btn.mapTo(self.central_widget, btn.rect().center())
            self.overlay.points.append(QPointF(pos.x(), pos.y()))
        self.overlay.update()

    def calculate_totals(self):
        totals = [0, 0, 0, 0, 0]
        for gid, btn in self.grid_widgets.items():
            if gid == self.start_point: continue
            txt = btn.text().strip()
            if len(txt) == 5 and txt.isdigit():
                for i in range(5):
                    totals[i] += int(txt[i])
        for i, name in enumerate(self.animal_names):
            self.stat_labels[name].setText(f"{name}: {totals[i]}")

    def toggle_nofly(self, grid_id):
        btn = self.grid_widgets[grid_id]
        if grid_id in self.nofly_zones:
            self.nofly_zones.remove(grid_id)
            btn.setText("00000")
            btn.setStyleSheet(self.style_normal)
        else:
            self.nofly_zones.append(grid_id)
            btn.setText("禁飞")
            btn.setStyleSheet(self.style_nofly)
            
        self.info_label.setText(f"禁飞区数: {len(self.nofly_zones)}\n航点总数: 0")
        self.calculate_totals()

    def reset_ui(self):
        self.nofly_zones.clear()
        self.info_label.setText("禁飞区数: 0\n航点总数: 0")
        if hasattr(self, 'timer'): self.timer.stop()
        self.plan_btn.setEnabled(True)
        
        self.current_step = 0
        self.route_list = []
        self.overlay.points.clear()
        self.overlay.update()
        
        for gid, btn in self.grid_widgets.items():
            if gid == self.start_point:
                btn.setText("起飞区")
                btn.setStyleSheet(self.style_takeoff)
            else:
                btn.setText("00000")
                btn.setStyleSheet(self.style_normal)
        self.calculate_totals()

    def update_status_msg(self, msg):
        self.status_lbl.setText(f"通信状态:\n{msg}")

    def update_grid_result(self, gid, animal_code):
        if gid in self.grid_widgets:
            btn = self.grid_widgets[gid]
            btn.setText(animal_code)
            btn.setStyleSheet(self.style_done)
            self.calculate_totals()

    def animate_path(self, route_list):
        self.info_label.setText(f"禁飞区数: {len(self.nofly_zones)}\n规划成功! 航点数: {len(route_list)}")
        self.current_step = 0
        self.route_list = route_list
        self.plan_btn.setEnabled(False)
        
        self.overlay.points.clear()
        self.overlay.update()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.draw_next_step)
        self.timer.start(150)

    def draw_next_step(self):
        if self.current_step < len(self.route_list):
            grid_id = self.route_list[self.current_step]
            btn = self.grid_widgets[grid_id]
            
            if grid_id != self.start_point:
                btn.setStyleSheet(self.style_route)
            
            # 在这里算好坐标，丢给画板，这样画板就不会去违规查内存了
            pos = btn.mapTo(self.central_widget, btn.rect().center())
            self.overlay.points.append(QPointF(pos.x(), pos.y()))
            self.overlay.update()
            
            self.current_step += 1
        else:
            self.timer.stop()
            self.plan_btn.setEnabled(True)
