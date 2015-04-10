#include "LRU.h"

LRU::LRU(long cacheSize)
{
    _size =0;
    _cacheSize=cacheSize;
    _requestCounter=0;
    _hitCounter=0;
    _evictPageDirty=false; // Dirty=0
    _head = new LRU_Node;
    _head->prev = _head;
    _head->next = _head;
    
    _overheadCounterWB=0;
    _overheadCounterWB_IOAdmin=0;
    _overheadCounterWB_IOEvict=0;
    _overheadCounterWT=0;
    _overheadCounterWT_IOAdmin=0;
    _overheadCounterWT_IOEvict=0;
    
    _evictPageData=0;
    _evictPageDirty=true;
    
    
    
    _missCounter=0;
    _writeHitCounter=0;
    _writeMissCounter=0;
    _writeCounter=0;
}




long LRU::size()
{
    return _size;
}


LRU_Node* LRU::search(long pageToSearch)
{
    LRU_Node* foundNode = _mappingTable[pageToSearch];
    if(foundNode)
    {
        //if (displayCoutLRU) cout<<"Found."<<endl;
        return foundNode;
    }
    else
    {
        //if (displayCoutLRU) cout<<"Not found."<<endl;
        return NULL;
    }
}



void LRU::print()
{
    if (_size==0)
    {
        cout<<"Empty list."<<endl;
    }
    else
    {
        LRU_Node * currentNode = _head->next;
        cout<<"["<<currentNode->data<<"]\t";
        currentNode=currentNode->next;
        long i=1;
        while (i<_size)
        {
            cout<<currentNode->data<<"\t";
            i++;
            currentNode=currentNode->next;
        }
        cout<<endl;
    }
    
}




void LRU::attachToMRUPage(long newPageData, bool DirtyValue)
{
    LRU_Node *newNode = new LRU_Node;
    newNode->data = newPageData;
    newNode->dirty = DirtyValue;
    _mappingTable[newPageData] = newNode;
    
    if (_size==0)
    {
        newNode->prev=_head;
        newNode->next=_head;
        _head->prev=newNode;
        _head->next=newNode;
    }
    else
    {
        newNode->next = _head;
        newNode->prev = _head->prev;
        _head->prev->next=newNode;
        _head->prev=newNode;
    }
    _size++;
    
}


void LRU::evictLRUPage()
{
    // remove _head's next page
    if (_size!=0)
    {
        LRU_Node* LRU_Node;
        LRU_Node=_head->next;
        
        _evictPageData=LRU_Node->data;
        _evictPageDirty=LRU_Node->dirty;
        
        _head->next=LRU_Node->next;
        LRU_Node->next->prev=_head;
        
        _mappingTable.erase(LRU_Node->data);
        _size--;
        delete LRU_Node;
    }
}



// evict a certain page and return page value
void LRU::evictAt(LRU_Node* nodeToDelete)
{
    if (_size!=0 && nodeToDelete!=NULL)
    {
        _evictPageData=nodeToDelete->data;
        _evictPageDirty=nodeToDelete->dirty;
        
        nodeToDelete->prev->next = nodeToDelete->next;
        nodeToDelete->next->prev = nodeToDelete->prev;

        _mappingTable.erase(nodeToDelete->data);
        _size--;
        delete nodeToDelete;
    }
}


bool LRU::input(long newPageData, int readWriteFlag)
{

    _requestCounter++;
	LRU_Node* foundNode = search(newPageData);
    
    // Hit
    // 1 3, oh(wb)=0, oh(wt)=0r/1w
    if (foundNode!=NULL)
	{
        
        if(displayCoutLRU) cout<<"Cache hit, then move the hitted page to the MRU page."<<endl;
        _hitCounter++;
        evictAt(foundNode);

        if(readWriteFlag)
        {
            attachToMRUPage(newPageData, _evictPageDirty);
            // WB:
            _overheadCounterWB_IO_CacheRead++;
        }
        else
        {
            // write, mark dirty flag for the new page
            attachToMRUPage(newPageData, true);
            
            // WB:
            _overheadCounterWB_IO_CacheWrite++;
            
            // WT: Write thru
            _overheadCounterWT++;
            _overheadCounterWT_IOEvict++;
            
            
            
            

        }

        
        
        
        if(displayCoutLRU) print();
        return true;
    }
    
    else // Miss
    //overhead(ReadMissFull)=2, overhead(ReadMissNotFull)=1, overhead(WriteMissFull)=1, overhead(WriteMissNotFull)=0
    {
        // For all miss case 2 4, oh(wt)=1, but oh(wb)=0/1/2
        
        // WB:
        if (!readWriteFlag)
            _overheadCounterWB_IO_CacheWrite++;

        _missCounter++;
        
        
        if(displayCoutLRU) cout<<"Cache miss, (if the cache is full then evict the LRU page and) then append the new page to the MRU page. "<<endl;
      
        // Cache is full
        if (_size==_cacheSize)
        {
            //if(displayCoutLRU) cout<<"Cache is full, then evict the LRU page."<<endl;
            // miss full
            // miss write full
            evictLRUPage();
           
            
            
            // After evicting the victim page
            // Read
            if (readWriteFlag)
            {
                
                // For evict
                // miss read full dirty
                // 4.2 miss read full dirty, oh(wb)=2, cache->data, data->cache
                if (_evictPageDirty)
                {
                    // WB:
                    _overheadCounterWB++;
                    _overheadCounterWB_IOEvict++;
                    
                    // WT:
                    // no overhead
                }
                

                // read, data->cache
                attachToMRUPage(newPageData,false);
                
                // WB:
                _overheadCounterWB++;
                _overheadCounterWB_IOAdmin++;
                
                // WT: write thru
                _overheadCounterWT++;
                _overheadCounterWT_IOAdmin++;

               
            }
            
            // Write
            else
            {
                
                // miss write full
                // 2.2 miss write full dirty, oh(wb)=1
                if (_evictPageDirty)
                {
                    // WB:
                    _overheadCounterWB++;
                    _overheadCounterWB_IOEvict++;
                    
                    // WT:
                    // no overhead
                }
                
                // write new page to cache
                attachToMRUPage(newPageData,true);
                
                // WB:
                // no overhead

                // WT: write thru
                _overheadCounterWT++;
                _overheadCounterWT_IOEvict++;
                
            }
            
            
        }
        
        
        // Cache is not full
        else
        {
            if (readWriteFlag)
            {
                // 4.1 miss read not full, oh(wb)=1
                // data->cache
                attachToMRUPage(newPageData,false);
                
                // WB:
                _overheadCounterWB++;
                _overheadCounterWB_IOAdmin++;
                
                // WT:
                _overheadCounterWT++;
                _overheadCounterWT_IOAdmin++;
                
            }
            else
            {
                // 2.1 miss write not full, oh(wb)=0
                attachToMRUPage(newPageData,true);
                
                // WB:
                // no overhead
                
                // WT: write thru
                _overheadCounterWT++;
                _overheadCounterWT_IOEvict++;
            }
            
        }
        
        if(displayCoutLRU) print();
        return false;
    }
}



float LRU::hitRatio()
{
    return (float)_hitCounter/_requestCounter;
}

long LRU::getHit()
{
    return _hitCounter;
}

long LRU::getTotalRequest()
{
    return _requestCounter;
}



void LRU::getOccupancyRatio(int algorithmID, vector<vector<long>> &occupancyNumberMatrix, vector<vector<float>> &occupancyRatioMatrix, int traceNumber, int algorithmNumber)
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
        LRU_Node * currentNode = _head->next;
        for (long i=0; i<_size; i++)
        {
            occupancyNumberMatrix[algorithmID][(currentNode->data)%10000]++;
            currentNode=currentNode->next;
        }
        
        for (int i=0; i<traceNumber; i++)
        {
            occupancyRatioMatrix[algorithmID][i]=(float) occupancyNumberMatrix[algorithmID][i]/_size;
        }
        //cout<<endl;
    }
}



long LRU::getOverheadWB()
{

    return _overheadCounterWB;

}

long LRU::getOverheadWB_IOAdmin()
{
    return _overheadCounterWB_IOAdmin;
}

long LRU::getOverheadWB_IOEvict()
{
    return _overheadCounterWB_IOEvict;
}


long LRU::getOverheadWT()
{
    
    return _overheadCounterWT;
    
}

long LRU::getOverheadWT_IOAdmin()
{
    return _overheadCounterWT_IOAdmin;
}

long LRU::getOverheadWT_IOEvict()
{
    return _overheadCounterWT_IOEvict;
}






long LRU::getOverheadWB_IO_CacheRead()
{
    return _overheadCounterWB_IO_CacheRead;
}



long LRU::getOverheadWB_IO_CacheWrite()
{
    return _overheadCounterWB_IO_CacheWrite;
}
