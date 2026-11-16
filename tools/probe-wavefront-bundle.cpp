#define FOTUFILM_HALIDE_ENABLED 1
#include "FotufilmHalideShared.h"
#include "Schedule/Gpu.h"
#include <Halide.h>
#include <array>
#include <cmath>
#include <cstdio>
#include <vector>
using namespace Halide;
using namespace fotufilm::gpu;
static int writes=0,expected_y=0,expected_n=0;
static bool wrong_region=false;
static int trace(JITUserContext *,const halide_trace_event_t *e) {
    if (e->event==halide_trace_produce && std::string(e->func)=="bundle_a") {
        ++writes;
        if (e->dimensions!=6 || e->coordinates[2]!=expected_y || e->coordinates[3]!=expected_n)
            wrong_region=true;
    }
    return 1;
}
int main(int argc,char **argv) {try {
    constexpr int W=65,H=321,CAP=256,BAND=64;
    GpuConfiguration config;config.device=DeviceAPI::Metal;config.half_blur=false;
    GpuSchedule s(config,false,true);
    ImageParam input(Float(32),3,"probe_input"),old(Float(32),3,"probe_old");
    Var x("x"),y("y"),c("channel");
    Buffer<float> in(W,H,3),ring(W,CAP,3);
    for (int k=0;k<3;++k) for(int j=0;j<H;++j)for(int i=0;i<W;++i)in(i,j,k)=.01f+float((i*7+j*13+k*19)%257)/257;
    ring.fill(std::nanf(""));input.set(in);old.set(ring);
    Func a("bundle_a");
    a(x,y,c)=(input(x,max(y-1,0),c)+2.f*input(x,y,c)+input(x,min(y+1,H-1),c))*.25f;
    a.output_buffer().dim(0).set_stride(1);a.output_buffer().dim(2).set_bounds(0,3).set_stride(W*CAP);
    s.gpu_pointwise(a,x,y,c,3);a.trace_realizations();
    Expr lo=a.output_buffer().dim(1).min(),hi=lo+a.output_buffer().dim(1).extent()-1;
    Func view("bundle_hybrid");
    view(x,y,c)=select(y>=lo&&y<=hi,a(x,clamp(y,lo,hi),c),old(x,y%CAP,c));
    const int strides[]={4,8,8},radii[]={1,1,2};
    std::vector<Func> outputs{a};std::array<Buffer<float>,3> fields;
    Func previous=view;int previous_stride=1,previous_w=W,previous_h=H;
    for(int i=0;i<3;++i) {
        int st=strides[i],w=(W+st-1)/st,h=(H+st-1)/st;
        Func u=s.gpu_decimate_level(previous,st/previous_stride,0,0,previous_w,previous_h,3,"probe_scale"+std::to_string(i));
        u=s.store_frame(u,false,3);previous=u;previous_stride=st;previous_w=w;previous_h=h;
        Func f=s.gpu_triple_box_blur(u,radii[i],w,h,false,"probe_f"+std::to_string(i),3);
        f.output_buffer().dim(0).set_stride(1);f.output_buffer().dim(2).set_bounds(0,3).set_stride(w*h);
        fields[i]=Buffer<float>(w,h,3);fields[i].fill(std::nanf(""));outputs.push_back(f);
    }
    Pipeline pipeline(outputs);pipeline.jit_handlers().custom_trace=trace;
    Target target=get_host_target();target.set_feature(Target::Metal);
    pipeline.compile_to_lowered_stmt(argc>1 ? argv[1] : "build/wavefront-bundle/probe.html",pipeline.infer_arguments(),HTML,target);
    ring.copy_to_device(DeviceAPI::Metal,target);for(auto &f:fields)f.copy_to_device(DeviceAPI::Metal,target);
    int head=0;std::array<int,3> fhead{};int calls=0,zeros=0;
    while(head<H) {
        int end=std::min(H,((head/64)+1)*64+80),n=std::min(end-head,std::min(CAP-head%CAP,37));
        auto aout=ring.cropped(1,head%CAP,n);aout.raw_buffer()->dim[1].min=head;
        std::vector<Buffer<void>> destinations{Buffer<float>(std::move(aout))};std::array<int,3> next{};
        for(int i=0;i<3;++i) {
            next[i]=head+n==H ? fields[i].height() : std::max(0,(head+n)/strides[i]-3*radii[i]);
            int count=next[i]-fhead[i];zeros+=count==0;
            auto out=fields[i].cropped(1,fhead[i],count);destinations.emplace_back(Buffer<float>(std::move(out)));
        }
        expected_y=head;expected_n=n;Realization result(destinations);pipeline.realize(result,target);
        ring.set_device_dirty();for(auto &f:fields)f.set_device_dirty();
        head+=n;fhead=next;++calls;
    }
    ring.copy_to_host();for(auto &f:fields)f.copy_to_host();
    for(int i=0;i<3;++i)for(int k=0;k<3;++k)for(int j=0;j<fields[i].height();++j)for(int v=0;v<fields[i].width();++v)
        if(!std::isfinite(fields[i](v,j,k)))throw std::runtime_error("nonfinite field");
    GpuSchedule reference_schedule(config,false,true);
    Func reference_light("reference_mtf");
    reference_light(x,y,c)=(input(x,max(y-1,0),c)+2.f*input(x,y,c)+input(x,min(y+1,H-1),c))*.25f;
    reference_light=reference_schedule.store_frame(reference_light,false,3);
    Func prior=reference_light;int ps=1,pw=W,ph=H;std::vector<Func> reference_outputs;
    std::array<Buffer<float>,3> reference;
    for(int i=0;i<3;++i) {
        int st=strides[i],w=(W+st-1)/st,h=(H+st-1)/st;
        Func u=reference_schedule.gpu_decimate_level(prior,st/ps,0,0,pw,ph,3,"reference_scale"+std::to_string(i));
        u=reference_schedule.store_frame(u,false,3);prior=u;ps=st;pw=w;ph=h;
        reference_outputs.push_back(reference_schedule.gpu_triple_box_blur(u,radii[i],w,h,false,"reference_f"+std::to_string(i),3));
        reference[i]=Buffer<float>(w,h,3);
    }
    Pipeline reference_pipeline(reference_outputs);Realization rr({reference[0],reference[1],reference[2]});
    reference_pipeline.realize(rr,target);float maximum=0;
    for(int i=0;i<3;++i) {
        reference[i].copy_to_host();
        for(int k=0;k<3;++k)for(int j=0;j<fields[i].height();++j)for(int v=0;v<fields[i].width();++v)
            maximum=std::max(maximum,std::abs(fields[i](v,j,k)-reference[i](v,j,k)));
    }
    if(maximum>1e-6f||writes!=calls||zeros<1||wrong_region)throw std::runtime_error("probe comparison/coverage failed");
    std::printf("probe passed: calls=%d A_productions=%d zero_extent_outputs=%d maximum_error=%.9g\n",calls,writes,zeros,maximum);

}catch(const Halide::Error &e){std::fprintf(stderr,"probe Halide error: %s\n",e.what());return 1;}catch(const std::exception &e){std::fprintf(stderr,"probe failed: %s\n",e.what());return 1;}}
