// Targeted current-source JIT counterpart of the isolated exact Coupler AOT twins.
#define FOTUFILM_HALIDE_ENABLED 1
#include "../Sources/FotufilmHalide/Pipeline/Gpu.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <vector>
int main(int argc,char **argv) {
    if (argc!=5 || (std::strcmp(argv[4],"0") && std::strcmp(argv[4],"1"))) return 2;
    using namespace fotufilm;
    using namespace fotufilm::gpu;
    using namespace fotufilm::pipelines;
    GpuConfiguration configuration;
    const std::string baseline=configuration.cache_key();
    assert(!configuration.windowed_coupler_fusion);
    configuration.windowed_coupler_fusion=true;
    assert(configuration.cache_key()!=baseline);
    configuration.windowed_coupler_fusion=false;
    assert(configuration.cache_key()==baseline);
    configuration.windowed_coupler_fusion=argv[4][0]=='1';
    FILE *f=std::fopen(argv[1],"rb");uint32_t h[10];
    if (!f || std::fread(h,sizeof(h),1,f)!=1 || std::memcmp(h,"FSWP",4)
        || (h[1]!=1 && h[1]!=2) || h[6]!=FOTUFILM_FRAME_CONFIGURATION_COUNT
        || h[7]!=33 || h[8]!=33*33*33*4 || !h[2] || !h[3]) return 2;
    std::vector<float> cfg(h[6]),exposure(h[8]),film(h[8]),paper(h[8]);
    for (auto *v:{&cfg,&exposure,&film,&paper})
        if (std::fread(v->data(),sizeof(float),v->size(),f)!=v->size()) return 2;
    std::fclose(f);
    const int32_t mask=int32_t(h[4])|FOTUFILM_FRAME_FLOAT_IO|FOTUFILM_FRAME_REALTIME;
    const int stages=mask & FOTUFILM_VARIANT_STAGE_BITS;
    if (stages!=FOTUFILM_AOT_PRINTED_NEGATIVE && stages!=FOTUFILM_AOT_PRINTED_NEGATIVE_LUMA) return 2;
    std::vector<float> input(size_t(h[2])*h[3]*4),output(input.size());
    f=std::fopen(argv[2],"rb");
    if (!f || std::fread(input.data(),sizeof(float),input.size(),f)!=input.size() || std::fgetc(f)!=EOF) return 2;
    std::fclose(f);
    GpuFramePipeline pipeline(mask,"_coupler_fusion_test",true,configuration,true);
    pipeline.run_host(input.data(),output.data(),h[2],h[3],cfg.data(),exposure.data(),film.data(),paper.data(),33,1,h[5],mask);
    for (size_t i=0;i<output.size();++i)
        if (!std::isfinite(output[i]) || (i%4==3 && output[i]!=input[i])) return 1;
    f=std::fopen(argv[3],"wb");
    if (!f) return 2;
    bool ok=std::fwrite(output.data(),sizeof(float),output.size(),f)==output.size();
    ok=std::fclose(f)==0 && ok;
    return ok ? 0 : 2;
}
