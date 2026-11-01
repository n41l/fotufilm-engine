#include "windowed-pool-recent.h"
#include <cassert>
#include <cstdio>
using E=WfRecentPool::Entry;
static void *id(uintptr_t n) {return reinterpret_cast<void *>(n);}
int main() {
    WfRecentPool s;
    for(int i=0;i<20;++i) s.request(48);s.request(72);s.beginFrame();
    s.touch(id(1));s.touch(id(2));
    auto p=s.plan({id(2),48},{{id(1),72}},72,100);
    assert(p.admit && p.evict.size()==1 && p.evict[0].buffer==id(1));
    std::puts("PASS frequent exact-size bin displaces colder idle bin");
    p=s.plan({id(1),72},{{id(2),48}},48,100);
    assert(!p.admit && p.evict.empty());
    std::puts("PASS cold incoming rejected without evicting hotter idle");
    s.clear();s.request(60);s.request(60);s.touch(id(1));s.touch(id(2));s.touch(id(3));
    p=s.plan({id(3),60},{{id(1),30},{id(2),30}},60,100);
    assert(p.admit && p.evict.size()==1);
    p=s.plan({id(3),60},{{id(1),30},{id(2),30}},60,70);
    assert(p.admit && p.evict.size()==2);
    std::puts("PASS admission can free several idle entries while respecting cap");
    s.clear();s.request(40);s.request(40);s.request(30);s.touch(id(1));s.touch(id(2));s.touch(id(3));
    p=s.plan({id(2),30},{{id(1),10},{id(3),40}},50,50);
    assert(!p.admit && p.evict.empty());
    std::puts("PASS rejected multi-victim admission is atomic");
    s.clear();for(int i=1;i<=3;++i)s.touch(id(i));
    p=s.plan({id(3),40},{{id(1),40},{id(2),40}},80,80);
    assert(p.admit && p.evict.size()==1 && p.evict[0].buffer==id(1));
    std::puts("PASS equal-demand tie uses physical least recent use");
    s.request(48);s.beginFrame();assert(s.heat(48)==1);s.beginFrame();assert(s.heat(48)==0);
    s.forget(id(1));assert(s.metadataObjects()==2);s.clear();assert(s.metadataObjects()==0);
    std::puts("PASS old workload demand expires and physical metadata is cleared");
    p=s.plan({id(1),101},{},0,100);assert(!p.admit);
    p=s.plan({id(1),100},{},0,100);assert(p.admit && p.evict.empty());
    std::puts("PASS oversize rejection and exact-cap admission");
}
