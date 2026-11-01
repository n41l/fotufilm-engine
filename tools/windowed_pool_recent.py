"""Exact diagnostic transformations; original fenced return order is preserved."""
ADMISSION='''        if (idle_bytes + length <= size_t(pool_megabytes()) << 20) {
            idle.emplace(length, entry.buffer);
            idle_bytes += length;
        } else {
            pooled.erase(entry.buffer);
            send(static_cast<id>(entry.buffer), "release");
        }'''
REPLACEMENTS=[(ADMISSION,'        wfRecentReturn(entry.buffer,length);',1),('    ++frame_depth;','    if (++frame_depth==1) wfRecentBeginFrame();',1),('    idle_bytes = 0;','    idle_bytes = 0;\n    wfRecentReset();',1)]
