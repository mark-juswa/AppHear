#include <jni.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <vector>

namespace {
constexpr int kPoseWidth = 192;
constexpr int kPoseHeight = 256;
constexpr int kHandSize = 224;

struct Sample {
    int a;
    int b;
    int c;
    int d;
    float wx;
    float wy;
};

struct Kernel {
    int width;
    int height;
    int row_stride;
    int pixel_stride;
    int rotation;
    int source_width;
    int source_height;
    size_t source_bytes;
    std::vector<uint8_t> raw;
    std::vector<Sample> pose_samples;

    Kernel(int w, int h, int row, int pixel, int rot)
        : width(w), height(h), row_stride(row), pixel_stride(pixel), rotation(rot) {
        if (w <= 0 || h <= 0 || w > 16384 || h > 16384 || pixel < 4 ||
            int64_t(row) < int64_t(w - 1) * pixel + 4 ||
            !(rot == 0 || rot == 90 || rot == 180 || rot == 270)) {
            throw std::invalid_argument("VNEXT_NATIVE_GEOMETRY_INVALID");
        }
        source_width = (rot == 90 || rot == 270) ? h : w;
        source_height = (rot == 90 || rot == 270) ? w : h;
        source_bytes = size_t(h - 1) * row + size_t(w - 1) * pixel + 4;
        if (source_bytes > 256 * 1024 * 1024) {
            throw std::invalid_argument("VNEXT_NATIVE_SOURCE_SIZE_INVALID");
        }
        raw.resize(source_bytes);
        pose_samples.resize(kPoseWidth * kPoseHeight);
        const float center_x = source_width * 0.5f;
        const float center_y = source_height * 0.5f;
        float scale_x = source_width * 1.25f;
        float scale_y = source_height * 1.25f;
        constexpr float aspect = float(kPoseWidth) / float(kPoseHeight);
        if (scale_x > scale_y * aspect) {
            scale_y = scale_x / aspect;
        } else {
            scale_x = scale_y * aspect;
        }
        for (int y = 0; y < kPoseHeight; ++y) {
            const float sy = center_y + (y - 128.0f) * scale_x / 192.0f;
            for (int x = 0; x < kPoseWidth; ++x) {
                const float sx = center_x + (x - 96.0f) * scale_x / 192.0f;
                pose_samples[y * kPoseWidth + x] = sample(sx, sy);
            }
        }
    }

    int offset(int x, int y) const {
        if (x < 0 || x >= source_width || y < 0 || y >= source_height) return -1;
        int raw_x;
        int raw_y;
        switch (rotation) {
            case 90:
                raw_x = y;
                raw_y = height - 1 - x;
                break;
            case 180:
                raw_x = width - 1 - x;
                raw_y = height - 1 - y;
                break;
            case 270:
                raw_x = width - 1 - y;
                raw_y = x;
                break;
            default:
                raw_x = x;
                raw_y = y;
        }
        return raw_y * row_stride + raw_x * pixel_stride;
    }

    Sample sample(float x, float y) const {
        const int x0 = int(std::floor(x));
        const int y0 = int(std::floor(y));
        return {
            offset(x0, y0),
            offset(x0 + 1, y0),
            offset(x0, y0 + 1),
            offset(x0 + 1, y0 + 1),
            x - x0,
            y - y0,
        };
    }

    float channel(const Sample& value, int channel_index) const {
        const auto read = [&](int base) -> float {
            return base < 0 ? 0.0f : float(raw[size_t(base + channel_index)]);
        };
        const float top = read(value.a) * (1.0f - value.wx) + read(value.b) * value.wx;
        const float bottom = read(value.c) * (1.0f - value.wx) + read(value.d) * value.wx;
        return top * (1.0f - value.wy) + bottom * value.wy;
    }

    void set_source(const uint8_t* source) { std::memcpy(raw.data(), source, source_bytes); }

    void pose(float* output) const {
        constexpr float mean[] = {123.675f, 116.28f, 103.53f};
        constexpr float std[] = {58.395f, 57.12f, 57.375f};
        constexpr int plane = kPoseWidth * kPoseHeight;
        for (int index = 0; index < plane; ++index) {
            for (int channel_index = 0; channel_index < 3; ++channel_index) {
                output[channel_index * plane + index] =
                    (channel(pose_samples[index], channel_index) - mean[channel_index]) /
                    std[channel_index];
            }
        }
    }

    void hand(float center_x, float center_y, float side, float* output) const {
        if (!std::isfinite(center_x) || !std::isfinite(center_y) || !std::isfinite(side) ||
            side <= 0.0f) {
            throw std::invalid_argument("VNEXT_NATIVE_ROI_INVALID");
        }
        const float left = center_x - side * 0.5f;
        const float top = center_y - side * 0.5f;
        for (int y = 0; y < kHandSize; ++y) {
            const float source_y = top + float(y) / 223.0f * side;
            for (int x = 0; x < kHandSize; ++x) {
                const float source_x = left + float(x) / 223.0f * side;
                const Sample value = sample(source_x, source_y);
                const int base = (y * kHandSize + x) * 3;
                for (int channel_index = 0; channel_index < 3; ++channel_index) {
                    output[base + channel_index] = channel(value, channel_index) / 255.0f;
                }
            }
        }
    }
};

void error(JNIEnv* environment, const char* message) {
    environment->ThrowNew(environment->FindClass("java/lang/IllegalArgumentException"), message);
}

Kernel* kernel(jlong handle) {
    if (handle == 0) throw std::invalid_argument("VNEXT_NATIVE_CLOSED_HANDLE");
    return reinterpret_cast<Kernel*>(handle);
}
}  // namespace

#define JNI_FN(name) Java_com_example_apphear_perceptionvnext_PerceptionVNextNative_##name

extern "C" JNIEXPORT jlong JNICALL JNI_FN(create)(
    JNIEnv* environment,
    jobject,
    jint width,
    jint height,
    jint row_stride,
    jint pixel_stride,
    jint rotation) {
    try {
        return reinterpret_cast<jlong>(
            new Kernel(width, height, row_stride, pixel_stride, rotation));
    } catch (const std::exception& exception) {
        error(environment, exception.what());
        return 0;
    }
}

extern "C" JNIEXPORT void JNICALL JNI_FN(destroy)(JNIEnv*, jobject, jlong handle) {
    delete reinterpret_cast<Kernel*>(handle);
}

extern "C" JNIEXPORT void JNICALL JNI_FN(preprocess)(
    JNIEnv* environment,
    jobject,
    jlong handle,
    jobject source,
    jint base,
    jint remaining,
    jobject output) {
    try {
        auto* value = kernel(handle);
        auto* input = static_cast<uint8_t*>(environment->GetDirectBufferAddress(source));
        auto* destination = static_cast<float*>(environment->GetDirectBufferAddress(output));
        const auto input_capacity = environment->GetDirectBufferCapacity(source);
        const auto output_capacity = environment->GetDirectBufferCapacity(output);
        if (!input || !destination || base < 0 || remaining < 0 ||
            size_t(remaining) < value->source_bytes || int64_t(base) + remaining > input_capacity ||
            output_capacity != int64_t(3 * kPoseWidth * kPoseHeight * sizeof(float))) {
            throw std::invalid_argument("VNEXT_NATIVE_DIRECT_BUFFER_BOUNDS");
        }
        value->set_source(input + base);
        value->pose(destination);
    } catch (const std::exception& exception) {
        error(environment, exception.what());
    }
}

extern "C" JNIEXPORT void JNICALL JNI_FN(crop)(
    JNIEnv* environment,
    jobject,
    jlong handle,
    jfloat center_x,
    jfloat center_y,
    jfloat side,
    jobject output) {
    try {
        auto* destination = static_cast<float*>(environment->GetDirectBufferAddress(output));
        if (!destination || environment->GetDirectBufferCapacity(output) !=
                                int64_t(kHandSize * kHandSize * 3 * sizeof(float))) {
            throw std::invalid_argument("VNEXT_NATIVE_CROP_BUFFER_BOUNDS");
        }
        kernel(handle)->hand(center_x, center_y, side, destination);
    } catch (const std::exception& exception) {
        error(environment, exception.what());
    }
}

extern "C" JNIEXPORT jintArray JNICALL JNI_FN(geometry)(
    JNIEnv* environment,
    jobject,
    jlong handle) {
    try {
        auto* value = kernel(handle);
        const int result_values[] = {value->source_width, value->source_height};
        auto result = environment->NewIntArray(2);
        environment->SetIntArrayRegion(result, 0, 2, result_values);
        return result;
    } catch (const std::exception& exception) {
        error(environment, exception.what());
        return nullptr;
    }
}
