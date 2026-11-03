"""Conservative lane-change and weaving event detection."""
from collections import defaultdict

class LaneChangeDetector:
    def __init__(self, min_changes=3, window_seconds=8.0, cooldown_seconds=8.0):
        if min_changes < 2 or window_seconds <= 0 or cooldown_seconds < 0: raise ValueError("invalid thresholds")
        self.min_changes, self.window_seconds, self.cooldown_seconds = min_changes, float(window_seconds), float(cooldown_seconds)
        self._last_event = defaultdict(lambda: None)

    def update(self, track_id, transitions):
        transitions = list(transitions)
        if len(transitions) < self.min_changes: return None
        end_time = transitions[-1][0]
        recent = [item for item in transitions if (end_time - item[0]).total_seconds() <= self.window_seconds]
        if len(recent) < self.min_changes: return None
        previous = self._last_event[track_id]
        if previous is not None and (end_time - previous).total_seconds() < self.cooldown_seconds: return None
        self._last_event[track_id] = end_time
        return {"event_type": "SUSPECTED_REPEATED_LANE_CHANGES", "track_id": track_id,
                "transition_count": len(recent), "window_seconds": self.window_seconds, "review_required": True}
