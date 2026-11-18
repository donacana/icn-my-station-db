package com.icn.camerasender.model

/**
 * WebSocket 서버와의 연결 및 송출 상태를 나타내는 클래스
 */
sealed class ConnectionState {
    /** 연결 대기 또는 연결 해제 상태 */
    data class Disconnected(val reason: String? = null) : ConnectionState()

    /** 서버에 연결을 시도 중인 상태 */
    data class Connecting(val serverUrl: String) : ConnectionState()

    /** 서버에 성공적으로 연결되었으나 아직 카메라 영상 송출은 시작하지 않은 상태 */
    data class Connected(val serverUrl: String) : ConnectionState()

    /** 실시간 카메라 영상이 지정된 규격(3 FPS, 640x360, JPEG 65%)으로 서버에 송출 중인 상태 */
    data class Streaming(val fps: Double = 0.0) : ConnectionState()

    /** 통신 단절 등으로 인해 자동 재연결을 시도 중인 상태 */
    data class Reconnecting(val attempt: Int, val delaySec: Long) : ConnectionState()

    /** 연결 중 예외 또는 에러가 발생한 상태 */
    data class Error(val message: String, val throwable: Throwable? = null) : ConnectionState()
}
