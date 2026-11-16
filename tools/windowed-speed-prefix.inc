// Added only to generated diagnostic shim copies. Timers do not change pool policy.
#include <cstddef>
extern "C" bool wf_speed_active();
extern "C" double wf_speed_clock();
extern "C" void wf_speed_cpu(const char *,double,double,size_t);
struct WfSpeedScope {
    const char *name;double begin;
    explicit WfSpeedScope(const char *n):name(n),begin(wf_speed_active()?wf_speed_clock():0) {}
    ~WfSpeedScope() {if(begin) wf_speed_cpu(name,begin,wf_speed_clock(),0);}
};
