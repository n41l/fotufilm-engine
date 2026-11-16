// Appended only to a frozen-R diagnostic shim; exact-size reuse remains exact.
#undef new_buffer
#ifndef WF_POOL_ALLOCATOR_ENTRY
#define WF_POOL_ALLOCATOR_ENTRY new_buffer
#endif
static WfRecentPool &wfRecent() { static auto *s=new WfRecentPool;return *s; }
static void wfRecentBeginFrame() { PoolLock held;wfRecent().beginFrame(); }
static void wfRecentReset() { wfRecent().clear(); } // Caller holds pool_mutex.
static void wfRecentDrop(void *buffer) {
    wfRecent().forget(buffer);pooled.erase(buffer);send(static_cast<id>(buffer),"release");
}
static void wfRecentReturn(void *buffer,size_t length) { // Completed incoming fence; pool_mutex held.
    std::vector<WfRecentPool::Entry> available;
    const size_t capacity=size_t(pool_megabytes())<<20;
    if(length>capacity-idle_bytes) {
        available.reserve(idle.size());for(const auto &entry:idle) available.push_back({entry.second,entry.first});
    }
    const auto plan=wfRecent().plan({buffer,length},available,idle_bytes,capacity);
    if(!plan.admit) {wfRecentDrop(buffer);return;}
    for(const auto &victim:plan.evict) {
        auto range=idle.equal_range(victim.length);
        auto found=range.first;while(found!=range.second && found->second!=victim.buffer) ++found;
        if(found==range.second) std::abort();
        idle_bytes-=found->first;idle.erase(found);wfRecentDrop(victim.buffer);
    }
    idle.emplace(length,buffer);idle_bytes+=length;
    if(idle_bytes>capacity) std::abort();
}
namespace Halide { namespace Runtime { namespace Internal { namespace Metal {
void *WF_POOL_ALLOCATOR_ENTRY(halide_metal_device *device,size_t requested) {
    const bool pooling=pool_megabytes()>0 && frame_depth>0;
    const size_t length=pooling?pooled_length(requested):requested;
    if(pooling) {
        PoolLock held;wfRecent().request(length);reclaim_returned();
        auto found=idle.find(length);
        if(found!=idle.end()) {
            void *buffer=found->second;idle.erase(found);idle_bytes-=length;
            pooled[buffer].references=1;wfRecent().touch(buffer);return buffer;
        }
    }
    void *buffer=((void *(*)(id,SEL,size_t,size_t))objc_msgSend)(
        reinterpret_cast<id>(device),sel_getUid("newBufferWithLength:options:"),length,0);
    if(buffer && pooling) {PoolLock held;pooled[buffer]=PooledBuffer{length,1};wfRecent().touch(buffer);}
    return buffer;
}
}}}}
