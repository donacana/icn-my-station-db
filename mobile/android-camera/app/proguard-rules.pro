# Proguard rules for ICN Camera Sender
# Keep OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**

# Keep CameraX
-keep class androidx.camera.** { *; }
