// Extend the unchanged stage20 observer in one diagnostic translation unit.
#define wf_speed_initialize wf_speed_base_initialize
#define wf_speed_begin wf_speed_base_begin
#define wf_speed_finish wf_speed_base_finish
#include "windowed-speed-probe.mm"
#undef wf_speed_initialize
#undef wf_speed_begin
#undef wf_speed_finish
#include <cstdlib>
#include <cstring>
#include <type_traits>
#include <unordered_set>
struct MethodEvent {std::string kind;double begin,end;size_t token,argument=0,bytes=0,queueLimit=0,pendingBefore=0;};
struct MethodLink {size_t token,index;std::string label;};
struct MethodFrame {
    bool enabled=false;size_t next=1,unlinkedCommits=0;
    std::vector<MethodEvent> events;std::vector<MethodLink> links;
    std::unordered_map<const void *,size_t> commands,encoders;std::unordered_set<size_t> linked;
};
static MethodFrame &methods() {static auto *p=new MethodFrame;return *p;}
static thread_local bool methodsActive=false;
static thread_local size_t currentToken=0;
static size_t commandToken(id object) {auto &s=methods();auto i=s.commands.find((const void *)object);return i==s.commands.end()?0:i->second;}
static size_t encoderToken(id object) {auto &s=methods();auto i=s.encoders.find((const void *)object);return i==s.encoders.end()?0:i->second;}
static void recordMethod(const char *kind,double a,double b,size_t token,size_t argument=0,size_t bytes=0) {
    methods().events.push_back({kind,a,b,token,argument,bytes});
}
template<class F> static auto timedMethod(const char *kind,size_t token,F call,size_t argument=0,size_t bytes=0) -> decltype(call()) {
    if(!methodsActive) return call();
    const double a=wf_speed_clock();
    if constexpr(std::is_void_v<decltype(call())>) {call();const double b=wf_speed_clock();recordMethod(kind,a,b,token,argument,bytes);}
    else {auto result=call();const double b=wf_speed_clock();recordMethod(kind,a,b,token,argument,bytes);return result;}
}
static id (*mCommand)(id,SEL);
static id (*mNativeCommand)(id,SEL);
static id (*mQueueLimit)(id,SEL,NSUInteger);
static auto &queueLimits() {static auto *p=new std::unordered_map<const void *,size_t>;return *p;}
static std::mutex &queueLimitMutex() {static auto *p=new std::mutex;return *p;}
static size_t ensureCommand(id command) {
    if(!command) return 0;auto &s=methods();auto it=s.commands.find((const void *)command);
    if(it!=s.commands.end()) return it->second;size_t token=s.next++;s.commands[(const void *)command]=token;return token;
}
static id nativeCommand(id object,SEL sel) {
    if(!methodsActive) return mNativeCommand(object,sel);
    size_t limit=0,pending=0;
    {std::lock_guard<std::mutex> lock(queueLimitMutex());auto it=queueLimits().find((const void *)object);if(it!=queueLimits().end()) limit=it->second;}
    {auto &base=state();std::lock_guard<std::mutex> lock(base.mutex);pending=base.pending;}
    double a=wf_speed_clock();id command=mNativeCommand(object,sel);double b=wf_speed_clock();
    size_t token=0;
    if(command) {token=methods().next++;methods().commands[(const void *)command]=token;}
    methods().events.push_back({"command_create_native",a,b,token,0,0,limit,pending});return command;
}
static id methodQueueLimit(id object,SEL sel,NSUInteger count) {
    id queue=timedMethod("queue_create_with_limit",0,[&]{return mQueueLimit(object,sel,count);},0,count);
    if(queue) {std::lock_guard<std::mutex> lock(queueLimitMutex());queueLimits()[(const void *)queue]=count;}return queue;
}
static id (*mEncoder)(id,SEL);
static id (*mFunction)(id,SEL,NSString *);
static id (*mPipeline)(id,SEL,id,NSError **);
static void (*mState)(id,SEL,id);
static void (*mBuffer)(id,SEL,id,NSUInteger,NSUInteger);
static void (*mBytes)(id,SEL,const void *,NSUInteger,NSUInteger);
static void (*mMemory)(id,SEL,NSUInteger,NSUInteger);
static void (*mDispatch)(id,SEL,MTLSize,MTLSize);
static void (*mEnd)(id,SEL);
static void (*mCommit)(id,SEL);
static id methodCommand(id object,SEL sel) {
    if(!methodsActive) return mCommand(object,sel);
    double a=wf_speed_clock();id command=mCommand(object,sel);double b=wf_speed_clock();size_t token=0;
    if(command) token=ensureCommand(command);
    recordMethod("command_create",a,b,token);return command;
}
static id methodEncoder(id object,SEL sel) {
    size_t token=methodsActive?commandToken(object):0;
    id encoder=timedMethod("encoder_create",token,[&]{return mEncoder(object,sel);});
    if(methodsActive && encoder) {methods().encoders[(const void *)encoder]=token;currentToken=token;}
    return encoder;
}
static id methodFunction(id object,SEL sel,NSString *name) {return timedMethod("function_lookup",currentToken,[&]{return mFunction(object,sel,name);});}
static id methodPipeline(id object,SEL sel,id function,NSError **error) {return timedMethod("pipeline_create",currentToken,[&]{return mPipeline(object,sel,function,error);});}
static void methodState(id object,SEL sel,id state) {timedMethod("pipeline_bind",methodsActive?encoderToken(object):0,[&]{mState(object,sel,state);});}
static void methodBuffer(id object,SEL sel,id buffer,NSUInteger offset,NSUInteger index) {
    const size_t bytes=methodsActive && buffer?[(id<MTLBuffer>)buffer length]:0;
    timedMethod("buffer_bind",methodsActive?encoderToken(object):0,[&]{mBuffer(object,sel,buffer,offset,index);},index,bytes);
}
static void methodBytes(id object,SEL sel,const void *bytes,NSUInteger length,NSUInteger index) {timedMethod("bytes_bind",methodsActive?encoderToken(object):0,[&]{mBytes(object,sel,bytes,length,index);},index,length);}
static void methodMemory(id object,SEL sel,NSUInteger length,NSUInteger index) {timedMethod("threadgroup_memory",methodsActive?encoderToken(object):0,[&]{mMemory(object,sel,length,index);},index,length);}
static void methodDispatch(id object,SEL sel,MTLSize groups,MTLSize threads) {timedMethod("dispatch",methodsActive?encoderToken(object):0,[&]{mDispatch(object,sel,groups,threads);});}
static void methodEnd(id object,SEL sel) {
    const size_t token=methodsActive?encoderToken(object):0;timedMethod("end_encoding",token,[&]{mEnd(object,sel);});
    if(methodsActive) {methods().encoders.erase((const void *)object);if(currentToken==token) currentToken=0;}
}
static void methodCommit(id object,SEL sel) {
    const size_t token=methodsActive?commandToken(object):0;timedMethod("command_commit",token,[&]{mCommit(object,sel);});
    if(!methodsActive) return;
    std::string label=[(id<MTLCommandBuffer>)object label].UTF8String ?: "";
    auto &base=state();std::lock_guard<std::mutex> lock(base.mutex);auto &s=methods();
    if(token && !base.gpu.empty() && base.gpu.back().label==label && !s.linked.count(base.gpu.size()-1)) {
        size_t index=base.gpu.size()-1;s.links.push_back({token,index,label});s.linked.insert(index);
    } else ++s.unlinkedCommits;
}
extern "C" bool wf_speed_initialize(bool useProbe) { @autoreleasepool {
    const char *setting=std::getenv("FOTUFILM_METAL_METHOD_PROBES");methods().enabled=useProbe && setting && !std::strcmp(setting,"1");
    if(!wf_speed_base_initialize(useProbe)) return false;
    // Warm the same small dummy library/classes in all modes before any timed frame.
    id<MTLDevice> dev=MTLCreateSystemDefaultDevice();if(!dev) return false;
    id<MTLCommandQueue> queue=[dev newCommandQueue];id<MTLCommandBuffer> command=[queue commandBuffer];id<MTLComputeCommandEncoder> encoder=[command computeCommandEncoder];
    NSError *error=nil;id<MTLLibrary> library=[dev newLibraryWithSource:@"#include <metal_stdlib>\nusing namespace metal; kernel void wf_probe_dummy(uint x [[thread_position_in_grid]]) {}" options:nil error:&error];
    if(!library) {std::fprintf(stderr,"METHOD_SETUP_FAILED %s\n",error.localizedDescription.UTF8String ?: "library");[encoder endEncoding];[queue release];[dev release];return false;}
    Method slots[]={class_getInstanceMethod(object_getClass(queue),@selector(commandBuffer)),class_getInstanceMethod(object_getClass(command),@selector(computeCommandEncoder)),class_getInstanceMethod(object_getClass(library),@selector(newFunctionWithName:)),class_getInstanceMethod(object_getClass(dev),@selector(newComputePipelineStateWithFunction:error:)),class_getInstanceMethod(object_getClass(encoder),@selector(setComputePipelineState:)),class_getInstanceMethod(object_getClass(encoder),@selector(setBuffer:offset:atIndex:)),class_getInstanceMethod(object_getClass(encoder),@selector(setBytes:length:atIndex:)),class_getInstanceMethod(object_getClass(encoder),@selector(setThreadgroupMemoryLength:atIndex:)),class_getInstanceMethod(object_getClass(encoder),@selector(dispatchThreadgroups:threadsPerThreadgroup:)),class_getInstanceMethod(object_getClass(encoder),@selector(endEncoding)),class_getInstanceMethod(object_getClass(command),@selector(commit)),class_getInstanceMethod(object_getClass(dev),@selector(newCommandQueueWithMaxCommandBufferCount:))};
    [encoder endEncoding];
    for(auto slot:slots) if(!slot) {[library release];[queue release];[dev release];return false;}
    if(methods().enabled) {
#define INSTALL(i,name,fn) name=reinterpret_cast<decltype(name)>(method_setImplementation(slots[i],reinterpret_cast<IMP>(fn)))
        mNativeCommand=previousCommand;previousCommand=nativeCommand;
        INSTALL(0,mCommand,methodCommand);INSTALL(1,mEncoder,methodEncoder);INSTALL(2,mFunction,methodFunction);INSTALL(3,mPipeline,methodPipeline);INSTALL(4,mState,methodState);INSTALL(5,mBuffer,methodBuffer);INSTALL(6,mBytes,methodBytes);INSTALL(7,mMemory,methodMemory);INSTALL(8,mDispatch,methodDispatch);INSTALL(9,mEnd,methodEnd);INSTALL(10,mCommit,methodCommit);INSTALL(11,mQueueLimit,methodQueueLimit);
#undef INSTALL
    }
    [library release];[queue release];[dev release];return true;
}}
extern "C" void wf_speed_begin(int frame) {
    methodsActive=false;currentToken=0;auto &s=methods();s.next=1;s.unlinkedCommits=0;s.events.clear();s.links.clear();s.commands.clear();s.encoders.clear();s.linked.clear();s.events.reserve(4096);s.links.reserve(256);s.commands.reserve(256);s.encoders.reserve(256);s.linked.reserve(256);
    wf_speed_base_begin(frame);methodsActive=s.enabled;
}
extern "C" bool wf_speed_finish(const char *path,double begin,double end) { @autoreleasepool {
    methodsActive=false;currentToken=0;if(!wf_speed_base_finish(path,begin,end)) return false;
    NSData *data=[NSData dataWithContentsOfFile:[NSString stringWithUTF8String:path]];
    NSMutableDictionary *root=data?[NSJSONSerialization JSONObjectWithData:data options:NSJSONReadingMutableContainers error:nullptr]:nil;if(!root) return false;
    NSMutableArray *events=[NSMutableArray array],*links=[NSMutableArray array];auto &s=methods();
    for(const auto &e:s.events) {
        NSMutableDictionary *item=[@{@"kind":[NSString stringWithUTF8String:e.kind.c_str()],@"begin":@(e.begin),@"end":@(e.end),@"command_token":@(e.token),@"argument":@(e.argument),@"bytes":@(e.bytes)} mutableCopy];
        if(e.kind=="command_create_native") {item[@"queue_limit"]=@(e.queueLimit);item[@"callback_pending_before"]=@(e.pendingBefore);}
        [events addObject:item];[item release];
    }
    for(const auto &e:s.links) [links addObject:@{@"token":@(e.token),@"gpu_index":@(e.index),@"label":[NSString stringWithUTF8String:e.label.c_str()]}];
    root[@"method_probes"]=@(s.enabled);root[@"metal_methods"]=events;root[@"method_commands"]=links;root[@"unlinked_native_commits"]=@(s.unlinkedCommits);
    data=[NSJSONSerialization dataWithJSONObject:root options:0 error:nullptr];return data && [data writeToFile:[NSString stringWithUTF8String:path] atomically:YES];
}}
