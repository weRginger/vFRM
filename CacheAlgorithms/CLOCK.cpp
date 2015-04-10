#include "CLOCK.h"

CLOCK::CLOCK(long cacheSize)
{
    _size =0;
    _cacheSize=cacheSize;
    _requestCounter=0;
    _hitCounter=0;
    _head = new CLOCK_Node;
    _head->prev = _head;
    _head->next = _head;
    
    
    _overheadCounterWB=0;
    _overheadCounterWB_IOAdmin=0;
    _overheadCounterWB_IOEvict=0;
    _overheadCounterWT=0;
    _overheadCounterWT_IOAdmin=0;
    _overheadCounterWT_IOEvict=0;
    
    _evictPageData=0;
    _evictPagePRB=0;
    _evictPageDirty=true;
    
    
}

long CLOCK::size()
{
    return _size;
}

void CLOCK::print()
{
    if (_size==0)
    {
        cout<<"Empty list."<<endl;
    }
    else
    {
        vector <int> PRB;
        CLOCK_Node * currentNode = _head->next;
        cout<<"["<<currentNode->data<<"]\t";
        PRB.push_back(currentNode->PRB);
        currentNode=currentNode->next;
        long i=1;
        while (i<_size)
        {
            cout<<currentNode->data<<"\t";
            PRB.push_back(currentNode->PRB);
            i++;
            currentNode=currentNode->next;
        }
        cout<<endl;
        
        for (long i=0; i<PRB.size(); i++)
        {
            if (i==0)
            {
                cout<<"["<<PRB[i]<<"]\t";
            }
            else
            {
                cout<<PRB[i]<<"\t";
            }
        }
        cout<<endl;
        
    }
}



CLOCK_Node* CLOCK::search(long pageToSearch)
{
    CLOCK_Node* foundNode = _mappingTable[pageToSearch];
    if(foundNode)
    {
        if (displayCoutCLOCK) cout<<"Found."<<endl;
        return foundNode;
    }
    else
    {
        if (displayCoutCLOCK) cout<<"Not found."<<endl;
        return NULL;
    }
}

void CLOCK::attachToTail(long newPageData, int PRBValue, bool DirtyValue)
{
    // New node
    CLOCK_Node *newNode = new CLOCK_Node;
    
    newNode->data   = newPageData;
    newNode->PRB    = PRBValue;
    newNode->dirty  = DirtyValue;

    
    _mappingTable[newPageData] = newNode;
    
    // Add new node to tail
    if (_size==0)
    {
        newNode->prev=_head;
        newNode->next=_head;
        _head->prev=newNode;
        _head->next=newNode;
    }
    else
    {   // _head -> old1 -> old2 -> [x] -> _head
        newNode->next = _head;
        newNode->prev = _head->prev;
        _head->prev->next=newNode;
        _head->prev=newNode;
    }
    _size++;
}


long CLOCK::getPageAt(CLOCK_Node* node)
{
    if (_size==0) return -1;
    return node->data;
}

int CLOCK::getPRBAt(CLOCK_Node* node)
{
    if (_size==0) return -1;
    return node->PRB;
}



void CLOCK::setPRBAt(CLOCK_Node* node, int PRBvalue)
{
    node->PRB=PRBvalue;
}



long CLOCK::getHeadPage()
{
    if (_size==0) return -1;
    return _head->next->data;
}

int CLOCK::getHeadPRB()
{
    if (_size==0) return -1;
    return _head->next->PRB;
}







void CLOCK::evictAt(CLOCK_Node* nodeToDelete)
{
    if (_size!=0 && nodeToDelete!=NULL)
    {
        nodeToDelete->prev->next = nodeToDelete->next;
        nodeToDelete->next->prev = nodeToDelete->prev;
        
        _evictPageData      =nodeToDelete->data;
        _evictPagePRB       =nodeToDelete->PRB;
        _evictPageDirty =nodeToDelete->dirty;
        
        _mappingTable.erase(nodeToDelete->data);
        delete nodeToDelete;
        _size--;
    }
}

void CLOCK::evictHead()
{
    if (_size!=0)
    {
        CLOCK_Node* LRU_Node;
        LRU_Node=_head->next;
        
        _evictPageData      =LRU_Node->data;
        _evictPagePRB       =LRU_Node->PRB;
        _evictPageDirty =LRU_Node->dirty;
        
        _head->next=LRU_Node->next;
        LRU_Node->next->prev=_head;
        

        _mappingTable.erase(LRU_Node->data);
        _size--;
        delete LRU_Node;
    }
}
    


    
    



bool CLOCK::input(long newPageData, int readWriteFlag)
{
    _requestCounter++;
	CLOCK_Node* foundNode = search(newPageData);
    
    // Case 1 and 2, oh(wb)=0, oh(wt)=1w/0r
    // Hit
    if (foundNode!=NULL)
	{
        if(displayCoutCLOCK) cout<<"Hit."<<endl;
        _hitCounter++;

		foundNode->PRB=1;
        
        if(readWriteFlag)
        {
            // WB:
            _overheadCounterWB_IO_CacheRead++;
        }
        else
        {
            //  write, mark dirty flag for the new page
            foundNode->dirty=1;
            
            // WB:
            _overheadCounterWB_IO_CacheWrite++;
            
            // WT: Write thru
            _overheadCounterWT++;
            _overheadCounterWT_IOEvict++;
            
            

        }
        
        
        return true;
    }
    
    // Miss
    else
    {
        
        if(displayCoutCLOCK) cout<<"Miss."<<endl;
        
        // WB:
        if (!readWriteFlag)
            _overheadCounterWB_IO_CacheWrite++;
        
        // 3.1 and 4.1 miss not full
        // Cache is not full, then append the new page to tail.
        if (_size<_cacheSize)
        {
            if(displayCoutCLOCK) cout<<"Cache is not full, then append the new page to tail with PRB=0."<<endl;
                        
            // 4.1 miss read not full, oh(wb)=1
            if (readWriteFlag)
            {
                // data->cache, overhead
                attachToTail(newPageData, 0, false);
                
                // WB:
                _overheadCounterWB++;
                _overheadCounterWB_IOAdmin++;
                
                // WT:
                _overheadCounterWT++;
                _overheadCounterWT_IOAdmin++;
                
            }
            // 3.1 miss write not full, oh(wb)=0
            else
            {
                
                attachToTail(newPageData, 0, true);
                
                // WB:
                // no overhead
                
                // WT: write thru
                _overheadCounterWT++;
                _overheadCounterWT_IOEvict++;

            }
            
        }
        
        
        // 3.2 3.3 4.2 4.3 miss full
        // Cache is full, then evict an old page and insert the new page
        else
        {
            if(displayCoutCLOCK) cout<<"Cache is full."<<endl;
            CLOCK_Node* headNode = _head->next;
            //cout<<"Current head ["<<headNode->data<<"]'s PRB is "<<headNode->PRB<<endl;
            while(1) // a circle
            {
                //cout<<"Current head ["<<headNode->data<<"]'s PRB is "<<headNode->PRB<<endl;
                
                // Evict and attach the new page to tail
                if (headNode->PRB==0)
                {
                    //cout<<"Current head ["<<headNode->data<<"]'s PRB is "<<headNode->PRB<<" == 0, evict it and insert the new page to tail."<<endl;
                    // Evict it and insert the new page to it.
                    
                    // Here evict a page from cache to data
                    //
                    
                    evictHead();
                    // T(cache)->data, overhead
                    
                    // 3.2 4.2 victim (head) is dirty
                    // 4.3 miss read full not dirty, oh(wb)=1
                    // After evicting the victim page, attach the new page to the cache
                    // 4. Read
                    if (readWriteFlag)
                    {
                        // 4.2 miss read full dirty, oh(wb)=2, cache->data + data->cache
                        if (_evictPageDirty)
                        {
                            // WB:
                            _overheadCounterWB++;
                            _overheadCounterWB_IOEvict++;
                            
                            // WT:
                            // no overhead
                        }
                        // read: data->cache
                        attachToTail(newPageData, 0, false);
                        
                        // WB:
                        _overheadCounterWB++;
                        _overheadCounterWB_IOAdmin++;
                        
                        // WT: write thru
                        _overheadCounterWT++;
                        _overheadCounterWT_IOAdmin++;
                        
                        
                    }
                    // 3. Write
                    else
                    {
                        // miss write full
                        // 3.2 miss write full dirty, oh(wb)=1
                        if (_evictPageDirty)
                        {
                            // WB:
                            _overheadCounterWB++;
                            _overheadCounterWB_IOEvict++;
                            
                            // WT:
                            // no overhead
                        }
                        
                        // write new page to cache
                        attachToTail(newPageData, 0, true);
                        
                        // WB:
                        // no overhead
                        
                        // WT: write thru
                        _overheadCounterWT++;
                        _overheadCounterWT_IOEvict++;
                    }

                    
                    break;
                }
                
                // headNode->PRB==1, turn CLOCK, NO OVHD!
                else
                {
                    headNode->PRB=0;
                    CLOCK_Node* tempNode=_head->prev;
                    // 1 <-> 2 <-> [_head] <-> [headNode] <-> 3
                    // _head is sentinal, and headNode is the real head node.
                    // Switch _head and headNode
                    // 1 <-> 2 <-> [headNode] <-> [_head] <-> 3
                    // We use tempNode to store the location of [3]
                    
                    // 1 <-> 2->[headNode]
                    _head->prev->next=headNode;
                    
                    // [_head] <- 3
                    headNode->next->prev=_head;
                    
                    // 1 <-> 2 -> [headNode] <- [_head] <-> 3
                    _head->next=headNode->next;
                    _head->prev=headNode;
                    
                    // 1 <-> 2 <-> [headNode] <-> [_head] <-> 3
                    headNode->next=_head;
                    headNode->prev=tempNode;
                    
                    
                    // Found mistake here! 20140207
                    // Should iterate to the new headNode instead of staying at the old one
                    // After switch [headNode] and [_head]:
                    // 1 <-> 2 <-> [headNode] <-> [_head] <-> 3
                    // Iterate to the new headNode
                    // 1 <-> 2 <-> [oldHeadNode] <-> [_head] <-> [3 newHeadNode]
                    headNode = _head->next;
                }
            }
        }
        return false;
    }
}

float CLOCK::hitRatio()
{
    return (float)_hitCounter/_requestCounter;
}

long CLOCK::getHit()
{
    return _hitCounter;
}

long CLOCK::getTotalRequest()
{
    return _requestCounter;
}


void CLOCK::getOccupancyRatio(int algorithmID, vector<vector<long>> &occupancyNumberMatrix, vector<vector<float>> &occupancyRatioMatrix, int traceNumber, int algorithmNumber)
{
    // Clean old data
    for (int i=0; i<traceNumber; i++)
    {
        occupancyNumberMatrix[algorithmID][i]=0;
        occupancyRatioMatrix[algorithmID][i]=0;
    }
    
    if (_size==0)
    {
        //cout<<"Empty list."<<endl;
    }
    
    else
    { 
        CLOCK_Node * currentNode = _head->next;
        for (long i=0; i<_size; i++)
        {
            //cout<<currentNode->data<<"\t";
            occupancyNumberMatrix[algorithmID][(currentNode->data)%10000]++;
            currentNode=currentNode->next;
        }
        
        
        for (int i=0; i<traceNumber; i++)
        {
            occupancyRatioMatrix[algorithmID][i]=(float) occupancyNumberMatrix[algorithmID][i]/_size;
            //cout<<"Trace["<<i<<"]="<<_traceOccupancyRatio[i]*100<<"%\t";
        }          //cout<<endl;
    }
    


}


long CLOCK::getOverheadWB()
{
    
    return _overheadCounterWB;
    
}

long CLOCK::getOverheadWB_IOAdmin()
{
    return _overheadCounterWB_IOAdmin;
}

long CLOCK::getOverheadWB_IOEvict()
{
    return _overheadCounterWB_IOEvict;
}


long CLOCK::getOverheadWT()
{
    
    return _overheadCounterWT;
    
}

long CLOCK::getOverheadWT_IOAdmin()
{
    return _overheadCounterWT_IOAdmin;
}

long CLOCK::getOverheadWT_IOEvict()
{
    return _overheadCounterWT_IOEvict;
}



long CLOCK::getOverheadWB_IO_CacheRead()
{
    return _overheadCounterWB_IO_CacheRead;
}


long CLOCK::getOverheadWB_IO_CacheWrite()
{
    return _overheadCounterWB_IO_CacheWrite;
}


