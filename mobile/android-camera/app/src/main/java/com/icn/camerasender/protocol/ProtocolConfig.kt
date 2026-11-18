package com.icn.camerasender.protocol

import okhttp3.Headers
import okhttp3.Request
import org.json.JSONObject

/**
 * YOLO DEMO 계약 (v0.3, 2026-11-11)
 *
 * 1.1 식별자:
 *  - cameraId: 정수 (demo_yolo_cameras.camera_id 값, 1차 기본값 1)
 *  - frameId: uint32 (연결마다 1부터 1씩 증가)
 *  - capturedAt: epoch 밀리초
 * 1.3 인증:
 *  - 쿼리 파라미터 `token` (백엔드 .env의 YOLO_CAMERA_TOKEN)
 * 2. 경로:
 *  - `wss://<host>/ws/yolo/camera?cameraId=1&token=...` (HTTP 배포면 `ws://`)
 * 1.4 종료 코드:
 *  - 4401: 토큰 오류
 *  - 4404: 등록되지 않은 cameraId
 *  - 4409: 같은 cameraId 카메라 또는 새 워커가 연결되어 기존 연결이 대체됨
 */
object ProtocolConfig {

    const val DEFAULT_ENDPOINT_PATH = "/ws/yolo/camera"

    // 계약 명시 종료 코드
    const val CLOSE_CODE_TOKEN_ERROR = 4401
    const val CLOSE_CODE_UNREGISTERED_CAMERA = 4404
    const val CLOSE_CODE_DUPLICATE_REPLACED = 4409

    /**
     * 계약(v0.3 2장)에 명시된 형태의 WebSocket 접속 URL을 생성합니다.
     * 형태: ws://<host>/ws/yolo/camera?cameraId=1&token=<token>
     */
    fun buildWebSocketUrl(baseUrl: String, cameraId: Long, token: String): String {
        var cleanUrl = baseUrl.trim()
        if (!cleanUrl.startsWith("ws://") && !cleanUrl.startsWith("wss://")) {
            cleanUrl = "ws://$cleanUrl"
        }

        val delimiter = if (cleanUrl.contains("?")) "&" else "?"
        val tokenParam = if (token.isNotBlank()) "&token=$token" else ""

        return "$cleanUrl${delimiter}cameraId=$cameraId$tokenParam"
    }

    /**
     * WebSocket 접속용 OkHttp Request 객체를 생성합니다.
     */
    fun createWebSocketRequest(serverUrl: String, cameraId: Long, token: String): Request {
        val finalUrl = buildWebSocketUrl(serverUrl, cameraId, token)
        val headers = Headers.Builder()
            .add("X-Client-Type", "Android-ICN-Camera-Sender")
            .add("X-Client-Version", "v0.4")
            .build()

        return Request.Builder()
            .url(finalUrl)
            .headers(headers)
            .build()
    }

    /**
     * 서버가 보낸 텍스트 메시지(hello 등)를 파싱합니다.
     * v0.3: {"type": "hello", "cameraId": 1, "maxFps": 10}
     */
    fun parseServerHello(jsonText: String): Pair<Long?, Int?> {
        return try {
            val json = JSONObject(jsonText)
            if (json.optString("type") == "hello") {
                val camId = if (json.has("cameraId")) json.optLong("cameraId", 1L) else null
                val maxFps = json.optInt("maxFps", 10)
                Pair(camId, maxFps)
            } else {
                Pair(null, null)
            }
        } catch (e: Exception) {
            Pair(null, null)
        }
    }

    fun getCloseReasonMessage(code: Int): String {
        return when (code) {
            CLOSE_CODE_TOKEN_ERROR -> "토큰 인증 오류 (코드 4401) - 토큰 설정을 확인하세요."
            CLOSE_CODE_UNREGISTERED_CAMERA -> "등록되지 않은 cameraId (코드 4404)"
            CLOSE_CODE_DUPLICATE_REPLACED -> "동일한 cameraId로 새 연결이 등록되어 대체됨 (코드 4409)"
            1000 -> "정상 종료"
            else -> "연결 종료 (코드 $code)"
        }
    }
}
