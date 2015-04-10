#ifndef _CAR_
#define _CAR_

#include <vector>
#include <iostream>
#include "CAR_LRU.h"
#include "CAR_CLOCK.h"
#include "CAR_Node.h"

#include "Config.h"
using namespace std;

class CAR
{
public:
                    CAR(long cacheSize);
	CAR_Node*       search(long pageToSearch);
    void            print();
    float           hitRatio();
    long            getHit();
    long            getTotalRequest();
    bool            mainCacheIsFull();      // T1 U T2
    bool            recencyCacheIsFull();   // T1 U B1
    bool            frequencyCacheIsFull(); // T2 U B2
    bool            allCacheIsFull();       // T1 U B1 U T2 U B2
    long            max(long a, long b);
    long            min(long a, long b);
    long            getP();
    bool            input(long newPageData, int readWriteFlag);
    void            replace();
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
    CAR_CLOCK       T1;
    CAR_CLOCK       T2;
    CAR_LRU         B1;
    CAR_LRU         B2;
    int             _foundCache;         // found cache index (T1=1,T2=2,B1=3,B2=4)
    CAR_Node*       _foundCacheNode;     // found cache item index (e.g. page index [6])
	long            _requestCounter;
	long            _hitCounter;
    long            _p;
    long            _c;

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
    long            _evictPageData;
    int             _evictPagePRB;
    bool            _evictPageDirty;
    
};



#endif