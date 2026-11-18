package com.icn.camerasender.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.widget.doAfterTextChanged
import com.icn.camerasender.R
import com.icn.camerasender.camera.CameraManager
import com.icn.camerasender.config.AppPreferences
import com.icn.camerasender.databinding.ActivityMainBinding
import com.icn.camerasender.model.ConnectionState
import com.icn.camerasender.model.StreamStatistics
import com.icn.camerasender.network.WebSocketManager
import com.icn.camerasender.protocol.YoloDemoV4PayloadFormatter

/**
 * ICN Camera Sender 메인 액티비티
 * YOLO DEMO 계약 (v0.4, 2026-11-11) 준수
 *
 * 추가 기능:
 * 1. 카메라 선택 기능 (카메라 1: T1 3번 출국장, 카메라 2: T1 스카이허브 라운지 서편, 직접 입력)
 * 2. cameraId 정수 1, 2 지원 및 RDS 등록값 임의 변경 지원
 * 3. 송출 중 카메라 변경 시 기존 연결 정상 종료 후 새 cameraId로 자동 재연결
 * 4. 카메라 미리보기 끊김 없이 유지
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var preferences: AppPreferences
    private lateinit var cameraManager: CameraManager
    private lateinit var webSocketManager: WebSocketManager

    private var isStreaming = false
    private var activeCameraId: Long = 1L

    // 카메라 권한 요청 런처
    private val cameraPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) {
            binding.permissionOverlay.visibility = View.GONE
            cameraManager.startCamera()
        } else {
            binding.permissionOverlay.visibility = View.VISIBLE
            showToast(getString(R.string.permission_camera_denied))
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        preferences = AppPreferences(this)
        activeCameraId = preferences.cameraId

        initWebSocketManager()
        initCameraManager()
        initViews()
        loadPreferencesToUi()
        checkCameraPermission()
    }

    private fun initWebSocketManager() {
        webSocketManager = WebSocketManager(
            stateListener = { state ->
                runOnUiThread { updateConnectionStateUi(state) }
            },
            statsListener = { stats ->
                runOnUiThread { updateStatisticsUi(stats) }
            },
            onMaxFpsUpdated = { maxFps ->
                runOnUiThread {
                    cameraManager.updateServerMaxFps(maxFps)
                    binding.tvLiveFps.text = "FPS: 0.0 / $maxFps"
                }
            }
        )
    }

    private fun initCameraManager() {
        cameraManager = CameraManager(
            context = this,
            lifecycleOwner = this,
            previewView = binding.previewView,
            onFrameCaptured = { frameId, payload ->
                webSocketManager.sendBinaryFrame(frameId, payload)
            }
        )
    }

    private fun initViews() {
        // 설정 패널 토글 버튼
        binding.btnToggleSettings.setOnClickListener {
            val isVisible = binding.settingsPanel.visibility == View.VISIBLE
            binding.settingsPanel.visibility = if (isVisible) View.GONE else View.VISIBLE
        }

        // 카메라 선택 라디오 버튼 리스너 (요구사항 1 & 2)
        binding.rbCamera1.setOnClickListener {
            binding.etCameraId.setText("1")
        }
        binding.rbCamera2.setOnClickListener {
            binding.etCameraId.setText("2")
        }
        binding.rbCameraCustom.setOnClickListener {
            binding.etCameraId.requestFocus()
        }

        // 직접 입력 필드 변경 시 라디오 버튼 싱크
        binding.etCameraId.doAfterTextChanged { text ->
            val value = text?.toString()?.trim()
            when (value) {
                "1" -> if (!binding.rbCamera1.isChecked) binding.rbCamera1.isChecked = true
                "2" -> if (!binding.rbCamera2.isChecked) binding.rbCamera2.isChecked = true
                else -> if (!binding.rbCameraCustom.isChecked) binding.rbCameraCustom.isChecked = true
            }
        }

        // 설정 저장 및 적용 버튼 (요구사항 3: 카메라 변경 시 기존 연결 종료 후 새 연결)
        binding.btnSaveSettings.setOnClickListener {
            val previousCameraId = activeCameraId
            saveUiToPreferences()
            val newCameraId = preferences.cameraId

            binding.settingsPanel.visibility = View.GONE
            updateCameraBadge(newCameraId)

            if (isStreaming && previousCameraId != newCameraId) {
                // 송출 중 카메라가 변경된 경우: 기존 연결 정상 종료 후 새 cameraId로 재연결 (미리보기는 유지)
                reconnectWithNewCamera(newCameraId)
                showToast("카메라가 ${getCameraName(newCameraId)}(으)로 변경되어 재연결합니다.")
            } else {
                showToast("설정이 저장되었습니다.")
            }
        }

        // 송출 시작 버튼
        binding.btnStartStream.setOnClickListener {
            saveUiToPreferences()
            startStreaming()
        }

        // 송출 중지 버튼
        binding.btnStopStream.setOnClickListener {
            stopStreaming()
        }

        // 권한 요청 버튼
        binding.btnRequestPermission.setOnClickListener {
            if (shouldShowRequestPermissionRationale(Manifest.permission.CAMERA)) {
                cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
            } else {
                val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                    data = Uri.fromParts("package", packageName, null)
                }
                startActivity(intent)
            }
        }
    }

    private fun loadPreferencesToUi() {
        binding.etServerUrl.setText(preferences.serverUrl)
        val camId = preferences.cameraId
        binding.etCameraId.setText(camId.toString())
        binding.etCameraToken.setText(preferences.cameraToken)

        when (camId) {
            1L -> binding.rbCamera1.isChecked = true
            2L -> binding.rbCamera2.isChecked = true
            else -> binding.rbCameraCustom.isChecked = true
        }

        updateCameraBadge(camId)
    }

    private fun saveUiToPreferences() {
        val url = binding.etServerUrl.text?.toString()?.trim().orEmpty()
        val cameraIdStr = binding.etCameraId.text?.toString()?.trim().orEmpty()
        val token = binding.etCameraToken.text?.toString()?.trim().orEmpty()

        if (url.isNotBlank()) {
            preferences.serverUrl = url
        }
        val parsedId = cameraIdStr.toLongOrNull() ?: 1L
        preferences.cameraId = parsedId
        activeCameraId = parsedId
        preferences.cameraToken = token
    }

    private fun getCameraName(cameraId: Long): String {
        return when (cameraId) {
            1L -> "카메라 1 (T1 3번 출국장)"
            2L -> "카메라 2 (T1 스카이허브 라운지)"
            else -> "카메라 (ID: $cameraId)"
        }
    }

    private fun updateCameraBadge(cameraId: Long) {
        binding.tvCurrentCameraBadge.text = "[${getCameraName(cameraId)}]"
    }

    private fun checkCameraPermission() {
        when {
            ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED -> {
                binding.permissionOverlay.visibility = View.GONE
                // 서버 연결과 무관하게 카메라 미리보기 즉시 시작
                cameraManager.startCamera()
            }
            else -> {
                binding.permissionOverlay.visibility = View.VISIBLE
                cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
            }
        }
    }

    private fun startStreaming() {
        val serverUrl = preferences.serverUrl
        val cameraId = preferences.cameraId
        val token = preferences.cameraToken

        if (serverUrl.isBlank()) {
            showToast("서버 주소를 올바르게 입력해주세요.")
            binding.settingsPanel.visibility = View.VISIBLE
            return
        }

        isStreaming = true
        activeCameraId = cameraId
        updateControlButtons(streaming = true)
        binding.settingsPanel.visibility = View.GONE
        updateCameraBadge(cameraId)

        // v0.4 표준 포맷터 적용 (cameraId: 정수, 헤더 길이 N + JSON + JPEG)
        val formatter = YoloDemoV4PayloadFormatter()

        // 카메라 프레임 분석 및 압축 시작 (frameId는 연결마다 1부터 시작)
        cameraManager.startStreaming(cameraId, formatter)

        // WebSocket 연결 시작 (URL: ws://.../ws/yolo/camera?cameraId=<cameraId>&token=<token>)
        webSocketManager.startStreaming(serverUrl, cameraId, token)
    }

    /**
     * 요구사항 3: 송출 중 카메라 변경 시 기존 WebSocket 연결을 정상 종료하고 새 cameraId로 재연결
     * 요구사항 4: 카메라 미리보기(Preview)는 끊김 없이 그대로 유지
     */
    private fun reconnectWithNewCamera(newCameraId: Long) {
        val serverUrl = preferences.serverUrl
        val token = preferences.cameraToken
        activeCameraId = newCameraId

        // 1. 기존 WebSocket 연결 정상 종료
        webSocketManager.stopStreaming()

        // 2. 새 cameraId 및 포맷터로 카메라 프레임 분석 갱신 (frameId 1부터 리셋, 프리뷰는 유지)
        val formatter = YoloDemoV4PayloadFormatter()
        cameraManager.startStreaming(newCameraId, formatter)

        // 3. 새 cameraId로 WebSocket 재연결
        webSocketManager.startStreaming(serverUrl, newCameraId, token)
    }

    private fun stopStreaming() {
        isStreaming = false
        updateControlButtons(streaming = false)

        // 카메라 분석 중지 (미리보기는 유지됨)
        cameraManager.stopStreaming()

        // WebSocket 연결 해제
        webSocketManager.stopStreaming()
    }

    private fun updateControlButtons(streaming: Boolean) {
        binding.btnStartStream.isEnabled = !streaming
        binding.btnStopStream.isEnabled = streaming
    }

    private fun updateConnectionStateUi(state: ConnectionState) {
        val (text, colorRes) = when (state) {
            is ConnectionState.Disconnected -> {
                Pair(state.reason ?: getString(R.string.status_disconnected), R.color.status_disconnected)
            }
            is ConnectionState.Connecting -> {
                Pair(getString(R.string.status_connecting), R.color.status_connecting)
            }
            is ConnectionState.Connected -> {
                Pair(getString(R.string.status_connected), R.color.status_connected)
            }
            is ConnectionState.Streaming -> {
                val fpsText = if (state.fps > 0) " (%.1f FPS)".format(state.fps) else ""
                Pair("영상 송출 중$fpsText", R.color.status_streaming)
            }
            is ConnectionState.Reconnecting -> {
                Pair("재연결 시도 중… (#${state.attempt}, ${state.delaySec}초 후)", R.color.status_reconnecting)
            }
            is ConnectionState.Error -> {
                Pair(state.message, R.color.status_error)
            }
        }

        binding.tvStatus.text = text
        val color = ContextCompat.getColor(this, colorRes)
        (binding.viewStatusDot.background as? GradientDrawable)?.setColor(color)
            ?: binding.viewStatusDot.setBackgroundColor(color)
    }

    private fun updateStatisticsUi(stats: StreamStatistics) {
        binding.tvFrameStats.text = getString(
            R.string.label_frame_stats,
            stats.currentFrameId,
            stats.sentFrames,
            stats.droppedFrames
        )
        binding.tvLiveFps.text = getString(R.string.label_live_fps, stats.currentFps)
    }

    private fun showToast(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
    }

    override fun onResume() {
        super.onResume()
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            binding.permissionOverlay.visibility = View.GONE
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        cameraManager.shutdown()
        webSocketManager.stopStreaming()
    }
}
