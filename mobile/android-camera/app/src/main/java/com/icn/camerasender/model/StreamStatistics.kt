package com.icn.camerasender.model

/**
 * 실시간 영상 송출 통계 정보 데이터 클래스
 * 통신 속도 저하로 인한 프레임 폐기(Drop) 현황 및 전송 현황을 실시간으로 추적합니다.
 */
data class StreamStatistics(
    val currentFrameId: Long = 0L,
    val totalCapturedFrames: Long = 0L,
    val sentFrames: Long = 0L,
    val droppedFrames: Long = 0L,
    val currentFps: Double = 0.0,
    val lastFrameSizeBytes: Int = 0,
    val lastSendLatencyMs: Long = 0L
)
