#pragma once
#include "FotufilmResolvedFrameParams.h"
#include "FotufilmHalideGeometry.h"
namespace fotufilm {
// Conservative serial source demand, distinct from the legacy performance estimate.
inline int64_t wavefront_source_reach(const ResolvedFrameParams &frame,
                                     const float *configuration,int32_t feature_mask) {
    const int stride[]={frame.halation_stride_0,frame.halation_stride_1,frame.halation_stride_2};
    const int strided_radius[]={frame.halation_strided_radius_0,frame.halation_strided_radius_1,frame.halation_strided_radius_2};
    int64_t source_reach = int64_t(frame.mtf_radius_0) + frame.mtf_radius_1 + frame.mtf_radius_2;
    if (feature_mask & FOTUFILM_FRAME_MTF_LUMA) source_reach += frame.mtf_luma_radius;
    for (int scale=0;scale<3;++scale) source_reach += fotufilm::resampled_grid_reach(
        fotufilm::kTripleBoxPasses*int64_t(strided_radius[scale]),stride[scale]);
    source_reach += fotufilm::gaussian_grid_reach(frame.coupler_sigma,frame.coupler_radius)
        + fotufilm::gaussian_grid_reach(frame.adjacency_sigma,frame.adjacency_radius)
        + fotufilm::gaussian_grid_reach(std::max(configuration[FOTUFILM_CONFIG_ADJACENCY_SECONDARY_SIGMA],0.151f),
            std::max(0,int32_t(configuration[FOTUFILM_CONFIG_ADJACENCY_SECONDARY_RADIUS])))
        + fotufilm::gaussian_grid_reach(frame.fringe_sigma,frame.fringe_radius)
        + int64_t(frame.grain_radius) + frame.print_mtf_radius;
    return source_reach;
}
}
