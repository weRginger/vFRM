#include "CAR.h"
using namespace std;

CAR::CAR(long cacheSize):T1(),T2(),B1(),B2()
{
    _c=cacheSize;
    _foundCache=-1;         // found cache index (T1=1,T2=2,B1=3,B2=4)
    _foundCacheNode=NULL;     // found cache item index (e.g. page index [6])
	_requestCounter=0;
	_hitCounter=0;
    _p=0;
    
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


CAR_Node* CAR::search(long pageToSearch)
{
    /*
     Search the page in all caches, it will modify the two private varibles: _foundCache, _foundCacheNode.
     The first one will record the found cache type, and the second will record the found page location.
     search() will return false if not found, and return true if found.
     If not found, to be safe, it will change the _foundCache and _foundCacheNode to NULL.
     */
    // clean search results
    _foundCache=-1;
	_foundCacheNode=T1.search(pageToSearch);
    //if(displayCoutCAR) cout<<"T1 found="<<found<<endl;
    if (_foundCacheNode!=NULL)
    {
        if (displayCoutCAR) cout<<"Found in T1.\n";
        _foundCache=1;
    }
    else
    {
    	_foundCacheNode=T2.search(pageToSearch);
        if (_foundCacheNode!=NULL)
        {
            if (displayCoutCAR) cout<<"Found in T2.\n";
            _foundCache=2;
        }
        else
        {
            _foundCacheNode=B1.search(pageToSearch);
            if (_foundCacheNode!=NULL)
            {
                if (displayCoutCAR) cout<<"Found in B1.\n";
                _foundCache=3;
            }
            else
            {
                _foundCacheNode=B2.search(pageToSearch);
                if (_foundCacheNode!=NULL)
                {
                    if (displayCoutCAR) cout<<"Found in B2.\n";
                    _foundCache=4;
                }
            }
        }
    }
    if(displayCoutCAR && _foundCacheNode==NULL) cout<<"NULL"<<endl;
    return _foundCacheNode;
}




void CAR::print()
{
    cout<<"T1:\t"<<endl;
    T1.print();
    cout<<"T2:\t"<<endl;
    T2.print();
    cout<<"B1:\t"<<endl;
    B1.print();
    cout<<"B2:\t"<<endl;
    B2.print();
    printf("P=%ld, Hit=%ld, TotalRequest=%ld, HitRatio=%f%%", _p, _hitCounter, _requestCounter, hitRatio()*100);
    cout<<endl;
}

float CAR::hitRatio()
{
    return (float)_hitCounter/_requestCounter;
}

long CAR::getHit()
{
    return _hitCounter;
}

long CAR::getTotalRequest()
{
    return _requestCounter;
}



bool CAR::mainCacheIsFull()         // T1 U T2
{
    if ((T1.size()+T2.size())==_c)
        return true;
    else
        return false;
}

bool CAR::recencyCacheIsFull()      // T1 U B1
{
    if (  ( T1.size()+B1.size() )  ==  _c  )
        return true;
    else
        return false;
}

bool CAR::frequencyCacheIsFull()    // T2 U B2
{
    if ((T2.size()+B2.size())==_c)
        return true;
    else
        return false;
    
}

bool CAR::allCacheIsFull()          // T1 U B1 U T2 U B2
{
    if ((T1.size()+T2.size()+B1.size()+B2.size())==2*_c)
        return true;
    else
        return false;
}

long CAR::max(long a, long b)
{
    return a>b? a:b;
}

long CAR::min(long a, long b)
{
    return a<b? a:b;
}

long CAR::getP()
{
    return _p;
}


bool CAR::input(long newPageData, int readWriteFlag)
{
    // Counter and cache size update
    _requestCounter++;
    // Search the page
    if(displayCoutCAR) cout<<"Search this page in the four lists: ";
    search(newPageData);
    
    
    
    // WT case 1 and 2, hit, oh(wt)=1w/0r
    // WB case 1 and 2, hit, oh(wb)=0, mark D
    // 1. found in T1 or T2, Main Cache Hit
    if (_foundCache==1||_foundCache==2)
    {
        _hitCounter++;
        if(displayCoutCAR) cout<<"Case 1. Main Cache Hit, access and set PRB to 1."<<endl;
        
        
        // read hit
        if(readWriteFlag)
        {
            // WB:
            _overheadCounterWB_IO_CacheRead++;
            // WT: no overhead
            
        }
        // write hit
        else
        {
            // WB:
            _overheadCounterWB_IO_CacheWrite++;
            
            // WT: write thru
            _overheadCounterWT++;
            _overheadCounterWT_IOEvict++;
        }

        
        
        
        // Mark the hitted page's PRB to one.
        if (_foundCache==1)
        {
            T1.setPRBAt(_foundCacheNode,1);
            // For WB, mark D if write
            if (!readWriteFlag)
            {
                T1.setDirtyAt(_foundCacheNode,true);
            }
        }
        else if (_foundCache==2)
        {
            T2.setPRBAt(_foundCacheNode,1);
            // For WB, mark D if write
            if (!readWriteFlag)
            {
                T2.setDirtyAt(_foundCacheNode,true);
            }
        }
        
        return true;
    }
    
    
    //  2. Cache miss in MainCache (T1 U T2)
    //  WT oh(wt)=1
    //  WB oh(wb)=?
    else
    {
        // WB:
        if (!readWriteFlag)
            _overheadCounterWB_IO_CacheWrite++;
        
        
        if(displayCoutCAR) cout<<"Case 2. Cache miss in MainCache."<<endl;
        if (mainCacheIsFull())
        {
            if(displayCoutCAR) cout<<"Case 2.1 MainCache is full, then replace and check RecencyCache and AllCache are full or not, and attach "<<newPageData<<" to T1's tail."<<endl;
            
            // overheads is calculated in the replace function
            replace();

            if (  (_foundCache!=3 && _foundCache!=4)  &&  recencyCacheIsFull()  )
            {
                if(displayCoutCAR) cout<<"RecencyCache is full and the page is not in B1 and B2, then evict B1's LRU page."<<endl;
                // Remove from B(data->data), already in data, no overhead
                B1.evictLRUPage(_evictPageData, _evictPagePRB, _evictPageDirty);
            }
            
            else if (  (_foundCache!=3 && _foundCache!=4)  &&  allCacheIsFull() )
            {
                if(displayCoutCAR) cout<<"AllCache is full and the page is not in B1 and B2, then evict B2's LRU page."<<endl;
                // Remove from B(data->data), already in data, no overhead
                B2.evictLRUPage(_evictPageData, _evictPagePRB, _evictPageDirty);
            }
        }
        
        

        
        // Totally miss, ovhd case 5 and 6, no ovhd
        if  (_foundCache!=3 && _foundCache!=4)
        {
            if(displayCoutCAR) cout<<"Case 2.2.1 Totally miss."<<endl;

            // read
            if (readWriteFlag)
            {
                T1.attachToTail(newPageData, 0, false);
                
                // WB case 6: totally miss read, data->cache
                _overheadCounterWB++;
                _overheadCounterWB_IOAdmin++;
                
                // WT: data->cache
                _overheadCounterWT++;
                _overheadCounterWT_IOAdmin++;
            }
            // write
            else
            {
                T1.attachToTail(newPageData, 0, true);
                
                // WB:
                // no overhead
                
                // WT: write thru to data
                _overheadCounterWT++;
                _overheadCounterWT_IOEvict++;
            }
            

        }
        
        
        
        // Hit in B1, B1->T2, oh()
        else if (_foundCache==3) // Hit in B1
        {
            if(displayCoutCAR) cout<<"Case 2.3 Hit in B1."<<endl;
            if(displayCoutCAR) cout<<"Increase T1's target size p."<<endl;
            _p = min(  _p+max(  1, B2.size()/B1.size()  )  ,   _c  );
            if(displayCoutCAR) cout<<"Move the page "<<newPageData<<" from B1 to T2's tail."<<endl;
            
            
            // B(data)->T(cache), overhead
            B1.evictAt(_foundCacheNode, _evictPageData, _evictPagePRB, _evictPageDirty);
            // no matter _evictPageDirty is true or not, B->T = Data->Cache, should be notDirty (false)
            
            
            
            
            // miss B read oh(wb)=1
            if (readWriteFlag)
            {
                // WB: write from data to cache
                _overheadCounterWB++;
                _overheadCounterWB_IOAdmin++;
                
                // WT: write from data to cache
                _overheadCounterWT++;
                _overheadCounterWT_IOAdmin++;
                
                T2.attachToTail(newPageData, 0, false);
            }
            // miss B write oh(wb)=D=1 1/D=0 0
            else
            {
                // WB:
                
                // WT: write thru from cache to data
                _overheadCounterWT++;
                _overheadCounterWT_IOEvict++;
                
                T2.attachToTail(newPageData, 0, true);
            }

        }
        
        // Hit in B2, B2->T2
        else if (_foundCache==4) 
        {
            if(displayCoutCAR) cout<<"Case 2.4 Hit in B1."<<endl;
            if(displayCoutCAR) cout<<"Increase T2's target size (c-p)."<<endl;
            _p = max(  _p - max(  1, B1.size()/B2.size()  )  ,   0  );
            if(displayCoutCAR) cout<<"Move the page "<<newPageData<<" from B1 to T2's tail."<<endl;
            
            
            // B(data)->T(cache)
            B2.evictAt(_foundCacheNode, _evictPageData, _evictPagePRB, _evictPageDirty);
            // no matter _evictPageDirty is true or not, B->T = Data->Cache, should be notDirty (false)


            // miss B read oh(wb)=1
            if (readWriteFlag)
            {
                // WB: write from data to cache
                _overheadCounterWB++;
                _overheadCounterWB_IOAdmin++;
                
                // WT: write from data to cache
                _overheadCounterWT++;
                _overheadCounterWT_IOAdmin++;
                
                T2.attachToTail(newPageData, 0, false);
            }
            // miss B write oh(wb)=D=1 1/D=0 0
            else
            {
                // WB:
                
                // WT: write thru from cache to data
                _overheadCounterWT++;
                _overheadCounterWT_IOEvict++;
                
                T2.attachToTail(newPageData, 0, true);
            }

        }
        
        
        
        // for miss
        return false;
    }
}



// T(cache)->B(data) has overhead, or T(cache)->T(cache) has no overhead
void CAR::replace()
{
    if(displayCoutCAR) cout<<"Replace a page from mainCache to reserve space for the new page."<<endl;
    bool    found = 0;
    while (!found)
    {
        if (T1.size() >= max(1,_p))
        {
            if(displayCoutCAR) cout<<"ReplaseCase 1. T1 is larger than p, then evict a page from T1."<<endl;
            if (T1.getHeadPRB()==0)  // T1.PRB[header]==0
            {
                if(displayCoutCAR) cout<<"T1 head page's PRB is 0, then move it to B1's MRU page (Downgrade to CacheDirectory)."<<endl;
                found = 1;

                T1.evictHead(_evictPageData, _evictPagePRB, _evictPageDirty);
                B1.attachToMRUPage(_evictPageData, _evictPagePRB, _evictPageDirty);
                
                // T(cache)->B(data)
                // WB:
                if (_evictPageDirty)
                {
                    _overheadCounterWB++;
                    _overheadCounterWB_IOEvict++;
                }
                
                // WT:
                // no overhead
                
            }
            else
            {
                if(displayCoutCAR) cout<<"T1 head page's PRB is 1, then move it to T1's tail (Upgrade to Frequency)."<<endl;
                
                
                T1.evictHead(_evictPageData, _evictPagePRB, _evictPageDirty);
                T2.attachToTail(_evictPageData, 0, _evictPageDirty);
                
                // No overhead
                // Detach T1's header and attach it to T2's MRU
            }
        }
        else
        {
            if(displayCoutCAR) cout<<"ReplaseCase 2. T2 is larger than (c-p), then evict a page from T2."<<endl;
            if  (T2.getHeadPRB()==0)
            {
                if(displayCoutCAR) cout<<"T2 head page's PRB is 0, then move it to B2's MRU page (Downgrade to CacheDirectory)."<<endl;
                found = 1;
                
                T2.evictHead(_evictPageData, _evictPagePRB, _evictPageDirty);
                B2.attachToMRUPage(_evictPageData, _evictPagePRB, _evictPageDirty);
                
                // T(cache)->B(data)
                // WB:
                if (_evictPageDirty)
                {
                    _overheadCounterWB++;
                    _overheadCounterWB_IOEvict++;
                }
                
                // WT:
                // no overhead
                
                
            }
            else
            {
                if(displayCoutCAR) cout<<"T2 head page's PRB is 1, then move it to T2's tail (Second chance for them to stay in T2)."<<endl;
                
                T2.evictHead(_evictPageData, _evictPagePRB, _evictPageDirty);
                T2.attachToTail(_evictPageData, 0, _evictPageDirty);
                
                // no overhead
            }
            
        }
    }
}




void CAR::getOccupancyRatio(int algorithmID, vector<vector<long>> &occupancyNumberMatrix, vector<vector<float>> &occupancyRatioMatrix, int traceNumber, int algorithmNumber)
{
    // Clean old data
    for (int i=0; i<traceNumber; i++)
    {
        occupancyNumberMatrix[algorithmID][i]=0;
        occupancyRatioMatrix[algorithmID][i]=0;
    }
    
    if (T1.size()+T2.size()==0)
    {
        //cout<<"Empty list."<<endl;
    }
    
    else if (T1.size()+T2.size()!=0)
    {
        T1.getOccupancyRatio(algorithmID, occupancyNumberMatrix, traceNumber, algorithmNumber);
        T2.getOccupancyRatio(algorithmID, occupancyNumberMatrix, traceNumber, algorithmNumber);
        for (int i=0; i<traceNumber; i++)
        {
            occupancyRatioMatrix[algorithmID][i]=(float) occupancyNumberMatrix[algorithmID][i] / (T1.size()+T2.size());
        }
    }
}




long CAR::getOverheadWB()
{
    return _overheadCounterWB;
}

long CAR::getOverheadWB_IOAdmin()
{
    return _overheadCounterWB_IOAdmin;
}

long CAR::getOverheadWB_IOEvict()
{
    return _overheadCounterWB_IOEvict;
}


long CAR::getOverheadWT()
{
    
    return _overheadCounterWT;
    
}

long CAR::getOverheadWT_IOAdmin()
{
    return _overheadCounterWT_IOAdmin;
}

long CAR::getOverheadWT_IOEvict()
{
    return _overheadCounterWT_IOEvict;
}


long CAR::getOverheadWB_IO_CacheRead()
{
    return _overheadCounterWB_IO_CacheRead;
}


long CAR::getOverheadWB_IO_CacheWrite()
{
    return _overheadCounterWB_IO_CacheWrite;
}

