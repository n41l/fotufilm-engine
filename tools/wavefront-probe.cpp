// Research-only AOT generator for the existing Gaussian stages. No runtime selector changes.
#define FOTUFILM_HALIDE_ENABLED 1
#include "FotufilmHalideShared.h"
#include "Schedule/Gpu.h"

#include <filesystem>
#include <iostream>
#include <string>

int main(int argc, char **argv) {
    if (argc != 5) {
        std::cerr << "usage: wavefront-probe general|windowed|wavefront OUTPUT BAND FOLD_ROWS\n";
        return 2;
    }
    const std::string mode = argv[1];
    const bool folded = mode == "wavefront";
    if (!folded && mode != "general" && mode != "windowed") return 2;
    const int band = std::stoi(argv[3]), fold = std::stoi(argv[4]);
    if (band <= 0 || fold < band + 128 || (fold & (fold - 1))) return 2;
    std::filesystem::create_directories(argv[2]);
    using namespace Halide;
    using namespace fotufilm::gpu;
    GpuConfiguration config;
    config.device = DeviceAPI::Metal;
    config.half_blur = config.half_lut = config.half_tetra = false;
    GpuSchedule schedule(config, mode != "general");
    ImageParam input(Float(32), 3, "input");
    Param<int32_t> width("width"), height("height"), radius("radius");
    Var x("x"), y("y"), channel("channel");
    input.dim(0).set_stride(4);
    input.dim(2).set_bounds(0, 4).set_stride(1);
    Func scene("scene");
    scene(x, y, channel) = input(x, y, channel);
    // Exactly the shared engine's blur construction and precision. Two stages compose reach.
    Func first = schedule.gpu_gaussian(scene, 1.1f, 1.4f, 1.7f, radius,
                                       width, height, false, "first");
    Func second = schedule.gpu_gaussian(first, 1.3f, 1.6f, 1.9f, radius,
                                        width, height, false, "second");
    Func output("probe_output");
    output(x, y, channel) = select(channel == 3, input(x, y, 3),
                                  second(x, y, min(channel, 2)));
    output.output_buffer().dim(0).set_stride(4);
    output.output_buffer().dim(2).set_bounds(0, 4).set_stride(1);
    if (mode == "general") {
        schedule.gpu_pointwise(output, x, y, channel, 4);
    } else {
        Var window, row, bx, by, tx, ty;
        output.compute_root().bound(channel, 0, 4).reorder(channel, x, y).unroll(channel)
            .split(y, window, row, band, TailStrategy::GuardWithIf)
            .gpu_tile(x, row, bx, by, tx, ty, config.tile_x, config.tile_y,
                      TailStrategy::GuardWithIf, DeviceAPI::Metal);
        for (Func stage : schedule.window_stores()) {
            stage.trace_realizations();
            // Fold one predecessor first. Folding every stage lets the final
            // stage's sliding select obscure monotonic bounds of its ancestors.
            if (folded && stage.name() == "first_horizontal") {
                stage.store_root().compute_at(output, window)
                    .fold_storage(stage.args()[1], fold);
            } else {
                stage.store_at(output, window).compute_at(output, window);
            }
        }
    }
    schedule.place_register_stages();
    const std::string prefix = std::string(argv[2]) + "/probe";
    Target target(Target::OSX, Target::ARM, 64, {Target::Metal, Target::StrictFloat});
    set_metal_compiler_and_linker(
        "xcrun -sdk macosx metal -mmacosx-version-min=14.0 -fmetal-math-mode=safe",
        "xcrun -sdk macosx metallib");
    Pipeline pipeline(output);
    const std::vector<Argument> arguments{input, width, height, radius};
    try {
        pipeline.compile_to_lowered_stmt(prefix + ".stmt", arguments, Text, target);
        pipeline.compile_to_static_library(prefix, arguments, "fotufilm_wavefront_probe", target);
    } catch (const Halide::Error &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
    std::cout << "AOT probe: " << mode << ", band=" << band << ", fold=" << fold << '\n';
}
