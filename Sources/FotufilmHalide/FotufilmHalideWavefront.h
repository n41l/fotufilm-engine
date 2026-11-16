#pragma once
// Private experimental whole-frame entry point; no public control or ABI change.
#include "include/FotufilmHalide.h"

// Diagnostic events: 1/2 producer enqueue begin/end, 3/4 consumer begin/end,
// 5 consumer GPU completion. The sink is synchronous and call-scoped.
using FotufilmWavefrontTrace = void (*)(void *, int32_t, int32_t, int32_t, int32_t, int32_t) noexcept;
struct FotufilmWavefrontOptions {
    uint32_t size = sizeof(FotufilmWavefrontOptions);
    uint32_t version = 1;
    int32_t mode = 1; // 0: original automatic selection, 1: request research wavefront.
    FotufilmWavefrontTrace trace = nullptr;
    void *trace_context = nullptr;
    int32_t test_fail_after_source_call = 0; // Honored only in fault-injection test builds.
    int32_t rows = 256; // 64, 128, 256, 512 or 1080. Unsupported requests retain original selection.
};
struct FotufilmWavefrontResult {
    int32_t requested_mode = 0;
    int32_t actual_mode = -1; // No pipeline selected yet.
    int32_t producer_rows = 0;
    int32_t producer_calls = 0;
    int32_t consumer_calls = 0;
    int32_t ring_rows = 0;
    int32_t drain_status = -1;
    const char *reason = "not executed"; // Static lifetime; never caller-owned.
};

// Synchronous, host-buffer-only, complete frames. Options belong to this call alone.
// Actual mode is selected before output writes. Errors from an admitted kernel propagate;
// no failed experimental call is retried as legacy over partially written output.
extern "C" int32_t fotufilm_halide_metal_process_linear_float_wavefront(
    const float *input, float *output, int32_t width, int32_t height,
    int32_t origin_x, int32_t origin_y, const float *configuration,
    const float *exposure_lut, const float *film_output_lut,
    const float *paper_output_lut, int32_t lut_dimension,
    uint64_t spectral_cache_id, int32_t feature_mask, uint32_t seed,
    const FotufilmWavefrontOptions *options, FotufilmWavefrontResult *result);
