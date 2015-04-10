#ifndef _CART_CLOCK_
#define _CART_CLOCK_

#include <iostream>
#include <vector>
#include <unordered_map>
#include "CART_Node.h"

#include "Config.h"
using namespace std;


class CART_CLOCK
{
public:
            CART_CLOCK();
    long    size();
    void    print();
    CART_Node*    search(long pageToSearch);
    void    attachToTail(long newPageData, int newPagePRB, int newPagePTB, bool newPageDirty);

    
    long    getPageAt(CART_Node* node);
    int     getPRBAt(CART_Node* node);
    int     getPTBAt(CART_Node* node);
    
    void    setPRBAt(CART_Node* node, int newPagePRB);
    void    setPTBAtTailToL();
    void    setDirtyAt(CART_Node* node, bool newPageDirty);
    
    long    getHeadPage();
    int     getHeadPRB();
    int     getHeadPTB();
    
    void    evictAt(CART_Node* nodeToDelete, long &_evictPageData, int &_evictPagePRB, int &_evictPagePTB, bool &_evictPageDirty);
    void    evictHead(long &_evictPageData, int &_evictPagePRB, int &_evictPagePTB, bool &_evictPageDirty);
    
//    void    getOccupancyRatio(int algorithmID, long occupancyNumberMatrix[algorithmNumber][traceNumber]);
    
    void    getOccupancyRatio(int algorithmID, vector<vector<long>> &occupancyNumberMatrix, int traceNumber, int algorithmNumber);
    
private:
    long              _size;
    CART_Node*        _head;
    std::unordered_map  <long,CART_Node*> _mappingTable;
};


#endif