// Diagnostic suffix only. Pool ownership, reclamation and capacity policy stay unchanged.
#include "wavefront-resource-shim.inc"
extern "C" void wf_pool_parameters(size_t requested,size_t *rounded,int *depth,size_t *capacity) {
    PoolLock held;
    *depth=frame_depth;
    *capacity=size_t(pool_megabytes()) << 20;
    *rounded=pool_megabytes()>0 && frame_depth>0 ? pooled_length(requested) : requested;
}
