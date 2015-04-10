#ifndef _LRU_
#define _LRU_

#include <iostream>
#include <vector>
#include <unordered_map>

#include "Config.h"
using namespace std;

struct LRU_Node
{
    long                data;
    bool                dirty;
    LRU_Node*           prev;
    LRU_Node*           next;
};


class LRU
{
public:
                        LRU(long cacheSize);
    long                size();
    LRU_Node*           search(long pageToSearch);
    void                print();
    void                attachToMRUPage(long newPageData, bool DirtyValue);
    void                evictLRUPage();
    void                evictAt(LRU_Node* nodeToDelete);
    bool                input(long newPageData, int readWriteFlag);   // hit=true, miss=false
    
    float               hitRatio();
    long                getHit();
    long                getTotalRequest();
    
    void                getOccupancyRatio(int algorithmID, vector<vector<long>> &occupancyNumberMatrix, vector<vector<float>> &occupancyRatioMatrix, int traceNumber, int algorithmNumber);
    
    
    // Overhead - SSD-HDD Update
    long                getOverheadWB();
    long                getOverheadWB_IOAdmin();
    long                getOverheadWB_IOEvict();
    long                getOverheadWT();
    long                getOverheadWT_IOAdmin();
    long                getOverheadWT_IOEvict();

    // Overhead - Original IO
    long                getOverheadWB_IO_CacheRead();
    long                getOverheadWB_IO_CacheWrite();
    
private:
    long                _size;
    long                _cacheSize;
    long                _requestCounter;
    long                _hitCounter;
    
    // debug
    long                _missCounter;
    long                _writeHitCounter;
    long                _writeMissCounter;
    
    long                _writeCounter;
    

    LRU_Node*           _head;
    std::unordered_map  <long, LRU_Node*> _mappingTable;
    
    // Overhead - SSD-HDD Update
    long                _overheadCounterWB;
    long                _overheadCounterWB_IOAdmin;
    long                _overheadCounterWB_IOEvict;
    long                _overheadCounterWT;
    long                _overheadCounterWT_IOAdmin;
    long                _overheadCounterWT_IOEvict;
    
    // Overhead - Original IO
    long                _overheadCounterWB_IO_CacheRead;
    long                _overheadCounterWB_IO_CacheWrite;
    
    
    
    // Assistant temp varibles
    long                _evictPageData;
    bool                _evictPageDirty;
    
};

#endif