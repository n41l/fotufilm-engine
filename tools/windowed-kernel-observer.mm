// Diagnostic-only injected library for this experiment's own verification workers.
// Never loaded in measurement workers. Records actual bound Metal function names.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>
#include <unordered_map>
static id (*original_pipeline)(id,SEL,id,NSError **);
static void (*original_bind)(id,SEL,id);
static auto &names() { static auto *p=new std::unordered_map<const void *,std::string>();return *p; }
static auto &name_mutex() { static auto *p=new std::mutex();return *p; }
static id observe_pipeline(id object,SEL selector,id<MTLFunction> function,NSError **error) {
    id result=original_pipeline(object,selector,function,error);
    if (result && function.name) {std::lock_guard<std::mutex> lock(name_mutex());names()[(const void *)result]=function.name.UTF8String;}
    return result;
}
static void observe_bind(id object,SEL selector,id state) {
    {std::lock_guard<std::mutex> lock(name_mutex());auto it=names().find((const void *)state);
     if (it!=names().end() && it->second.find("_kernel_frame_coupler_diffused_")!=std::string::npos
         && it->second.find("_down_")!=std::string::npos)
         std::fprintf(stderr,"UNIT_GPU_KERNEL %s\n",it->second.c_str());}
    original_bind(object,selector,state);
}
__attribute__((constructor)) static void install() { @autoreleasepool {
    const char *enabled=std::getenv("FOTUFILM_UNIT_KERNEL_OBSERVER");
    if (!enabled || std::strcmp(enabled,"1")) return;
    id<MTLDevice> device=MTLCreateSystemDefaultDevice();
    id<MTLCommandQueue> queue=[device newCommandQueue];id<MTLCommandBuffer> buffer=[queue commandBuffer];
    id<MTLComputeCommandEncoder> encoder=[buffer computeCommandEncoder];
    Method pipeline=class_getInstanceMethod(object_getClass(device),@selector(newComputePipelineStateWithFunction:error:));
    Method bind=class_getInstanceMethod(object_getClass(encoder),@selector(setComputePipelineState:));
    if (!pipeline || !bind) {std::fprintf(stderr,"UNIT_OBSERVER_FAILED\n");std::exit(2);}
    original_pipeline=reinterpret_cast<decltype(original_pipeline)>(method_setImplementation(pipeline,reinterpret_cast<IMP>(observe_pipeline)));
    original_bind=reinterpret_cast<decltype(original_bind)>(method_setImplementation(bind,reinterpret_cast<IMP>(observe_bind)));
    [encoder endEncoding];[queue release];std::fprintf(stderr,"UNIT_OBSERVER_READY\n");
} }
