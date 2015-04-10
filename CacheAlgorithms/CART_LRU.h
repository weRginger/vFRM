#ifndef _CART_LRU_
#define _CART_LRU_

#include <iostream>
#include <vector>
#include <unordered_map>
#include "CART_Node.h"

#include "Config.h"
using namespace std;

class CART_LRU
{
public:
                        CART_LRU();
    long                size();
    CART_Node*          search(long pageToSearch);
    void                print();
    void                attachToMRUPage(long newPageData, int newPagePRB, int newPagePTB, bool DirtyValue);
    void                evictLRUPage(long &_evictPageData, int &_evictPagePRB, int &_evictPagePTB, bool &_evictPageDirty);
    void                evictAt(CART_Node* nodeToDelete, long &_evictPageData, int &_evictPagePRB, int &_evictPagePTB, bool &_evictPageDirty);
    
    

private:
    long                _size;
    CART_Node*          _head;
    std::unordered_map  <long,CART_Node*> _mappingTable;
};


#endif