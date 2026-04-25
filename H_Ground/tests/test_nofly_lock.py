"""
测试禁飞区锁定功能
验证：
1. 删除了清空航线和清空禁飞区按钮
2. 禁飞区在生成航线后被锁定
3. 全局复位可以解锁禁飞区
"""
import sys
from PyQt5.QtWidgets import QApplication
from ui_view import GroundStationUI

def test_ui_buttons():
    """测试UI按钮是否正确"""
    app = QApplication(sys.argv)
    ui = GroundStationUI()
    
    # 验证删除的按钮不存在
    assert not hasattr(ui, 'clear_route_btn'), "清空航线按钮应该被删除"
    assert not hasattr(ui, 'clear_nofly_btn'), "清空禁飞区按钮应该被删除"
    
    # 验证保留的按钮存在
    assert hasattr(ui, 'reset_all_btn'), "全局复位按钮应该存在"
    assert hasattr(ui, 'plan_btn'), "规划按钮应该存在"
    assert hasattr(ui, 'send_btn'), "发送按钮应该存在"
    
    print("✓ 按钮检查通过：清空航线和清空禁飞区按钮已删除，全局复位按钮保留")
    return True

def test_nofly_lock():
    """测试禁飞区锁定功能"""
    app = QApplication(sys.argv)
    ui = GroundStationUI()
    
    # 初始状态：禁飞区未锁定
    assert ui.nofly_zone_locked == False, "初始状态禁飞区应该未锁定"
    print("✓ 初始状态：禁飞区未锁定")
    
    # 设置禁飞区
    ui.toggle_nofly('A1_B1')
    assert 'A1_B1' in ui.nofly_zones, "应该能够设置禁飞区"
    print("✓ 可以设置禁飞区")
    
    # 模拟生成航线（调用animate_path会锁定禁飞区）
    test_route = ['A9_B1', 'A8_B1', 'A7_B1']
    ui.animate_path(test_route, animate=False)
    
    # 验证禁飞区已锁定
    assert ui.nofly_zone_locked == True, "生成航线后禁飞区应该被锁定"
    print("✓ 生成航线后禁飞区已锁定")
    
    # 尝试修改禁飞区（应该失败）
    initial_count = len(ui.nofly_zones)
    ui.handle_grid_click('A2_B2')  # 尝试添加新禁飞区
    assert len(ui.nofly_zones) == initial_count, "锁定后不应该能修改禁飞区"
    print("✓ 锁定后无法修改禁飞区")
    
    # 全局复位
    ui.reset_all()
    
    # 验证禁飞区已解锁
    assert ui.nofly_zone_locked == False, "全局复位后禁飞区应该解锁"
    assert len(ui.nofly_zones) == 0, "全局复位后禁飞区应该被清空"
    print("✓ 全局复位后禁飞区解锁并清空")
    
    # 验证可以再次设置禁飞区
    ui.toggle_nofly('A3_B3')
    assert 'A3_B3' in ui.nofly_zones, "复位后应该能够重新设置禁飞区"
    print("✓ 复位后可以重新设置禁飞区")
    
    return True

if __name__ == '__main__':
    try:
        print("=" * 50)
        print("测试1: UI按钮检查")
        print("=" * 50)
        test_ui_buttons()
        
        print("\n" + "=" * 50)
        print("测试2: 禁飞区锁定功能")
        print("=" * 50)
        test_nofly_lock()
        
        print("\n" + "=" * 50)
        print("所有测试通过！✓")
        print("=" * 50)
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
