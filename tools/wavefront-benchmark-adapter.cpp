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
#include <string>
#include <unordered_map>
static int generation=0,phase=0;
static std::atomic<int> committed{0},completed{0};
static std::mutex drain_mutex;
static std::condition_variable drained;
static void (*original_commit)(id,SEL);
static id (*original_pipeline)(id,SEL,id,NSError **);
static void (*original_set_pipeline)(id,SEL,id);
static std::mutex kernel_mutex;
static std::unordered_map<const void *,std::string> kernel_names;
static id observed_pipeline(id object,SEL selector,id<MTLFunction> function,NSError **error) {
    id result=original_pipeline(object,selector,function,error);
    if (result && function.name) {
        std::lock_guard<std::mutex> lock(kernel_mutex);
        kernel_names[(__bridge const void *)result]=function.name.UTF8String;
    }
    return result;
}
static void observed_set_pipeline(id object,SEL selector,id state) {
    if (phase) {
        std::lock_guard<std::mutex> lock(kernel_mutex);
        auto found=kernel_names.find((__bridge const void *)state);
        if (found!=kernel_names.end()) std::fprintf(stderr,"GPU_KERNEL %d %d %s\n",generation,phase,found->second.c_str());
    }
    original_set_pipeline(object,selector,state);
}
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
        id<MTLComputeCommandEncoder> encoder=[buffer computeCommandEncoder];
        Method pipeline=class_getInstanceMethod(object_getClass(device),@selector(newComputePipelineStateWithFunction:error:));
        Method bind=class_getInstanceMethod(object_getClass(encoder),@selector(setComputePipelineState:));
        Method method=class_getInstanceMethod(object_getClass(buffer),@selector(commit));
        if (!method || !pipeline || !bind) return false;
        original_pipeline=reinterpret_cast<decltype(original_pipeline)>(method_setImplementation(pipeline,
            reinterpret_cast<IMP>(observed_pipeline)));
        original_set_pipeline=reinterpret_cast<decltype(original_set_pipeline)>(method_setImplementation(bind,
            reinterpret_cast<IMP>(observed_set_pipeline)));
        [encoder endEncoding];
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
    phase=(event==1 || (event>=8&&event<=10)) ? 1 : event==3 ? 2 : event==6 ? 3 : 0;
    if (event==1) std::fprintf(stderr,"ROW_PLAN %d %d %d %d %d\n",band,start,rows,slot,
        static_cast<FotufilmWavefrontResult *>(context)->ring_rows);
    if(event>=8&&event<=10) std::fprintf(stderr,"FIELD_PLAN %d %d %d %d %d\n",event-8,band,start,rows,slot);
    if (event==6) std::fprintf(stderr,"LOG_PLAN %d %d %d %d 1024\n",band,start,rows,slot);
    if (event==3) std::fprintf(stderr,"CONSUMER_PLAN %d %d %d\n",band,start,rows);
    if (event==5) std::fprintf(stderr,"BAND_COMPLETE %d\n",band);
}
static int32_t trace(void *, const halide_trace_event_t *event) {
    static int32_t identity=0;
    if (event->event==halide_trace_produce && event->dimensions==6)
        std::fprintf(stderr,"PRODUCE %s %d %d %d %d %d %d\n",event->func,
            event->coordinates[0],event->coordinates[1],event->coordinates[2],
            event->coordinates[3],event->coordinates[4],event->coordinates[5]);
    else if (event->event==halide_trace_produce) {
        std::fprintf(stderr,"PRODUCE_ND %s %d",event->func,event->dimensions);
        for (int i=0;i<event->dimensions;++i) std::fprintf(stderr," %d",event->coordinates[i]);
        std::fputc('\n',stderr);
    }
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
        return end && !*end && (rows==64 || rows==128 || rows==256 || rows==512 || rows==1080) ? int(rows) : 0;
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
