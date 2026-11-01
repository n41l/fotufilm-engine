"""Exact-anchor extension of the original long-window driver, sampled once per second."""
HELPERS=r'''
#include "windowed-speed-probe.h"
#include <string>
static std::string wfLongDirectory;
static double wfLongNext=0, wfLongBegin=0, wfLongCpuBegin=0;
static bool wfLongSample=false;
static double wfLongCpu() {
    static mach_port_t thread=mach_thread_self();
    thread_basic_info_data_t info{};mach_msg_type_number_t count=THREAD_BASIC_INFO_COUNT;
    if(thread_info(thread,THREAD_BASIC_INFO,reinterpret_cast<thread_info_t>(&info),&count)!=KERN_SUCCESS) return NAN;
    return double(info.user_time.seconds+info.system_time.seconds)+double(info.user_time.microseconds+info.system_time.microseconds)*1e-6;
}
static void wfLongStart(uint64_t id, NSString *phase, double limit) {
    const double t=now();
    wfLongSample=([phase isEqualToString:@"verification"] || t>=wfLongNext) && t+.002<limit;
    if(!wfLongSample) return;
    while(wfLongNext<=t) wfLongNext+=1;
    wf_speed_begin(int(id));wfLongCpuBegin=wfLongCpu();wfLongBegin=wf_speed_clock();
}
static NSDictionary *wfLongFinish(uint64_t id) {
    if(!wfLongSample) return @{@"sampled":@NO};
    const double end=wf_speed_clock(), cpuEnd=wfLongCpu(), writeBegin=now();
    const std::string path=wfLongDirectory+"/"+std::to_string(id)+".json";
    if(!wf_speed_finish(path.c_str(),wfLongBegin,end)) std::exit(3);
    return @{@"sampled":@YES,@"trace_path":[NSString stringWithUTF8String:path.c_str()],
        @"main_thread_cpu_ms":@((cpuEnd-wfLongCpuBegin)*1000),@"trace_write_ms":@((now()-writeBegin)*1000)};
}
'''

def generate(source):
    def replace(old,new):
        nonlocal source
        if source.count(old)!=1:raise ValueError('original driver anchor changed: '+old)
        source=source.replace(old,new)
    replace('int main(int argc, char **argv)',HELPERS+'\nint main(int argc, char **argv)')
    replace('    if (!installObservers()) return 2;', '''    const char *traceDirectory=std::getenv("FOTUFILM_LONG_TRACE_DIRECTORY");
    if(!traceDirectory || !*traceDirectory || !wf_speed_initialize(true)) return 2;
    wfLongDirectory=traceDirectory;
    if (!installObservers()) return 2;
    wfLongNext=now()+.5;''')
    replace('        const double start = now();','        wfLongStart(id,phase,limit);\n        const double start = now();')
    # No selected frame can be abandoned with an active observer at the deadline.
    replace('if (start >= limit) { emit(', 'if (start >= limit) { if(wfLongSample) wfLongFinish(id); emit(')
    replace('        const double completed = now();','        const double completed = now();\n        NSDictionary *sample=wfLongFinish(id);')
    replace('@"new_buffer_allocations":@(allocations.load()-beforeAllocations)});', '@"new_buffer_allocations":@(allocations.load()-beforeAllocations),@"probe_sample":sample});')
    replace('    emit(@{@"type":@"window",', '    wfLongNext=t0+.5;\n    emit(@{@"type":@"window",')
    return source
