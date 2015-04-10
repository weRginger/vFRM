#ifndef _CART_
#define _CART_

#include <vector>
#include <iostream>
#include "CART_CLOCK.h"
#include "CART_LRU.h"
#include "CART_Node.h"

#include "Config.h"
using namespace std;

class CART
{
public:
                    CART(long cacheSize);
	CART_Node*      search(long pageToSearch);
    void            print();
    float           hitRatio();
    long            getHit();
    long            getTotalRequest();
    long            max(long a, long b);
    long            min(long a, long b);
    long            getP();
    long            getQ();
    bool            input(long newPageData, int readWriteFlag);
    void            replace();
//    void            getOccupancyRatio(int algorithmID, long occupancyNumberMatrix[algorithmNumber][traceNumber], float occupancyRatioMatrix[algorithmNumber][traceNumber]);

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
    CART_CLOCK      T1;
    CART_CLOCK      T2;
    CART_LRU        B1;
    CART_LRU        B2;
    int             _foundCache;         // found cache index (T1=1,T2=2,B1=3,B2=4)
    CART_Node*      _foundCacheNode;     // found cache item index (e.g. page index [6])
	long            _requestCounter;
	long            _hitCounter;
    long            _p;
    long            _q;
    long            _c;
    long            _ns;
    long            _nl;
    
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
    int             _evictPagePTB;
    bool            _evictPageDirty;
};



#endif
