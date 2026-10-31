#pragma once
#include "../include/FotufilmHalide.h"
#include "../FotufilmHalideGeometry.h"
namespace fotufilm::gpu {
// Private Metal float-realtime layout. The public packed configuration is unchanged.
constexpr int kWavefrontLightRows = 2048;
constexpr int kWavefrontLightBase = (FOTUFILM_FRAME_CONFIGURATION_COUNT + 63) & ~63;
constexpr int kWavefrontLightMargin = 2 * kWindowMaximumReach;
// Every admitted band must retain both spatial margins before its consumer finishes.
static_assert(512 + 2 * kWavefrontLightMargin <= kWavefrontLightRows);
}
