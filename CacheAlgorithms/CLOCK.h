#ifndef _CLOCK_
#define _CLOCK_

#include <iostream>
#include <vector>
#include <unordered_map>


#include "Config.h"
using namespace std;


struct CLOCK_Node
{
    long                data;
    int                 PRB;
    bool                dirty;
    CLOCK_Node*         prev;
    CLOCK_Node*         next;
};


class CLOCK
{
public:
                        CLOCK(long cacheSize);
    long                size();
    void                print();
    CLOCK_Node*         search(long pageToSearch);
    void                attachToTail(long newPageData, int PRBValue, bool DirtyValue);
    
    
    long                getPageAt(CLOCK_Node* node);
    int                 getPRBAt(CLOCK_Node* node);
    
    void                setPRBAt(CLOCK_Node* node, int PRBValue);
    
    long                getHeadPage();
    int                 getHeadPRB();
    
    void                evictAt(CLOCK_Node* nodeToDelete);
    void                evictHead();
    bool                input(long newPageData, int readWriteFlag);
    
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
    long                getOverheadWB_IO_CacheWrite();
    long                getOverheadWB_IO_CacheRead();
    
private:
    long                _size;
    long                _cacheSize;
    long                _requestCounter;
    long                _hitCounter;

    CLOCK_Node*         _head;
    std::unordered_map  <long,CLOCK_Node*> _mappingTable;
    
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
    int                 _evictPagePRB;
    bool                _evictPageDirty;
};


#endif