// Count-based resource diagnosis. The shared benchmark helpers provide identical Metal counters.
#define main wf_unused_timed_main
#include "wavefront-benchmark.mm"
#undef main
#include "wavefront-resource-observer.h"
#if WF_RESOURCE_CANDIDATE
#include "../Sources/FotufilmHalide/FotufilmHalideWavefront.h"
#endif
#include <filesystem>
#include <string>
#include <unordered_map>
struct ResourcePack {
    uint32_t h[10]{};uint64_t cacheId=0;std::vector<float> cfg,exposure,film,paper;
    bool load(const char *path) {
        FILE *f=std::fopen(path,"rb");if (!f) return false;
        bool ok=std::fread(h,sizeof(h),1,f)==1 && !std::memcmp(h,"FSWP",4)
            && (h[1]==1 || h[1]==2) && h[2]>0 && h[3]>0 && h[2]<=8192 && h[3]<=8192 && h[6]==FOTUFILM_FRAME_CONFIGURATION_COUNT && h[7]==33 && h[8]==33*33*33*4;
        if (ok) {cfg.resize(h[6]);exposure.resize(h[8]);film.resize(h[8]);paper.resize(h[8]);
            for (auto *v:{&cfg,&exposure,&film,&paper}) ok=ok && std::fread(v->data(),sizeof(float),v->size(),f)==v->size();}
        std::fclose(f);return ok;
    }
};
int main(int argc,char **argv) { @autoreleasepool {
    if (argc!=3 && argc!=4) return 2;
    const bool step=argc==4 && !std::strcmp(argv[3],"--step");
    NSData *data=[NSData dataWithContentsOfFile:[NSString stringWithUTF8String:argv[1]]];
    NSDictionary *plan=data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:nullptr] : nil;
    if (![plan isKindOfClass:[NSDictionary class]]) return 2;
    NSArray *actions=plan[@"actions"];std::filesystem::create_directories(argv[2]);
    std::unordered_map<std::string,ResourcePack> packs;size_t maxCount=0,fixtureBytes=0;
    for (NSDictionary *a in actions) if ([a[@"type"] isEqual:@"frame"]) {
        std::string path=[a[@"pack"] UTF8String];
        if (!packs.count(path)) {ResourcePack p;if (!p.load(path.c_str())) return 2;
            p.cacheId=packs.size()+1;fixtureBytes+=(p.cfg.size()+p.exposure.size()+p.film.size()+p.paper.size())*4;packs.emplace(path,std::move(p));}
        auto &p=packs.at(path);maxCount=std::max(maxCount,size_t(p.h[2])*p.h[3]*4);
    }
    std::vector<float> input,output;input.reserve(maxCount);output.reserve(maxCount);
    if (!installObservers() || !wf_resource_initialize()) return 2;
    void *context=nullptr,*previous=nullptr;uint64_t overallPeak=device.currentAllocatedSize;int frame=0;
    auto cleanup=[&] {
        if (context) {fotufilm_halide_metal_context_restore(previous);fotufilm_halide_metal_context_destroy(context);context=nullptr;}
        fotufilm_halide_metal_release_pool();return wf_resource_drain();
    };
    emit(@{@"type":@"resource_identity",@"observer":@(bool(WF_RESOURCE_OBSERVER)),@"fixture_host_bytes":@(fixtureBytes),
        @"scope":@"count-based resource diagnosis; no FPS or latency scores",@"initial_memory":memory()});
    for (NSDictionary *action in actions) { @autoreleasepool {
        NSString *type=action[@"type"];
        if ([type isEqual:@"idle"] || [type isEqual:@"cleanup"]) {
            if ([type isEqual:@"cleanup"] && !cleanup()) return 1;
            std::this_thread::sleep_for(std::chrono::seconds([action[@"seconds"] intValue]));
            if (!wf_resource_drain()) return 1;
            auto marker=wf_resource_mark([type UTF8String],frame);overallPeak=std::max(overallPeak,gpuPeak.load());
            emit(@{@"type":type,@"frame":@(frame),@"marker":@(marker),@"memory":memory()});continue;
        }
        if (![type isEqual:@"frame"]) return 2;
        if (!context) {context=fotufilm_halide_metal_context_create();if (!context) return 2;previous=fotufilm_halide_metal_context_bind(context);}
        auto &p=packs.at([action[@"pack"] UTF8String]);const int w=p.h[2],h=p.h[3];const size_t n=size_t(w)*h*4;
        input.resize(n);output.resize(n);FILE *f=std::fopen([action[@"input"] UTF8String],"rb");
        if (!f) return 2;const bool read=std::fread(input.data(),sizeof(float),n,f)==n && std::fgetc(f)==EOF;std::fclose(f);if (!read) return 2;
        for (float x:input) if (!std::isfinite(x)) return 2;
        std::fill(output.begin(),output.end(),std::nanf(""));
        gpuPeak.store(device.currentAllocatedSize);const uint64_t beforeAlloc=allocations.load(),beforeDispatch=dispatches.load();
        NSDictionary *before=memory();auto begin=wf_resource_mark("frame_begin",frame);
        fotufilm_bench_actual_variant=nullptr;fotufilm_bench_aot_calls=0;
        int status=0,actual=0,sources=0,consumers=0,rows=0,drain=-1;
        const int mask=int32_t(p.h[4]) | FOTUFILM_FRAME_FLOAT_IO | FOTUFILM_FRAME_REALTIME;
        const bool experimental=[action[@"mode"] isEqual:@"E"];const char *reason="legacy API";
#if WF_RESOURCE_CANDIDATE
        if (experimental) {
            FotufilmWavefrontOptions options;options.rows=[action[@"band"] intValue];FotufilmWavefrontResult result;
            status=fotufilm_halide_metal_process_linear_float_wavefront(input.data(),output.data(),w,h,0,0,p.cfg.data(),
                p.exposure.data(),p.film.data(),p.paper.data(),33,p.cacheId,mask,p.h[5],&options,&result);
            actual=result.actual_mode;sources=result.producer_calls;consumers=result.consumer_calls;rows=result.producer_rows;drain=result.drain_status;reason=result.reason;
        } else
#else
        if (experimental) return 2;
#endif
        {status=fotufilm_halide_metal_process_linear_float(input.data(),output.data(),w,h,0,0,p.cfg.data(),p.exposure.data(),p.film.data(),p.paper.data(),33,p.cacheId,mask,p.h[5]);}
        if (!wf_resource_drain()) return 1;auto end=wf_resource_mark("frame_end",frame);
        const int expected=[action[@"expected_mode"] intValue];bool valid=!status && actual==expected && fotufilm_bench_actual_variant && dispatches.load()>beforeDispatch;
        if (actual==1) valid=valid && rows==h && consumers==(h+[action[@"band"] intValue]-1)/[action[@"band"] intValue]
            && fotufilm_bench_aot_calls==sources+consumers && drain==0;
        else valid=valid && fotufilm_bench_aot_calls==1;
        for (size_t i=0;i<n;++i) if (!std::isfinite(output[i]) || (i%4==3 && output[i]!=input[i])) valid=false;
        NSString *digest=hash(output);if (action[@"expected_sha256"] && ![digest isEqual:action[@"expected_sha256"]]) valid=false;
        NSDictionary *after=memory();overallPeak=std::max(overallPeak,gpuPeak.load());
        if ([plan[@"dump"] boolValue]) {
            auto path=std::filesystem::path(argv[2])/(std::to_string(frame)+".rgba32f");FILE *dump=std::fopen(path.c_str(),"wb");if (!dump) return 2;
            const bool written=std::fwrite(output.data(),sizeof(float),n,dump)==n;const bool closed=std::fclose(dump)==0;if (!written || !closed) return 2;
        }
        emit(@{@"type":@"resource_frame",@"frame":@(frame),@"id":action[@"id"],@"status":valid ? @"success" : @"failure",
            @"actual_mode":@(actual),@"actual_variant":[NSString stringWithUTF8String:fotufilm_bench_actual_variant ? fotufilm_bench_actual_variant : "none"],
            @"reason":[NSString stringWithUTF8String:reason],@"aot_calls":@(fotufilm_bench_aot_calls),@"gpu_dispatches":@(dispatches.load()-beforeDispatch),
            @"new_buffers":@(allocations.load()-beforeAlloc),@"producer_rows":@(rows),@"source_calls":@(sources),@"consumer_calls":@(consumers),
            @"output_sha256":digest,@"before_memory":before,@"memory":after,@"begin_marker":@(begin),@"end_marker":@(end),
            @"host_input_capacity_bytes":@(input.capacity()*4),@"host_output_capacity_bytes":@(output.capacity()*4)});
        if (!valid) return 1;++frame;
        if (step && std::getchar()!='\n') return 2;
    }}
    if (!cleanup()) return 1;wf_resource_mark("final",frame);
    if (!wf_resource_write((std::filesystem::path(argv[2])/"resource-trace.json").c_str())) return 1;
    emit(@{@"type":@"resource_complete",@"frames":@(frame),@"gpu_total_peak_bytes":@(overallPeak),@"memory":memory()});
    return 0;
}}
