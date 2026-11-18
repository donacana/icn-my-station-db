package com.icn.camerasender.camera

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Matrix
import android.util.Log
import android.util.Size
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.AspectRatioStrategy
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import com.icn.camerasender.protocol.FramePayloadFormatter
import java.io.ByteArrayOutputStream
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

/**
 * CameraX 카메라 생명주기 및 실시간 미리보기, 영상 분석(ImageAnalysis) 관리자
 *
 * [YOLO DEMO 계약 (v0.3) 충족]
 * 1. 후면 카메라 실시간 미리보기 (서버 연결 여부와 무관하게 항상 동작)
 * 2. 해상도: 640×360
 * 3. 기본 3 FPS (서버 hello 수신 시 최대 maxFps 이내 동적 조절)
 * 4. 압축: JPEG 품질 65% (인메모리 압축, 파일 저장 안 함)
 * 5. 연결마다 1부터 1씩 증가하는 frameId 부여 (uint32)
 * 6. 헤더 길이 N + 헤더 JSON(cameraId: 정수) + JPEG 바이너리 패킷 생성
 */
class CameraManager(
    private val context: Context,
    private val lifecycleOwner: LifecycleOwner,
    private val previewView: PreviewView,
    private val onFrameCaptured: (frameId: Long, payload: ByteArray) -> Boolean
) {

    companion object {
        private const val TAG = "CameraManager"

        // 640x360 해상도 (16:9 비율)
        const val TARGET_WIDTH = 640
        const val TARGET_HEIGHT = 360

        // 기본 3 FPS (333ms)
        const val DEFAULT_TARGET_FPS = 3

        // JPEG 압축 품질 65%
        const val JPEG_QUALITY = 65
    }

    private var cameraProvider: ProcessCameraProvider? = null
    private var camera: Camera? = null
    private var preview: Preview? = null
    private var imageAnalysis: ImageAnalysis? = null

    // 백그라운드 분석 스레드
    private val analysisExecutor: ExecutorService = Executors.newSingleThreadExecutor()

    // 송출 제어 변수
    private val isStreamingActive = AtomicBoolean(false)
    private val frameIdCounter = AtomicLong(1L)
    private var lastAnalyzedTimestampMs = 0L

    // 프레임 전송 주기 (기본 333ms)
    private var currentIntervalMs = 1000L / DEFAULT_TARGET_FPS

    // v0.3: 현재 카메라 ID는 정수(Long)
    private var currentCameraId = 1L
    private var payloadFormatter: FramePayloadFormatter? = null

    /**
     * 카메라 초기화 및 실시간 미리보기 시작
     */
    fun startCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(context)

        cameraProviderFuture.addListener({
            try {
                cameraProvider = cameraProviderFuture.get()
                bindCameraUseCases()
            } catch (e: Exception) {
                Log.e(TAG, "ProcessCameraProvider initialization failed", e)
            }
        }, ContextCompat.getMainExecutor(context))
    }

    private fun bindCameraUseCases() {
        val provider = cameraProvider ?: return

        // 1. 해상도 셀렉터 구성 (640x360 16:9 우선 선호)
        val resolutionSelector = ResolutionSelector.Builder()
            .setAspectRatioStrategy(AspectRatioStrategy.RATIO_16_9_FALLBACK_AUTO_STRATEGY)
            .setResolutionStrategy(
                ResolutionStrategy(
                    Size(TARGET_WIDTH, TARGET_HEIGHT),
                    ResolutionStrategy.FALLBACK_RULE_CLOSEST_HIGHER_THEN_LOWER
                )
            )
            .build()

        // 2. 실시간 미리보기 (Preview) UseCase 구성
        preview = Preview.Builder()
            .setResolutionSelector(resolutionSelector)
            .build().also {
                it.setSurfaceProvider(previewView.surfaceProvider)
            }

        // 3. 이미지 분석 (ImageAnalysis) UseCase 구성
        imageAnalysis = ImageAnalysis.Builder()
            .setResolutionSelector(resolutionSelector)
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
            .build()
            .also { analysis ->
                analysis.setAnalyzer(analysisExecutor) { imageProxy ->
                    processImageFrame(imageProxy)
                }
            }

        // 후면 카메라 기본 선택
        val cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA

        try {
            provider.unbindAll()
            camera = provider.bindToLifecycle(
                lifecycleOwner,
                cameraSelector,
                preview,
                imageAnalysis
            )
            Log.i(TAG, "CameraX use cases bound successfully (Preview + ImageAnalysis)")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to bind CameraX use cases", e)
        }
    }

    /**
     * 영상 송출 활성화
     * 계약 1.1: 연결마다 frameId는 1부터 1씩 증가
     */
    fun startStreaming(cameraId: Long, formatter: FramePayloadFormatter) {
        this.currentCameraId = cameraId
        this.payloadFormatter = formatter
        this.frameIdCounter.set(1L) // 연결마다 1부터 시작
        this.currentIntervalMs = 1000L / DEFAULT_TARGET_FPS
        this.lastAnalyzedTimestampMs = 0L
        this.isStreamingActive.set(true)
        Log.i(TAG, "Streaming mode activated for camera: $cameraId (frameId reset to 1)")
    }

    /**
     * 서버 hello 메시지로 maxFps를 수신한 경우 전송 주기 업데이트
     */
    fun updateServerMaxFps(maxFps: Int) {
        val targetFps = DEFAULT_TARGET_FPS.coerceAtMost(maxFps.coerceAtLeast(1))
        this.currentIntervalMs = 1000L / targetFps
        Log.i(TAG, "Updated frame interval to ${currentIntervalMs}ms (target: ${targetFps} FPS, server max: $maxFps)")
    }

    /**
     * 영상 송출 비활성화 (카메라 미리보기는 계속 유지)
     */
    fun stopStreaming() {
        this.isStreamingActive.set(false)
        Log.i(TAG, "Streaming mode deactivated (Preview continues)")
    }

    /**
     * ImageAnalysis로부터 프레임 전달받아 FPS 제한, 640x360 스케일, JPEG 65% 인메모리 압축 후 전송
     */
    private fun processImageFrame(imageProxy: ImageProxy) {
        try {
            if (!isStreamingActive.get()) {
                return
            }

            val currentTime = System.currentTimeMillis()

            // FPS 쓰로틀링 (기본 333ms 간격)
            if (currentTime - lastAnalyzedTimestampMs < currentIntervalMs) {
                return
            }
            lastAnalyzedTimestampMs = currentTime

            val formatter = payloadFormatter ?: return

            // 1. ImageProxy를 Bitmap으로 변환 (인메모리)
            val bitmap = imageProxy.toBitmap()
            val rotationDegrees = imageProxy.imageInfo.rotationDegrees

            // 2. 센서 회전 보정 및 640x360 크기 조정
            val transformedBitmap = rotateAndScaleBitmap(bitmap, rotationDegrees, TARGET_WIDTH, TARGET_HEIGHT)

            // 3. JPEG 65% 인메모리 압축 (디스크 저장 안 함)
            val outputStream = ByteArrayOutputStream()
            transformedBitmap.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, outputStream)
            val jpegBytes = outputStream.toByteArray()

            // 비트맵 메모리 명시적 해제
            if (transformedBitmap != bitmap) {
                transformedBitmap.recycle()
            }
            bitmap.recycle()

            // 4. 계약 1.1: 연결마다 1부터 1씩 증가 (uint32)
            val frameId = frameIdCounter.getAndIncrement()

            // 5. 계약 1.2 (v0.3): 헤더 길이 N + 헤더 JSON(cameraId: 정수) + JPEG 바이너리 패키징
            val binaryPayload = formatter.formatPayload(
                frameId = frameId,
                timestampMs = currentTime,
                cameraId = currentCameraId,
                width = TARGET_WIDTH,
                height = TARGET_HEIGHT,
                jpegBytes = jpegBytes
            )

            // 6. 전송 콜백 호출 (네트워크 상태에 따라 송출 또는 폐기)
            onFrameCaptured(frameId, binaryPayload)

        } catch (e: Exception) {
            Log.e(TAG, "Error in processImageFrame", e)
        } finally {
            imageProxy.close()
        }
    }

    private fun rotateAndScaleBitmap(
        source: Bitmap,
        rotationDegrees: Int,
        targetWidth: Int,
        targetHeight: Int
    ): Bitmap {
        // 1. 센서 회전 각도 적용
        val matrix = Matrix()
        if (rotationDegrees != 0) {
            matrix.postRotate(rotationDegrees.toFloat())
        }

        val rotatedBitmap = if (rotationDegrees != 0) {
            Bitmap.createBitmap(source, 0, 0, source.width, source.height, matrix, true)
        } else {
            source
        }

        // 2. 16:9 비율 유지 센터 크롭 (화면 왜곡 방지)
        val targetRatio = targetWidth.toFloat() / targetHeight.toFloat()
        val rotatedWidth = rotatedBitmap.width
        val rotatedHeight = rotatedBitmap.height
        val currentRatio = rotatedWidth.toFloat() / rotatedHeight.toFloat()

        val cropWidth: Int
        val cropHeight: Int
        val cropX: Int
        val cropY: Int

        if (currentRatio > targetRatio) {
            // 원본이 16:9보다 좌우로 더 넓은 경우 -> 좌우를 중앙 기준으로 자름
            cropHeight = rotatedHeight
            cropWidth = (rotatedHeight * targetRatio).toInt().coerceAtMost(rotatedWidth)
            cropX = (rotatedWidth - cropWidth) / 2
            cropY = 0
        } else {
            // 원본이 16:9보다 위아래로 더 긴 경우 (4:3 또는 세로 프레임) -> 위아래를 중앙 기준으로 자름
            cropWidth = rotatedWidth
            cropHeight = (rotatedWidth / targetRatio).toInt().coerceAtMost(rotatedHeight)
            cropX = 0
            cropY = (rotatedHeight - cropHeight) / 2
        }

        val croppedBitmap = if (cropWidth != rotatedWidth || cropHeight != rotatedHeight) {
            Bitmap.createBitmap(rotatedBitmap, cropX, cropY, cropWidth, cropHeight)
        } else {
            rotatedBitmap
        }

        if (rotatedBitmap != source && rotatedBitmap != croppedBitmap) {
            rotatedBitmap.recycle()
        }

        // 3. 목표 640x360 해상도로 부드럽게 스케일링
        val finalBitmap = if (croppedBitmap.width != targetWidth || croppedBitmap.height != targetHeight) {
            val scaled = Bitmap.createScaledBitmap(croppedBitmap, targetWidth, targetHeight, true)
            if (croppedBitmap != source && croppedBitmap != scaled) {
                croppedBitmap.recycle()
            }
            scaled
        } else {
            croppedBitmap
        }

        return finalBitmap
    }

    fun shutdown() {
        stopStreaming()
        try {
            cameraProvider?.unbindAll()
            analysisExecutor.shutdown()
        } catch (e: Exception) {
            Log.e(TAG, "Error shutting down CameraManager", e)
        }
    }
}
