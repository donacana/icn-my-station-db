package com.icn.camerasender.network

import android.os.Handler
import android.os.Looper
import android.util.Log
import com.icn.camerasender.model.ConnectionState
import com.icn.camerasender.model.StreamStatistics
import com.icn.camerasender.protocol.ProtocolConfig
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import okio.ByteString.Companion.toByteString
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

/**
 * YOLO DEMO 계약 (v0.3) 준수 WebSocket 관리자
 *
 * 1. URL: ws://<host>/ws/yolo/camera?cameraId=1&token=... (cameraId: 정수)
 * 2. 서버 연결 직후 hello 수신: {"type": "hello", "cameraId": 1, "maxFps": 10}
 * 3. 재연결 주기: 1초 → 2초 → 4초 (최대 4초)
 * 4. 종료 코드 처리: 4401(토큰 오류), 4404(미등록), 4409(다른 연결로 대체)
 * 5. 통신 지연 시 이전 프레임 자동 폐기 (Drop)
 */
class WebSocketManager(
    private val stateListener: (ConnectionState) -> Unit,
    private val statsListener: (StreamStatistics) -> Unit,
    private val onMaxFpsUpdated: (Int) -> Unit
) {

    companion object {
        private const val TAG = "WebSocketManager"
        private const val MAX_PENDING_QUEUE_BYTES = 64 * 1024L
    }

    private val mainHandler = Handler(Looper.getMainLooper())

    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .writeTimeout(5, TimeUnit.SECONDS)
        .pingInterval(10, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    private var webSocket: WebSocket? = null
    private var currentRequest: Request? = null

    // 제어 플래그
    private val shouldBeStreaming = AtomicBoolean(false)
    private val isConnecting = AtomicBoolean(false)
    private val isConnected = AtomicBoolean(false)
    private val isSendingFrame = AtomicBoolean(false)

    // 통계 지표 카운터
    private val totalCapturedCount = AtomicLong(0)
    private val sentCount = AtomicLong(0)
    private val droppedCount = AtomicLong(0)
    private val latestFrameId = AtomicLong(0)

    // FPS 계산 변수
    private var lastFpsCalcTime = System.currentTimeMillis()
    private var framesSentInInterval = 0
    private var currentFps = 0.0

    // 재접속 제어 (1초 -> 2초 -> 최대 4초)
    private var reconnectAttempt = 0
    private var reconnectRunnable: Runnable? = null
    private var lastServerUrl: String = ""
    private var lastCameraId: Long = 1L
    private var lastToken: String = ""

    /**
     * WebSocket 서버 연결 시작
     */
    fun startStreaming(serverUrl: String, cameraId: Long, token: String) {
        lastServerUrl = serverUrl
        lastCameraId = cameraId
        lastToken = token

        shouldBeStreaming.set(true)
        reconnectAttempt = 0
        cancelPendingReconnect()

        // 통계 초기화
        totalCapturedCount.set(0)
        sentCount.set(0)
        droppedCount.set(0)
        framesSentInInterval = 0
        currentFps = 0.0
        lastFpsCalcTime = System.currentTimeMillis()

        connectInternal()
    }

    /**
     * WebSocket 연결 해제 및 송출 중단
     */
    fun stopStreaming() {
        shouldBeStreaming.set(false)
        cancelPendingReconnect()

        try {
            webSocket?.close(1000, "Client stopped stream")
        } catch (e: Exception) {
            Log.w(TAG, "Error closing websocket", e)
        } finally {
            webSocket = null
            isConnected.set(false)
            isConnecting.set(false)
            isSendingFrame.set(false)
            notifyState(ConnectionState.Disconnected("송출이 중지되었습니다."))
        }
    }

    private fun connectInternal() {
        if (isConnected.get() || isConnecting.get()) return

        isConnecting.set(true)
        notifyState(ConnectionState.Connecting(lastServerUrl))

        val request = ProtocolConfig.createWebSocketRequest(
            serverUrl = lastServerUrl,
            cameraId = lastCameraId,
            token = lastToken
        )
        currentRequest = request

        Log.d(TAG, "Connecting to WebSocket")

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.i(TAG, "WebSocket connected successfully")
                isConnecting.set(false)
                isConnected.set(true)
                reconnectAttempt = 0

                if (shouldBeStreaming.get()) {
                    notifyState(ConnectionState.Streaming(currentFps))
                } else {
                    notifyState(ConnectionState.Connected(lastServerUrl))
                }
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                Log.d(TAG, "Received server text message")

                // 서버 hello 메시지 파싱: {"type": "hello", "cameraId": 1, "maxFps": 10}
                val (camId, maxFps) = ProtocolConfig.parseServerHello(text)
                if (maxFps != null && maxFps > 0) {
                    Log.i(TAG, "Server negotiated maxFps: $maxFps for camera: $camId")
                    mainHandler.post {
                        onMaxFpsUpdated(maxFps)
                    }
                }
            }

            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                Log.d(TAG, "Received binary message: ${bytes.size} bytes")
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Log.w(TAG, "WebSocket closing by server: code=$code")
                webSocket.close(code, reason)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.w(TAG, "WebSocket closed: code=$code")
                isConnected.set(false)
                isConnecting.set(false)

                val message = ProtocolConfig.getCloseReasonMessage(code)

                when (code) {
                    ProtocolConfig.CLOSE_CODE_TOKEN_ERROR -> {
                        // 4401: 토큰 오류
                        shouldBeStreaming.set(false)
                        notifyState(ConnectionState.Error(message))
                    }
                    ProtocolConfig.CLOSE_CODE_UNREGISTERED_CAMERA -> {
                        // 4404: 미등록 cameraId
                        shouldBeStreaming.set(false)
                        notifyState(ConnectionState.Error(message))
                    }
                    ProtocolConfig.CLOSE_CODE_DUPLICATE_REPLACED -> {
                        // 4409: 동일 cameraId로 새 기기 연결됨
                        shouldBeStreaming.set(false)
                        notifyState(ConnectionState.Disconnected("다른 기기에서 연결되어 대체되었습니다 (4409)"))
                    }
                    else -> {
                        if (shouldBeStreaming.get()) {
                            scheduleReconnect()
                        } else {
                            notifyState(ConnectionState.Disconnected(message))
                        }
                    }
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                val errorMsg = t.message ?: "네트워크 연결 실패"
                Log.e(TAG, "WebSocket failure (Response code: ${response?.code})")
                isConnected.set(false)
                isConnecting.set(false)

                val responseCode = response?.code
                if (responseCode == 401 || responseCode == ProtocolConfig.CLOSE_CODE_TOKEN_ERROR) {
                    shouldBeStreaming.set(false)
                    notifyState(ConnectionState.Error("인증 실패 (401/4401): 토큰을 확인하세요."))
                    return
                }

                if (shouldBeStreaming.get()) {
                    notifyState(ConnectionState.Error("연결 오류: $errorMsg", t))
                    scheduleReconnect()
                } else {
                    notifyState(ConnectionState.Error(errorMsg, t))
                }
            }
        })
    }

    fun sendBinaryFrame(frameId: Long, binaryData: ByteArray): Boolean {
        latestFrameId.set(frameId)
        totalCapturedCount.incrementAndGet()

        val socket = webSocket
        if (!isConnected.get() || socket == null) {
            droppedCount.incrementAndGet()
            dispatchStats(binaryData.size, 0L)
            return false
        }

        val queueSize = socket.queueSize()
        if (queueSize > MAX_PENDING_QUEUE_BYTES) {
            droppedCount.incrementAndGet()
            Log.w(TAG, "Network backpressure: Queue size $queueSize bytes. Dropped frame #$frameId")
            dispatchStats(binaryData.size, 0L)
            return false
        }

        if (!isSendingFrame.compareAndSet(false, true)) {
            droppedCount.incrementAndGet()
            dispatchStats(binaryData.size, 0L)
            return false
        }

        val startTime = System.currentTimeMillis()
        return try {
            val byteString = binaryData.toByteString()
            val success = socket.send(byteString)

            if (success) {
                sentCount.incrementAndGet()
                framesSentInInterval++
                val latency = System.currentTimeMillis() - startTime
                updateFps()
                dispatchStats(binaryData.size, latency)
                true
            } else {
                droppedCount.incrementAndGet()
                dispatchStats(binaryData.size, 0L)
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error sending frame #$frameId", e)
            droppedCount.incrementAndGet()
            dispatchStats(binaryData.size, 0L)
            false
        } finally {
            isSendingFrame.set(false)
        }
    }

    private fun updateFps() {
        val now = System.currentTimeMillis()
        val elapsed = now - lastFpsCalcTime
        if (elapsed >= 1000L) {
            currentFps = (framesSentInInterval * 1000.0) / elapsed
            framesSentInInterval = 0
            lastFpsCalcTime = now

            if (shouldBeStreaming.get() && isConnected.get()) {
                notifyState(ConnectionState.Streaming(currentFps))
            }
        }
    }

    private fun dispatchStats(frameSize: Int, latencyMs: Long) {
        val stats = StreamStatistics(
            currentFrameId = latestFrameId.get(),
            totalCapturedFrames = totalCapturedCount.get(),
            sentFrames = sentCount.get(),
            droppedFrames = droppedCount.get(),
            currentFps = currentFps,
            lastFrameSizeBytes = frameSize,
            lastSendLatencyMs = latencyMs
        )
        mainHandler.post {
            statsListener(stats)
        }
    }

    private fun scheduleReconnect() {
        if (!shouldBeStreaming.get()) return

        reconnectAttempt++
        val delaySec = when (reconnectAttempt) {
            1 -> 1L
            2 -> 2L
            else -> 4L
        }
        val delayMs = delaySec * 1000L

        Log.i(TAG, "Scheduling reconnect attempt #$reconnectAttempt in $delaySec seconds...")
        notifyState(ConnectionState.Reconnecting(reconnectAttempt, delaySec))

        cancelPendingReconnect()
        reconnectRunnable = Runnable {
            if (shouldBeStreaming.get()) {
                connectInternal()
            }
        }
        mainHandler.postDelayed(reconnectRunnable!!, delayMs)
    }

    private fun cancelPendingReconnect() {
        reconnectRunnable?.let {
            mainHandler.removeCallbacks(it)
            reconnectRunnable = null
        }
    }

    private fun notifyState(state: ConnectionState) {
        mainHandler.post {
            stateListener(state)
        }
    }
}
