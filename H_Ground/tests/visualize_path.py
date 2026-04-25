#!/usr/bin/env python3
"""可视化路径规划结果"""

from algorithm import RoutePlanner

def visualize_grid(route_list, nofly_zones, checkpoints=None):
    """可视化网格和路径"""
    # 创建9x7网格
    grid = [['.' for _ in range(9)] for _ in range(7)]
    
    # 标记禁飞区
    for nofly in nofly_zones:
        parts = nofly.split('_')
        x = int(parts[0][1:]) - 1
        y = int(parts[1][1:]) - 1
        grid[y][x] = 'X'
    
    # 标记路径（用数字表示访问顺序）
    checkpoint_set = set(checkpoints) if checkpoints else set()
    for i, cell in enumerate(route_list):
        parts = cell.split('_')
        x = int(parts[0][1:]) - 1
        y = int(parts[1][1:]) - 1
        
        if grid[y][x] == 'X':
            continue
        
        if i == 0:
            grid[y][x] = 'S'  # 起点
        elif i == len(route_list) - 1:
            grid[y][x] = 'E'  # 终点
        elif i in checkpoint_set:
            grid[y][x] = 'C'  # 检查点
        else:
            grid[y][x] = 'o'  # 普通航点
    
    # 打印网格
    print("\n图例: S=起点 E=终点 C=检查点 o=航点 X=禁飞区 .=未访问")
    print("\n    ", end="")
    for i in range(1, 10):
        print(f"A{i} ", end="")
    print()
    
    for y in range(7):
        print(f"B{y+1}  ", end="")
        for x in range(9):
            print(f" {grid[y][x]} ", end="")
        print()

def main():
    print("="*60)
    print("路径规划可视化")
    print("="*60)
    
    planner = RoutePlanner(cols=9, rows=7)
    
    # 测试场景：角落禁飞区
    nofly = [f'A{x}_B1' for x in range(1, 4)] + [f'A1_B{y}' for y in range(2, 4)]
    
    print(f"\n禁飞区: {nofly}")
    
    route_list, return_idx, checkpoints, merged_route, merged_checkpoints = planner.plan_route(nofly)
    quality = planner.evaluate_path_quality(route_list, checkpoints)
    
    print(f"\n路径统计:")
    print(f"  - 总航点: {len(route_list)}")
    print(f"  - 检查点: {len(checkpoints)}")
    print(f"  - 路径长度: {quality['path_length']}")
    print(f"  - 转弯次数: {quality['turn_count']}")
    print(f"  - 绕路比率: {quality['detour_ratio']:.3f}")
    
    print(f"\n原始路径:")
    visualize_grid(route_list, nofly, checkpoints)
    
    print(f"\n优化后路径 (合并共线航点):")
    visualize_grid(merged_route, nofly, merged_checkpoints)
    
    print(f"\n路径序列 (前20个航点):")
    for i, cell in enumerate(route_list[:20]):
        marker = " [检查点]" if i in checkpoints else ""
        print(f"  {i:2d}. {cell}{marker}")
    if len(route_list) > 20:
        print(f"  ... (共{len(route_list)}个航点)")

if __name__ == '__main__':
    main()
