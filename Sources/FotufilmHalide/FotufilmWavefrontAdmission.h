#pragma once
#include "FotufilmResolvedFrameParams.h"
#include "FotufilmHalideGeometry.h"
namespace fotufilm {
// Post-MTF RGB demand for the three admitted row-window graphs. Parallel halation
// scales and chemistry arms form a union; only successive spatial operations add.
// This is a safe frame-coordinate bound, including grid alignment/interpolation,
// rather than a minimum inferred allocation. The old admission remains in force.
inline int64_t wavefront_post_mtf_reach(const ResolvedFrameParams &frame, int32_t feature_mask) {
    int64_t halation = 0, chemistry = 0;
    if (feature_mask & FOTUFILM_FRAME_HALATION) {
        const int strides[] = {frame.halation_stride_0,frame.halation_stride_1,frame.halation_stride_2};
        const int radii[] = {frame.halation_strided_radius_0,frame.halation_strided_radius_1,frame.halation_strided_radius_2};
        for (int i=0;i<3;++i) halation = std::max(halation,
            resampled_grid_reach(kTripleBoxPasses*int64_t(radii[i]),strides[i]));
    }
    if ((feature_mask & FOTUFILM_FRAME_COUPLERS) && (feature_mask & FOTUFILM_FRAME_COUPLER_DIFFUSION))
        chemistry = gaussian_grid_reach(frame.coupler_sigma,frame.coupler_radius);
    if (feature_mask & FOTUFILM_FRAME_ADJACENCY)
        chemistry = std::max(chemistry,gaussian_grid_reach(frame.adjacency_sigma,frame.adjacency_radius));
    // Grain draws are an independent coordinate branch, not an image-light predecessor.
    return halation + chemistry + ((feature_mask & FOTUFILM_FRAME_PRINT_MTF) ? int64_t(frame.print_mtf_radius) : 0);
}

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
