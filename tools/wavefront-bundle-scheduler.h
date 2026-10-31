// Explicit two-stage research host: one producer call emits new light plus
// three coarse grids. Shared Graph/Stages define all photographic expressions.
using BundleFunction=int (*)(FOTUFILM_AOT_FRAME_SIGNATURE,halide_buffer_t *,halide_buffer_t *,halide_buffer_t *);
template<class Invoke>
int run_wavefront_bundle(const WavefrontVariant &variant,BundleFunction producer,
    halide_buffer_t *out,int width,int height,const float *configuration,
    const int *strides,const int *radii,int log_reach,const FotufilmWavefrontOptions &options,
    FotufilmWavefrontResult *result,Invoke invoke) {
    using namespace fotufilm::gpu;
    if(!producer||variant.rows!=512)return -94;
    FrameScope frame_scope;
    int w[3],h[3],base[3],fhead[3]={},updates[3]={};
    int64_t total=kWavefrontLightBase+int64_t(width)*kWavefrontLightRows*3;
    for(int i=0;i<3;++i) {
        if(strides[i]<=0||radii[i]<0)return -94;
        w[i]=(width+strides[i]-1)/strides[i];h[i]=(height+strides[i]-1)/strides[i];
        if(total>INT32_MAX)return -1;base[i]=int(total);total+=int64_t(w[i])*h[i]*3;
    }
    if(total>INT32_MAX)return -1;
    Buffer<float> cfg(static_cast<float *>(nullptr),int(total));
    int error=cfg.device_malloc(halide_metal_device_interface());
    if(!error)error=halide_device_malloc(nullptr,out,halide_metal_device_interface());
    if(error)return error;
    id native=reinterpret_cast<id>(halide_metal_get_buffer(nullptr,cfg.raw_buffer()));
    if(((unsigned long(*)(id,SEL))objc_msgSend)(native,sel_getUid("storageMode"))!=0)return -1;
    float *mapped=static_cast<float *>(((void *(*)(id,SEL))objc_msgSend)(native,sel_getUid("contents")));
    if(!mapped)return -1;cfg.raw_buffer()->host=reinterpret_cast<uint8_t *>(mapped);
    std::memcpy(mapped,configuration,FOTUFILM_FRAME_CONFIGURATION_COUNT*sizeof(float));
    if(options.trace)std::fill(mapped+kWavefrontLightBase,mapped+total,std::nanf(""));
    cfg.set_device_dirty();
    std::array<WavefrontCrop,4> scalar;
    std::array<halide_buffer_t,4> rings;
    halide_dimension_t shape[4][3];
    for(int i=0;i<4;++i) {
        int offset=i ? base[i-1] : kWavefrontLightBase;
        int columns=i ? w[i-1] : width,rows=i ? h[i-1] : kWavefrontLightRows;
        auto &s=scalar[i];s.dimensions[0]={offset,columns*rows*3,1,0};s.buffer=*cfg.raw_buffer();
        s.buffer.dim=s.dimensions;s.buffer.device=0;s.buffer.device_interface=nullptr;
        s.buffer.host=reinterpret_cast<uint8_t *>(mapped+offset);
        error=halide_device_crop(nullptr,cfg.raw_buffer(),&s.buffer);s.active=!error;if(error)return error;
        shape[i][0]={0,columns,1,0};shape[i][1]={0,rows,columns,0};shape[i][2]={0,3,columns*rows,0};
        rings[i]=s.buffer;rings[i].dimensions=3;rings[i].dim=shape[i];
    }
    auto crop=[&](WavefrontCrop &target,int index,int y,int rows)->int {
        int physical=index ? y : y%kWavefrontLightRows;
        std::copy(shape[index],shape[index]+3,target.dimensions);target.dimensions[1].min=physical;target.dimensions[1].extent=rows;
        target.buffer=rings[index];target.buffer.dim=target.dimensions;target.buffer.device=0;target.buffer.device_interface=nullptr;
        target.buffer.host=rings[index].host+int64_t(physical)*shape[index][0].extent*sizeof(float);
        int e=halide_device_crop(nullptr,&rings[index],&target.buffer);target.active=!e;
        target.dimensions[1].min=y;return e;
    };
    auto trace=[&](int event,int band,int y,int rows,int slot) {
        if(options.trace)options.trace(options.trace_context,event,band,y,rows,slot);
    };
    std::vector<int> labels(kWavefrontLightRows,-1);int head=0,completed=-1,calls=0,consumers=0;
    const int bands=(height+511)/512;if(result)result->ring_rows=kWavefrontLightRows;
    for(int band=0;band<bands&&!error;++band) {
        int start=band*512,rows=std::min(512,height-start),end=std::min(height,start+rows+kWavefrontLightMargin);
        while(head<end&&!error) {
            int n=std::min(end-head,kWavefrontLightRows-head%kWavefrontLightRows);
            for(int y=head;y<head+n;++y) {
                int old=labels[y%kWavefrontLightRows];
                if(old>=0&&std::min(bands-1,(old+kWavefrontLightMargin)/512)>completed){error=-91;break;}
            }
            if(error)break;
            int next[3];std::array<WavefrontCrop,4> target;
            error=crop(target[0],0,head,n);if(error)break;
            for(int i=0;i<3&&!error;++i) {
                next[i]=head+n==height ? h[i] : std::max(0,(head+n)/strides[i]-fotufilm::kTripleBoxPasses*radii[i]);
                if(next[i]<fhead[i]||next[i]>h[i]){error=-96;break;}
                if(next[i]>fhead[i]) {
                    int lo=std::max(0,(fhead[i]-fotufilm::kTripleBoxPasses*radii[i])*strides[i]);
                    int hi=std::min(height,(next[i]+fotufilm::kTripleBoxPasses*radii[i])*strides[i]);
                    for(int y=lo;y<hi;++y)if(y<head||y>=head+n) {
                        if(labels[y%kWavefrontLightRows]!=y || (y%kWavefrontLightRows>=head%kWavefrontLightRows
                            &&y%kWavefrontLightRows<head%kWavefrontLightRows+n)){error=-92;break;}
                    }
                }
                if(!error)error=crop(target[i+1],i+1,fhead[i],next[i]-fhead[i]);
            }
            if(error)break;
            trace(1,band,head,n,head%kWavefrontLightRows);
            for(int i=0;i<3;++i)trace(8+i,band,fhead[i],next[i]-fhead[i],h[i]);
            error=invoke(producer,cfg.raw_buffer(),&target[0].buffer,&target[1].buffer,&target[2].buffer,&target[3].buffer);
            trace(2,band,head,n,head%kWavefrontLightRows);if(error)break;
            cfg.set_device_dirty();for(int y=head;y<head+n;++y)labels[y%kWavefrontLightRows]=y;
            head+=n;++calls;for(int i=0;i<3;++i){updates[i]+=next[i]>fhead[i];fhead[i]=next[i];}
            if(result){result->producer_rows+=n;++result->producer_calls;}
#if FOTUFILM_WAVEFRONT_TESTING
            if(options.test_fail_after_source_call==calls){error=-93;break;}
#endif
        }
        if(error)break;
        for(int y=std::max(0,start-log_reach);y<std::min(height,start+rows+log_reach);++y)
            if(labels[y%kWavefrontLightRows]!=y){error=-92;break;}
        for(int i=0;i<3&&!error;++i) {
            int required=std::min(h[i],(std::min(height,start+rows+log_reach)+strides[i]-1)/strides[i]+1);
            if(fhead[i]<required)error=-92;
        }
        if(error)break;
        WavefrontCrop target;std::copy(out->dim,out->dim+3,target.dimensions);
        target.dimensions[1].min=start;target.dimensions[1].extent=rows;target.buffer=*out;
        target.buffer.dim=target.dimensions;target.buffer.device=0;target.buffer.device_interface=nullptr;
        target.buffer.host=out->host+int64_t(start)*out->dim[1].stride*sizeof(float);
        error=halide_device_crop(nullptr,out,&target.buffer);target.active=!error;if(error)break;
        trace(3,band,start,rows,0);error=invoke(variant.consumer,cfg.raw_buffer(),&target.buffer);trace(4,band,start,rows,0);
        if(!error){out->set_device_dirty();error=halide_device_sync(nullptr,out);}
        if(!error){completed=band;++consumers;if(result)++result->consumer_calls;trace(5,band,start,rows,0);}
    }
    int drain=halide_device_sync(nullptr,out);if(result)result->drain_status=drain;
    static thread_local bool reported=false;
    if(!error&&!drain&&!reported) {
        std::fprintf(stderr,"BUNDLE_COUNTS light_rows=%d producer_calls=%d consumer_calls=%d field_rows0=%d field_rows1=%d field_rows2=%d field_updates0=%d field_updates1=%d field_updates2=%d\n",
            head,calls,consumers,fhead[0],fhead[1],fhead[2],updates[0],updates[1],updates[2]);reported=true;
    }
    return error ? error : drain;
}
