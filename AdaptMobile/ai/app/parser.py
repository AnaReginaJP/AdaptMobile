import re
import json

def parse_project_file(filename: str, content: str) -> dict:
    """
    Parses an uploaded project file (package.json, build.gradle, AndroidManifest.xml,
    pubspec.yaml, Podfile, README.md, etc.) and extracts detected framework,
    libraries, dependencies, min SDKs, and characteristics.
    """
    fname = filename.lower()
    extracted = {
        "filename": filename,
        "format": "unknown",
        "framework": "Native / Unspecified",
        "language": "Unknown",
        "target_platforms": ["Android", "iOS"],
        "dependencies": [],
        "heavy_features": [],
        "min_android_sdk": None,
        "min_ios_sdk": None,
        "is_game_or_3d": False,
        "uses_ml": False,
        "uses_camera_ar": False,
        "uses_heavy_media": False
    }

    # 1. package.json (React Native, Expo, Ionic, Cordova, Capacitor, Web/PWA)
    if fname.endswith("package.json"):
        extracted["format"] = "package.json"
        try:
            data = json.loads(content)
            extracted["project_name"] = data.get("name", "MobileProject")
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            extracted["dependencies"] = list(deps.keys())

            if "react-native" in deps or "@react-native/core" in deps:
                extracted["framework"] = "React Native"
                extracted["language"] = "TypeScript/JavaScript"
                if "expo" in deps:
                    extracted["framework"] = "React Native (Expo)"
            elif "@ionic/react" in deps or "@ionic/vue" in deps or "@ionic/angular" in deps:
                extracted["framework"] = "Ionic"
                extracted["language"] = "TypeScript/Web"
            elif "@capacitor/core" in deps:
                extracted["framework"] = "Capacitor"
                extracted["language"] = "TypeScript/Web"
            elif "cordova" in deps:
                extracted["framework"] = "Apache Cordova"
            elif "three" in deps or "@react-three/fiber" in deps:
                extracted["framework"] = "Web3D / React Native"

            # Check heavy dependencies
            dep_keys_lower = [k.lower() for k in deps.keys()]
            for dep in dep_keys_lower:
                if any(x in dep for x in ["three", "fiber", "babylon", "filament", "3d", "expo-gl"]):
                    extracted["heavy_features"].append("3D Graphics / WebGL")
                    extracted["is_game_or_3d"] = True
                if any(x in dep for x in ["tensorflow", "tflite", "mediapipe", "onnx", "vision-camera"]):
                    extracted["heavy_features"].append("Machine Learning / Vision AI")
                    extracted["uses_ml"] = True
                if any(x in dep for x in ["camera", "webrtc", "vision", "ar", "arkit", "arcore"]):
                    extracted["heavy_features"].append("Camera / AR Features")
                    extracted["uses_camera_ar"] = True
                if any(x in dep for x in ["video", "ffmpeg", "player", "audio"]):
                    extracted["heavy_features"].append("Video / High-Res Media")
                    extracted["uses_heavy_media"] = True
                if any(x in dep for x in ["realm", "watermelondb", "sqlite"]):
                    extracted["heavy_features"].append("Local Embedded Database")
        except Exception:
            pass

    # 2. build.gradle or build.gradle.kts (Android)
    elif "gradle" in fname:
        extracted["format"] = "gradle"
        extracted["target_platforms"] = ["Android"]
        extracted["language"] = "Kotlin / Java"
        extracted["framework"] = "Android Native"

        min_sdk_match = re.search(r'minSdk(?:Version)?\s*=?\s*([0-9]+)', content)
        if min_sdk_match:
            sdk_num = int(min_sdk_match.group(1))
            extracted["min_android_sdk"] = sdk_num

        if "androidx.compose" in content:
            extracted["framework"] = "Android Native (Jetpack Compose)"
        elif "com.unity3d" in content or "unityLibrary" in content:
            extracted["framework"] = "Unity Android Export"
            extracted["is_game_or_3d"] = True
        elif "org.godotengine" in content:
            extracted["framework"] = "Godot Android"
            extracted["is_game_or_3d"] = True
        elif "flutter" in content:
            extracted["framework"] = "Flutter Android"

        # Check heavy modules
        if re.search(r'org.tensorflow|org.pytorch|mediapipe', content, re.I):
            extracted["heavy_features"].append("Embedded Machine Learning (TensorFlow/PyTorch)")
            extracted["uses_ml"] = True
        if re.search(r'camerax|camera2|filament|vulkan|sceneview|arcore', content, re.I):
            extracted["heavy_features"].append("CameraX / ARCore / 3D Scene")
            extracted["uses_camera_ar"] = True
        if re.search(r'exoplayer|media3|ffmpeg', content, re.I):
            extracted["heavy_features"].append("ExoPlayer / Media Streaming")
            extracted["uses_heavy_media"] = True

    # 3. AndroidManifest.xml
    elif "androidmanifest" in fname:
        extracted["format"] = "manifest"
        extracted["target_platforms"] = ["Android"]
        extracted["framework"] = "Android Native"
        min_sdk_match = re.search(r'android:minSdkVersion\s*=\s*["\']([0-9]+)["\']', content)
        if min_sdk_match:
            extracted["min_android_sdk"] = int(min_sdk_match.group(1))
        if "android.hardware.camera.ar" in content or "com.google.ar.core" in content:
            extracted["heavy_features"].append("ARCore Augmented Reality")
            extracted["uses_camera_ar"] = True
        if "android.hardware.vulkan.version" in content or "vulkan" in content.lower():
            extracted["heavy_features"].append("Vulkan Hardware Acceleration")
            extracted["is_game_or_3d"] = True

    # 4. pubspec.yaml (Flutter)
    elif "pubspec" in fname:
        extracted["format"] = "pubspec.yaml"
        extracted["framework"] = "Flutter"
        extracted["language"] = "Dart"
        extracted["target_platforms"] = ["Android", "iOS"]

        # Parse dependencies from yaml content lines
        deps = []
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and ":" in line:
                key = line.split(":")[0].strip()
                if key not in ["name", "description", "version", "environment", "flutter", "dev_dependencies", "dependencies"]:
                    deps.append(key)
        extracted["dependencies"] = deps[:40]

        dep_str = content.lower()
        if "camera" in dep_str or "ar_flutter_plugin" in dep_str:
            extracted["heavy_features"].append("Camera / AR Plugin")
            extracted["uses_camera_ar"] = True
        if "tflite_flutter" in dep_str or "google_ml_kit" in dep_str:
            extracted["heavy_features"].append("Google ML Kit / TensorFlow")
            extracted["uses_ml"] = True
        if "flame" in dep_str or "flutter_cube" in dep_str or "model_viewer" in dep_str:
            extracted["heavy_features"].append("Flame 2D/3D Engine")
            extracted["is_game_or_3d"] = True
        if "video_player" in dep_str or "chewie" in dep_str:
            extracted["heavy_features"].append("Video Player")
            extracted["uses_heavy_media"] = True

    # 5. Podfile / Package.swift (iOS)
    elif "podfile" in fname or fname.endswith(".swift"):
        extracted["format"] = "ios"
        extracted["framework"] = "iOS Native (Swift/ObjC)"
        extracted["language"] = "Swift"
        extracted["target_platforms"] = ["iOS"]
        platform_match = re.search(r"platform\s*:ios\s*,\s*['\"]([0-9\.]+)['\"]", content)
        if platform_match:
            extracted["min_ios_sdk"] = float(platform_match.group(1))

    # 6. README.md or general markdown/text
    elif fname.endswith(".md") or fname.endswith(".txt"):
        extracted["format"] = "documentation"
        c_lower = content.lower()
        if "flutter" in c_lower:
            extracted["framework"] = "Flutter"
            extracted["language"] = "Dart"
        elif "react native" in c_lower or "react-native" in c_lower:
            extracted["framework"] = "React Native"
            extracted["language"] = "TypeScript/JavaScript"
        elif "unity" in c_lower:
            extracted["framework"] = "Unity 3D"
            extracted["language"] = "C#"
            extracted["is_game_or_3d"] = True
        elif "unreal" in c_lower or "ue5" in c_lower:
            extracted["framework"] = "Unreal Engine"
            extracted["language"] = "C++ / Blueprints"
            extracted["is_game_or_3d"] = True
        elif "godot" in c_lower:
            extracted["framework"] = "Godot"
            extracted["is_game_or_3d"] = True
        elif "swift" in c_lower or "ios" in c_lower and "android" not in c_lower:
            extracted["framework"] = "iOS Native"
            extracted["language"] = "Swift"
            extracted["target_platforms"] = ["iOS"]
        elif "kotlin" in c_lower or "android" in c_lower and "ios" not in c_lower:
            extracted["framework"] = "Android Native"
            extracted["language"] = "Kotlin"
            extracted["target_platforms"] = ["Android"]

        # Look for mentions of features
        if any(w in c_lower for w in ["3d", "vulkan", "shader", "opengl", "gpu"]):
            extracted["heavy_features"].append("3D Rendering / Shaders")
            extracted["is_game_or_3d"] = True
        if any(w in c_lower for w in ["machine learning", "ai", "yolo", "neural", "vision", "tensorflow", "coreml"]):
            extracted["heavy_features"].append("AI / Machine Learning")
            extracted["uses_ml"] = True
        if any(w in c_lower for w in ["camera", "augmented reality", "arcore", "arkit"]):
            extracted["heavy_features"].append("Augmented Reality / Camera")
            extracted["uses_camera_ar"] = True
        if any(w in c_lower for w in ["video", "streaming", "4k"]):
            extracted["heavy_features"].append("High-Def Video Streaming")
            extracted["uses_heavy_media"] = True

    # Sin repetidos: varias dependencias pueden aportar la misma característica
    extracted["heavy_features"] = list(dict.fromkeys(extracted["heavy_features"]))

    return extracted
