#ifndef _CAR_LRU_
#define _CAR_LRU_

#include <iostream>
#include <vector>
#include <unordered_map>
#include "CAR_Node.h"

#include "Config.h"
using namespace std;

class CAR_LRU
{
public:
                        CAR_LRU();
    long                size();
    CAR_Node*           search(long pageToSearch);
    void                print();
    
    void                attachToMRUPage(long newPageData, int PRBValue, bool DirtyValue);
    
    void                evictLRUPage(long &_evictPageData, int &_evictPagePRB, bool &_evictPageDirty);
    void                evictAt(CAR_Node* nodeToDelete, long &_evictPageData, int &_evictPagePRB, bool &_evictPageDirty);
    
private:
    long                _size;
    CAR_Node*           _head;
    std::unordered_map  <long,CAR_Node*> _mappingTable;
};


#endif