// Included only by the explicit macOS three-stage diagnostic host build.
// Shared film expressions remain in Graph/Stages; this file owns scheduling only.
template<class Invoke>
int run_wavefront_three_stage(const WavefrontVariant &variant, FrameFunction halation,
    halide_buffer_t *out,int width,int height,const float *configuration,
    int log_reach,int halo_reach,const FotufilmWavefrontOptions &options,
    FotufilmWavefrontResult *result,Invoke invoke) {
    using namespace fotufilm::gpu;
    if (!halation || variant.rows!=512 || log_reach<0 || halo_reach<0
        || 512+2*log_reach>kWavefrontLogRows
        || 512+2*(log_reach+halo_reach)>kWavefrontLightRows) return -94;
    FrameScope frame_scope;
    const int64_t a_count=int64_t(width)*kWavefrontLightRows*3;
    const int64_t b_count=int64_t(width)*kWavefrontLogRows*3;
    if (kWavefrontLightBase+a_count+b_count>INT32_MAX) return -1;
    Buffer<float> cfg(static_cast<float *>(nullptr),int(kWavefrontLightBase+a_count+b_count));
    int error=cfg.device_malloc(halide_metal_device_interface());
    if (!error) error=halide_device_malloc(nullptr,out,halide_metal_device_interface());
    if (error) return error;
    id native=reinterpret_cast<id>(halide_metal_get_buffer(nullptr,cfg.raw_buffer()));
    if (((unsigned long (*)(id,SEL))objc_msgSend)(native,sel_getUid("storageMode"))!=0) return -1;
    auto *mapped=static_cast<float *>(((void *(*)(id,SEL))objc_msgSend)(native,sel_getUid("contents")));
    if (!mapped) return -1;
    cfg.raw_buffer()->host=reinterpret_cast<uint8_t *>(mapped);
    std::memcpy(mapped,configuration,FOTUFILM_FRAME_CONFIGURATION_COUNT*sizeof(float));
    if (options.trace) std::fill_n(mapped+kWavefrontLightBase,size_t(a_count+b_count),std::nanf(""));
    cfg.set_device_dirty();
    // The unchanged first-stage ABI sees its original prefix+light extent. All views
    // retain the same physical shared Metal allocation until the final queue drain.
    halide_dimension_t source_cfg_dim=cfg.raw_buffer()->dim[0];
    source_cfg_dim.extent=int(kWavefrontLightBase+a_count);
    halide_buffer_t source_cfg=*cfg.raw_buffer();source_cfg.dim=&source_cfg_dim;
    WavefrontCrop scalar_a,scalar_b;
    auto field=[&](WavefrontCrop &target,int base,int count)->int {
        target.dimensions[0]={base,count,1,0};target.buffer=*cfg.raw_buffer();
        target.buffer.dim=target.dimensions;target.buffer.device=0;target.buffer.device_interface=nullptr;
        target.buffer.host=reinterpret_cast<uint8_t *>(mapped+base);
        int e=halide_device_crop(nullptr,cfg.raw_buffer(),&target.buffer);target.active=!e;return e;
    };
    error=field(scalar_a,kWavefrontLightBase,int(a_count));
    if (!error) error=field(scalar_b,int(kWavefrontLightBase+a_count),int(b_count));
    if (error) return error;
    halide_dimension_t shape_a[]={{0,width,1,0},{0,kWavefrontLightRows,width,0},{0,3,width*kWavefrontLightRows,0}};
    halide_dimension_t shape_b[]={{0,width,1,0},{0,kWavefrontLogRows,width,0},{0,3,width*kWavefrontLogRows,0}};
    halide_buffer_t ring_a=scalar_a.buffer,ring_b=scalar_b.buffer;
    ring_a.dimensions=ring_b.dimensions=3;ring_a.dim=shape_a;ring_b.dim=shape_b;
    std::vector<int> labels_a(kWavefrontLightRows,-1),labels_b(kWavefrontLogRows,-1);
    int head_a=0,head_b=0,completed=-1,a_calls=0,b_calls=0,c_calls=0;
    const int bands=(height+511)/512;
    if (result) result->ring_rows=kWavefrontLightRows;
    auto trace=[&](int event,int band,int y,int rows,int slot) {
        if (options.trace) options.trace(options.trace_context,event,band,y,rows,slot);
    };
    auto reserve=[&](const std::vector<int> &labels,int y,int n,int capacity,int support)->bool {
        for (int row=y;row<y+n;++row) {
            int old=labels[row%capacity];
            if (old>=0 && std::min(bands-1,(old+support)/512)>completed) return false;
        }
        return true;
    };
    auto crop=[&](WavefrontCrop &target,halide_buffer_t &ring,halide_dimension_t *shape,int y,int n)->int {
        const int capacity=shape[1].extent,slot=y%capacity;
        std::copy(shape,shape+3,target.dimensions);target.dimensions[1].min=slot;target.dimensions[1].extent=n;
        target.buffer=ring;target.buffer.dim=target.dimensions;target.buffer.device=0;target.buffer.device_interface=nullptr;
        target.buffer.host=ring.host+int64_t(slot)*width*sizeof(float);
        int e=halide_device_crop(nullptr,&ring,&target.buffer);target.active=!e;
        target.dimensions[1].min=y;return e;
    };
    for (int band=0;band<bands && !error;++band) {
        const int start=band*512,rows=std::min(512,height-start);
        const int end_b=std::min(height,start+rows+log_reach);
        while (head_b<end_b && !error) {
            const int n_b=std::min(end_b-head_b,kWavefrontLogRows-head_b%kWavefrontLogRows);
            const int end_a=std::min(height,head_b+n_b+halo_reach);
            while (head_a<end_a && !error) {
                const int n_a=std::min(end_a-head_a,kWavefrontLightRows-head_a%kWavefrontLightRows);
                if (!reserve(labels_a,head_a,n_a,kWavefrontLightRows,log_reach+halo_reach)) {error=-91;break;}
                WavefrontCrop target;error=crop(target,ring_a,shape_a,head_a,n_a);if (error) break;
                trace(1,band,head_a,n_a,head_a%kWavefrontLightRows);
                source_cfg.flags=cfg.raw_buffer()->flags;
                error=invoke(variant.source,&source_cfg,&target.buffer);
                trace(2,band,head_a,n_a,head_a%kWavefrontLightRows);if (error) break;
                cfg.set_device_dirty();
                for (int y=head_a;y<head_a+n_a;++y) labels_a[y%kWavefrontLightRows]=y;
                head_a+=n_a;++a_calls;
                if (result) {result->producer_rows+=n_a;++result->producer_calls;}
#if FOTUFILM_WAVEFRONT_TESTING
                if (options.test_fail_after_source_call==a_calls) {error=-93;break;}
#endif
            }
            if (error) break;
            for (int y=std::max(0,head_b-halo_reach);y<end_a;++y)
                if (labels_a[y%kWavefrontLightRows]!=y) {error=-92;break;}
            if (error) break;
            if (!reserve(labels_b,head_b,n_b,kWavefrontLogRows,log_reach)) {error=-91;break;}
            WavefrontCrop target;error=crop(target,ring_b,shape_b,head_b,n_b);if (error) break;
            trace(6,band,head_b,n_b,head_b%kWavefrontLogRows);
            error=invoke(halation,cfg.raw_buffer(),&target.buffer);
            trace(7,band,head_b,n_b,head_b%kWavefrontLogRows);if (error) break;
            cfg.set_device_dirty();
            for (int y=head_b;y<head_b+n_b;++y) labels_b[y%kWavefrontLogRows]=y;
            head_b+=n_b;++b_calls;
#if FOTUFILM_WAVEFRONT_TESTING
            if (options.test_fail_after_source_call==-b_calls) {error=-95;break;}
#endif
        }
        if (error) break;
        for (int y=std::max(0,start-log_reach);y<end_b;++y)
            if (labels_b[y%kWavefrontLogRows]!=y) {error=-92;break;}
        if (error) break;
        WavefrontCrop target;
        std::copy(out->dim,out->dim+3,target.dimensions);target.dimensions[1].min=start;target.dimensions[1].extent=rows;
        target.buffer=*out;target.buffer.dim=target.dimensions;target.buffer.device=0;target.buffer.device_interface=nullptr;
        target.buffer.host=out->host+int64_t(start)*out->dim[1].stride*sizeof(float);
        error=halide_device_crop(nullptr,out,&target.buffer);target.active=!error;if (error) break;
        trace(3,band,start,rows,0);error=invoke(variant.consumer,cfg.raw_buffer(),&target.buffer);trace(4,band,start,rows,0);
        if (!error) {out->set_device_dirty();error=halide_device_sync(nullptr,out);}
        if (!error) {completed=band;++c_calls;if (result) ++result->consumer_calls;trace(5,band,start,rows,0);}
    }
    const int drain=halide_device_sync(nullptr,out);if (result) result->drain_status=drain;
    static thread_local bool reported=false;
    if (!reported && !error && !drain) {
        std::fprintf(stderr,"THREE_STAGE_COUNTS light_rows=%d log_rows=%d light_calls=%d log_calls=%d output_calls=%d log_ring_rows=%d log_reach=%d halo_reach=%d\n",
            head_a,head_b,a_calls,b_calls,c_calls,kWavefrontLogRows,log_reach,halo_reach);
        reported=true;
    }
    return error ? error : drain;
}
