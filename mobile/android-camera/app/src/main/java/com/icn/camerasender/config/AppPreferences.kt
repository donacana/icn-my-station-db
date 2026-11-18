package com.icn.camerasender.config

import android.content.Context
import android.content.SharedPreferences

/**
 * 앱의 주요 설정(서버 주소, 카메라 ID, 인증 토큰 등)을 SharedPreferences에 안전하게 저장하고 관리합니다.
 * YOLO DEMO 계약 (v0.4, 2026-11-11) 준수:
 * - 서버 주소: ws://<SERVER_HOST>/ws/yolo/camera (공개 Nginx 주소, TLS 환경에서는 wss:// 사용)
 * - cameraId: 1 (정수)
 * - 쿼리 파라미터 인증용 token (YOLO_CAMERA_TOKEN)
 * - 640x360, 기본 3 FPS (최대 maxFps), JPEG 65%
 */
class AppPreferences(context: Context) {

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    var serverUrl: String
        get() = prefs.getString(KEY_SERVER_URL, DEFAULT_SERVER_URL) ?: DEFAULT_SERVER_URL
        set(value) = prefs.edit().putString(KEY_SERVER_URL, value.trim()).apply()

    var cameraId: Long
        get() = prefs.getLong(KEY_CAMERA_ID, DEFAULT_CAMERA_ID)
        set(value) = prefs.edit().putLong(KEY_CAMERA_ID, value).apply()

    var cameraToken: String
        get() = prefs.getString(KEY_CAMERA_TOKEN, DEFAULT_CAMERA_TOKEN) ?: DEFAULT_CAMERA_TOKEN
        set(value) = prefs.edit().putString(KEY_CAMERA_TOKEN, value.trim()).apply()

    // 고정 요구사항: 640x360, 기본 3 FPS, JPEG 65%
    val targetWidth: Int = 640
    val targetHeight: Int = 360
    val defaultFps: Int = 3
    val jpegQuality: Int = 65

    companion object {
        private const val PREFS_NAME = "icn_camera_sender_prefs"
        private const val KEY_SERVER_URL = "key_server_url"
        private const val KEY_CAMERA_ID = "key_camera_id"
        private const val KEY_CAMERA_TOKEN = "key_camera_token"

        // 기본값: 배포된 백엔드 서버의 공개 WebSocket 경로를 앱 설정에서 입력
        const val DEFAULT_SERVER_URL = "ws://<SERVER_HOST>/ws/yolo/camera"
        const val DEFAULT_CAMERA_ID = 1L
        const val DEFAULT_CAMERA_TOKEN = "" // 백엔드 .env의 YOLO_CAMERA_TOKEN 입력
    }
}
