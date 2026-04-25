#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""简单测试"""

from algorithm import RoutePlanner

def main():
    print("="*60)
    print("简单测试")
    print("="*60)
    
    planner = RoutePlanner(cols=9, rows=7)
    
    # 测试1: 空禁飞区
    print("\n测试1: 空禁飞区")
    result = planner.plan_route([])
    print(f"返回值类型: {type(result)}")
    print(f"返回值长度: {len(result)}")
    
    if len(result) == 5:
        route, return_idx, checkpoints, merged, merged_cp = result
        quality = planner.evaluate_path_quality(route, checkpoints)
        
        print(f"路径长度: {quality['path_length']}")
        print(f"覆盖单元: {quality['unique_cells']}")
        print(f"转弯次数: {quality['turn_count']}")
        print(f"绕路比率: {quality['detour_ratio']:.3f}")
        print("测试1通过")
    else:
        print(f"错误: 返回值数量不正确")
    
    # 测试2: 带禁飞区
    print("\n测试2: 带禁飞区")
    nofly = ['A5_B3', 'A6_B3', 'A7_B3']
    result = planner.plan_route(nofly)
    
    if len(result) == 5:
        route, return_idx, checkpoints, merged, merged_cp = result
        quality = planner.evaluate_path_quality(route, checkpoints)
        
        print(f"路径长度: {quality['path_length']}")
        print(f"覆盖单元: {quality['unique_cells']}")
        print(f"转弯次数: {quality['turn_count']}")
        print(f"绕路比率: {quality['detour_ratio']:.3f}")
        
        # 验证禁飞区避障
        violated = any(cell in nofly for cell in route)
        if not violated:
            print("禁飞区避障: 通过")
        else:
            print("禁飞区避障: 失败")
        
        print("测试2通过")
    else:
        print(f"错误: 返回值数量不正确")
    
    print("\n="*60)
    print("所有测试完成")
    print("="*60)

if __name__ == '__main__':
    main()
