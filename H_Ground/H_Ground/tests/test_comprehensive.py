#!/usr/bin/env python3
"""综合测试路径规划优化"""

from algorithm import RoutePlanner
import time

def test_scenario(name, nofly_zones, expected_max_detour=1.2):
    """测试单个场景"""
    print(f"\n{'='*60}")
    print(f"场景: {name}")
    print(f"{'='*60}")
    
    planner = RoutePlanner(cols=9, rows=7)
    
    if nofly_zones:
        print(f"禁飞区数量: {len(nofly_zones)}")
    else:
        print("禁飞区: 无")
    
    start_time = time.time()
    route_list, return_idx, checkpoints, merged_route, merged_checkpoints = planner.plan_route(nofly_zones)
    elapsed = time.time() - start_time
    
    quality = planner.evaluate_path_quality(route_list, checkpoints)
    
    print(f"\n结果:")
    print(f"  ✓ 耗时: {elapsed:.4f}秒")
    print(f"  ✓ 原始路径: {len(route_list)} 航点")
    print(f"  ✓ 优化路径: {len(merged_route)} 航点")
    print(f"  ✓ 检查点: {len(checkpoints)} -> {len(merged_checkpoints)}")
    
    print(f"\n质量指标:")
    print(f"  - 路径长度: {quality['path_length']}")
    print(f"  - 覆盖单元: {quality['unique_cells']}")
    print(f"  - 重复访问: {quality['repeat_visits']}")
    print(f"  - 转弯次数: {quality['turn_count']}")
    print(f"  - 绕路比率: {quality['detour_ratio']:.3f}")
    print(f"  - 路径代价: {quality['path_cost']:.2f}")
    
    # 验证
    print(f"\n验证:")
    
    # 覆盖率
    expected_coverage = 9 * 7 - len(nofly_zones) if nofly_zones else 9 * 7
    coverage_ok = quality['unique_cells'] == expected_coverage
    print(f"  {'✓' if coverage_ok else '✗'} 覆盖率: {quality['unique_cells']}/{expected_coverage}")
    
    # 禁飞区避障
    nofly_violated = any(cell in nofly_zones for cell in route_list) if nofly_zones else False
    print(f"  {'✓' if not nofly_violated else '✗'} 禁飞区避障")
    
    # 绕路比率
    detour_ok = quality['detour_ratio'] <= expected_max_detour
    print(f"  {'✓' if detour_ok else '✗'} 绕路比率 <= {expected_max_detour}")
    
    # 性能
    perf_ok = elapsed < 1.0
    print(f"  {'✓' if perf_ok else '✗'} 性能 < 1秒")
    
    all_ok = coverage_ok and not nofly_violated and detour_ok and perf_ok
    print(f"\n{'✓ 通过' if all_ok else '✗ 失败'}")
    
    return quality, all_ok

def main():
    print("\n" + "="*60)
    print("无人机路径规划优化 - 综合测试")
    print("="*60)
    
    results = []
    all_passed = True
    
    # 场景1: 空禁飞区
    q1, ok1 = test_scenario("空禁飞区（理想情况）", [])
    results.append(('空禁飞区', q1))
    all_passed = all_passed and ok1
    
    # 场景2: 少量分散禁飞区
    nofly2 = ['A3_B3', 'A6_B4', 'A7_B2']
    q2, ok2 = test_scenario("少量分散禁飞区", nofly2)
    results.append(('少量分散', q2))
    all_passed = all_passed and ok2
    
    # 场景3: 中等密度禁飞区
    nofly3 = [f'A{x}_B{y}' for x in [3, 6] for y in range(2, 6)]
    q3, ok3 = test_scenario("中等密度禁飞区", nofly3)
    results.append(('中等密度', q3))
    all_passed = all_passed and ok3
    
    # 场景4: 墙状禁飞区（需要绕行）
    nofly4 = [f'A5_B{y}' for y in range(2, 7)]
    q4, ok4 = test_scenario("墙状禁飞区（允许绕路比率>1.2）", nofly4, expected_max_detour=1.3)
    results.append(('墙状', q4))
    all_passed = all_passed and ok4
    
    # 场景5: 角落禁飞区
    nofly5 = [f'A{x}_B1' for x in range(1, 4)] + [f'A1_B{y}' for y in range(2, 4)]
    q5, ok5 = test_scenario("角落禁飞区", nofly5)
    results.append(('角落', q5))
    all_passed = all_passed and ok5
    
    # 总结
    print(f"\n{'='*60}")
    print("测试总结")
    print(f"{'='*60}")
    
    print(f"\n场景对比:")
    print(f"{'场景':<15} {'绕路比率':<12} {'转弯次数':<12} {'路径代价':<12}")
    print("-" * 60)
    for name, quality in results:
        print(f"{name:<15} {quality['detour_ratio']:<12.3f} {quality['turn_count']:<12} {quality['path_cost']:<12.2f}")
    
    avg_detour = sum(q['detour_ratio'] for _, q in results) / len(results)
    avg_turns = sum(q['turn_count'] for _, q in results) / len(results)
    
    print(f"\n平均指标:")
    print(f"  - 平均绕路比率: {avg_detour:.3f}")
    print(f"  - 平均转弯次数: {avg_turns:.1f}")
    
    print(f"\n{'='*60}")
    if all_passed:
        print("✓ 所有测试通过！")
    else:
        print("✗ 部分测试失败")
    print(f"{'='*60}\n")
    
    return 0 if all_passed else 1

if __name__ == '__main__':
    exit(main())
