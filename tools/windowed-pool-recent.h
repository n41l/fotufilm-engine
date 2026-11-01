#pragma once
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <unordered_map>
#include <vector>

// Host-policy experiment: two-frame size demand, then physical last-use ordering.
// The caller holds pool_mutex. This class never observes or modifies GPU fences.
class WfRecentPool {
public:
    struct Entry { void *buffer; size_t length; };
    struct Plan { bool admit; std::vector<Entry> evict; };
    void beginFrame() { previous.swap(current); current.clear(); }
    void request(size_t length) { ++current[length]; }
    void touch(void *buffer) { touched[buffer]=++sequence; }
    void forget(void *buffer) { touched.erase(buffer); }
    void clear() { current.clear(); previous.clear(); touched.clear(); sequence=0; }
    size_t metadataObjects() const { return touched.size(); }
    uint64_t heat(size_t length) const { return count(current,length)+count(previous,length); }
    Plan plan(Entry incoming, const std::vector<Entry> &idle, size_t bytes, size_t cap) const {
        if(incoming.length>cap || bytes>cap) return {false,{}};
        if(incoming.length<=cap-bytes) return {true,{}};
        const size_t needed=incoming.length-(cap-bytes);
        auto candidates=idle;candidates.push_back(incoming);
        std::sort(candidates.begin(),candidates.end(),[&](const Entry &a,const Entry &b) {
            if(heat(a.length)!=heat(b.length)) return heat(a.length)<heat(b.length);
            if(age(a.buffer)!=age(b.buffer)) return age(a.buffer)<age(b.buffer);
            if(a.length!=b.length) return a.length>b.length;
            return reinterpret_cast<uintptr_t>(a.buffer)<reinterpret_cast<uintptr_t>(b.buffer);
        });
        Plan result{true,{}};size_t freed=0;
        for(const auto &entry:candidates) {
            // Reject atomically: do not discard other cold entries if admission would
            // eventually discard this incoming buffer as well.
            if(entry.buffer==incoming.buffer) return {false,{}};
            result.evict.push_back(entry);freed+=entry.length;
            if(freed>=needed) return result;
        }
        return {false,{}};
    }
private:
    std::unordered_map<size_t,uint64_t> current,previous;
    std::unordered_map<void *,uint64_t> touched;
    uint64_t sequence=0;
    static uint64_t count(const std::unordered_map<size_t,uint64_t> &map,size_t n) {
        auto p=map.find(n);return p==map.end()?0:p->second;
    }
    uint64_t age(void *buffer) const { auto p=touched.find(buffer);return p==touched.end()?0:p->second; }
};
