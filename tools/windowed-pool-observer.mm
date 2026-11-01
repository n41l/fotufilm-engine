// Wrap the existing diagnostic observer; production shim and AOT archives are unmodified.
#define new_buffer wf_pool_observed_new_buffer
#include "wavefront-resource-observer.mm"
#undef new_buffer
extern "C" void wf_pool_parameters(size_t,size_t *,int *,size_t *);
struct PoolAttempt {
    uint64_t begin,end,physical;size_t requested,rounded,capacity;int depth;bool fresh;
    std::vector<PoolItem> before,after;
};
static auto &attempts() {static auto *p=new std::vector<PoolAttempt>;return *p;}
static std::vector<PoolItem> poolSnapshot() {
    std::vector<RawPoolItem> raw;
    wf_resource_visit_pool([](void *o,size_t n,int refs,int state,unsigned long status,void *ctx) {
        static_cast<std::vector<RawPoolItem> *>(ctx)->push_back({o,n,refs,state,status});
    },&raw);
    auto &s=ledger();std::lock_guard<std::mutex> lock(s.mutex);std::vector<PoolItem> result;
    for (const auto &r:raw) {
        auto it=s.objects.find(r.object);
        if (it==s.objects.end()) {s.errors.push_back("pool snapshot has unobserved physical object");continue;}
        result.push_back({it->second,r.length,r.references,r.state,r.status});
    }
    return result;
}
namespace Halide { namespace Runtime { namespace Internal { namespace Metal {
void *new_buffer(halide_metal_device *device,size_t requested) {
    PoolAttempt a{};a.requested=requested;wf_pool_parameters(requested,&a.rounded,&a.depth,&a.capacity);
    a.before=poolSnapshot();uint64_t previousPhysical;
    {auto &s=ledger();std::lock_guard<std::mutex> lock(s.mutex);a.begin=++s.event;previousPhysical=s.physical.size();}
    void *buffer=wf_pool_observed_new_buffer(device,requested);
    {auto &s=ledger();std::lock_guard<std::mutex> lock(s.mutex);a.end=++s.event;
     auto it=s.objects.find(buffer);if (it!=s.objects.end()) {a.physical=it->second;a.fresh=a.physical>previousPhysical;}}
    a.after=poolSnapshot();attempts().push_back(std::move(a));return buffer;
}
}}}}
static NSArray *poolArray(const std::vector<PoolItem> &items) {
    NSMutableArray *result=[NSMutableArray array];
    for (const auto &i:items) [result addObject:@{@"physical":@(i.physical),@"length":@(i.length),@"references":@(i.references),@"state":@(i.state),@"fence_status":@(i.status)}];
    return result;
}
extern "C" bool wf_pool_write(const char *path) {
    if (!wf_resource_write(path)) return false;
    NSMutableArray *rows=[NSMutableArray array];
    for (const auto &a:attempts()) [rows addObject:@{@"begin":@(a.begin),@"end":@(a.end),@"physical":@(a.physical),@"fresh":@(a.fresh),@"requested":@(a.requested),@"rounded":@(a.rounded),@"frame_depth":@(a.depth),@"capacity":@(a.capacity),@"before":poolArray(a.before),@"after":poolArray(a.after)}];
    NSDictionary *report=@{@"complete":@YES,@"attempts":rows,@"scope":@"read-only before/after snapshots; GPU fence status may progress between snapshots; no latency scores"};
    NSData *data=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:nullptr];
    NSString *target=[[[NSString stringWithUTF8String:path] stringByDeletingLastPathComponent] stringByAppendingPathComponent:@"pool-attempts.json"];
    return data && [data writeToFile:target atomically:YES];
}
