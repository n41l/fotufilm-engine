// Same external driver links independently against R or C AOT. Not a performance benchmark.
#include "probe.h"
#include "HalideBuffer.h"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>

int32_t trace(void *, const halide_trace_event_t *event) {
    static int32_t identity = 0;
    if (event->event == halide_trace_produce && event->dimensions == 6) {
        std::fprintf(stderr, "PRODUCE %s %d %d %d %d %d %d\n", event->func,
                     event->coordinates[0], event->coordinates[1],
                     event->coordinates[2], event->coordinates[3],
                     event->coordinates[4], event->coordinates[5]);
    }
    return ++identity;
}

int main(int argc, char **argv) {
    if (argc != 5 && argc != 6) return 2;
    const int base_width = std::atoi(argv[1]), base_height = std::atoi(argv[2]);
    const int radius = std::atoi(argv[3]), frames = argc == 6 ? std::atoi(argv[5]) : 1;
    if (base_width <= 0 || base_height <= 0 || radius < 1 || radius > 31
        || frames < 1 || frames > 3) return 2;
#if FOTUFILM_PROBE_FOLDED
    // The upstream one-pixel shortcut bypasses the horizontal producer. Its
    // fold head then does not advance; reject before allocating or writing.
    if (radius == 1) return 3;
#endif
    halide_set_custom_trace(trace);
    FILE *dump = std::fopen(argv[4], "wb");
    if (!dump) return 2;
    for (int frame = 0; frame < frames; ++frame) {
    // A/B/A geometry, changed input and alpha, all within the same Metal runtime.
    const int width = base_width + frame % 2, height = base_height + frame % 2;
    auto input = Halide::Runtime::Buffer<float>::make_interleaved(width, height, 4);
    auto output = Halide::Runtime::Buffer<float>::make_interleaved(width, height, 4);
    output.fill(std::nanf(""));
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            input(x, y, 0) = 0.03f + float((x * 7 + y * 13 + frame * 127) % 997) / 997.0f;
            input(x, y, 1) = (x == width / 2 || y % 64 == 0) ? 4.0f : 0.18f;
            input(x, y, 2) = float((x ^ y) & 31) / 31.0f;
            input(x, y, 3) = float((x + y + frame) % 3) * 0.5f;
        }
    }
    input.set_host_dirty();
    const int error = fotufilm_wavefront_probe(input.raw_buffer(), width, height, radius,
                                              output.raw_buffer());
    if (error || output.copy_to_host()) return 1;
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            for (int c = 0; c < 4; ++c) if (!std::isfinite(output(x, y, c))) return 1;
            if (output(x, y, 3) != input(x, y, 3)) return 1;
        }
    }
    if (std::fwrite(output.data(), sizeof(float), size_t(width) * height * 4, dump)
        != size_t(width) * height * 4) return 2;
    }
    return std::fclose(dump) == 0 ? 0 : 2;
}
