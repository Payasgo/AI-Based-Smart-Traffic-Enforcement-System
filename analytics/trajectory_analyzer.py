"""Per-track trajectory history and lane-transition observations."""
from collections import defaultdict, deque
from dataclasses import dataclass

@dataclass(frozen=True)
class TrajectoryPoint:
    timestamp: object
    x: float
    y: float
    lane_id: str | None = None

class TrajectoryAnalyzer:
    def __init__(self, max_points=60):
        if max_points < 2: raise ValueError("max_points must be >= 2")
        self._history = defaultdict(lambda: deque(maxlen=max_points))

    def update(self, track_id, timestamp, centroid, lane_id=None):
        x, y = centroid
        point = TrajectoryPoint(timestamp, float(x), float(y), lane_id)
        self._history[track_id].append(point)
        return point

    def history(self, track_id): return tuple(self._history.get(track_id, ()))

    def lane_transitions(self, track_id, window_seconds=8.0):
        points = self.history(track_id)
        if not points: return []
        latest = points[-1].timestamp
        selected = [p for p in points if (latest - p.timestamp).total_seconds() <= window_seconds]
        transitions, previous = [], None
        for point in selected:
            if point.lane_id is None: continue
            if previous is not None and point.lane_id != previous: transitions.append((point.timestamp, previous, point.lane_id))
            previous = point.lane_id
        return transitions

    def lateral_displacement(self, track_id):
        points = self.history(track_id)
        return 0.0 if len(points) < 2 else points[-1].x - points[0].x
