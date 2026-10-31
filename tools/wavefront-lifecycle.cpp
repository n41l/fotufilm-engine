// External R/C fixture driver. Shared film expressions remain in each checkout's engine.
#include "FotufilmHalide.h"
#if FOTUFILM_WAVEFRONT_OPTIONS_TESTS
#include "../Sources/FotufilmHalide/FotufilmHalideWavefront.h"
#include "../Sources/FotufilmHalide/Pipeline/WavefrontLightLayout.h"
#ifndef FOTUFILM_LIFECYCLE_BAND
#define FOTUFILM_LIFECYCLE_BAND 256
#endif
#endif
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <vector>
extern "C" {
const char *fotufilm_bench_actual_variant = nullptr;
int fotufilm_bench_aot_calls = 0;
int fotufilm_bench_trace_variants = 0;
}
struct Pack {
    uint32_t h[10];
    std::vector<float> configuration, exposure, film, paper;
    bool load(const char *path) {
        FILE *f=std::fopen(path,"rb");if (!f) return false;
        bool ok=std::fread(h,sizeof(h),1,f)==1 && !std::memcmp(h,"FSWP",4)
            && (h[1]==1 || h[1]==2) && h[6]==FOTUFILM_FRAME_CONFIGURATION_COUNT
            && h[7]==33 && h[8]==33*33*33*4;
        if (ok) {
            configuration.resize(h[6]);exposure.resize(h[8]);film.resize(h[8]);paper.resize(h[8]);
            for (auto *v:{&configuration,&exposure,&film,&paper})
                ok=ok && std::fread(v->data(),sizeof(float),v->size(),f)==v->size();
        }
        std::fclose(f);return ok;
    }
};
int main(int argc,char **argv) {
    if (argc!=4) return 2;
    Pack color,mono;if (!color.load(argv[1]) || !mono.load(argv[2])) return 2;
    std::filesystem::create_directories(argv[3]);
#if FOTUFILM_WAVEFRONT_OPTIONS_TESTS
    std::vector<float> valid_input(32*32*4,0.5f),sentinel(valid_input.size(),123.0f);
    const int control=fotufilm_halide_metal_process_linear_float(valid_input.data(),sentinel.data(),32,32,0,0,
        color.configuration.data(),color.exposure.data(),color.film.data(),color.paper.data(),33,1,
        color.h[4] | FOTUFILM_FRAME_FLOAT_IO | FOTUFILM_FRAME_REALTIME,color.h[5]);
    if (control || !std::isfinite(sentinel[0]) || sentinel[3]!=0.5f) return 1;
    for (int test=0;test<4;++test) {
        std::fill(sentinel.begin(),sentinel.end(),123.0f);fotufilm_bench_aot_calls=0;
        FotufilmWavefrontOptions options;
        if (test==0) options.size=0;
        if (test==1) options.version=2;
        if (test==2) options.mode=3;
        FotufilmWavefrontResult result;
        const int status=fotufilm_halide_metal_process_linear_float_wavefront(
            valid_input.data(),sentinel.data(),32,32,0,0,color.configuration.data(),
            color.exposure.data(),color.film.data(),color.paper.data(),33,1,
            color.h[4] | FOTUFILM_FRAME_FLOAT_IO | FOTUFILM_FRAME_REALTIME,color.h[5],
            test==3 ? nullptr : &options,&result);
        if (status!=-1 || fotufilm_bench_aot_calls || result.actual_mode!=-1) return 1;
        for (float value:sentinel) if (value!=123.0f) return 1;
    }
    std::puts("{\"type\":\"invalid_options\",\"passed\":true,\"checks\":4}");
#endif
    for (int frame=0;frame<15;++frame) {
#if !FOTUFILM_WAVEFRONT_OPTIONS_TESTS
        if (frame==11) continue; // C-only submission failure, followed by normal frame 12.
#endif
        Pack &p=frame==1 ? mono : color;
        const int width=frame==14 ? 65 : frame==10 ? 32 : frame==1 ? 1919 : 1920;
        const int height=(frame==1 || frame==14) ? 1081 : 1080, origin=frame==14 ? 7 : 0;
        const uint32_t seed=p.h[5]+frame;
        auto config=p.configuration;
        if (frame==1) {
            const float gate[]={100,200,float(width-100),float(height-200),8};
            std::memcpy(config.data()+FOTUFILM_CONFIG_GATE,gate,sizeof(gate));
            config[FOTUFILM_CONFIG_GATE_CORNER]=16;
        } else if (frame==2) {
            const float gate[]={0,0,0,0,0};
            std::memcpy(config.data()+FOTUFILM_CONFIG_GATE,gate,sizeof(gate));
        }
        if (frame==10) {
            config[FOTUFILM_CONFIG_ADJACENCY_SIGMA]=0.151f;
            config[FOTUFILM_CONFIG_ADJACENCY_RADIUS]=100;
            config[FOTUFILM_CONFIG_COUPLER_SIGMA]=0.151f;
            config[FOTUFILM_CONFIG_COUPLER_RADIUS]=100;
            config[FOTUFILM_CONFIG_GRAIN_RADIUS]=170;
        }
        int32_t mask=p.h[4] | FOTUFILM_FRAME_FLOAT_IO | FOTUFILM_FRAME_REALTIME;
        if (frame==4) mask &= ~FOTUFILM_FRAME_MTF;
        if (frame==12) mask ^= FOTUFILM_FRAME_MTF_LUMA; // Switch the private cache between RGB and RGB+luma.
        if (frame==5 || frame==6) mask &= ~FOTUFILM_FRAME_REALTIME;
        if (frame==6) mask |= FOTUFILM_FRAME_EXACT_MATH;
        const char *encoding=frame==13 ? "rec709" : "linear";
        if (frame==13) {
            mask |= FOTUFILM_FRAME_ENCODE_OUT | FOTUFILM_FRAME_OUTPUT_POWER;
            config[FOTUFILM_CONFIG_OUTPUT_TRANSFER]=1;
            const float gamma[]={1,1,1.0f/2.4f,0,0,0};
            std::memcpy(config.data()+FOTUFILM_CONFIG_OUTPUT_COEFFICIENTS,gamma,sizeof(gamma));
        }
        std::vector<float> input(size_t(width)*height*4),output(input.size(),std::nanf(""));
        for (int y=0;y<height;++y) for (int x=0;x<width;++x) {
            const size_t i=(size_t(y)*width+x)*4;
            input[i]=0.03f+float((x*7+y*13+frame*127)%997)/997;
            input[i+1]=(x==width/2 || y%64==0) ? 4.0f : 0.18f;
            input[i+2]=float((x^y^frame)&31)/31 - ((frame==9 || frame==12) ? 0.25f : 0.0f);
            input[i+3]=float((x+y+frame)%3)*0.5f;
        }
        fotufilm_bench_aot_calls=0;fotufilm_bench_actual_variant=nullptr;
        int status=0,actual_mode=0,expected_calls=1;
        const char *reason="original API";
#if FOTUFILM_WAVEFRONT_OPTIONS_TESTS
        FotufilmWavefrontOptions options;options.rows=frame==7 ? 17 : FOTUFILM_LIFECYCLE_BAND;options.mode=frame==8 ? 0 : 1;
        if (frame==11) options.test_fail_after_source_call=1;
        FotufilmWavefrontResult result;
        status=fotufilm_halide_metal_process_linear_float_wavefront(input.data(),output.data(),
            width,height,origin,origin,config.data(),p.exposure.data(),p.film.data(),p.paper.data(),
            33,uint64_t(frame+1),mask,seed,&options,&result);
        actual_mode=result.actual_mode;reason=result.reason;
        if (frame==11) {
            if (status!=-93 || result.actual_mode!=1 || result.producer_calls!=1
                || result.consumer_calls!=0 || result.drain_status!=0 || fotufilm_bench_aot_calls!=1) return 1;
            for (float value:output) if (!std::isnan(value)) return 1;
            std::puts("{\"type\":\"injected_failure\",\"frame\":11,\"passed\":true,\"drained\":true,\"consumer_calls\":0}");
            continue;
        }
        if (actual_mode!=((frame<4 || frame==9 || frame==12 || frame==13) ? 1 : 0)) return 1;
        if (actual_mode==1) {
            if (result.producer_rows!=height || result.consumer_calls!=(height+options.rows-1)/options.rows || result.ring_rows!=fotufilm::gpu::kWavefrontLightRows) return 1;
            expected_calls=result.producer_calls+result.consumer_calls;
        }
#else
        status=fotufilm_halide_metal_process_linear_float(input.data(),output.data(),width,height,
            origin,origin,config.data(),p.exposure.data(),p.film.data(),p.paper.data(),33,uint64_t(frame+1),mask,seed);
#endif
        if (status || fotufilm_bench_aot_calls!=expected_calls || !fotufilm_bench_actual_variant) return 1;
        for (size_t i=0;i<output.size();++i)
            if (!std::isfinite(output[i]) || (i%4==3 && output[i]!=input[i])) return 1;
        const auto path=std::filesystem::path(argv[3])/(std::to_string(frame)+".rgba32f");
        FILE *f=std::fopen(path.c_str(),"wb");if (!f) return 2;
        const bool written=std::fwrite(output.data(),sizeof(float),output.size(),f)==output.size();
        const bool closed=std::fclose(f)==0;if (!written || !closed) return 2;
        std::printf("{\"type\":\"frame\",\"frame\":%d,\"width\":%d,\"height\":%d,\"seed\":%u,"
            "\"actual_variant\":\"%s\",\"actual_mode\":%d,\"reason\":\"%s\","
            "\"finite\":true,\"alpha_exact\":true,\"encoding\":\"%s\",\"feature_mask\":%d,\"origin\":%d}\n",frame,width,height,seed,
            fotufilm_bench_actual_variant,actual_mode,reason,encoding,mask,origin);
        std::fflush(stdout);
    }
}
