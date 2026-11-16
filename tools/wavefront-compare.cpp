// Streaming counterpart of verify-aot-windows.sh's numerical contract; keeps dumps off RAM.
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>

int main(int argc, char **argv) {
    if (argc != 4) return 2;
    FILE *left = std::fopen(argv[1], "rb"), *right = std::fopen(argv[2], "rb");
    if (!left || !right) return 2;
    if (std::fseek(left, 0, SEEK_END) || std::fseek(right, 0, SEEK_END)) return 2;
    const long left_bytes = std::ftell(left), right_bytes = std::ftell(right);
    if (left_bytes <= 0 || left_bytes != right_bytes || left_bytes % 16) return 1;
    std::rewind(left);
    std::rewind(right);
    const bool srgb = std::strcmp(argv[3], "srgb") == 0;
    const bool rec709 = std::strcmp(argv[3], "rec709") == 0;
    if (!srgb && !rec709 && std::strcmp(argv[3], "linear")) return 2;
    auto decode = [&](double value) {
        const double a = std::abs(value);
        if (rec709) return std::copysign(std::pow(a, 2.4), value);
        if (srgb) return std::copysign(a <= 0.04045 ? a / 12.92
                                      : std::pow((a + 0.055) / 1.055, 2.4), value);
        return value;
    };
    float a[65536], b[65536];
    double maximum = 0, encoded = 0;
    size_t total = 0;
    bool alpha = true, finite = true;
    while (true) {
        size_t na = std::fread(a, sizeof(float), 65536, left);
        size_t nb = std::fread(b, sizeof(float), 65536, right);
        if (na != nb || std::ferror(left) || std::ferror(right)) return 1;
        if (!na) break;
        for (size_t i = 0; i < na; ++i) {
            finite = finite && std::isfinite(a[i]) && std::isfinite(b[i]);
            if (((total + i) & 3) == 3) alpha = alpha && a[i] == b[i];
            maximum = std::max(maximum, std::abs(decode(a[i]) - decode(b[i])));
            encoded = std::max(encoded, std::abs(double(a[i]) - double(b[i])));
        }
        total += na;
    }
    std::fclose(left);
    std::fclose(right);
    const bool passed = total && total % 4 == 0 && finite && alpha
        && maximum <= 1e-5 && encoded < 1.0 / 255;
    std::printf("{\"passed\":%s,\"samples\":%zu,\"max_linear_error\":%.17g,"
                "\"max_encoded_error\":%.17g,\"finite\":%s,\"alpha_exact\":%s}\n",
                passed ? "true" : "false", total, maximum, encoded,
                finite ? "true" : "false", alpha ? "true" : "false");
    return passed ? 0 : 1;
}
