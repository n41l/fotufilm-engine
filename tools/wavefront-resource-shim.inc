// Appended only to a generated diagnostic copy of FotufilmHalideIOS.cpp.
// Observe the original pool without reclaiming, releasing or changing it.
extern "C" void wf_resource_visit_pool(
    void (*visit)(void *,size_t,int,int,unsigned long,void *),void *context) {
    PoolLock held;
    std::set<void *> idle_objects;
    for (const auto &entry:idle) idle_objects.insert(entry.second);
    for (const auto &entry:pooled) {
        int state=entry.second.references>0 ? 0 : idle_objects.count(entry.first) ? 1 : 2;
        unsigned long status=0;
        if (state==2) for (const auto &r:returning) if (r.buffer==entry.first) {
            status=r.fence ? ((unsigned long (*)(id,SEL))objc_msgSend)(r.fence,sel_getUid("status")) : 4;
            break;
        }
        visit(entry.first,entry.second.length,entry.second.references,state,status,context);
    }
}
