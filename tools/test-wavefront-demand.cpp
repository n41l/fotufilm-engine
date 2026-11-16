// Host-only dependency checks for the three admitted row-window graphs.
#include "FotufilmWavefrontAdmission.h"
#include <array>
#include <cstdio>

int main() {
    std::array<float,FOTUFILM_FRAME_CONFIGURATION_COUNT> configuration{};
    fotufilm::ResolvedFrameParams p(configuration.data(),3840,2160,42,0,0,0);
    p.halation_stride_0=4;p.halation_stride_1=8;p.halation_stride_2=8;
    p.halation_strided_radius_0=3;p.halation_strided_radius_1=2;p.halation_strided_radius_2=4;
    p.coupler_sigma=0.5f;p.coupler_radius=2;
    p.adjacency_sigma=2.0f;p.adjacency_radius=7;p.print_mtf_radius=1;
    const int h=FOTUFILM_FRAME_HALATION, a=FOTUFILM_FRAME_ADJACENCY;
    const int c=FOTUFILM_FRAME_COUPLERS, d=FOTUFILM_FRAME_COUPLER_DIFFUSION;
    const int m=FOTUFILM_FRAME_PRINT_MTF;
    struct Case {int mask;int expected;};
    const Case cases[]={{0,0},{h,112},{a,12},{c,0},{d,0},{c|d,3},
        {a|c|d,12},{h|a|c|d|m,125},{FOTUFILM_FRAME_GRAIN|FOTUFILM_FRAME_MTF,0},
        {h|a|c|d|m|FOTUFILM_FRAME_GRAIN,125}};
    for (auto test:cases) {
        if (fotufilm::wavefront_post_mtf_reach(p,test.mask)!=test.expected) return 1;
    }
    // MTF is before this edge, and random-field blur is independent of image light.
    p.mtf_radius_0=999;p.mtf_luma_radius=999;p.grain_radius=999;
    if (fotufilm::wavefront_post_mtf_reach(p,h|a|c|d|m)!=125) return 1;
    const Case log_cases[]={{0,0},{h,0},{a,12},{c,0},{d,0},{c|d,3},
        {a|c|d,12},{h|a|c|d|m,13},{FOTUFILM_FRAME_GRAIN|FOTUFILM_FRAME_MTF,0},
        {h|a|c|d|m|FOTUFILM_FRAME_GRAIN,13}};
    for (auto test:log_cases)
        if (fotufilm::wavefront_log_reach(p,test.mask)!=test.expected) return 1;
    std::puts("post-MTF dependency checks=11; post-halation log dependency checks=10 passed");
}
