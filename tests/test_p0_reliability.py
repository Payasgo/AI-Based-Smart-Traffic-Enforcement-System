import csv,sys,threading,time
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from camera.camera_config import CameraConfig
from camera.evidence_context import CameraEvidenceLogger
from camera.inference_worker import CameraInferenceWorker
from camera.multi_camera_runner import MultiCameraRunner
from utils.evidence_logger import EvidenceLogger

def test_jurisdiction_env_validation(monkeypatch):
    from config.settings import _traffic_jurisdiction
    monkeypatch.setenv("TRAFFIC_JURISDICTION","ANDHRA_PRADESH");assert _traffic_jurisdiction()=="ANDHRA_PRADESH"
    monkeypatch.setenv("TRAFFIC_JURISDICTION","IN")
    with pytest.raises(ValueError):_traffic_jurisdiction()

def test_camera_calibration_is_applied():
    camera=CameraConfig.from_dict({"camera_id":"north","source":0,"location_id":"site-7","calibration":{"calibration_version":"v3","jurisdiction":"ANDHRA_PRADESH","speed_limit_kmh":40,"wrong_way_direction":[1,0],"traffic_stop_line_y":0.6,"road_rule_zones":[{"name":"bus","polygon":[[0,.5],[.5,.5],[.5,1]]}]}})
    config=MultiCameraRunner._camera_config(camera)
    assert (config.SPEED_LIMIT_KMH,config.WRONG_WAY_DIRECTION_X,config.TRAFFIC_STOP_LINE_Y)==(40,1,.6)
    assert config.TRAFFIC_JURISDICTION=="ANDHRA_PRADESH" and config.CAMERA_SITE_ID=="site-7" and config.CALIBRATION_VERSION=="v3"

def test_invalid_camera_calibration_rejected():
    with pytest.raises(ValueError,match="normalized"):CameraConfig("bad",0,calibration={"traffic_stop_line_y":1.5})
    with pytest.raises(ValueError,match="non-zero"):CameraConfig("bad",0,calibration={"wrong_way_direction":[0,0]})

def test_legacy_csv_migration_and_camera_metadata(tmp_path):
    logs,evidence=tmp_path/"logs",tmp_path/"evidence";logs.mkdir()
    (logs/"violations.csv").write_text("timestamp,violation_type,license_plate,speed_kmh,evidence_image,location\n2026-01-01,OLD,ABC,,old.jpg,site\n",encoding="utf-8")
    logger=EvidenceLogger(logs,evidence);scoped=CameraEvidenceLogger(logger,"CAM-A","site-1","cal-v2")
    scoped.log_violation("SPEEDING","ABC123",55.2,datetime.now(timezone.utc),"")
    with (logs/"violations.csv").open(newline="",encoding="utf-8") as f:rows=list(csv.DictReader(f))
    assert len(rows)==2 and rows[0]["violation_type"]=="OLD"
    assert rows[1]["camera_id"]=="CAM-A" and rows[1]["site_id"]=="site-1" and rows[1]["calibration_version"]=="cal-v2"
    assert rows[1]["event_id"] and rows[1]["review_status"]=="PENDING_REVIEW"

def test_concurrent_evidence_appends_are_not_lost(tmp_path):
    logger=EvidenceLogger(tmp_path/"logs",tmp_path/"evidence");stamp=datetime.now(timezone.utc)
    threads=[threading.Thread(target=lambda n=n:[logger.log_violation("TEST",str(n),None,stamp,"",camera_id=f"cam-{n}") for _ in range(25)]) for n in range(8)]
    for t in threads:t.start()
    for t in threads:t.join()
    with logger.csv_path.open(newline="",encoding="utf-8") as f:rows=list(csv.DictReader(f))
    assert len(rows)==200 and len({row["event_id"] for row in rows})==200

def test_worker_exposes_pipeline_error():
    class Stream:
        sent=False
        def read(self,timeout=0):
            if not self.sent:
                self.sent=True;return SimpleNamespace(frame=object(),timestamp=datetime.now(timezone.utc),sequence=1)
            time.sleep(.01);return None
    class Tracker:
        def update(self,frame,timestamp):return {}
    worker=CameraInferenceWorker("cam",Stream(),Tracker(),on_result=lambda _:(_ for _ in ()).throw(RuntimeError("pipeline boom")))
    worker.start();deadline=time.time()+1
    while time.time()<deadline and worker.error_count==0:time.sleep(.01)
    worker.stop()
    assert worker.error_count==1 and "pipeline boom" in worker.last_error and worker.last_error_at
    assert worker.processed_frames==0
