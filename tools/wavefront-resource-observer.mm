// External diagnostic interposition. Original pool functions are renamed only in shim.o.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include "HalideRuntimeMetal.h"
#include <algorithm>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

struct Physical { uint64_t id,object,length,allocated,born,freed=0,lease=0; };
struct Lease { uint64_t id,physical,requested,born,logicalEnd=0,fence=0,reuseProof=0; int references=1,roles=0; std::string aot; };
struct Fence { uint64_t identity,committed,completed=0; id native=nullptr; bool delivered=false; long status=0; };
struct PoolItem { uint64_t physical,length; int references,state; unsigned long status; };
struct Mark { uint64_t event; int frame; std::string name; std::vector<PoolItem> pool; };
struct Ledger {
    std::mutex mutex;std::condition_variable done;uint64_t event=0,latestFence=0;
    std::vector<Physical> physical;std::vector<Lease> leases;std::vector<Fence> fences;std::vector<Mark> marks;
    std::unordered_map<void *,uint64_t> objects;std::vector<std::string> errors;
};
static Ledger &ledger() { static auto *p=new Ledger;return *p; }
static thread_local std::string currentAot;
static const char witnessKey=0;
static id (*previousNewBuffer)(id,SEL,NSUInteger,MTLResourceOptions);
static void physicalFreed(uint64_t identity) {
    auto &s=ledger();std::lock_guard<std::mutex> lock(s.mutex);auto &p=s.physical.at(identity-1);
    p.freed=++s.event;s.objects.erase(reinterpret_cast<void *>(p.object));
    if (p.lease && s.leases[p.lease-1].references) s.errors.push_back("physical buffer freed with logical references");
}
@interface WfResourceWitness : NSObject { @public uint64_t identity; }
@end
@implementation WfResourceWitness
- (void)dealloc { physicalFreed(identity);[super dealloc]; }
@end
static void witness(id<MTLBuffer> buffer) {
    if (!buffer || objc_getAssociatedObject(buffer,&witnessKey)) return;
    const uint64_t length=buffer.length,allocated=buffer.allocatedSize;
    auto &s=ledger();uint64_t identity;
    { std::lock_guard<std::mutex> lock(s.mutex);identity=s.physical.size()+1;
      if (s.objects.count((__bridge void *)buffer)) s.errors.push_back("duplicate physical buffer identity");
      s.physical.push_back({identity,uint64_t((uintptr_t)(__bridge void *)buffer),length,allocated,++s.event});
      s.objects[(__bridge void *)buffer]=identity; }
    WfResourceWitness *token=[WfResourceWitness new];token->identity=identity;
    objc_setAssociatedObject(buffer,&witnessKey,token,OBJC_ASSOCIATION_RETAIN_NONATOMIC);[token release];
}
static id observedNewBuffer(id object,SEL selector,NSUInteger length,MTLResourceOptions options) {
    id buffer=previousNewBuffer(object,selector,length,options);witness(buffer);return buffer;
}
extern "C" bool wf_resource_initialize() {
    id<MTLDevice> device=MTLCreateSystemDefaultDevice();
    Method method=class_getInstanceMethod(object_getClass(device),@selector(newBufferWithLength:options:));
    if (!method) return false;
    previousNewBuffer=reinterpret_cast<decltype(previousNewBuffer)>(method_setImplementation(method,reinterpret_cast<IMP>(observedNewBuffer)));
    return previousNewBuffer!=nullptr;
}
extern "C" void wf_resource_aot_enter(const char *name) { currentAot=name; }
extern "C" void wf_resource_aot_leave() { currentAot.clear(); }
extern "C" void wf_resource_bind(const char *symbol,const char *argument,halide_buffer_t *buffer) {
    if (!buffer || !buffer->device) return;
    void *native=reinterpret_cast<void *>(halide_metal_get_buffer(nullptr,buffer));if (!native) return;
    std::string name=argument;int roles=0;
    if (name.find("input")!=std::string::npos) roles|=1;
    if (name.find("output")!=std::string::npos) roles|=2;
    if (name.find("configuration")!=std::string::npos) roles|=4;
    if (name.find("_lut")!=std::string::npos) roles|=8;
    if (name.find("film_tiles")!=std::string::npos) roles|=16;
    if (std::string(symbol).find("_wavefront_light_")!=std::string::npos && (roles&(2|4))) roles|=32;
    auto &s=ledger();std::lock_guard<std::mutex> lock(s.mutex);auto found=s.objects.find(native);
    if (found==s.objects.end() || !s.physical[found->second-1].lease) {s.errors.push_back("bound external buffer has no tracked lease");return;}
    s.leases[s.physical[found->second-1].lease-1].roles|=roles;
}
namespace Halide { namespace Runtime { namespace Internal {
namespace Metal {
void *wf_original_new_buffer(halide_metal_device *,size_t);
void wf_original_commit_command_buffer(halide_metal_command_buffer *);
void *new_buffer(halide_metal_device *device,size_t requested) {
    void *buffer=wf_original_new_buffer(device,requested);if (!buffer) return nullptr;
    auto &s=ledger();id proof=nullptr;uint64_t prior=0;
    { std::lock_guard<std::mutex> lock(s.mutex);auto it=s.objects.find(buffer);
      if (it==s.objects.end()) {s.errors.push_back("Halide buffer not observed by Metal allocation hook");return buffer;}
      auto &p=s.physical[it->second-1];prior=p.lease;
      if (prior) {auto &old=s.leases[prior-1];if (old.references) s.errors.push_back("rented buffer still logically active");
        if (old.fence && !s.fences[old.fence-1].completed) {proof=s.fences[old.fence-1].native;[proof retain];}}
    }
    const bool reusable=!proof || [(id<MTLCommandBuffer>)proof status]==MTLCommandBufferStatusCompleted;
    [proof release];
    { std::lock_guard<std::mutex> lock(s.mutex);auto &p=s.physical[s.objects.at(buffer)-1];
      if (!reusable) s.errors.push_back("pool reused buffer before observed GPU completion");
      if (prior && reusable) s.leases[prior-1].reuseProof=++s.event;
      uint64_t n=s.leases.size()+1;s.leases.push_back({n,p.id,requested,++s.event,0,0,0,1,0,currentAot});p.lease=n; }
    return buffer;
}
void commit_command_buffer(halide_metal_command_buffer *opaque) {
    id<MTLCommandBuffer> buffer=(__bridge id<MTLCommandBuffer>)reinterpret_cast<void *>(opaque);
    [buffer retain];auto &s=ledger();uint64_t n;
    {std::lock_guard<std::mutex> lock(s.mutex);n=s.fences.size()+1;s.fences.push_back({n,++s.event,0,buffer});s.latestFence=n;}
    [buffer addCompletedHandler:^(id<MTLCommandBuffer> done) {
        const long status=done.status;
        {auto &state=ledger();std::lock_guard<std::mutex> lock(state.mutex);auto &f=state.fences[n-1];
         f.completed=++state.event;f.status=status;f.native=nullptr;
         if (status!=MTLCommandBufferStatusCompleted) state.errors.push_back("GPU command failed");}
        [done release];
        {auto &state=ledger();std::lock_guard<std::mutex> lock(state.mutex);state.fences[n-1].delivered=true;}
        ledger().done.notify_all();
    }];
    wf_original_commit_command_buffer(opaque);
}
}
void wf_original_retain_ns_object(void *);
void wf_original_release_ns_object(void *);
void retain_ns_object(void *object) {
    wf_original_retain_ns_object(object);auto &s=ledger();std::lock_guard<std::mutex> lock(s.mutex);
    auto it=s.objects.find(object);if (it==s.objects.end()) return;auto n=s.physical[it->second-1].lease;
    if (n) {auto &l=s.leases[n-1];if (l.references<=0) s.errors.push_back("retain after lease returned");++l.references;}
}
void release_ns_object(void *object) {
    {auto &s=ledger();std::lock_guard<std::mutex> lock(s.mutex);auto it=s.objects.find(object);
     if (it!=s.objects.end()) {auto n=s.physical[it->second-1].lease;if (n) {
      auto &l=s.leases[n-1];if (l.references<=0) s.errors.push_back("unbalanced logical release");
      if (--l.references==0) {l.logicalEnd=++s.event;l.fence=s.latestFence;}}}}
    wf_original_release_ns_object(object);
}
}}}
extern "C" bool wf_resource_drain() {
    auto &s=ledger();std::unique_lock<std::mutex> lock(s.mutex);
    return s.done.wait_for(lock,std::chrono::seconds(5),[&]{return std::all_of(s.fences.begin(),s.fences.end(),[](const auto &f){return f.delivered;});});
}
extern "C" void wf_resource_visit_pool(void (*)(void *,size_t,int,int,unsigned long,void *),void *);
struct RawPoolItem { void *object;size_t length;int references,state;unsigned long status; };
extern "C" unsigned long long wf_resource_mark(const char *name,int frame) {
    std::vector<RawPoolItem> raw;
    wf_resource_visit_pool([](void *object,size_t length,int references,int state,unsigned long status,void *context) {
        static_cast<std::vector<RawPoolItem> *>(context)->push_back({object,length,references,state,status});
    },&raw);
    auto &s=ledger();std::lock_guard<std::mutex> lock(s.mutex);const auto e=++s.event;
    Mark marker{e,frame,name,{}};
    for (const auto &item:raw) {
        auto it=s.objects.find(item.object);
        if (it==s.objects.end()) {s.errors.push_back("pool owns an untracked physical buffer");continue;}
        marker.pool.push_back({it->second,item.length,item.references,item.state,item.status});
    }
    s.marks.push_back(std::move(marker));return e;
}
extern "C" bool wf_resource_write(const char *path) {
    if (!wf_resource_drain()) return false;
    auto &s=ledger();std::lock_guard<std::mutex> lock(s.mutex);
    NSMutableArray *physical=[NSMutableArray array],*leases=[NSMutableArray array],*fences=[NSMutableArray array],*marks=[NSMutableArray array],*errors=[NSMutableArray array];
    for (const auto &p:s.physical) [physical addObject:@{@"id":@(p.id),@"length":@(p.length),@"allocated":@(p.allocated),@"born":@(p.born),@"freed":@(p.freed)}];
    for (const auto &l:s.leases) [leases addObject:@{@"id":@(l.id),@"physical":@(l.physical),@"requested":@(l.requested),@"born":@(l.born),@"logical_end":@(l.logicalEnd),@"fence":@(l.fence),@"reuse_proof":@(l.reuseProof),@"references":@(l.references),@"roles":@(l.roles),@"aot":[NSString stringWithUTF8String:l.aot.c_str()]}];
    for (const auto &f:s.fences) [fences addObject:@{@"id":@(f.identity),@"commit":@(f.committed),@"complete":@(f.completed),@"delivered":@(f.delivered),@"status":@(f.status)}];
    for (const auto &m:s.marks) {
        NSMutableArray *pool=[NSMutableArray array];
        for (const auto &p:m.pool) [pool addObject:@{@"physical":@(p.physical),@"length":@(p.length),@"references":@(p.references),@"state":@(p.state),@"fence_status":@(p.status)}];
        [marks addObject:@{@"event":@(m.event),@"frame":@(m.frame),@"name":[NSString stringWithUTF8String:m.name.c_str()],@"pool":pool}];
    }
    for (const auto &e:s.errors) [errors addObject:[NSString stringWithUTF8String:e.c_str()]];
    NSDictionary *result=@{@"physical":physical,@"leases":leases,@"fences":fences,@"markers":marks,@"errors":errors,
      @"scope":@"allocator/CPU event order; GPU-safe live intervals are conservative observation bounds; no performance score"};
    NSData *data=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nullptr];
    return data && [data writeToFile:[NSString stringWithUTF8String:path] atomically:YES];
}
