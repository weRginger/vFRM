#include "CAR_LRU.h"

CAR_LRU::CAR_LRU()
{
    _size=0;
    _head = new CAR_Node;
    _head->prev = _head;
    _head->next = _head;
}


long CAR_LRU::size()
{
    return _size;
}


CAR_Node* CAR_LRU::search(long pageToSearch)
{
    CAR_Node* foundNode = _mappingTable[pageToSearch];
    if(foundNode)
    {
        if (displayCoutCAR) cout<<"Found."<<endl;
        return foundNode;
    }
    else
    {
        if (displayCoutCAR) cout<<"Not found."<<endl;
        return NULL;
    }
}



void CAR_LRU::print()
{
    if (_size==0)
    {
        cout<<"Empty list."<<endl;
    }
    else
    {
        vector <int> PTB;
        CAR_Node * currentNode = _head->next;
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




void CAR_LRU::attachToMRUPage(long newPageData, int newPagePRB, bool DirtyValue)
{
    CAR_Node *newNode = new CAR_Node;
    
    newNode->data   = newPageData;
    newNode->PRB    = newPagePRB;
    newNode->dirty  = DirtyValue;
    
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


void CAR_LRU::evictLRUPage(long &_evictPageData, int &_evictPagePRB, bool &_evictPageDirty)
{
    // remove _head's next page
    if (_size!=0)
    {
        CAR_Node* LRU_Node;
        LRU_Node=_head->next;
        
        _evictPageData      = LRU_Node->data;
        _evictPagePRB       = LRU_Node->PRB;
        _evictPageDirty     = LRU_Node->dirty;
        
        _head->next=LRU_Node->next;
        LRU_Node->next->prev=_head;
        
        _mappingTable.erase(LRU_Node->data);
        _size--;
        delete LRU_Node;
    }
}


// evict a certain page and return page value
void CAR_LRU::evictAt(CAR_Node* nodeToDelete, long &_evictPageData, int &_evictPagePRB, bool &_evictPageDirty)
{
    if (_size!=0 && nodeToDelete!=NULL)
    {
        
        _evictPageData      = nodeToDelete->data;
        _evictPagePRB       = nodeToDelete->PRB;
        _evictPageDirty     = nodeToDelete->dirty;
        
        
        nodeToDelete->prev->next = nodeToDelete->next;
        nodeToDelete->next->prev = nodeToDelete->prev;
        
        _mappingTable.erase(nodeToDelete->data);
        _size--;
        delete nodeToDelete;
    }
}