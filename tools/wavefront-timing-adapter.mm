// Diagnostic-only clean-R adapter. The formal benchmark worker is unchanged.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include "FotufilmHalide.h"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <memory>
#include <mutex>
#include <set>
#include <sys/resource.h>
#include <time.h>
#include <vector>

struct GPUInterval { double start,end; long status; };
struct TimingCall {
    std::mutex mutex;
    std::condition_variable done;
    int committed=0,completed=0,waits=0;
    double waitSeconds=0;
    std::set<const void *> queues;
    std::vector<GPUInterval> gpu;
};
static std::shared_ptr<TimingCall> activeCall;
static void (*originalCommit)(id,SEL);
static void (*originalWait)(id,SEL);
static double wall() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
static double threadCPU() {
    timespec t{};
    return clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t)==0 ? t.tv_sec+t.tv_nsec*1e-9 : -1;
}
static double processCPU() {
    rusage r{};
    if (getrusage(RUSAGE_SELF,&r)) return -1;
    return r.ru_utime.tv_sec+r.ru_utime.tv_usec*1e-6+r.ru_stime.tv_sec+r.ru_stime.tv_usec*1e-6;
}
static void observedCommit(id object,SEL selector) {
    auto state=std::atomic_load(&activeCall);
    if (state) {
        id<MTLCommandBuffer> buffer=object;
        { std::lock_guard<std::mutex> guard(state->mutex);
          ++state->committed;state->queues.insert((__bridge const void *)buffer.commandQueue); }
        [buffer addCompletedHandler:^(id<MTLCommandBuffer> done) {
            { std::lock_guard<std::mutex> guard(state->mutex);
              state->gpu.push_back({done.GPUStartTime,done.GPUEndTime,(long)done.status});
              ++state->completed; }
            state->done.notify_all();
        }];
    }
    originalCommit(object,selector);
}
static void observedWait(id object,SEL selector) {
    auto state=std::atomic_load(&activeCall);
    const double begin=wall();originalWait(object,selector);const double elapsed=wall()-begin;
    if (state) { std::lock_guard<std::mutex> guard(state->mutex);
        ++state->waits;state->waitSeconds+=elapsed; }
}
static bool installTiming() {
    static const bool installed=[] {
        id<MTLDevice> device=MTLCreateSystemDefaultDevice();
        id<MTLCommandQueue> queue=[device newCommandQueue];
        id<MTLCommandBuffer> buffer=[queue commandBuffer];
        Method commit=class_getInstanceMethod(object_getClass(buffer),@selector(commit));
        Method wait=class_getInstanceMethod(object_getClass(buffer),@selector(waitUntilCompleted));
        if (!commit || !wait) { [queue release];return false; }
        originalCommit=reinterpret_cast<decltype(originalCommit)>(method_setImplementation(commit,reinterpret_cast<IMP>(observedCommit)));
        originalWait=reinterpret_cast<decltype(originalWait)>(method_setImplementation(wait,reinterpret_cast<IMP>(observedWait)));
        [queue release];return originalCommit && originalWait;
    }();
    return installed;
}
extern "C" int32_t fotufilm_timing_process_linear_float(
    const float *input,float *output,int32_t width,int32_t height,
    int32_t origin_x,int32_t origin_y,const float *configuration,
    const float *exposure_lut,const float *film_output_lut,const float *paper_output_lut,
    int32_t lut_dimension,uint64_t spectral_cache_id,int32_t feature_mask,uint32_t seed) {
    if (!installTiming()) return -96;
    auto state=std::make_shared<TimingCall>();std::atomic_store(&activeCall,state);
    const double cpu0=threadCPU(),process0=processCPU(),start=wall();
    const int32_t result=fotufilm_halide_metal_process_linear_float(input,output,width,height,
        origin_x,origin_y,configuration,exposure_lut,film_output_lut,paper_output_lut,
        lut_dimension,spectral_cache_id,feature_mask,seed);
    const double elapsed=wall()-start,cpu1=threadCPU(),process1=processCPU();
    std::atomic_store(&activeCall,std::shared_ptr<TimingCall>{});
    std::unique_lock<std::mutex> guard(state->mutex);
    const bool drained=state->done.wait_for(guard,std::chrono::seconds(5),[&]{return state->completed==state->committed;});
    std::sort(state->gpu.begin(),state->gpu.end(),[](auto a,auto b){return a.start<b.start;});
    double sum=0,united=0,end=0;int valid=0,failed=0;
    for (const auto &g:state->gpu) {
        if (g.status!=MTLCommandBufferStatusCompleted) ++failed;
        if (g.start>0 && g.end>=g.start) {
            ++valid;sum+=g.end-g.start;united+=std::max(0.,g.end-std::max(end,g.start));end=std::max(end,g.end);
        }
    }
    const bool timingComplete=drained && state->committed>0 && state->completed==state->committed
        && valid==state->committed && !failed;
    const double span=valid && state->gpu.front().start>0 ? end-state->gpu.front().start : 0;
    NSMutableArray *intervals=[NSMutableArray arrayWithCapacity:state->gpu.size()];
    for (const auto &g:state->gpu) [intervals addObject:@[@(g.start),@(g.end),@(g.status)]];
    static uint64_t identity=0;
    NSDictionary *event=@{@"id":@(identity++),@"gpu_intervals":intervals,@"api_wall_seconds":@(elapsed),
        @"main_thread_cpu_seconds":@(cpu0>=0 && cpu1>=cpu0 ? cpu1-cpu0 : -1),
        @"process_cpu_seconds":@(process0>=0 && process1>=process0 ? process1-process0 : -1),
        @"wait_wall_seconds":@(state->waitSeconds),@"wait_count":@(state->waits),
        @"committed":@(state->committed),@"completed":@(state->completed),@"timestamped":@(valid),
        @"queue_count":@(state->queues.size()),@"gpu_sum_seconds":@(sum),@"gpu_union_seconds":@(united),
        @"gpu_span_seconds":@(span),@"timing_complete":@(timingComplete),@"engine_error":@(result)};
    NSData *data=[NSJSONSerialization dataWithJSONObject:event options:0 error:nullptr];
    if (!data || std::fprintf(stderr,"API_TIMING %.*s\n",int(data.length),(const char *)data.bytes)<0 || std::fflush(stderr)) return -97;
    if (!drained) return -98;
    return result;
}
