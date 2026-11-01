// Count-based timing attribution; no additional GPU wait is inserted inside the API call.
#define main wf_unused_benchmark_main
#include "wavefront-benchmark.mm"
#undef main
#include "windowed-speed-probe.h"
#include <filesystem>
static double mainThreadCpu() {
    static mach_port_t thread=mach_thread_self();thread_basic_info_data_t info{};mach_msg_type_number_t count=THREAD_BASIC_INFO_COUNT;
    if(thread_info(thread,THREAD_BASIC_INFO,reinterpret_cast<thread_info_t>(&info),&count)!=KERN_SUCCESS) return NAN;
    return double(info.user_time.seconds+info.system_time.seconds)+double(info.user_time.microseconds+info.system_time.microseconds)*1e-6;
}
int main(int argc,char **argv) { @autoreleasepool {
    if(argc!=7) return 2;const bool probes=std::atoi(argv[4])!=0;const int warm=std::atoi(argv[5]),measured=std::atoi(argv[6]);
    if(warm<0 || measured<1 || measured>200) return 2;
    FILE *pack=std::fopen(argv[1],"rb");uint32_t h[10];
    if(!pack || std::fread(h,sizeof(h),1,pack)!=1 || std::memcmp(h,"FSWP",4) || (h[1]!=1 && h[1]!=2) || h[6]!=FOTUFILM_FRAME_CONFIGURATION_COUNT || h[8]!=33*33*33*4 || !h[2] || !h[3] || h[2]>8192 || h[3]>8192) return 2;
    std::vector<float> cfg(h[6]),exposure(h[8]),film(h[8]),paper(h[8]);
    for(auto *v:{&cfg,&exposure,&film,&paper}) if(std::fread(v->data(),sizeof(float),v->size(),pack)!=v->size()) return 2;std::fclose(pack);
    std::vector<float> input(size_t(h[2])*h[3]*4),output(input.size(),NAN);FILE *image=std::fopen(argv[2],"rb");
    if(!image || std::fread(input.data(),sizeof(float),input.size(),image)!=input.size() || std::fgetc(image)!=EOF) return 2;std::fclose(image);
    if(!wf_speed_initialize(probes) || !installObservers()) return 2;
    std::filesystem::create_directories(argv[3]);const int mask=h[4]|FOTUFILM_FRAME_FLOAT_IO|FOTUFILM_FRAME_REALTIME;
    auto phaseHash=[&](const char *phase) {
        for(size_t i=0;i<output.size();++i) if(!std::isfinite(output[i]) || (i%4==3 && output[i]!=input[i])) return false;
        emit(@{@"type":@"phase_hash",@"phase":[NSString stringWithUTF8String:phase],@"output_sha256":hash(output)});return true;
    };
    for(int frame=0;frame<warm+measured;++frame) { @autoreleasepool {
        fotufilm_bench_actual_variant=nullptr;fotufilm_bench_aot_calls=0;uint64_t beforeAlloc=allocations.load(),beforeDispatch=dispatches.load();
        wf_speed_begin(frame);double cpuBegin=mainThreadCpu(),begin=wf_speed_clock();
        int error=fotufilm_halide_metal_process_linear_float(input.data(),output.data(),h[2],h[3],0,0,cfg.data(),exposure.data(),film.data(),paper.data(),33,1,mask,h[5]);
        double end=wf_speed_clock(),cpuEnd=mainThreadCpu();auto path=std::filesystem::path(argv[3])/(std::to_string(frame)+".json");
        if(!wf_speed_finish(path.c_str(),begin,end)) return 1;
        if(error || !fotufilm_bench_actual_variant || fotufilm_bench_aot_calls!=1) return 1;
        emit(@{@"type":@"frame",@"frame":@(frame),@"phase":frame<warm?@"warmup":@"measurement",@"probes":@(probes),@"api_ms":@((end-begin)*1000),@"main_thread_cpu_ms":std::isfinite(cpuEnd-cpuBegin)?@((cpuEnd-cpuBegin)*1000):(id)[NSNull null],@"actual_variant":[NSString stringWithUTF8String:fotufilm_bench_actual_variant],@"aot_calls":@(fotufilm_bench_aot_calls),@"dispatches":@(dispatches.load()-beforeDispatch),@"new_buffers":@(allocations.load()-beforeAlloc),@"memory":memory()});
        if(frame==warm-1 && !phaseHash("warmup")) return 1;
    }}
    if(!phaseHash("measurement")) return 1;
    emit(@{@"type":@"complete",@"frames":@(warm+measured),@"probes":@(probes)});return 0;
}}
