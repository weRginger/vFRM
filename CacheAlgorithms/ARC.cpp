#include "ARC.h"

using namespace std;

ARC::ARC(long cacheSize):T1(),T2(),B1(),B2()
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
    _evictPageDirty=true;


}


ARC_Node* ARC::search(long pageToSearch)
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
    //if(displayCoutARC) cout<<"T1 found="<<found<<endl;
    if (_foundCacheNode!=NULL)
    {
        if (displayCoutARC) cout<<"Found in T1.\n";
        _foundCache=1;
    }
    else
    {
    	_foundCacheNode=T2.search(pageToSearch);
        if (_foundCacheNode!=NULL)
        {
            if (displayCoutARC) cout<<"Found in T2.\n";
            _foundCache=2;
        }
        else
        {
            _foundCacheNode=B1.search(pageToSearch);
            if (_foundCacheNode!=NULL)
            {
                if (displayCoutARC) cout<<"Found in B1.\n";
                _foundCache=3;
            }
            else
            {
                _foundCacheNode=B2.search(pageToSearch);
                if (_foundCacheNode!=NULL)
                {
                    if (displayCoutARC) cout<<"Found in B2.\n";
                    _foundCache=4;
                }
            }
        }
    }
    if(displayCoutARC && _foundCacheNode==NULL) cout<<"NULL"<<endl;
    return _foundCacheNode;
}




void ARC::print()
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

float ARC::hitRatio()
{
    return (float)_hitCounter/_requestCounter;
}

long ARC::getHit()
{
    return _hitCounter;
}

long ARC::getTotalRequest()
{
    return _requestCounter;
}


long ARC::max(long a, long b)
{
    return a>b? a:b;
}

long ARC::min(long a, long b)
{
    return a<b? a:b;
}

long ARC::getP()
{
    return _p;
}


bool ARC::input(long newPageData, int readWriteFlag)
{
    if (displayCoutARC) print();
    // Counter and cache size update
    _requestCounter++;
    // Search the page
    if(displayCoutARC) cout<<"Search this page in the four lists: ";
    search(newPageData);
    
    
    // WT case 1 and 2, hit, oh(wt)=1w/0r
    // WB case 1 and 2, hit, oh(wb)=0
    // 1. found in T1 or T2, Main Cache Hit
    if (_foundCache==1||_foundCache==2)
    {
        _hitCounter++;
        if(displayCoutARC) cout<<"Case 1. Main Cache Hit, access and move it to T1 or T2's MRU."<<endl;
        
        // read hit
        if(readWriteFlag)
        {
            // WB: no overhead
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
        
        // Move it to MRU
        // Evict
        if (_foundCache==1)
        {
            T1.evictAt(_foundCacheNode, _evictPageData, _evictPageDirty);
        }
        else if (_foundCache==2)
        {
            T2.evictAt(_foundCacheNode, _evictPageData, _evictPageDirty);
        }
        
        // Attach
        if (readWriteFlag)
        {
            T2.attachToMRUPage(newPageData, _evictPageDirty);
        }
        // write
        else
        {
            T2.attachToMRUPage(newPageData, true);
        }

        return true;
    }
    
    // WT case 3 and 4, Hit in B, oh(wt)=1
    //  2. Hit in B1, oh(wb)=1r/Dw
    else if (_foundCache==3)
    {
        if(displayCoutARC) cout<<"Case 2. Hit in B1, then increase T1's target size p, and move the page "<<newPageData<<" from B1 to T2's tail."<<endl;
        _p = min(    _p  +   max(  1, B2.size()/B1.size()  )    ,     _c  );
        
        
        // T(cache)->B(Data), overhead=D=0/1=WB_Evict
        replace(newPageData, _p);
        
        
        
        // B(data)->T(cache)
        B1.evictAt(_foundCacheNode, _evictPageData, _evictPageDirty);
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
            
            T2.attachToMRUPage(newPageData, false);
        }
        // miss B write oh(wb)=D=1 1/D=0 0
        else
        {
            // WB: depends on replace (D=0/1)
            _overheadCounterWB_IO_CacheWrite++;
            
            // WT: write thru from cache to data
            _overheadCounterWT++;
            _overheadCounterWT_IOEvict++;
            
            T2.attachToMRUPage(newPageData, true);
        }
        
        
        
        return false;
    }
    
    // Hit in B, B->cache, oh(wt)=1, oh(wb)=1r/0w
    // 3. HIT in B2
    else if (_foundCache==4)
    {
        if(displayCoutARC) cout<<"Case 3. Hit in B2, then decrease T1's target size p, and move the page "<<newPageData<<" from B2 to T2's tail."<<endl;
        _p = max(     _p -  max(  1, B1.size()/B2.size()  )      ,   0  );
        
        
        
        // T(cache)->B(Data), overhead=D=0/1=WB_Evict
        replace(newPageData,_p);
        
        
        
        // B(data)->T(cache)
        B2.evictAt(_foundCacheNode, _evictPageData, _evictPageDirty);
        // no matter _evictPageDirty is ture or not, B->T = Data->Cache, should be notDirty (false)
        
        
        
        
        // miss B read oh(wb)=1
        if (readWriteFlag)
        {
            // WB: write from memory to cache
            _overheadCounterWB++;
            _overheadCounterWB_IOAdmin++;
            
            // WT: write from memory to cache
            _overheadCounterWT++;
            _overheadCounterWT_IOAdmin++;

            T2.attachToMRUPage(newPageData, false);
        }
        // miss B write oh(wb)=D=1 1/D=0 0
        else
        {
            // WB: depends on replace (D=0/1)
            _overheadCounterWB_IO_CacheWrite++;
            
            // WT: write thru from cache to data
            _overheadCounterWT++;
            _overheadCounterWT_IOEvict++;

            T2.attachToMRUPage(newPageData,true);
            
            
        }
        
        return false;
    }
    
    // 4. Totally miss.
    // WT case 5 and 6, totally miss, oh(wt)=1
    // if(_foundCache!=3 && _foundCache!=4)
    else
    {
        if(displayCoutARC) cout<<"Case 4. Totally miss."<<endl;
        

        
        // Case A: T1+B1==c
        if (T1.size()+B1.size()==_c)
        {

            // B(data)->Data, No overhead for WB
            if (T1.size()<_c)
            {
                // Discard LRU of B1 (data->data), no overhead
                B1.evictLRUPage(_evictPageData, _evictPageDirty);

                // T->B(data), overhead in replace, depends on dirtyFlag
                replace(newPageData,_p);
            }
            else
            {
                // B1 is empty
                T1.evictLRUPage(_evictPageData, _evictPageDirty);
                
                // Overhead for WB: T(cache)->Data
                if(_evictPageDirty)
                {
                    // WB
                    _overheadCounterWB++;
                    _overheadCounterWB_IOEvict++;
                }
            }
        }
        
        // Case B: T1+B1<c
        else if (T1.size()+B1.size()<_c)
        {
            if (T1.size()+T2.size()+B1.size()+B2.size()>=_c)
            {
                if (T1.size()+T2.size()+B1.size()+B2.size()==2*_c)
                {
                    B2.evictLRUPage(_evictPageData, _evictPageDirty);
                    // B(data)->Data, No overhead for WB
                }
                // T->B(data), overhead=dirtyFlag
                replace(newPageData, _p);
            }
        }
        
        // Finally move the new page to MRU in T1
        if (readWriteFlag)
        {
            T1.attachToMRUPage(newPageData, false);
            
            // WB case 6: totally miss read, data->cache
            _overheadCounterWB++;
            _overheadCounterWB_IOAdmin++;
           
            // WT: data->cache
            _overheadCounterWT++;
            _overheadCounterWT_IOAdmin++;
        }
        else
        {
            T1.attachToMRUPage(newPageData, true);
            
            // WB:
            _overheadCounterWB_IO_CacheWrite++;
            
            // WT: write thru to data
            _overheadCounterWT++;
            _overheadCounterWT_IOEvict++;
        }
        
        
        
        
        
        
        return false;
    }
}


// T(cache)->B(data), overhead=dirtyFlag
void ARC::replace(long newPageData, long p)
{
    
    if (     (T1.size()!=0)     &&     (  (T1.size()>_p)    || (_foundCache==4 && T1.size()==_p)  )        )
    {
        T1.evictLRUPage(_evictPageData,_evictPageDirty);
        B1.attachToMRUPage(_evictPageData,_evictPageDirty);
        
        // T->B(data)
        if (_evictPageDirty)
        {
            _overheadCounterWB++;
            _overheadCounterWB_IOEvict++;

        }
    }
    else
    {
        T2.evictLRUPage(_evictPageData,_evictPageDirty);
        B2.attachToMRUPage(_evictPageData,_evictPageDirty);
        // T->B(data)
        if (_evictPageDirty)
        {
            _overheadCounterWB++;
            _overheadCounterWB_IOEvict++;

        }
    }
}


void ARC::getOccupancyRatio(int algorithmID, vector<vector<long>> &occupancyNumberMatrix, vector<vector<float>> &occupancyRatioMatrix, int traceNumber, int algorithmNumber)
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


long ARC::getOverheadWB()
{
    
    return _overheadCounterWB;
    
}

long ARC::getOverheadWB_IOAdmin()
{
    return _overheadCounterWB_IOAdmin;
}

long ARC::getOverheadWB_IOEvict()
{
    return _overheadCounterWB_IOEvict;
}


long ARC::getOverheadWT()
{
    
    return _overheadCounterWT;
    
}

long ARC::getOverheadWT_IOAdmin()
{
    return _overheadCounterWT_IOAdmin;
}

long ARC::getOverheadWT_IOEvict()
{
    return _overheadCounterWT_IOEvict;
}

long ARC::getOverheadWB_IO_CacheRead()
{
    return _overheadCounterWB_IO_CacheRead;
}


long ARC::getOverheadWB_IO_CacheWrite()
{
    return _overheadCounterWB_IO_CacheWrite;
}

