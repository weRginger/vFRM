#include "CART.h"
#define S 0
#define L 1
using namespace std;

CART::CART(long cacheSize):T1(),T2(),B1(),B2()
{
    _c=cacheSize;
    _foundCache=-1;         // found cache index (T1=1,T2=2,B1=3,B2=4)
    _foundCacheNode=NULL;     // found cache item index (e.g. page index [6])
	_requestCounter=0;
	_hitCounter=0;
    _p=0;
    _q=0;
    _ns=0;
    _nl=0;

    _overheadCounterWB=0;
    _overheadCounterWB_IOAdmin=0;
    _overheadCounterWB_IOEvict=0;
    _overheadCounterWT=0;
    _overheadCounterWT_IOAdmin=0;
    _overheadCounterWT_IOEvict=0;
    
    _evictPageData=0;
    _evictPagePRB=0;
    _evictPagePTB=0;
    _evictPageDirty=true;
}




CART_Node* CART::search(long pageToSearch)
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
    //if(displayCoutCART) cout<<"T1 found="<<found<<endl;
    if (_foundCacheNode!=NULL)
    {
        if (displayCoutCART) cout<<"Found in T1.\n";
        _foundCache=1;
    }
    else
    {
    	_foundCacheNode=T2.search(pageToSearch);
        if (_foundCacheNode!=NULL)
        {
            if (displayCoutCART) cout<<"Found in T2.\n";
            _foundCache=2;
        }
        else
        {
            _foundCacheNode=B1.search(pageToSearch);
            if (_foundCacheNode!=NULL)
            {
                if (displayCoutCART) cout<<"Found in B1.\n";
                _foundCache=3;
            }
            else
            {
                _foundCacheNode=B2.search(pageToSearch);
                if (_foundCacheNode!=NULL)
                {
                    if (displayCoutCART) cout<<"Found in B2.\n";
                    _foundCache=4;
                }
            }
        }
    }
    if(displayCoutCART && _foundCacheNode==NULL) cout<<"NULL"<<endl;
    return _foundCacheNode;
}

void CART::print()
{
    cout<<"T1:\t"<<endl;
    T1.print();
    cout<<"T2:\t"<<endl;
    T2.print();
    cout<<"B1:\t"<<endl;
    B1.print();
    cout<<"B2:\t"<<endl;
    B2.print();
    printf("P=%ld, Q=%ld, Hit=%ld, TotalRequest=%ld, HitRatio=%f%%.", _p, _q, _hitCounter, _requestCounter, hitRatio()*100);
    cout<<endl;
}

float CART::hitRatio()
{
    return (float)_hitCounter/_requestCounter;
}

long CART::getHit()
{
    return _hitCounter;
}

long CART::getTotalRequest()
{
    return _requestCounter;
}


long CART::max(long a, long b)
{
    return a>b? a:b;
}

long CART::min(long a, long b)
{
    return a<b? a:b;
}

long CART::getP()
{
    return _p;
}

long CART::getQ()
{
    return _q;
}



bool CART::input(long newPageData, int readWriteFlag)
{
    // Counter and cache size update
    _requestCounter++;
    // Search the page
    if(displayCoutCART) cout<<"Search this page in the four lists: ";
    search(newPageData);
    
    
    
    // WT case 1 and 2, hit, oh(wt)=1w/0r
    // WB case 1 and 2, hit, oh(wb)=0, mark D
    // 1. found in T1 or T2, Main Cache Hit
    if (_foundCache==1||_foundCache==2)
    {
        _hitCounter++;
        if(displayCoutCART) cout<<"Case 1. T1 U T2 Hit, access and set PRB to 1."<<endl;
        
        
        
        
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
    else
    {
        // WB:
        if (!readWriteFlag)
            _overheadCounterWB_IO_CacheWrite++;

        if(displayCoutCART) cout<<"Case 2. T1 U T2 miss."<<endl;
        if (T1.size()+T2.size()==_c)  //T1+T2=C
        {
            if(displayCoutCART) cout<<"Case 2.1 T1 U T2 = C, then replace a page from T1 or T2 to make space for the new page."<<endl;
     
            
            // overheads is calculated in the replace function
            replace();
            
            
            if (  (_foundCache!=3 && _foundCache!=4)  &&  (B1.size()+B2.size()==_c+1)  && (B1.size()>max(0,_q) || B2.size()==0) )
            {
                if(displayCoutCART) cout<<"2.1.1 Remove the bottom page in B1 from the history."<<endl;
                // Remove from B(data->data), already in data, no overhead
                B1.evictLRUPage(_evictPageData, _evictPagePRB, _evictPagePTB, _evictPageDirty);
            }
            
            else if (  (_foundCache!=3 && _foundCache!=4)  &&  (B1.size()+B2.size()==_c+1) )
            {
                if(displayCoutCART) cout<<"2.1.2 Remove the bottom page in B2 from the history."<<endl;
                // Remove from B(data->data), already in data, no overhead
                B2.evictLRUPage(_evictPageData, _evictPagePRB, _evictPagePTB, _evictPageDirty);
            }
        }
        
        
        
        // Totally miss, ovhd case 5 and 6
        if  (_foundCache!=3 && _foundCache!=4)
        {
            if(displayCoutCART) cout<<"Case 2.2 Totally miss, then attach to T1's tail."<<endl;
         
            _ns++;
            
            
            
            // read
            if (readWriteFlag)
            {
                T1.attachToTail(newPageData, 0, S, false);
                
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
                T1.attachToTail(newPageData, 0, S, true);
                
                // WB:
                // no overhead
                
                // WT: write thru to data
                _overheadCounterWT++;
                _overheadCounterWT_IOEvict++;
            }
            

            
        }
        
        
        else if (_foundCache==3) // Hit in B1
        {
            if(displayCoutCART) cout<<"Case 2.3 Hit in B1."<<endl;
            if(displayCoutCART) cout<<"Increase T1's target size p."<<endl;
            _p = min(  _p+max(  1, _ns/B1.size()  )  ,   _c  );
            if(displayCoutCART) cout<<"Move the page "<<newPageData<<" from B1 to T1's tail."<<endl;
            
            _nl++;
            
            
            // B(data)->T(cache), overhead
            B1.evictAt(_foundCacheNode, _evictPageData, _evictPagePRB, _evictPagePTB, _evictPageDirty);
            // no matter _evictPageDirty is true or not, B->T = Data->Cache, should be notDirty (false)
            
            
            // miss B read oh(wb)=1
            if (readWriteFlag)
            {
                T1.attachToTail(newPageData, 0, L, false);
                
                // WB: write from data to cache
                _overheadCounterWB++;
                _overheadCounterWB_IOAdmin++;
                
                // WT: write from data to cache
                _overheadCounterWT++;
                _overheadCounterWT_IOAdmin++;
                

            }
            // miss B write oh(wb)=D=1 1/D=0 0
            else
            {
                
                T1.attachToTail(newPageData, 0, L, true);
                
                // WB:
                // no overhead
                
                // WT: write thru from cache to data
                _overheadCounterWT++;
                _overheadCounterWT_IOEvict++;
                
            }


            
        }
        
        else if (_foundCache==4) // Hit in B2
        {
            if(displayCoutCART) cout<<"Case 2.4 Hit in B2."<<endl;
            if(displayCoutCART) cout<<"Increase T2's target size (c-p)."<<endl;
            _p = max(  _p - max(  1, B1.size()/B2.size()  )  ,   0  );
            if(displayCoutCART) cout<<"Move the page "<<newPageData<<" from B2 to T1's tail."<<endl;
            
            
            _nl++;
            
            
            // B(data)->T(cache), overhead
            B2.evictAt(_foundCacheNode, _evictPageData, _evictPagePRB, _evictPagePTB, _evictPageDirty);
            // no matter _evictPageDirty is true or not, B->T = Data->Cache, should be notDirty (false)
            
            
            // miss B read oh(wb)=1
            if (readWriteFlag)
            {
                T1.attachToTail(newPageData, 0, L, false);
                
                // WB: write from data to cache
                _overheadCounterWB++;
                _overheadCounterWB_IOAdmin++;
                
                // WT: write from data to cache
                _overheadCounterWT++;
                _overheadCounterWT_IOAdmin++;
                
                
            }
            // miss B write oh(wb)=D=1 1/D=0 0
            else
            {
                T1.attachToTail(newPageData, 0, L, true);
                
                // WB:
                // no overhead
                
                // WT: write thru from cache to data
                _overheadCounterWT++;
                _overheadCounterWT_IOEvict++;
                

            }
            

            
            
            if(T2.size()+B2.size()+T1.size()-_ns>=_c)
            {
                _q = min(_q+1, 2*_c-T1.size());
            }
        }
    
        return false;
    }
}


// T(cache)->B(data) has overhead, or T(cache)->T(cache) has no overhead
void CART::replace()
{
    if(displayCoutCART) cout<<"Replace a page from mainCache to reserve space for the new page."<<endl;
    
    while (T2.getHeadPRB()==1)
    {

        T2.evictHead(_evictPageData, _evictPagePRB, _evictPagePTB, _evictPageDirty);
        T1.attachToTail(_evictPageData, 0, L, _evictPageDirty);
        // T->T no overhead
        
        if(T2.size()+B2.size()+T1.size()-_ns>=_c)
        {
            _q = min(_q+1, 2*_c-T1.size());
        }
    }
    
    
    
    
    
    while ( (T1.getHeadPTB()==L) || (T1.getHeadPRB()==1) )
    {
        int _T1HeadPTB=T1.getHeadPTB();
        if (T1.getHeadPRB()==1)
        {
            
            T1.evictHead(_evictPageData, _evictPagePRB, _evictPagePTB, _evictPageDirty);
            T1.attachToTail(_evictPageData, 0, _evictPagePTB, _evictPageDirty);
            // T->T no overhead
            
            
            if (T1.size()>=min(_p+1,B1.size()) && (_T1HeadPTB==S))
            {
                if (displayCoutCART) cout<<"SetPTBofMovedPageTo:L.\n";
                T1.setPTBAtTailToL();
                
                _ns--;
                _nl++;
            }
        }
        else
        {
            if (displayCoutCART) cout<<"attchToT2Tail.\n";

            
            T1.evictHead(_evictPageData, _evictPagePRB, _evictPagePTB, _evictPageDirty);
            T2.attachToTail(_evictPageData, _evictPagePRB, L, _evictPageDirty);
            // T->T no overhead
            
            _q = max (_q-1,_c-T1.size());
        }
    }
    
    
    if (T1.size()>=max(1,_p))
    {

        T1.evictHead(_evictPageData, _evictPagePRB, _evictPagePTB, _evictPageDirty);
        B1.attachToMRUPage(_evictPageData, _evictPagePRB, S, _evictPageDirty);
        
        // T(cache)->B(data)
        // WB:
        if (_evictPageDirty)
        {
            _overheadCounterWB++;
            _overheadCounterWB_IOEvict++;
        }
        
        // WT:
        // no overhead

        _ns--;
    }
    else
    {

        T2.evictHead(_evictPageData, _evictPagePRB, _evictPagePTB, _evictPageDirty);
        B2.attachToMRUPage(_evictPageData, _evictPagePRB, L, _evictPageDirty);
        
        // T(cache)->B(data)
        // WB:
        if (_evictPageDirty)
        {
            _overheadCounterWB++;
            _overheadCounterWB_IOEvict++;
        }
        
        // WT:
        // no overhead

        _nl--;
    }
    
    
}




void CART::getOccupancyRatio(int algorithmID, vector<vector<long>> &occupancyNumberMatrix, vector<vector<float>> &occupancyRatioMatrix, int traceNumber, int algorithmNumber)
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





long CART::getOverheadWB()
{
    
    return _overheadCounterWB;
    
}

long CART::getOverheadWB_IOAdmin()
{
    return _overheadCounterWB_IOAdmin;
}

long CART::getOverheadWB_IOEvict()
{
    return _overheadCounterWB_IOEvict;
}


long CART::getOverheadWT()
{
    
    return _overheadCounterWT;
    
}

long CART::getOverheadWT_IOAdmin()
{
    return _overheadCounterWT_IOAdmin;
}

long CART::getOverheadWT_IOEvict()
{
    return _overheadCounterWT_IOEvict;
}

long CART::getOverheadWB_IO_CacheRead()
{
    return _overheadCounterWB_IO_CacheRead;
}


long CART::getOverheadWB_IO_CacheWrite()
{
    return _overheadCounterWB_IO_CacheWrite;
}


