#pragma once
#if WF_RESOURCE_OBSERVER
extern "C" bool wf_resource_initialize();
extern "C" bool wf_resource_drain();
extern "C" unsigned long long wf_resource_mark(const char *, int);
extern "C" bool wf_resource_write(const char *);
#else
inline bool wf_resource_initialize() { return true; }
inline bool wf_resource_drain() { return true; }
inline unsigned long long wf_resource_mark(const char *, int) { return 0; }
inline bool wf_resource_write(const char *) { return true; }
#endif
