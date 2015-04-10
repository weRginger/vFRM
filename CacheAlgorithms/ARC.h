#ifndef _ARC_
#define _ARC_


#include <vector>
#include <iostream>
#include "ARC_LRU.h"
#include "ARC_Node.h"

#include "Config.h"
using namespace std;

class ARC
{
public:
                    ARC(long cacheSize);
	ARC_Node*       search(long pageToSearch);
    void            print();
    float           hitRatio();
    long            getHit();
    long            getTotalRequest();
    long            max(long a, long b);
    long            min(long a, long b);
    long            getP();
    bool            input(long newPageData, int readWriteFlag);
    void            replace(long newPageData, long p);
    void            getOccupancyRatio(int algorithmID, vector<vector<long>> &occupancyNumberMatrix, vector<vector<float>> &occupancyRatioMatrix, int traceNumber, int algorithmNumber);
    
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
    ARC_LRU     T1;
    ARC_LRU     T2;
    ARC_LRU     B1;
    ARC_LRU     B2;
    int         _foundCache;         // found cache index (T1=1,T2=2,B1=3,B2=4)
    ARC_Node*   _foundCacheNode;     // found cache item index (e.g. page index [6])
	long        _requestCounter;
	long        _hitCounter;
    long        _p;
    long        _c;
    
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