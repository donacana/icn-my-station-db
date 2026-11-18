"""
YOLO DEMO 계약 (v0.3, 2026-11-11) 준수 백엔드 WebSocket 수신 서버 예제
경로: /ws/yolo/camera (휴대폰 앱 -> 백엔드)

v0.3 변경사항:
- cameraId가 문자열에서 demo_yolo_cameras.camera_id(정수/int)로 변경
- 헤더 JSON 예시: {"cameraId": 1, "frameId": 1523, "capturedAt": 1762923785120, "width": 640, "height": 360}
- URL: ws://<host>/ws/yolo/camera?cameraId=1&token=...
"""

import time
import json
import struct
import logging
from typing import Optional, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, status
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("YoloDemoBackend")

app = FastAPI(title="YOLO DEMO Contract v0.3 Backend Receiver")

# .env YOLO_CAMERA_TOKEN 모의 값
YOLO_CAMERA_TOKEN = "demo-camera-token"

# 활성 카메라 연결 추적 (cameraId: int -> WebSocket)
active_cameras: Dict[int, WebSocket] = {}

@app.get("/")
def health_check():
    return {
        "status": "online",
        "contract": "YOLO DEMO v0.3",
        "endpoint": "/ws/yolo/camera"
    }

@app.websocket("/ws/yolo/camera")
async def websocket_camera_endpoint(
    websocket: WebSocket,
    cameraId: int = Query(1),
    token: Optional[str] = Query(None)
):
    # 1.3 인증 토큰 검증
    if token != YOLO_CAMERA_TOKEN:
        logger.warning(f"인증 실패: 잘못된 토큰 (cameraId={cameraId})")
        await websocket.close(code=4401, reason="토큰 오류")
        return

    # 1.4 중복 연결 처리 (동일 cameraId 기존 연결 4409로 종료)
    if cameraId in active_cameras:
        old_ws = active_cameras[cameraId]
        logger.warning(f"동일 cameraId ({cameraId}) 중복 연결 감지 -> 기존 연결 4409 종료")
        try:
            await old_ws.close(code=4409, reason="새 카메라 연결로 대체됨")
        except Exception:
            pass

    await websocket.accept()
    active_cameras[cameraId] = websocket
    logger.info(f"카메라 연결 승인: [cameraId={cameraId}] (호스트: {websocket.client.host if websocket.client else 'unknown'})")

    # 2.1 연결 직후 백엔드 -> 앱 hello 메시지 전송 (v0.3: cameraId 정수)
    hello_msg = {
        "type": "hello",
        "cameraId": cameraId,
        "maxFps": 10
    }
    await websocket.send_text(json.dumps(hello_msg))
    logger.info(f"[{cameraId}] <- hello 메시지 전송: {hello_msg}")

    frame_counter = 0
    last_log_time = time.time()
    frames_in_interval = 0

    try:
        while True:
            # 바이너리 데이터 수신
            data = await websocket.receive_bytes()
            now_ms = int(time.time() * 1000)
            frame_counter += 1
            frames_in_interval += 1

            if len(data) < 4:
                logger.error("잘못된 프레임: 데이터가 4바이트 미만입니다.")
                continue

            # 1.2 바이너리 형식 파싱:
            # 0~3: 헤더 길이 N (uint32, big-endian)
            (header_len,) = struct.unpack_from(">I", data, 0)
            offset = 4

            if len(data) < offset + header_len:
                logger.error(f"잘못된 프레임: 헤더 길이({header_len})가 실제 데이터보다 큽니다.")
                continue

            # 4~4+N-1: 헤더 JSON (UTF-8)
            header_json_bytes = data[offset : offset + header_len]
            header_dict = json.loads(header_json_bytes.decode("utf-8"))
            offset += header_len

            # 4+N~끝: JPEG 바이트
            jpeg_bytes = data[offset:]

            frame_id = header_dict.get("frameId")
            captured_at = header_dict.get("capturedAt", 0)
            width = header_dict.get("width")
            height = header_dict.get("height")
            recv_cam_id = header_dict.get("cameraId")
            latency_ms = max(0, now_ms - captured_at) if captured_at else None

            # 1초마다 수신 통계 로그 출력
            curr_time = time.time()
            if curr_time - last_log_time >= 1.0:
                calc_fps = frames_in_interval / (curr_time - last_log_time)
                latency_str = f", Latency: {latency_ms}ms" if latency_ms is not None else ""
                logger.info(
                    f"Camera [id={recv_cam_id}] | Frame #{frame_id} | "
                    f"Recv FPS: {calc_fps:.1f} | Res: {width}x{height} | "
                    f"JPEG: {len(jpeg_bytes)/1024:.1f} KB{latency_str}"
                )
                frames_in_interval = 0
                last_log_time = curr_time

    except WebSocketDisconnect:
        logger.warning(f"카메라 연결 끊김: [id={cameraId}]")
    except Exception as e:
        logger.error(f"카메라 프레임 처리 중 오류 [id={cameraId}]: {e}", exc_info=True)
    finally:
        if active_cameras.get(cameraId) == websocket:
            del active_cameras[cameraId]
        logger.info(f"카메라 리소스 정리 완료: [id={cameraId}] (총 수신: {frame_counter} 프레임)")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
