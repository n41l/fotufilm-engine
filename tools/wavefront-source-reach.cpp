// Scalar planning diagnostic only; no GPU work or performance conclusion.
#include "../Sources/FotufilmHalide/FotufilmWavefrontAdmission.h"
#include "FotufilmHalide.h"
#include <cstdio>
#include <cstring>
#include <vector>
int main(int argc,char **argv) {
    for (int i=1;i<argc;++i) {
        FILE *file=std::fopen(argv[i],"rb");uint32_t h[10];
        if (!file || std::fread(h,sizeof(h),1,file)!=1 || std::memcmp(h,"FSWP",4)
            || h[6]!=FOTUFILM_FRAME_CONFIGURATION_COUNT) return 2;
        std::vector<float> configuration(h[6]);
        if (std::fread(configuration.data(),sizeof(float),h[6],file)!=h[6]) return 2;
        std::fclose(file);
        fotufilm::ResolvedFrameParams frame(configuration.data(),h[2],h[3],h[5],0,0,0);
        std::printf("%s source_reach=%lld post_mtf_reach=%lld\n",argv[i],
            (long long)fotufilm::wavefront_source_reach(frame,configuration.data(),h[4]),
            (long long)fotufilm::wavefront_post_mtf_reach(frame,h[4]));
    }
}
