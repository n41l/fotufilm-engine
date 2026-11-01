// Process-local probes. CPU nested intervals and GPU execution overlap; never add them.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include "HalideRuntimeMetal.h"
#include "windowed-speed-probe.h"
#include <mach/mach_time.h>
#include <chrono>
#include <condition_variable>
#include <mutex>
#include <string>
#include <vector>
#include <unordered_map>
struct CpuEvent {std::string kind,label;double begin,end;size_t bytes;};
struct GpuEvent {std::string label;double submitBegin=0,submitEnd=0,start=0,end=0;long status=0;bool done=false;};
struct SpeedFrame {std::mutex mutex;std::condition_variable cv;int id=-1;bool enabled=false;std::vector<CpuEvent> cpu;std::vector<GpuEvent> gpu;size_t pending=0;std::unordered_map<const void *,double> encoding;};
static SpeedFrame &state() {static auto *p=new SpeedFrame;return *p;}
static bool enabled=false;
static thread_local SpeedFrame *activeFrame=nullptr;
extern "C" double wf_speed_clock() {
    static mach_timebase_info_data_t timebase=[] {mach_timebase_info_data_t t;mach_timebase_info(&t);return t;}();
    return double(mach_absolute_time())*double(timebase.numer)/double(timebase.denom)*1e-9;
}
extern "C" bool wf_speed_active() {return activeFrame!=nullptr;}
extern "C" void wf_speed_cpu(const char *kind,double begin,double end,size_t bytes) {
    if (activeFrame) activeFrame->cpu.push_back({kind,"",begin,end,bytes});
}
static id (*previousBuffer)(id,SEL,NSUInteger,MTLResourceOptions);
static void (*previousWait)(id,SEL);
static id (*previousCommand)(id,SEL);
static id timedCommand(id queue,SEL selector) {
    if(!activeFrame) return previousCommand(queue,selector);
    double begin=wf_speed_clock();id command=previousCommand(queue,selector);
    if(command) activeFrame->encoding[(const void *)command]=begin;return command;
}
static id timedBuffer(id object,SEL selector,NSUInteger length,MTLResourceOptions options) {
    if (!activeFrame) return previousBuffer(object,selector,length,options);
    double begin=wf_speed_clock();id result=previousBuffer(object,selector,length,options);double end=wf_speed_clock();
    wf_speed_cpu(result?"metal_new_buffer":"metal_new_buffer_failed",begin,end,length);return result;
}
static void timedWait(id object,SEL selector) {
    if (!activeFrame) {previousWait(object,selector);return;}
    std::string label=[(id<MTLCommandBuffer>)object label].UTF8String ?: "";
    double begin=wf_speed_clock();previousWait(object,selector);double end=wf_speed_clock();
    activeFrame->cpu.push_back({"wait_until_completed",label,begin,end,0});
}
extern "C" bool wf_speed_initialize(bool useProbe) { @autoreleasepool {
    enabled=useProbe;if (!enabled) return true;
    id<MTLDevice> device=MTLCreateSystemDefaultDevice();if(!device) return false;
    id<MTLCommandQueue> queue=[device newCommandQueue];id<MTLCommandBuffer> command=[queue commandBuffer];
    Method allocation=class_getInstanceMethod(object_getClass(device),@selector(newBufferWithLength:options:));
    Method wait=class_getInstanceMethod(object_getClass(command),@selector(waitUntilCompleted));
    Method factory=class_getInstanceMethod(object_getClass(queue),@selector(commandBuffer));
    if(!allocation || !wait || !factory) {[queue release];return false;}
    previousBuffer=reinterpret_cast<decltype(previousBuffer)>(method_setImplementation(allocation,reinterpret_cast<IMP>(timedBuffer)));
    previousWait=reinterpret_cast<decltype(previousWait)>(method_setImplementation(wait,reinterpret_cast<IMP>(timedWait)));
    previousCommand=reinterpret_cast<decltype(previousCommand)>(method_setImplementation(factory,reinterpret_cast<IMP>(timedCommand)));
    [queue release];return previousBuffer && previousWait && previousCommand;
}}
extern "C" void wf_speed_begin(int frame) {
    auto &s=state();s.id=frame;s.enabled=enabled;s.cpu.clear();s.gpu.clear();s.pending=0;s.cpu.reserve(1024);s.gpu.reserve(256);s.encoding.clear();s.encoding.reserve(256);
    activeFrame=enabled?&s:nullptr;
}
namespace Halide { namespace Runtime { namespace Internal { namespace Metal {
void *wf_original_new_buffer(halide_metal_device *,size_t);
void wf_original_commit_command_buffer(halide_metal_command_buffer *);
void *new_buffer(halide_metal_device *device,size_t requested) {
    if (!activeFrame) return wf_original_new_buffer(device,requested);
    double begin=wf_speed_clock();void *result=wf_original_new_buffer(device,requested);double end=wf_speed_clock();
    wf_speed_cpu("allocator_inclusive",begin,end,requested);return result;
}
void commit_command_buffer(halide_metal_command_buffer *opaque) {
    if (!activeFrame) {wf_original_commit_command_buffer(opaque);return;}
    const double encodeEnd=wf_speed_clock();auto *s=activeFrame;id<MTLCommandBuffer> command=(id<MTLCommandBuffer>)reinterpret_cast<void *>(opaque);
    std::string label=command.label.UTF8String ?: "";size_t index;
    auto encoded=s->encoding.find((const void *)command);
    if(encoded!=s->encoding.end()) {s->cpu.push_back({"encode_envelope",label,encoded->second,encodeEnd,0});s->encoding.erase(encoded);}
    {std::lock_guard<std::mutex> lock(s->mutex);index=s->gpu.size();s->gpu.push_back({label});++s->pending;}
    [command addCompletedHandler:^(id<MTLCommandBuffer> done) {
        double begin=done.GPUStartTime,end=done.GPUEndTime;long status=done.status;
        {std::lock_guard<std::mutex> lock(s->mutex);auto &row=s->gpu[index];row.start=begin;row.end=end;row.status=status;row.done=true;--s->pending;}
        s->cv.notify_all();
    }];
    double begin=wf_speed_clock();wf_original_commit_command_buffer(opaque);double end=wf_speed_clock();
    {std::lock_guard<std::mutex> lock(s->mutex);s->gpu[index].submitBegin=begin;s->gpu[index].submitEnd=end;}
    wf_speed_cpu("commit_cpu",begin,end,0);
}
}
void wf_original_release_ns_object(void *);
void release_ns_object(void *object) {
    if(!activeFrame) {wf_original_release_ns_object(object);return;}
    double begin=wf_speed_clock();wf_original_release_ns_object(object);double end=wf_speed_clock();
    wf_speed_cpu("runtime_release_inclusive",begin,end,0);
}
}}}
extern "C" bool wf_speed_finish(const char *path,double apiBegin,double apiEnd) { @autoreleasepool {
    activeFrame=nullptr;auto &s=state();double flushBegin=wf_speed_clock();
    std::unique_lock<std::mutex> lock(s.mutex);
    if (!s.cv.wait_for(lock,std::chrono::seconds(5),[&]{return s.pending==0;})) return false;
    double flushEnd=wf_speed_clock();NSMutableArray *cpu=[NSMutableArray array],*gpu=[NSMutableArray array];
    for(const auto &e:s.cpu) [cpu addObject:@{@"kind":[NSString stringWithUTF8String:e.kind.c_str()],@"label":[NSString stringWithUTF8String:e.label.c_str()],@"begin":@(e.begin),@"end":@(e.end),@"bytes":@(e.bytes)}];
    for(const auto &e:s.gpu) [gpu addObject:@{@"label":[NSString stringWithUTF8String:e.label.c_str()],@"submit_begin":@(e.submitBegin),@"submit_end":@(e.submitEnd),@"gpu_start":@(e.start),@"gpu_end":@(e.end),@"status":@(e.status),@"done":@(e.done)}];
    NSDictionary *report=@{@"frame":@(s.id),@"probes":@(s.enabled),@"api_begin":@(apiBegin),@"api_end":@(apiEnd),@"flush_seconds":@(flushEnd-flushBegin),@"cpu":cpu,@"commands":gpu,@"clock":@"mach_absolute_time seconds; Metal host timestamps validated separately"};
    NSData *data=[NSJSONSerialization dataWithJSONObject:report options:0 error:nullptr];return data && [data writeToFile:[NSString stringWithUTF8String:path] atomically:YES];
}}
