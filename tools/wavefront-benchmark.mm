// External macOS whole-frame benchmark driver. Engine and AOT sources remain unmodified.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include "FotufilmHalide.h"
#include <CommonCrypto/CommonDigest.h>
#include <mach/mach.h>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <thread>
#include <vector>

extern "C" {
const char *fotufilm_bench_actual_variant = nullptr;
int fotufilm_bench_aot_calls = 0;
int fotufilm_bench_trace_variants = 0;
}
static id<MTLDevice> device;
static std::atomic<uint64_t> dispatches{0}, allocations{0}, gpuPeak{0};
static void (*originalDispatch)(id, SEL, MTLSize, MTLSize);
static id (*originalBuffer)(id, SEL, NSUInteger, MTLResourceOptions);
static double now() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
static void observeGPU() {
    const uint64_t value = device.currentAllocatedSize;
    uint64_t previous = gpuPeak.load();
    while (previous < value && !gpuPeak.compare_exchange_weak(previous, value)) {}
}
static void countedDispatch(id object, SEL selector, MTLSize groups, MTLSize threads) {
    ++dispatches;
    originalDispatch(object, selector, groups, threads);
}
static id countedBuffer(id object, SEL selector, NSUInteger length, MTLResourceOptions options) {
    id buffer = originalBuffer(object, selector, length, options);
    if (buffer) ++allocations;
    observeGPU();
    return buffer;
}
static bool installObservers() {
    device = MTLCreateSystemDefaultDevice();
    if (!device) return false;
    id<MTLCommandQueue> queue = [device newCommandQueue];
    id<MTLCommandBuffer> command = [queue commandBuffer];
    id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
    Method dispatch = class_getInstanceMethod(object_getClass(encoder),
        @selector(dispatchThreadgroups:threadsPerThreadgroup:));
    Method allocate = class_getInstanceMethod(object_getClass(device), @selector(newBufferWithLength:options:));
    if (!dispatch || !allocate) return false;
    originalDispatch = reinterpret_cast<decltype(originalDispatch)>(method_getImplementation(dispatch));
    originalBuffer = reinterpret_cast<decltype(originalBuffer)>(method_getImplementation(allocate));
    method_setImplementation(dispatch, reinterpret_cast<IMP>(countedDispatch));
    method_setImplementation(allocate, reinterpret_cast<IMP>(countedBuffer));
    [encoder endEncoding];
    [command commit];
    [command waitUntilCompleted];
    [queue release];
    observeGPU();
    return true;
}
static NSDictionary *memory() {
    observeGPU();
    task_vm_info_data_t info{};
    mach_msg_type_number_t count = TASK_VM_INFO_COUNT;
    const kern_return_t error = task_info(mach_task_self(), TASK_VM_INFO,
        reinterpret_cast<task_info_t>(&info), &count);
    return @{ @"device_current_bytes": @(device.currentAllocatedSize),
              @"device_peak_bytes": @(gpuPeak.load()),
              @"process_footprint_bytes": error == KERN_SUCCESS ? @(info.phys_footprint) : (id)[NSNull null],
              @"process_lifetime_peak_bytes": error == KERN_SUCCESS ? @(info.ledger_phys_footprint_peak) : (id)[NSNull null],
              @"buffer_allocations": @(allocations.load()), @"thermal_state": @([NSProcessInfo processInfo].thermalState) };
}
static void emit(NSDictionary *event) {
    NSData *data = [NSJSONSerialization dataWithJSONObject:event options:0 error:NULL];
    if (!data || std::fwrite(data.bytes, 1, data.length, stdout) != data.length
        || std::fputc('\n', stdout) == EOF || std::fflush(stdout)) std::exit(2);
}
static NSString *hash(const std::vector<float> &values) {
    unsigned char digest[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256(values.data(), static_cast<CC_LONG>(values.size()*sizeof(float)), digest);
    char encoded[65];
    for (int i=0;i<32;++i) std::snprintf(encoded+2*i, 3, "%02x", digest[i]);
    return [NSString stringWithUTF8String:encoded];
}

int main(int argc, char **argv) { @autoreleasepool {
    if (argc != 3 && (argc != 5 || std::strcmp(argv[3],"--dump"))) {
        std::fprintf(stderr, "usage: wavefront-benchmark PACK INPUT.rgba32f [--dump OUTPUT.rgba32f]\n"); return 2;
    }
    FILE *pack = std::fopen(argv[1], "rb");
    uint32_t h[10];
    if (!pack || std::fread(h, sizeof(h), 1, pack) != 1 || std::memcmp(h,"FSWP",4)
        || (h[1]!=1 && h[1]!=2) || h[6]!=FOTUFILM_FRAME_CONFIGURATION_COUNT
        || h[7]!=33 || h[8]!=33*33*33*4 || h[2]<1 || h[3]<1 || h[2]>8192 || h[3]>8192) return 2;
    std::vector<float> configuration(h[6]), exposure(h[8]), film(h[8]), paper(h[8]);
    for (auto *values : {&configuration,&exposure,&film,&paper}) {
        if (std::fread(values->data(),sizeof(float),values->size(),pack)!=values->size()) return 2;
    }
    std::fclose(pack);
    std::vector<float> input(size_t(h[2])*h[3]*4), output(input.size(),std::nanf(""));
    FILE *image = std::fopen(argv[2],"rb");
    if (!image || std::fread(input.data(),sizeof(float),input.size(),image)!=input.size()
        || std::fgetc(image)!=EOF) return 2;
    std::fclose(image);
    for (float value : input) if (!std::isfinite(value)) return 2;
    if (!installObservers()) return 2;
    const int32_t mask = int32_t(h[4]) | FOTUFILM_FRAME_FLOAT_IO | FOTUFILM_FRAME_REALTIME;
    emit(@{@"type":@"identity", @"width":@(h[2]), @"height":@(h[3]), @"mask":@(mask),
           @"seed":@(h[5]), @"input_sha256":hash(input), @"initial_memory":memory(),
           @"encoded_output":@((mask & FOTUFILM_FRAME_ENCODE_OUT)!=0),
           @"delivery_transfer":@(configuration[FOTUFILM_CONFIG_OUTPUT_TRANSFER]),
           @"delivery_coefficients":@[@(configuration[FOTUFILM_CONFIG_OUTPUT_COEFFICIENTS]),
               @(configuration[FOTUFILM_CONFIG_OUTPUT_COEFFICIENTS+1]),
               @(configuration[FOTUFILM_CONFIG_OUTPUT_COEFFICIENTS+2]),
               @(configuration[FOTUFILM_CONFIG_OUTPUT_COEFFICIENTS+3]),
               @(configuration[FOTUFILM_CONFIG_OUTPUT_COEFFICIENTS+4]),
               @(configuration[FOTUFILM_CONFIG_OUTPUT_COEFFICIENTS+5])],
           @"clock":@"std::chrono::steady_clock seconds", @"clock_sample":@(now()),
           @"gpu_observer":@"newBufferWithLength allocation boundaries and post-call currentAllocatedSize",
           @"dispatch_observer":@"dispatchThreadgroups:threadsPerThreadgroup:"});
    uint64_t identity = 0;
    double firstStart = 0;
    auto invoke = [&](NSString *phase, double limit) -> int { @autoreleasepool {
        const uint64_t id = identity++;
        const uint64_t beforeDispatch = dispatches.load(), beforeAllocations = allocations.load();
        fotufilm_bench_aot_calls = 0;
        fotufilm_bench_actual_variant = nullptr;
        emit(@{@"type":@"call_start", @"id":@(id), @"phase":phase, @"submitted_at":@(now())});
        const double start = now();
        if (start >= limit) { emit(@{@"type":@"not_submitted",@"id":@(id)}); return 1; }
        if (!firstStart) firstStart = start;
        int error;
        @autoreleasepool {
            error = fotufilm_halide_metal_process_linear_float(input.data(),output.data(),h[2],h[3],
                0,0,configuration.data(),exposure.data(),film.data(),paper.data(),33,1,mask,h[5]);
        }
        const double completed = now();
        bool valid = !error && fotufilm_bench_aot_calls > 0 && dispatches.load() > beforeDispatch;
        // Constant-cost samples outside the timed API; complete hashes are taken at phase boundaries.
        const size_t step = std::max(size_t(4),(output.size()/64/4)*4);
        for (size_t i=0; i<output.size(); i+=step) {
            valid = valid && std::isfinite(output[i]) && std::isfinite(output[i+1])
                && std::isfinite(output[i+2]) && output[i+3] == input[i+3];
        }
        emit(@{@"type":@"call_complete",@"id":@(id),@"phase":phase,@"started_at":@(start),
               @"completed_at":@(completed),@"status":valid ? @"success" : @"failure",@"engine_error":@(error),
               @"actual_variant":fotufilm_bench_actual_variant ? [NSString stringWithUTF8String:fotufilm_bench_actual_variant] : @"none",
               @"aot_calls":@(fotufilm_bench_aot_calls),@"gpu_dispatches":@(dispatches.load()-beforeDispatch),
               @"thermal_state":@([NSProcessInfo processInfo].thermalState),
               @"new_buffer_allocations":@(allocations.load()-beforeAllocations)});
        return valid ? 0 : 2;
    }};
    if (argc == 5) {
        if (invoke(@"verification",INFINITY)) return 1;
        for (size_t i=0;i<output.size();++i) if (!std::isfinite(output[i]) || (i%4==3 && output[i]!=input[i])) return 1;
        FILE *dump=std::fopen(argv[4],"wb");
        if (!dump) return 2;
        const bool written=std::fwrite(output.data(),sizeof(float),output.size(),dump)==output.size();
        const bool closed=std::fclose(dump)==0;
        if (!written || !closed) return 2;
        emit(@{@"type":@"verification_complete",@"memory":memory(),@"output_sha256":hash(output)});
        return 0;
    }
    do { if (invoke(@"warmup",INFINITY)) return 1; } while (now()-firstStart < 5.0);
    for (size_t i=0;i<output.size();++i) if (!std::isfinite(output[i]) || (i%4==3 && output[i]!=input[i])) return 1;
    emit(@{@"type":@"warmup_complete",@"memory":memory(),@"output_sha256":hash(output)});
    gpuPeak.store(device.currentAllocatedSize);
    const double t0 = now(), t1 = t0+30, deadline = t1+2;
    emit(@{@"type":@"window",@"t0":@(t0),@"t1":@(t1),@"deadline":@(deadline)});
    while (now()<t1) { const int result=invoke(@"measurement",t1); if (result==2) return 1; if (result==1) break; }
    emit(@{@"type":@"measurement_complete",@"memory":memory(),@"output_sha256":hash(output)});
    std::this_thread::sleep_for(std::chrono::seconds(5));
    emit(@{@"type":@"retained",@"memory":memory(),@"idle_release":@"none; upstream pool policy unchanged"});
    return 0;
}}
