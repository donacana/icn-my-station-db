package com.icn.camerasender.protocol

import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * YOLO DEMO 계약 (v0.4, 2026-11-11) 1.2 바이너리 프레임 형식 구현
 *
 * [바이너리 프레임 형식]
 * -------------------------------------------------------------
 * 위치    | 크기       | 내용
 * -------------------------------------------------------------
 * 0       | 4바이트    | 헤더 길이 N (uint32, big-endian)
 * 4       | N바이트    | 헤더 JSON (UTF-8)
 * 4+N     | 나머지     | JPEG 바이트 (640x360, 품질 65%)
 * -------------------------------------------------------------
 *
 * [v0.4 헤더 JSON 규격 - cameraId가 정수(Long)]
 * {"cameraId": 1, "frameId": 1523, "capturedAt": 1762923785120, "width": 640, "height": 360}
 */
interface FramePayloadFormatter {
    fun formatPayload(
        frameId: Long,
        timestampMs: Long,
        cameraId: Long,
        width: Int,
        height: Int,
        jpegBytes: ByteArray
    ): ByteArray
}

/**
 * YOLO DEMO v0.4 표준 계약 포맷터 (v0.3 및 v0.4 공통 바이너리 규격)
 */
class YoloDemoV4PayloadFormatter : FramePayloadFormatter {

    override fun formatPayload(
        frameId: Long,
        timestampMs: Long,
        cameraId: Long,
        width: Int,
        height: Int,
        jpegBytes: ByteArray
    ): ByteArray {
        // 1. 헤더 JSON 생성 (v0.4: cameraId 정수)
        // {"cameraId": 1, "frameId": 1523, "capturedAt": 1762923785120, "width": 640, "height": 360}
        val headerJson = buildString {
            append("{\"cameraId\":").append(cameraId).append(",")
            append("\"frameId\":").append(frameId).append(",")
            append("\"capturedAt\":").append(timestampMs).append(",")
            append("\"width\":").append(width).append(",")
            append("\"height\":").append(height).append("}")
        }

        val headerJsonBytes = headerJson.toByteArray(Charsets.UTF_8)
        val headerLength = headerJsonBytes.size // N
        val totalSize = 4 + headerLength + jpegBytes.size

        // 2. 바이너리 패킷 조합 (Big-Endian uint32 + JSON + JPEG)
        val buffer = ByteBuffer.allocate(totalSize).order(ByteOrder.BIG_ENDIAN)
        buffer.putInt(headerLength)        // 0~3: 헤더 길이 N (uint32)
        buffer.put(headerJsonBytes)        // 4~(4+N-1): 헤더 JSON 바이트
        buffer.put(jpegBytes)              // (4+N)~끝: JPEG 바이너리

        return buffer.array()
    }
}
