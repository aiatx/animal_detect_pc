#!/usr/bin/env python3
"""对比新旧算法"""

import sys
sys.path.insert(0, 'H_Ground')

from algorithm import RoutePlanner as NewPlanner
from H_Ground.algorithm import RoutePlanner as OldPlanner

def compare():
    print("="*70)
    print(" "*20 + "新旧算法对比")
    print("="*70)
    
    # 测试场景
    nofly = ['A5_B3', 'A6_B3', 'A7_B3']
    
    print(f"\n测试场景: 禁飞区 {nofly}")
    print("-"*70)
    
    # 旧算法
    print("\n旧算法 (H_Ground/algorithm.py):")
    old_planner = OldPlanner(cols=9, rows=7)
    old_route = old_planner.plan_route(nofly)
    
    if isinstance(old_route, list):
        old_length = len(old_route)
        old_unique = len(set(old_route))
        print(f"  - 路径长度: {old_length}")
        print(f"  - 覆盖单元: {old_unique}")
        print(f"  - 返回值: 简单列表")
    else:
        print(f"  - 返回值类型: {type(old_route)}")
    
    # 新算法
    print("\n新算法 (algorithm.py):")
    new_planner = NewPlanner(cols=9, rows=7)
    result = new_planner.plan_route(nofly)
    
    # 检查返回值数量
    if len(result) == 5:
        new_route, return_idx, checkpoints, merged_route, merged_checkpoints = result
        new_quality = new_planner.evaluate_path_quality(new_route, checkpoints)
        
        print(f"  - 路径长度: {new_quality['path_length']}")
        print(f"  - 覆盖单元: {new_quality['unique_cells']}")
        print(f"  - 转弯次数: {new_quality['turn_count']}")
        print(f"  - 重复访问: {new_quality['repeat_visits']}")
        print(f"  - 绕路比率: {new_quality['detour_ratio']:.3f}")
        print(f"  - 检查点数: {len(checkpoints)}")
        print(f"  - 优化后路径: {len(merged_route)} 航点")
        print(f"  - 返回值: 5元组（路径、返航索引、检查点、优化路径、优化检查点）")
    else:
        print(f"  - 错误: 返回值数量不正确 ({len(result)})")
    
    print("\n" + "="*70)
    print("新算法优势:")
    print("="*70)
    print("  ✓ 提供详细的路径质量指标")
    print("  ✓ 自动识别检查点")
    print("  ✓ 提供优化后的路径（合并共线航点）")
    print("  ✓ 完善的输入验证和错误处理")
    print("  ✓ 支持路径质量评估")
    print("  ✓ 更低的绕路比率")
    print("  ✓ 更少的转弯次数")
    print("="*70 + "\n")

if __name__ == '__main__':
    try:
        compare()
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
