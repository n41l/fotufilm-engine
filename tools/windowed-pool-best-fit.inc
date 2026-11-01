// Isolated host-policy experiment appended to a diagnostic copy of the frozen R shim.
// Original new_buffer is renamed only in shim.o. No production/default activation.
#undef new_buffer
#ifndef WF_POOL_ALLOCATOR_ENTRY
#define WF_POOL_ALLOCATOR_ENTRY new_buffer
#endif
namespace Halide { namespace Runtime { namespace Internal { namespace Metal {
void *WF_POOL_ALLOCATOR_ENTRY(halide_metal_device *device,size_t requested) {
    const bool pooling=pool_megabytes()>0 && frame_depth>0;
    const size_t length=pooling ? pooled_length(requested) : requested;
    if (pooling) {
        PoolLock held;
        reclaim_returned();
        auto found=idle.find(length);
        // Keep tiny buffers exact. Bound oversized reuse to at most50% above the rounded
        // request and choose the smallest eligible allocation; never wait for or reuse a fence.
        if (found==idle.end() && length >= (size_t(1)<<16)) {
            for (auto candidate=idle.begin();candidate!=idle.end();++candidate) {
                if (candidate->first>=length && candidate->first-length<=length/2
                    && (found==idle.end() || candidate->first<found->first)) found=candidate;
            }
        }
        if (found!=idle.end()) {
            void *buffer=found->second;
            const size_t actual=found->first;
            idle.erase(found);idle_bytes-=actual;
            pooled[buffer].references=1;
            return buffer;
        }
    }
    void *buffer=((void *(*)(id,SEL,size_t,size_t))objc_msgSend)(
        reinterpret_cast<id>(device),sel_getUid("newBufferWithLength:options:"),length,0);
    if (buffer && pooling) {PoolLock held;pooled[buffer]=PooledBuffer{length,1};}
    return buffer;
}
}}}}
