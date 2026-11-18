from dataclasses import replace
import pytest
from app.config import Settings, load_settings, validate_settings, resolve_backend, model_path
from app.inference_base import class_names


def test_defaults(tmp_path):
    s=load_settings(tmp_path/"missing.env")
    assert s.backend=="onnx_cpu" and s.imgsz==416


def test_environment_precedence(tmp_path,monkeypatch):
    env=tmp_path/"settings.env"
    env.write_text("YOLO_CONF=0.4\nYOLO_IMGSZ=320\n")
    monkeypatch.setenv("YOLO_CONF","0.6")
    s=load_settings(env)
    assert s.conf==0.6 and s.imgsz==320


@pytest.mark.parametrize("changes",[
    {"conf":float("nan")},{"conf":0},{"max_fps":-1},{"imgsz":417},
    {"ws_url":"https://localhost"},{"ws_url":"ws://example.com/ws"},
    {"ws_url":"ws://u:secret@localhost"},{"mock_mode":False},
    {"backend":"magic"},{"intra_threads":28},{"gesture_open":"help_fist"}])
def test_invalid_settings(changes):
    with pytest.raises(ValueError): validate_settings(replace(Settings(),**changes))


def test_boolean(monkeypatch,tmp_path):
    monkeypatch.setenv("ENABLE_TRACKING","yes")
    with pytest.raises(ValueError): load_settings(tmp_path/"missing")


def test_model_missing_no_silent_demo(tmp_path):
    with pytest.raises(FileNotFoundError): model_path(replace(Settings(),onnx_model_path=tmp_path/"custom.onnx"),"onnx_cpu")


def test_auto_prefers_onnx(tmp_path):
    path=tmp_path/"exists.onnx"; path.touch()
    assert resolve_backend(replace(Settings(),backend="auto",onnx_model_path=path))[0]=="onnx_cpu"


def test_class_mapping(tmp_path):
    path=tmp_path/"data.yaml"; path.write_text("names: [help_open, person, help_fist]\nnc: 3\n")
    assert class_names(None,path)[1]=="person"
    with pytest.raises(ValueError): class_names({0:"person"},path)
    with pytest.raises(ValueError): class_names({0:"human"})


def test_secret_repr():
    assert "secret" not in repr(Settings(token="secret",ws_url="secret"))


def test_ec2_can_forbid_demo_model_fallback(tmp_path):
    missing=tmp_path/"best.onnx"
    with pytest.raises(FileNotFoundError):
        model_path(replace(Settings(),onnx_model_path=missing,allow_demo_model=False),"onnx_cpu")


def test_remote_ec2_requires_explicit_safe_configuration():
    remote=replace(Settings(),protocol="demo-v0.3",camera_id=1,mock_mode=False,
                   allow_remote_ec2=True,token="secret",
                   ws_url="ws://worker.example/ws/yolo/worker",
                   model_version="icn-v1-yolo11n")
    assert validate_settings(remote).model_version=="icn-v1-yolo11n"
    for changes in ({"allow_remote_ec2":False},{"token":""},
                    {"ws_url":"ws://worker.example/wrong"},
                    {"protocol":"mock-v1"},{"ws_url":"ws://127.0.0.1/ws/yolo/worker"}):
        with pytest.raises(ValueError):
            validate_settings(replace(remote,**changes))


def test_explicit_ec2_env_file(monkeypatch,tmp_path):
    env=tmp_path/"ec2.env"
    env.write_text("\n".join(("YOLO_PROTOCOL=demo-v0.3","CAMERA_ID=1",
        "WORKER_ID=suam-school-pc","WORKER_MODEL_VERSION=icn-v1-yolo11n",
        "WS_URL=ws://worker.example/ws/yolo/worker","YOLO_WORKER_TOKEN=secret",
        "MOCK_MODE=false","ALLOW_REMOTE_EC2=true")))
    monkeypatch.setenv("YOLO_ENV_FILE",str(env))
    s=load_settings()
    assert s.camera_id==1 and s.worker_id=="suam-school-pc"
    assert s.model_version=="icn-v1-yolo11n" and not s.mock_mode


def test_explicit_env_file_token_survives_empty_ambient(monkeypatch,tmp_path):
    env=tmp_path/"ec2.env"
    env.write_text("\n".join(("YOLO_PROTOCOL=demo-v0.3","CAMERA_ID=1",
        "WS_URL=ws://worker.example/ws/yolo/worker","YOLO_WORKER_TOKEN=file-secret",
        "MOCK_MODE=false","ALLOW_REMOTE_EC2=true")))
    monkeypatch.setenv("YOLO_ENV_FILE",str(env))
    monkeypatch.setenv("YOLO_WORKER_TOKEN","")
    assert load_settings().token=="file-secret"


def test_v04_remote_two_camera_env(monkeypatch,tmp_path):
    env=tmp_path/"ec2.env"
    env.write_text("\n".join(("YOLO_PROTOCOL=demo-v0.4","CAMERA_ID=1","CAMERA_IDS=1,2",
        "WORKER_MODEL_VERSION=icn-v1-yolo11n-finger-gun",
        "WS_URL=wss://worker.example/ws/yolo/worker","YOLO_WORKER_TOKEN=secret",
        "MOCK_MODE=false","ALLOW_REMOTE_EC2=true")))
    monkeypatch.setenv("YOLO_ENV_FILE",str(env))
    settings=load_settings()
    assert settings.protocol=="demo-v0.4" and settings.camera_ids==(1,2)
    assert settings.token=="secret" and settings.ws_url.startswith("wss://")
