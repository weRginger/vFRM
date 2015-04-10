#ifndef _ARC_LRU_
#define _ARC_LRU_

#include <iostream>
#include <vector>
#include <unordered_map>
#include "ARC_Node.h"

#include "Config.h"
using namespace std;

class ARC_LRU
{
public:
                        ARC_LRU();
    long                size();
    ARC_Node*           search(long pageToSearch);
    void                print();
    void                attachToMRUPage(long newPageData, bool newPageDirty);
    void                evictLRUPage(long &_evictPageData, bool &_evictPageDirty);
    void                evictAt(ARC_Node* nodeToDelete, long &_evictPageData, bool &_evictPageDirty);
//    void                getOccupancyRatio(int algorithmID, long occupancyNumberMatrix[algorithmNumber][traceNumber]);
    
    void                getOccupancyRatio(int algorithmID, vector<vector<long>> &occupancyNumberMatrix, int traceNumber, int algorithmNumber);
    
private:
    long                _size;
    ARC_Node*          _head;
    std::unordered_map  <long,ARC_Node*> _mappingTable;
};


#endif