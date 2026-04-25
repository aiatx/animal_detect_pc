#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试美化后的UI"""

import sys
from PyQt5.QtWidgets import QApplication
from ui_view import GroundStationUI

def main():
    app = QApplication(sys.argv)
    
    # 创建UI
    ui = GroundStationUI()
    
    # 模拟一些数据
    ui.nofly_zones.add('A5_B3')
    ui.nofly_zones.add('A6_B3')
    ui.grid_widgets['A5_B3'].setText("禁飞")
    ui.grid_widgets['A5_B3'].setStyleSheet(ui.style_nofly)
    ui.grid_widgets['A6_B3'].setText("禁飞")
    ui.grid_widgets['A6_B3'].setStyleSheet(ui.style_nofly)
    
    # 模拟一些检测结果
    ui.grid_data['A3_B2'] = "12034"
    ui.detected_cells.add('A3_B2')
    ui.grid_widgets['A3_B2'].setText("12034")
    ui.grid_widgets['A3_B2'].setStyleSheet(ui.style_done)
    
    ui.grid_data['A4_B2'] = "00102"
    ui.detected_cells.add('A4_B2')
    ui.grid_widgets['A4_B2'].setText("00102")
    ui.grid_widgets['A4_B2'].setStyleSheet(ui.style_done)
    
    # 更新统计
    ui.calculate_totals()
    ui.update_info_label()
    
    ui.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
