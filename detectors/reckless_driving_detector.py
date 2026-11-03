"""Rule-based risk triage. Outputs are review alerts, never legal conclusions."""
class RecklessDrivingDetector:
    def __init__(self, lane_change_threshold=3, ttc_warning_seconds=2.0):
        if lane_change_threshold < 2 or ttc_warning_seconds <= 0: raise ValueError("invalid thresholds")
        self.lane_change_threshold, self.ttc_warning_seconds = lane_change_threshold, float(ttc_warning_seconds)

    def evaluate(self, track_id, lane_change_count=0, indicator_state="UNKNOWN", manoeuvre_direction=None,
                 ttc_seconds=None, indicator_visible=False):
        if indicator_state not in {"LEFT", "RIGHT", "BOTH", "OFF", "UNKNOWN"}: raise ValueError("unsupported indicator state")
        reasons = []
        if lane_change_count >= self.lane_change_threshold: reasons.append("REPEATED_LANE_CHANGES")
        if ttc_seconds is not None and 0 <= float(ttc_seconds) <= self.ttc_warning_seconds: reasons.append("LOW_TIME_TO_COLLISION")
        if indicator_visible and manoeuvre_direction in {"LEFT", "RIGHT"}:
            if indicator_state == "OFF": reasons.append("INDICATOR_NOT_OBSERVED")
            elif indicator_state in {"LEFT", "RIGHT"} and indicator_state != manoeuvre_direction: reasons.append("INDICATOR_DIRECTION_MISMATCH")
        if not reasons: return None
        risk = "HIGH" if "LOW_TIME_TO_COLLISION" in reasons else ("MEDIUM" if len(reasons) >= 2 else "LOW")
        return {"event_type": "SUSPECTED_UNSAFE_DRIVING_BEHAVIOUR", "track_id": track_id,
                "risk_level": risk, "reasons": reasons, "indicator_state": indicator_state,
                "review_required": True, "legal_violation_confirmed": False}
