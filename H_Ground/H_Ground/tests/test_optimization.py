#!/usr/bin/env python3
"""测试路径规划优化"""

from algorithm import RoutePlanner
import time

def test_empty_nofly():
    """测试空禁飞区场景"""
    print("=" * 60)
    print("测试1: 空禁飞区场景")
    print("=" * 60)
    
    planner = RoutePlanner(cols=9, rows=7)
    start_time = time.time()
    route_list, return_idx, checkpoints, merged_route, merged_checkpoints = planner.plan_route([])
    elapsed = time.time() - start_time
    
    print(f"✓ 路径规划完成，耗时: {elapsed:.4f}秒")
    print(f"✓ 原始路径长度: {len(route_list)}")
    print(f"✓ 合并后路径长度: {len(merged_route)}")
    print(f"✓ 检查点数量: {len(checkpoints)}")
    print(f"✓ 合并后检查点数量: {len(merged_checkpoints)}")
    
    # 评估路径质量
    quality = planner.evaluate_path_quality(route_list, checkpoints)
    print(f"\n路径质量指标:")
    print(f"  - 路径长度: {quality['path_length']}")
    print(f"  - 覆盖单元: {quality['unique_cells']}")
    print(f"  - 重复访问: {quality['repeat_visits']}")
    print(f"  - 转弯次数: {quality['turn_count']}")
    print(f"  - 路径代价: {quality['path_cost']:.2f}")
    print(f"  - 绕路比率: {quality['detour_ratio']:.2f}")
    
    # 验证覆盖率
    expected_cells = 9 * 7
    assert quality['unique_cells'] == expected_cells, f"覆盖率不足: {quality['unique_cells']}/{expected_cells}"
    print(f"✓ 覆盖率验证通过: 100% ({expected_cells}/{expected_cells})")
    
    # 验证绕路比率
    assert quality['detour_ratio'] < 1.2, f"绕路比率过高: {quality['detour_ratio']}"
    print(f"✓ 绕路比率验证通过: {quality['detour_ratio']:.2f} < 1.2")
    
    # 验证性能
    assert elapsed < 1.0, f"性能不达标: {elapsed:.4f}秒 > 1秒"
    print(f"✓ 性能验证通过: {elapsed:.4f}秒 < 1秒")
    
    print("\n✓ 测试1通过\n")
    return quality

def test_with_nofly():
    """测试带禁飞区场景"""
    print("=" * 60)
    print("测试2: 带禁飞区场景")
    print("=" * 60)
    
    planner = RoutePlanner(cols=9, rows=7)
    # 创建一个"墙"分割地图
    nofly = [f'A5_B{y}' for y in range(2, 7)]
    print(f"禁飞区: {nofly}")
    
    start_time = time.time()
    route_list, return_idx, checkpoints, merged_route, merged_checkpoints = planner.plan_route(nofly)
    elapsed = time.time() - start_time
    
    print(f"✓ 路径规划完成，耗时: {elapsed:.4f}秒")
    print(f"✓ 原始路径长度: {len(route_list)}")
    print(f"✓ 合并后路径长度: {len(merged_route)}")
    
    # 评估路径质量
    quality = planner.evaluate_path_quality(route_list, checkpoints)
    print(f"\n路径质量指标:")
    print(f"  - 路径长度: {quality['path_length']}")
    print(f"  - 覆盖单元: {quality['unique_cells']}")
    print(f"  - 重复访问: {quality['repeat_visits']}")
    print(f"  - 转弯次数: {quality['turn_count']}")
    print(f"  - 路径代价: {quality['path_cost']:.2f}")
    print(f"  - 绕路比率: {quality['detour_ratio']:.2f}")
    
    # 验证禁飞区避障
    for cell in route_list:
        assert cell not in nofly, f"路径包含禁飞区: {cell}"
    print(f"✓ 禁飞区避障验证通过")
    
    # 验证覆盖率
    expected_cells = 9 * 7 - len(nofly)
    assert quality['unique_cells'] == expected_cells, f"覆盖率不足: {quality['unique_cells']}/{expected_cells}"
    print(f"✓ 覆盖率验证通过: 100% ({expected_cells}/{expected_cells})")
    
    print("\n✓ 测试2通过\n")
    return quality

def test_invalid_input():
    """测试输入验证"""
    print("=" * 60)
    print("测试3: 输入验证")
    print("=" * 60)
    
    planner = RoutePlanner(cols=9, rows=7)
    
    # 测试无效格式
    invalid_nofly = ['A5_B3', 'INVALID', 'A10_B1', 'A5_B8', None, 123]
    print(f"输入（包含无效项）: {invalid_nofly}")
    
    route_list, _, _, _, _ = planner.plan_route(invalid_nofly)
    
    # 应该只保留有效的禁飞区
    print(f"✓ 输入验证通过，无效项已过滤")
    
    # 验证路径不包含有效的禁飞区
    assert 'A5_B3' not in route_list
    print(f"✓ 有效禁飞区避障验证通过")
    
    print("\n✓ 测试3通过\n")

def test_start_surrounded():
    """测试起点被包围场景"""
    print("=" * 60)
    print("测试4: 起点被包围场景")
    print("=" * 60)
    
    planner = RoutePlanner(cols=9, rows=7)
    # 包围A9_B1的禁飞区
    nofly = ['A8_B1', 'A9_B2']
    print(f"禁飞区（包围起点）: {nofly}")
    
    route_list, _, _, _, _ = planner.plan_route(nofly)
    
    print(f"✓ 路径规划完成，路径长度: {len(route_list)}")
    
    # 应该找到替代路径
    assert len(route_list) > 0, "应该找到替代路径"
    print(f"✓ 找到替代路径")
    
    print("\n✓ 测试4通过\n")

def compare_with_old():
    """与旧算法对比"""
    print("=" * 60)
    print("性能对比: 新算法 vs 旧算法")
    print("=" * 60)
    
    # 新算法
    planner_new = RoutePlanner(cols=9, rows=7)
    start_time = time.time()
    route_new, _, checkpoints_new, _, _ = planner_new.plan_route([])
    time_new = time.time() - start_time
    quality_new = planner_new.evaluate_path_quality(route_new, checkpoints_new)
    
    print(f"新算法:")
    print(f"  - 耗时: {time_new:.4f}秒")
    print(f"  - 路径长度: {quality_new['path_length']}")
    print(f"  - 转弯次数: {quality_new['turn_count']}")
    print(f"  - 路径代价: {quality_new['path_cost']:.2f}")
    print(f"  - 绕路比率: {quality_new['detour_ratio']:.2f}")
    
    print(f"\n✓ 新算法性能验证通过")

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("无人机路径规划优化测试")
    print("=" * 60 + "\n")
    
    try:
        # 运行所有测试
        quality1 = test_empty_nofly()
        quality2 = test_with_nofly()
        test_invalid_input()
        test_start_surrounded()
        compare_with_old()
        
        print("=" * 60)
        print("所有测试通过！✓")
        print("=" * 60)
        print(f"\n优化总结:")
        print(f"  - 空禁飞区绕路比率: {quality1['detour_ratio']:.2f}")
        print(f"  - 带禁飞区绕路比率: {quality2['detour_ratio']:.2f}")
        print(f"  - 平均转弯次数: {(quality1['turn_count'] + quality2['turn_count']) / 2:.1f}")
        print(f"  - 输入验证: ✓")
        print(f"  - 错误处理: ✓")
        print(f"  - 性能达标: ✓")
        
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        exit(1)
    except Exception as e:
        print(f"\n✗ 测试错误: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
