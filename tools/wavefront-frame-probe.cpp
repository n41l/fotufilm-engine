// One full-frame call for stock capability discovery. Cold call time is diagnostic only.
#include "FotufilmHalide.h"
#include "FotufilmResolvedFrameParams.h"
#include "FotufilmHalideGeometry.h"
#include <CommonCrypto/CommonDigest.h>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

extern "C" {
const char *fotufilm_bench_actual_variant = nullptr;
int fotufilm_bench_aot_calls = 0;
int fotufilm_bench_trace_variants = 0;
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    FILE *pack = std::fopen(argv[1], "rb");
    if (!pack) return 2;
    uint32_t h[10];
    if (std::fread(h, sizeof(h), 1, pack) != 1 || std::memcmp(h, "FSWP", 4)) return 2;
    if (h[1] != 1 && h[1] != 2) {
        std::printf("{\"status\":\"unsupported\",\"reason\":\"pack construction is outside this frame API\"}\n");
        std::fclose(pack);
        return 0;
    }
    if (h[2] < 1 || h[2] > 8192 || h[3] < 1 || h[3] > 8192
        || h[6] != FOTUFILM_FRAME_CONFIGURATION_COUNT || h[7] != 33 || h[8] != 33*33*33*4) return 2;
    std::vector<float> config(h[6]), exposure(h[8]), film(h[8]), paper(h[8]);
    for (auto *v : {&config, &exposure, &film, &paper}) {
        if (std::fread(v->data(), sizeof(float), v->size(), pack) != v->size()) return 2;
    }
    std::fclose(pack);
    const int width = int(h[2]), height = int(h[3]);
    const int32_t mask = int32_t(h[4]) | FOTUFILM_FRAME_FLOAT_IO | FOTUFILM_FRAME_REALTIME;
    std::vector<float> input(size_t(width)*height*4), output(input.size(), std::nanf(""));
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            const size_t i = (size_t(y)*width+x)*4;
            input[i] = 0.03f + float((x*7+y*13)%997)/997;
            input[i+1] = (x == width/2 || y%128 == 0) ? 4.0f : 0.18f;
            input[i+2] = float((x^y)&31)/31;
            input[i+3] = 1.0f;
        }
    }
    const auto start = std::chrono::steady_clock::now();
    const int error = fotufilm_halide_metal_process_linear_float(input.data(), output.data(),
        width, height, 0, 0, config.data(), exposure.data(), film.data(), paper.data(),
        33, 1, mask, h[5]);
    const double ms = std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now()-start).count();
    bool finite = !error, alpha = !error;
    if (!error) {
        for (size_t i = 0; i < output.size(); ++i) finite = finite && std::isfinite(output[i]);
        for (size_t i = 3; i < output.size(); i += 4) alpha = alpha && output[i] == input[i];
    }
    unsigned char digest[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256(output.data(), CC_LONG(output.size()*sizeof(float)), digest);
    char hash[65];
    for (int i=0;i<32;++i) std::snprintf(hash+2*i, 3, "%02x", digest[i]);
    fotufilm::ResolvedFrameParams frame(config.data(), width, height, h[5], 0, 0, 0);
    const float *configuration = config.data();
    const int32_t feature_mask = mask;
    // The external driver extracts this diagnostic calculation verbatim from R's
    // shim. It never selects or overrides the actual runtime function.
#include FOTUFILM_BENCH_REACH_PROBE
    std::printf("{\"status\":\"%s\",\"error\":%d,\"width\":%d,\"height\":%d,"
        "\"mask\":%d,\"seed\":%u,\"actual_variant\":\"%s\",\"aot_calls\":%d,"
        "\"cold_call_ms_diagnostic_only\":%.6f,\"finite\":%s,\"alpha_exact\":%s,"
        "\"output_sha256\":\"%s\",\"grain_model\":%.0f,\"grain_radius\":%d,"
        "\"mtf_radii\":[%d,%d,%d],\"mtf_luma_radius\":%d,"
        "\"spatial_reach\":%lld,\"upstream_window_reach_limit\":%d}\n",
        (!error && finite && alpha) ? "success" : "failure", error, width, height, mask,
        h[5], fotufilm_bench_actual_variant ? fotufilm_bench_actual_variant : "none",
        fotufilm_bench_aot_calls, ms, finite ? "true" : "false", alpha ? "true" : "false",
        hash, config[FOTUFILM_CONFIG_GRAIN_MODE], frame.grain_radius,
        frame.mtf_radius_0, frame.mtf_radius_1, frame.mtf_radius_2, frame.mtf_luma_radius,
        static_cast<long long>(std::max(image_reach, grain_reach)), fotufilm::kWindowMaximumReach);
    return !error && finite && alpha ? 0 : 1;
}
