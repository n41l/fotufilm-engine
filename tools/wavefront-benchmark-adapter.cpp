// C-only adapter. The common benchmark source is byte-identical to clean R's driver.
#include "../Sources/FotufilmHalide/FotufilmHalideWavefront.h"
#include "HalideRuntime.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>

#ifndef FOTUFILM_WAVEFRONT_BAND
#define FOTUFILM_WAVEFRONT_BAND 256
#endif
#if FOTUFILM_WAVEFRONT_TRACE
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <mutex>
static int generation=0,phase=0;
static std::atomic<int> committed{0},completed{0};
static std::mutex drain_mutex;
static std::condition_variable drained;
static void (*original_commit)(id,SEL);
static void observed_commit(id object,SEL selector) {
    if (phase) {
        const int ordinal=++committed,tag_generation=generation,tag_phase=phase;
        id<MTLCommandBuffer> buffer=object;
        const void *queue=(__bridge const void *)buffer.commandQueue;
        [buffer addCompletedHandler:^(id<MTLCommandBuffer> done) {
            std::fprintf(stderr,"GPU_COMPLETION %d %d %d %p %.12f %.12f %ld\n",
                ordinal,tag_generation,tag_phase,queue,done.GPUStartTime,done.GPUEndTime,(long)done.status);
            {std::lock_guard<std::mutex> lock(drain_mutex);++completed;}
            drained.notify_all();
        }];
    }
    original_commit(object,selector);
}
static bool install_observer() {
    static const bool installed=[] {
        id<MTLDevice> device=MTLCreateSystemDefaultDevice();
        id<MTLCommandQueue> queue=[device newCommandQueue];
        id<MTLCommandBuffer> buffer=[queue commandBuffer];
        Method method=class_getInstanceMethod(object_getClass(buffer),@selector(commit));
        if (!method) return false;
        original_commit=reinterpret_cast<decltype(original_commit)>(method_setImplementation(method,
            reinterpret_cast<IMP>(observed_commit)));
        [queue release];
        return original_commit!=nullptr;
    }();
    return installed;
}
static bool drain_observer() {
    std::unique_lock<std::mutex> lock(drain_mutex);
    return drained.wait_for(lock,std::chrono::seconds(5),[]{return completed.load()==committed.load();});
}
static void rows_trace(void *context,int32_t event,int32_t band,int32_t start,int32_t rows,int32_t slot) noexcept {
    generation=band+1;
    phase=event==1 ? 1 : event==3 ? 2 : 0;
    if (event==1) std::fprintf(stderr,"ROW_PLAN %d %d %d %d %d\n",band,start,rows,slot,
        static_cast<FotufilmWavefrontResult *>(context)->ring_rows);
    if (event==3) std::fprintf(stderr,"CONSUMER_PLAN %d %d %d\n",band,start,rows);
    if (event==5) std::fprintf(stderr,"BAND_COMPLETE %d\n",band);
}
static int32_t trace(void *, const halide_trace_event_t *event) {
    static int32_t identity=0;
    if (event->event==halide_trace_produce && event->dimensions==6)
        std::fprintf(stderr,"PRODUCE %s %d %d %d %d %d %d\n",event->func,
            event->coordinates[0],event->coordinates[1],event->coordinates[2],
            event->coordinates[3],event->coordinates[4],event->coordinates[5]);
    return ++identity;
}
#endif
extern "C" int32_t fotufilm_wavefront_bench_process_linear_float(
    const float *input, float *output, int32_t width, int32_t height,
    int32_t origin_x, int32_t origin_y, const float *configuration,
    const float *exposure_lut, const float *film_output_lut,
    const float *paper_output_lut, int32_t lut_dimension,
    uint64_t spectral_cache_id, int32_t feature_mask, uint32_t seed) {
#if FOTUFILM_WAVEFRONT_TRACE
    if (!install_observer()) return -91;
    halide_set_custom_trace(trace);
#endif
    FotufilmWavefrontOptions options;
    options.rows = FOTUFILM_WAVEFRONT_BAND;
#if FOTUFILM_WAVEFRONT_RUNTIME_BAND
    // Diagnostic-only profile selection, fixed once before any measurement window.
    static const int selected_rows = [] {
        const char *value = std::getenv("FOTUFILM_WAVEFRONT_BENCH_ROWS");
        if (!value) return int(FOTUFILM_WAVEFRONT_BAND);
        char *end = nullptr;
        const long rows = std::strtol(value,&end,10);
        return end && !*end && (rows==64 || rows==128 || rows==256 || rows==512) ? int(rows) : 0;
    }();
    if (!selected_rows) return -94;
    options.rows = selected_rows;
#endif
    FotufilmWavefrontResult result;
#if FOTUFILM_WAVEFRONT_TRACE
    options.trace=rows_trace;
    options.trace_context=&result;
#endif
    const int status = fotufilm_halide_metal_process_linear_float_wavefront(
        input, output, width, height, origin_x, origin_y, configuration,
        exposure_lut, film_output_lut, paper_output_lut, lut_dimension,
        spectral_cache_id, feature_mask, seed, &options, &result);
#if FOTUFILM_WAVEFRONT_TRACE
    if (!drain_observer()) {
        std::fprintf(stderr,"GPU_COMPLETION_DRAIN_FAILED %d %d\n",committed.load(),completed.load());
        return -92;
    }
#endif
    static thread_local bool reported = false;
    if (!reported) {
        std::fprintf(stderr, "WAVEFRONT_POLICY requested=%d actual=%d rows=%d reason=%s\n",
            result.requested_mode, result.actual_mode, options.rows, result.reason);
        std::fprintf(stderr,"WAVEFRONT_COUNTS rows=%d source_calls=%d consumer_calls=%d ring_rows=%d\n",
            result.producer_rows,result.producer_calls,result.consumer_calls,result.ring_rows);
        reported = true;
    }
    return status;
}
