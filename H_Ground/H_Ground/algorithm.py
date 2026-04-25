class RoutePlanner:
    def __init__(self, cols=9, rows=7):
        self.cols = cols
        self.rows = rows
        self.columns = [f'A{i}' for i in range(1, 10)]
        self.row_names = [f'B{i}' for i in range(1, 8)]

    def bfs_path(self, start, goal, nofly_zones):
        """标准 BFS 寻路：绕开禁飞区，允许穿过已走过的路"""
        queue = [(start, [start])]
        visited = set([start])
        while queue:
            curr, path = queue.pop(0)
            if curr == goal:
                return path[1:] # 返回不含起点的路径
            
            cx, cy = curr
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < 9 and 0 <= ny < 7:
                    grid_id = f"{self.columns[nx]}_{self.row_names[ny]}"
                    if grid_id not in nofly_zones and (nx, ny) not in visited:
                        visited.add((nx, ny))
                        queue.append(((nx, ny), path + [(nx, ny)]))
        return []

    def plan_route(self, nofly_zones):
        """优化版弓字型：长边优先 (横向扫掠) + BFS 绕路"""
        targets = []
        
        # --- 核心修改：改为优先走横向长边 (A1-A9)，以减少掉头次数 ---
        for y in range(7): # 从底(B1)向上(B7)逐行扫描
            
            # 偶数行(B1, B3...)从右向左扫(A9->A1)，奇数行(B2, B4...)从左向右扫(A1->A9)
            x_range = range(8, -1, -1) if y % 2 == 0 else range(9)
            
            for x in x_range:
                grid_id = f"{self.columns[x]}_{self.row_names[y]}"
                if grid_id not in nofly_zones:
                    targets.append((x, y))
        
        # 2. 依次连线
        start_coord = (8, 0) # A9_B1
        full_path = [start_coord]
        curr = start_coord
        
        for target in targets:
            if target == curr: continue
            path_chunk = self.bfs_path(curr, target, nofly_zones)
            full_path.extend(path_chunk)
            curr = target
            
        # 3. 扫完返航
        if curr != start_coord:
            return_chunk = self.bfs_path(curr, start_coord, nofly_zones)
            full_path.extend(return_chunk)

        return [f"{self.columns[x]}_{self.row_names[y]}" for x, y in full_path]
