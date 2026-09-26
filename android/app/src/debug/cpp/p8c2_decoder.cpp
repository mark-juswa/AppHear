// P8-C2 heatmap-only adapter. Geometry math is copied without alteration from
// p7dr2.cpp::Kernel::decode/restore; obsolete identity logits are intentionally absent.
#include <jni.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>

namespace {
struct Decoder {
    int w, h, rw, rh, left, top;
    std::array<uint8_t, 9216> admissible{};
    std::array<int, 50> peaks{};
    std::array<float, 50> maxima{};
    std::array<float, 100> xy{}, source{};

    Decoder(int width, int height) : w(width), h(height) {
        if (w <= 0 || h <= 0 || w > 16384 || h > 16384) {
            throw std::invalid_argument("GEOMETRY_INVALID");
        }
        double scale = std::min(384.0 / w, 384.0 / h);
        rw = std::max(1, int(std::floor(w * scale + .5)));
        rh = std::max(1, int(std::floor(h * scale + .5)));
        left = (384 - rw) / 2;
        top = (384 - rh) / 2;
        for (int i = 0; i < 96; ++i) for (int j = 0; j < 96; ++j) {
            double x = inverseX(4 * (j + .5) - .5);
            double y = inverseY(4 * (i + .5) - .5);
            admissible[i * 96 + j] = (x >= 0 && x <= w - 1 && y >= 0 && y <= h - 1);
        }
    }

    double inverseX(double x) const { return (x - left + .5) * w / rw - .5; }
    double inverseY(double y) const { return (y - top + .5) * h / rh - .5; }

    void decode(const float* heat) {
        if (std::none_of(admissible.begin(), admissible.end(), [](uint8_t v) { return v != 0; })) {
            throw std::invalid_argument("INPUT_TRANSFORM_INVALID");
        }
        maxima.fill(-std::numeric_limits<float>::infinity());
        peaks.fill(-1);
        int k = 0;
        for (int cell = 0; cell < 9216; ++cell) for (int p = 0; p < 50; ++p) {
            float v = heat[k++];
            if (!std::isfinite(v)) throw std::invalid_argument("NATIVE_OUTPUT_INVALID");
            if (admissible[cell] && v > maxima[p]) { maxima[p] = v; peaks[p] = cell; }
        }
        for (int p = 0; p < 50; ++p) {
            int px = peaks[p] % 96, py = peaks[p] / 96;
            double sum = 0, sx = 0, sy = 0;
            for (int i = std::max(0, py - 1); i <= std::min(95, py + 1); ++i)
                for (int j = std::max(0, px - 1); j <= std::min(95, px + 1); ++j) {
                    if (!admissible[i * 96 + j]) continue;
                    double weight = std::exp(double(heat[(i * 96 + j) * 50 + p]) - maxima[p]);
                    sum += weight; sx += j * weight; sy += i * weight;
                }
            xy[p * 2] = float(4 * (sx / sum + .5) - .5);
            xy[p * 2 + 1] = float(4 * (sy / sum + .5) - .5);
            source[p * 2] = float(inverseX(xy[p * 2]));
            source[p * 2 + 1] = float(inverseY(xy[p * 2 + 1]));
            if (!std::isfinite(source[p * 2]) || !std::isfinite(source[p * 2 + 1])) {
                throw std::invalid_argument("SOURCE_OUTPUT_NONFINITE");
            }
        }
    }
};

void error(JNIEnv* env, const char* message) {
    env->ThrowNew(env->FindClass("java/lang/IllegalArgumentException"), message);
}

Decoder* decoder(jlong handle) {
    if (!handle) throw std::invalid_argument("CLOSED_NATIVE_HANDLE");
    return reinterpret_cast<Decoder*>(handle);
}
}

#define JNI_FN(name) Java_com_example_apphear_p8c2_P8c2Native_##name

extern "C" JNIEXPORT jlong JNICALL JNI_FN(create)(JNIEnv* env, jobject, jint width, jint height) {
    try { return reinterpret_cast<jlong>(new Decoder(width, height)); }
    catch (const std::exception& e) { error(env, e.what()); return 0; }
}

extern "C" JNIEXPORT void JNICALL JNI_FN(destroy)(JNIEnv*, jobject, jlong handle) {
    delete reinterpret_cast<Decoder*>(handle);
}

extern "C" JNIEXPORT void JNICALL JNI_FN(decode)(
    JNIEnv* env, jobject, jlong handle, jobject heatmap,
    jfloatArray input_xy, jfloatArray source_xy, jintArray peaks
) {
    try {
        auto* state = decoder(handle);
        auto* heat = static_cast<float*>(env->GetDirectBufferAddress(heatmap));
        if (!heat || env->GetDirectBufferCapacity(heatmap) != 460800 * 4) {
            throw std::invalid_argument("DIRECT_BUFFER_BOUNDS_INVALID");
        }
        if (!input_xy || env->GetArrayLength(input_xy) != 100 ||
            !source_xy || env->GetArrayLength(source_xy) != 100 ||
            !peaks || env->GetArrayLength(peaks) != 50) {
            throw std::invalid_argument("READOUT_SHAPE_INVALID");
        }
        state->decode(heat);
        env->SetFloatArrayRegion(input_xy, 0, 100, state->xy.data());
        env->SetFloatArrayRegion(source_xy, 0, 100, state->source.data());
        env->SetIntArrayRegion(peaks, 0, 50, state->peaks.data());
    } catch (const std::exception& e) { error(env, e.what()); }
}
