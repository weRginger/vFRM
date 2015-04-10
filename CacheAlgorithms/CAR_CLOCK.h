#ifndef _CAR_CLOCK_
#define _CAR_CLOCK_

#include <iostream>
#include <vector>
#include <unordered_map>
#include "CAR_Node.h"

#include "Config.h"
using namespace std;


class CAR_CLOCK
{
public:
            CAR_CLOCK();
    long    size();
    void    print();
    CAR_Node*    search(long pageToSearch);
    void    attachToTail(long newPageData, int newPagePRB, bool newPageDirty);
    
    
    long    getPageAt(CAR_Node* node);
    int     getPRBAt(CAR_Node* node);
    
    void    setPRBAt(CAR_Node* node, int newPagePRB);
    void    setDirtyAt(CAR_Node* node, bool newPageDirty);
    
    long    getHeadPage();
    int     getHeadPRB();
    
    void    evictAt(CAR_Node* nodeToDelete, long &_evictPageData, int &_evictPagePRB, bool &_evictPageDirty);
    void    evictHead(long &_evictPageData, int &_evictPagePRB, bool &_evictPageDirty);
    
//    void    getOccupancyRatio(int algorithmID, long occupancyNumberMatrix[algorithmNumber][traceNumber]);
    
    
    void    getOccupancyRatio(int algorithmID, vector<vector<long>> &occupancyNumberMatrix, int traceNumber, int algorithmNumber);
    
    
    
    
private:
    long             _size;
    CAR_Node*        _head;
    std::unordered_map  <long,CAR_Node*> _mappingTable;
};


#endif