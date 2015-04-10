#include "ARC_LRU.h"

ARC_LRU::ARC_LRU()
{
    _size=0;
    _head = new ARC_Node;
    _head->prev = _head;
    _head->next = _head;
}



long ARC_LRU::size()
{
    return _size;
}


ARC_Node* ARC_LRU::search(long pageToSearch)
{
    ARC_Node* foundNode = _mappingTable[pageToSearch];
    if(foundNode)
    {
        if (displayCoutARC) cout<<"Found."<<endl;
        return foundNode;
    }
    else
    {
        if (displayCoutARC) cout<<"Not found."<<endl;
        return NULL;
    }
}



void ARC_LRU::print()
{
    if (_size==0)
    {
        cout<<"Empty list."<<endl;
    }
    else
    {
        vector <int> PTB;
        ARC_Node * currentNode = _head->next;
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







void ARC_LRU::attachToMRUPage(long newPageData, bool newPageDirty)
{
    ARC_Node *newNode = new ARC_Node;
    newNode->data   = newPageData;
    newNode->dirty  = newPageDirty;
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


void ARC_LRU::evictLRUPage(long &_evictPageData, bool &_evictPageDirty)
{
    // remove _head's next page
    if (_size!=0)
    {
        ARC_Node* LRU_Node;
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


// Evict a certain page and return page value
void ARC_LRU::evictAt(ARC_Node* nodeToDelete, long &_evictPageData, bool &_evictPageDirty)
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


void ARC_LRU::getOccupancyRatio(int algorithmID, vector<vector<long>> &occupancyNumberMatrix,
                                int traceNumber, int algorithmNumber)
{
    ARC_Node * currentNode = _head->next;
    for (long i=0; i<_size; i++)
    {
        occupancyNumberMatrix[algorithmID][(currentNode->data)%10000]++;
        currentNode=currentNode->next;
    }
}