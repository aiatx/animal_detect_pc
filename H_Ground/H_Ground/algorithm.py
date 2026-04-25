import heapq
import math
from collections import deque


def compress_route(raw_route, detected_cells):
    def _to_xy(cell):
        a, b = cell.split('_', 1)
        return int(a[1:]), int(b[1:])

    if len(raw_route) < 3:
        return list(raw_route)

    compressed = [raw_route[0]]
    checked = set(detected_cells)
    checked.add(raw_route[0])
    for i in range(1, len(raw_route) - 1):
        prev_cell, curr_cell, next_cell = raw_route[i - 1], raw_route[i], raw_route[i + 1]
        if curr_cell in checked:
            x1, y1 = _to_xy(prev_cell)
            x2, y2 = _to_xy(curr_cell)
            x3, y3 = _to_xy(next_cell)
            dx1, dy1 = x2 - x1, y2 - y1
            dx2, dy2 = x3 - x2, y3 - y2
            if dx1 * dy2 - dy1 * dx2 == 0 and dx1 * dx2 + dy1 * dy2 > 0:
                continue
        compressed.append(curr_cell)
        checked.add(curr_cell)

    compressed.append(raw_route[-1])
    return compressed


class RoutePlanner:
    def __init__(self, cols=9, rows=7):
        self.cols = cols
        self.rows = rows
        self.columns = [f'A{i}' for i in range(1, 10)]
        self.row_names = [f'B{i}' for i in range(1, 8)]
        self.directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    def _grid_id(self, x, y):
        return f"{self.columns[x]}_{self.row_names[y]}"

    def _neighbors(self, node, nofly_zones):
        cx, cy = node
        for dx, dy in self.directions:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < self.cols and 0 <= ny < self.rows:
                if self._grid_id(nx, ny) not in nofly_zones:
                    yield (nx, ny), (dx, dy)

    def _heuristic(self, node, goal):
        return abs(node[0] - goal[0]) + abs(node[1] - goal[1])

    def _nearest_free(self, start, nofly_zones):
        sx, sy = start
        best = None
        best_dist = None
        for y in range(self.rows):
            for x in range(self.cols):
                if self._grid_id(x, y) in nofly_zones:
                    continue
                dist = abs(x - sx) + abs(y - sy)
                if best is None or dist < best_dist:
                    best = (x, y)
                    best_dist = dist
        return best

    def _sweep_targets(self, orientation, corner, reachable, nofly_zones):
        start_x, start_y = corner
        targets = []

        if orientation == "h":
            y_range = range(self.rows) if start_y == 0 else range(self.rows - 1, -1, -1)
            left_to_right = True if start_x == 0 else False
            for y in y_range:
                x_range = range(self.cols) if left_to_right else range(self.cols - 1, -1, -1)
                for x in x_range:
                    if (x, y) in reachable and self._grid_id(x, y) not in nofly_zones:
                        targets.append((x, y))
                left_to_right = not left_to_right
        else:
            x_range = range(self.cols) if start_x == 0 else range(self.cols - 1, -1, -1)
            bottom_to_top = True if start_y == 0 else False
            for x in x_range:
                y_range = range(self.rows) if bottom_to_top else range(self.rows - 1, -1, -1)
                for y in y_range:
                    if (x, y) in reachable and self._grid_id(x, y) not in nofly_zones:
                        targets.append((x, y))
                bottom_to_top = not bottom_to_top

        return targets

    def _rotate_targets(self, targets, start_coord):
        if not targets:
            return []
        if start_coord in targets:
            idx = targets.index(start_coord)
            return targets[idx + 1:] + targets[:idx]
        return targets

    def _count_unvisited_neighbors(self, cell, unvisited, nofly_zones):
        count = 0
        for neighbor, _ in self._neighbors(cell, nofly_zones):
            if neighbor in unvisited:
                count += 1
        return count

    def _choose_next_unvisited_neighbor(self, curr, last_dir, unvisited, nofly_zones):
        candidates = []
        for neighbor, step_dir in self._neighbors(curr, nofly_zones):
            if neighbor not in unvisited:
                continue
            # 优先级1: 保持方向一致（减少转弯）
            same_dir = 0 if last_dir and step_dir == last_dir else 1
            # 优先级2: 优先访问"死胡同"（未访问邻居少的节点）
            degree = self._count_unvisited_neighbors(neighbor, unvisited, nofly_zones)
            # 优先级3: 曼哈顿距离作为tie-breaker
            dist_to_start = abs(neighbor[0] - (self.cols - 1)) + abs(neighbor[1])
            candidates.append((same_dir, -degree, dist_to_start, neighbor, step_dir))
        if not candidates:
            return None, None
        candidates.sort()
        _, _, _, best, best_dir = candidates[0]
        return best, best_dir

    def _nearest_unvisited(self, start, unvisited, nofly_zones):
        if not unvisited:
            return None
        queue = deque([start])
        visited = {start}
        while queue:
            curr = queue.popleft()
            if curr in unvisited:
                return curr
            for neighbor, _ in self._neighbors(curr, nofly_zones):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return None

    def _path_cost(self, path):
        if len(path) < 2:
            return 0
        length = len(path) - 1
        repeats = len(path) - len(set(path))
        turns = 0
        last_dir = None
        for i in range(1, len(path)):
            dx = path[i][0] - path[i - 1][0]
            dy = path[i][1] - path[i - 1][1]
            step_dir = (0 if dx == 0 else (1 if dx > 0 else -1),
                        0 if dy == 0 else (1 if dy > 0 else -1))
            if last_dir and step_dir != last_dir:
                turns += 1
            last_dir = step_dir
        return length + repeats * 1.2 + turns * 0.6

    def evaluate_path_quality(self, route_list, checkpoint_indices=None):
        """评估路径质量
        
        参数:
            route_list: 路径列表 ['A9_B1', 'A8_B1', ...]
            checkpoint_indices: 检查点索引列表（可选）
        
        返回:
            dict: 包含以下指标的字典
                - path_length: 路径长度（步数）
                - unique_cells: 覆盖的唯一单元数
                - repeat_visits: 重复访问次数
                - turn_count: 转弯次数
                - checkpoint_count: 检查点数量（如果提供）
                - path_cost: 综合路径代价
                - detour_ratio: 绕路比率（实际长度/理论最短长度）
        """
        if not route_list:
            return {
                'path_length': 0,
                'unique_cells': 0,
                'repeat_visits': 0,
                'turn_count': 0,
                'checkpoint_count': 0,
                'path_cost': 0,
                'detour_ratio': 0
            }
        
        # 转换为坐标
        path = [self._convert_gridid_to_coord(cell) for cell in route_list]
        
        # 基本指标
        path_length = len(path) - 1
        unique_cells = len(set(route_list))
        repeat_visits = len(route_list) - unique_cells
        
        # 计算转弯次数
        turns = 0
        last_dir = None
        for i in range(1, len(path)):
            dx = path[i][0] - path[i - 1][0]
            dy = path[i][1] - path[i - 1][1]
            step_dir = (0 if dx == 0 else (1 if dx > 0 else -1),
                        0 if dy == 0 else (1 if dy > 0 else -1))
            if last_dir and step_dir != last_dir:
                turns += 1
            last_dir = step_dir
        
        # 检查点数量
        checkpoint_count = len(checkpoint_indices) if checkpoint_indices else 0
        
        # 综合代价
        path_cost = path_length + repeat_visits * 1.2 + turns * 0.6
        
        # 绕路比率（理论最短路径 = 覆盖所有唯一单元的最小步数）
        # 对于全覆盖，理论最短路径约等于唯一单元数
        theoretical_min = unique_cells if unique_cells > 0 else 1
        detour_ratio = path_length / theoretical_min if theoretical_min > 0 else 0
        
        return {
            'path_length': path_length,
            'unique_cells': unique_cells,
            'repeat_visits': repeat_visits,
            'turn_count': turns,
            'checkpoint_count': checkpoint_count,
            'path_cost': path_cost,
            'detour_ratio': detour_ratio
        }

    def _build_full_path(self, start_coord, targets, nofly_zones):
        full_path = [start_coord]
        curr = start_coord
        visited_cells = {start_coord}
        last_dir = None

        for target in targets:
            if target == curr:
                continue
            path_chunk, last_dir = self.a_star_path(
                curr,
                target,
                nofly_zones,
                visited_cells=visited_cells,
                last_dir=last_dir,
                forbidden_cells={start_coord},
                revisit_penalty=0.8,
                turn_penalty=0.2
            )
            if not path_chunk:
                continue
            full_path.extend(path_chunk)
            for cell in path_chunk:
                visited_cells.add(cell)
            curr = target

        return_start_index = None
        if curr != start_coord:
            return_start_index = len(full_path) - 1
            # 返航时使用A*规划路径，避开禁飞区
            return_path, _ = self.a_star_path(
                curr,
                start_coord,
                nofly_zones,
                visited_cells=set(),
                last_dir=None,
                forbidden_cells=None,
                revisit_penalty=0.0,
                turn_penalty=0.2
            )
            if return_path:
                full_path.extend(return_path)
            else:
                full_path.append(start_coord)

        return full_path, return_start_index

    def _reachable_cells(self, start, nofly_zones):
        if start is None:
            return set()
        queue = [start]
        visited = {start}
        while queue:
            curr = queue.pop(0)
            for neighbor, _ in self._neighbors(curr, nofly_zones):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return visited

    def a_star_path(self, start, goal, nofly_zones, visited_cells=None, last_dir=None,
                    forbidden_cells=None, revisit_penalty=0.8, turn_penalty=0.2):
        """带转弯代价与复用惩罚的 A*：更少折返、更少重复"""
        if start == goal:
            return [], last_dir

        visited_cells = visited_cells or set()
        start_state = (start, last_dir)
        open_set = [(self._heuristic(start, goal), 0, start, last_dir)]
        came_from = {}
        g_score = {start_state: 0}

        while open_set:
            _, current_g, current, current_dir = heapq.heappop(open_set)
            state = (current, current_dir)
            if current_g > g_score.get(state, float('inf')):
                continue
            if current == goal:
                path = self._reconstruct_path(came_from, (current, current_dir), start_state)
                if len(path) >= 2:
                    last_dx = path[-1][0] - path[-2][0]
                    last_dy = path[-1][1] - path[-2][1]
                    last_dir = (int(math.copysign(1, last_dx)) if last_dx != 0 else 0,
                                int(math.copysign(1, last_dy)) if last_dy != 0 else 0)
                return path[1:], last_dir

            for neighbor, step_dir in self._neighbors(current, nofly_zones):
                if forbidden_cells and neighbor in forbidden_cells and neighbor != goal:
                    continue
                turn_cost = 0 if current_dir is None or step_dir == current_dir else turn_penalty
                revisit_cost = revisit_penalty if neighbor in visited_cells else 0
                tentative_g = current_g + 1 + turn_cost + revisit_cost
                neighbor_state = (neighbor, step_dir)
                if tentative_g < g_score.get(neighbor_state, float('inf')):
                    came_from[neighbor_state] = (current, current_dir)
                    g_score[neighbor_state] = tentative_g
                    f_score = tentative_g + self._heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f_score, tentative_g, neighbor, step_dir))

        return [], last_dir

    def _reconstruct_path(self, came_from, goal_state, start_state):
        path = []
        state = goal_state
        while state != start_state:
            pos, _ = state
            path.append(pos)
            state = came_from[state]
        path.append(start_state[0])
        path.reverse()
        return path

    def _extract_checkpoints(self, full_path, start_coord):
        """从完整路径中提取检查点（需要停顿的点）
        检查点标准：起飞点、方向改变点、未访问过的点
        已访问过的点可以作为路径点连续通过
        """
        if len(full_path) < 2:
            return list(range(len(full_path)))
        
        checkpoints = [0]  # 起飞点总是检查点
        visited_inspection = {start_coord}  # 已经检查过的点
        
        for i in range(1, len(full_path)):
            curr = full_path[i]
            prev = full_path[i - 1]
            
            # 计算方向
            dx = curr[0] - prev[0]
            dy = curr[1] - prev[1]
            curr_dir = (dx, dy)
            
            # 判断是否需要作为检查点
            is_checkpoint = False
            
            # 规则1: 方向改变时必须停顿
            if i > 1:
                prev_prev = full_path[i - 2]
                dx_prev = prev[0] - prev_prev[0]
                dy_prev = prev[1] - prev_prev[1]
                prev_dir = (dx_prev, dy_prev)
                if curr_dir != prev_dir:
                    is_checkpoint = True
            
            # 规则2: 未访问过的点必须作为检查点
            if curr not in visited_inspection:
                is_checkpoint = True
                visited_inspection.add(curr)
            
            if is_checkpoint:
                checkpoints.append(i)
        
        return checkpoints

    def _merge_collinear_waypoints(self, full_path, checkpoint_indices):
        """合并共线的连续非检查点，实现已检区域连续跨越
        
        如果连续多个非检查点（可连续跨越的点）处于同一直线上，
        则合并为只保留起点和终点，中间不停顿。
        
        返回: (合并后的路径, 合并后的检查点索引)
        """
        if len(full_path) < 3:
            return full_path, checkpoint_indices
        
        checkpoint_set = set(checkpoint_indices)
        merged_path = []
        merged_checkpoints = []
        
        i = 0
        while i < len(full_path):
            current_in_merged_idx = len(merged_path)
            merged_path.append(full_path[i])
            
            # 如果是检查点，记录索引
            if i in checkpoint_set:
                merged_checkpoints.append(current_in_merged_idx)
                i += 1
                continue
            
            # 非检查点：尝试向前合并连续共线的非检查点
            j = i + 1
            
            # 找到下一个检查点或路径末尾
            while j < len(full_path) and j not in checkpoint_set:
                j += 1
            
            # 在 i 到 j-1 之间，检查是否共线并可以合并
            if j - i > 1:
                # 有多个连续非检查点，检查是否共线
                segment = full_path[i:j]
                
                # 检查共线性：所有相邻向量方向是否相同
                directions = []
                for k in range(len(segment) - 1):
                    dx = segment[k + 1][0] - segment[k][0]
                    dy = segment[k + 1][1] - segment[k][1]
                    directions.append((dx, dy))
                
                # 如果所有方向都相同（共线），直接跳到段末
                all_same_direction = len(set(directions)) == 1
                
                if all_same_direction:
                    # 共线：跳过中间的点，直接到段末
                    i = j - 1
                else:
                    # 不共线：需要保留转向点
                    # 向前查找所有需要保留的转向点
                    last_dir = None
                    for k in range(i + 1, j):
                        dx = full_path[k][0] - full_path[k - 1][0]
                        dy = full_path[k][1] - full_path[k - 1][1]
                        curr_dir = (dx, dy)
                        
                        if last_dir is not None and curr_dir != last_dir:
                            # 检测到转向，保留前一个点
                            merged_path.append(full_path[k - 1])
                        
                        last_dir = curr_dir
                    
                    i = j - 1
            else:
                i += 1
        
        return merged_path, merged_checkpoints

    def _convert_gridid_to_coord(self, grid_id):
        """将格子ID（如 'A5_B3'）转换为坐标 (x, y)"""
        parts = grid_id.split('_')
        x = int(parts[0][1:]) - 1  # A1-A9 -> 0-8
        y = int(parts[1][1:]) - 1  # B1-B7 -> 0-6
        return (x, y)

    def _validate_nofly_zones(self, nofly_zones):
        """验证禁飞区输入的有效性
        
        检查项:
            1. 格式检查：每个禁飞区ID应符合 'A[1-9]_B[1-7]' 格式
            2. 边界检查：列号应在1-cols范围内，行号应在1-rows范围内
            3. 重复检查：移除重复的禁飞区ID
        
        返回:
            set: 验证后的有效禁飞区集合
        """
        if not nofly_zones:
            return set()
        
        validated = set()
        for zone in nofly_zones:
            if not isinstance(zone, str):
                continue
            
            # 格式检查
            if '_' not in zone:
                continue
            
            parts = zone.split('_')
            if len(parts) != 2:
                continue
            
            try:
                # 提取列号和行号
                if not parts[0].startswith('A') or not parts[1].startswith('B'):
                    continue
                
                col_num = int(parts[0][1:])
                row_num = int(parts[1][1:])
                
                # 边界检查
                if 1 <= col_num <= self.cols and 1 <= row_num <= self.rows:
                    validated.add(zone)
            except (ValueError, IndexError):
                # 格式错误，跳过
                continue
        
        return validated

    def merge_route_by_cell_state(self, route_list, detected_cells):
        """基于网格状态的航点合并算法
        
        逻辑：
        1. 方向一致性检测：连续三点共线
        2. 状态检测：中间点是已检查状态（detected_cells中存在）
        3. 执行合并：剔除中间点，直接飞越
        4. 转弯保留：如需转弯则保留中间点作为转弯支撑
        
        参数：
            route_list: 原始路由列表 ['A9_B1', 'A8_B1', ...]
            detected_cells: 已检测格子集合 {'A5_B3', 'A5_B4', ...}
        
        返回：
            合并后的路由列表
        """
        if len(route_list) < 3:
            return route_list
        
        # 转换为坐标系统便于计算
        coords = [self._convert_gridid_to_coord(gid) for gid in route_list]
        
        merged_indices = []  # 保留下来的点的索引
        i = 0
        
        while i < len(coords):
            merged_indices.append(i)
            
            if i + 2 < len(coords):
                # 检查是否可以合并从 i+1 开始的点
                j = i + 1
                
                while j + 1 < len(coords):
                    p_prev = coords[i]
                    p_curr = coords[j]
                    p_next = coords[j + 1]
                    
                    # 检查共线性：使用向量叉积
                    # 向量 p_prev -> p_curr
                    v1 = (p_curr[0] - p_prev[0], p_curr[1] - p_prev[1])
                    # 向量 p_prev -> p_next
                    v2 = (p_next[0] - p_prev[0], p_next[1] - p_prev[1])
                    
                    # 叉积为0表示共线
                    cross_product = v1[0] * v2[1] - v1[1] * v2[0]
                    is_collinear = (cross_product == 0)
                    
                    # 检查状态：p_curr 是否已检查
                    is_detected = route_list[j] in detected_cells
                    
                    # 可以合并的条件：共线 且 已检查
                    if is_collinear and is_detected:
                        # 继续检查下一个点是否也能合并
                        j += 1
                    else:
                        # 不能继续合并
                        break
                
                # 如果 j > i+1，说明跳过了一些点
                if j > i + 1:
                    # 下一个需要检查的点是 j
                    i = j - 1
            
            i += 1
        
        # 根据保留的索引重构路由列表
        merged_route = [route_list[idx] for idx in merged_indices]
        
        return merged_route

    def plan_route(self, nofly_zones):
        """启发式全覆盖：优先走未访问邻居，必要时用 A* 跳转，减少重复"""
        # 输入验证：转换为集合并验证格式
        nofly_zones = self._validate_nofly_zones(nofly_zones)

        start_coord = (self.cols - 1, 0)  # A9_B1 固定起飞区
        
        # 检查起点是否可达
        if self._grid_id(start_coord[0], start_coord[1]) in nofly_zones:
            # 起点在禁飞区，寻找最近的可达点
            start_coord = self._nearest_free(start_coord, nofly_zones)
            if start_coord is None:
                return [], None, [], [], []  # 无可达区域
        
        reachable = self._reachable_cells(start_coord, nofly_zones)
        if not reachable:
            return [], None, [], [], []

        unvisited = set(reachable)
        unvisited.discard(start_coord)
        visited = {start_coord}

        full_path = [start_coord]
        curr = start_coord
        last_dir = None

        while unvisited:
            next_cell, next_dir = self._choose_next_unvisited_neighbor(curr, last_dir, unvisited, nofly_zones)
            if next_cell is not None:
                full_path.append(next_cell)
                curr = next_cell
                last_dir = next_dir
                visited.add(curr)
                unvisited.discard(curr)
                continue

            target = self._nearest_unvisited(curr, unvisited, nofly_zones)
            if target is None:
                break

            path_chunk, last_dir = self.a_star_path(
                curr,
                target,
                nofly_zones,
                visited_cells=visited,
                last_dir=last_dir,
                forbidden_cells={start_coord},
                revisit_penalty=3.0,  # 增加重复访问惩罚
                turn_penalty=0.3      # 增加转弯惩罚
            )
            if not path_chunk:
                # 无法到达目标，从未访问集合中移除
                unvisited.discard(target)
                continue

            for cell in path_chunk:
                full_path.append(cell)
                curr = cell
                visited.add(curr)
                unvisited.discard(curr)

        return_start_index = None
        if curr != start_coord:
            return_start_index = len(full_path) - 1
            # 返航时使用A*规划路径，避开禁飞区
            return_path, _ = self.a_star_path(
                curr,
                start_coord,
                nofly_zones,
                visited_cells=set(),
                last_dir=None,
                forbidden_cells=None,
                revisit_penalty=0.0,
                turn_penalty=0.2
            )
            if return_path:
                full_path.extend(return_path)
            else:
                full_path.append(start_coord)

        # 核心注意：下面这两行必须和上面的 if 平齐！绝对不能缩进到 if 里面！
        route_list = [f"{self.columns[x]}_{self.row_names[y]}" for x, y in full_path]
        
        # 提取检查点（需要停顿的航点）
        checkpoint_indices = self._extract_checkpoints(full_path, start_coord)
        
        # 合并共线的连续非检查点，实现已检区域连续跨越
        merged_path, merged_checkpoint_indices = self._merge_collinear_waypoints(full_path, checkpoint_indices)
        merged_route_list = [f"{self.columns[x]}_{self.row_names[y]}" for x, y in merged_path]
        
        # 返回: 原始路径列表, 返航起点, 检查点索引, 合并后的路径列表, 合并后的检查点索引
        return route_list, return_start_index, checkpoint_indices, merged_route_list, merged_checkpoint_indices
