// Same count-based frames and Metal counters; additionally save allocator-attempt snapshots.
#define wf_resource_write wf_pool_write
#include "wavefront-resource-driver.mm"
#undef wf_resource_write
