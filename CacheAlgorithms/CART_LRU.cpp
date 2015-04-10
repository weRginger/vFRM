#include "CART_LRU.h"

CART_LRU::CART_LRU()
{
    _size=0;
    _head = new CART_Node;
    _head->prev = _head;
    _head->next = _head;
}



long CART_LRU::size()
{
    return _size;
}


CART_Node* CART_LRU::search(long pageToSearch)
{
    CART_Node* foundNode = _mappingTable[pageToSearch];
    if(foundNode)
    {
        if (displayCoutCART) cout<<"Found."<<endl;
        return foundNode;
    }
    else
    {
        if (displayCoutCART) cout<<"Not found."<<endl;
        return NULL;
    }
}



void CART_LRU::print()
{
    if (_size==0)
    {
        cout<<"Empty list."<<endl;
    }
    else
    {
        vector <int> PTB;
        CART_Node * currentNode = _head->next;
        cout<<"["<<currentNode->data<<"]\t";
        PTB.push_back(currentNode->PTB);
        currentNode=currentNode->next;
        long i=1;
        while (i<_size)
        {
            cout<<currentNode->data<<"\t";
            PTB.push_back(currentNode->PTB);
            i++;
            currentNode=currentNode->next;
        }
        cout<<endl;

        for (long i=0; i<PTB.size(); i++)
        {
            if (i==0)
            {
                if (PTB[i]==0)
                {
                    cout<<"[S]\t";
                }
                else
                {
                    cout<<"[L]\t";
                }
            
            }
            else
            {
                if (PTB[i]==0)
                {
                    cout<<"S\t";
                }
                else
                {
                    cout<<"L\t";
                }
            
            }
        }
        cout<<endl;
    }
    
}







void CART_LRU::attachToMRUPage(long newPageData, int newPagePRB, int newPagePTB, bool newPageDirty)
{
    CART_Node *newNode = new CART_Node;
    
    newNode->data   = newPageData;
    newNode->PRB    = newPagePRB;
    newNode->PTB    = newPagePTB;
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


void CART_LRU::evictLRUPage(long &_evictPageData, int &_evictPagePRB, int &_evictPagePTB, bool &_evictPageDirty)
{
    // remove _head's next page
    if (_size!=0)
    {
        CART_Node* LRU_Node;
        LRU_Node=_head->next;
        
        _evictPageData      = LRU_Node->data;
        _evictPagePRB       = LRU_Node->PRB;
        _evictPagePTB       = LRU_Node->PTB;
        _evictPageDirty     = LRU_Node->dirty;

        
        _head->next=LRU_Node->next;
        LRU_Node->next->prev=_head;
        
        _mappingTable.erase(LRU_Node->data);
        _size--;
        delete LRU_Node;
    }
}



void CART_LRU::evictAt(CART_Node* nodeToDelete, long &_evictPageData, int &_evictPagePRB, int &_evictPagePTB, bool &_evictPageDirty)
{
    if (_size!=0 && nodeToDelete!=NULL)
    {
        nodeToDelete->prev->next = nodeToDelete->next;
        nodeToDelete->next->prev = nodeToDelete->prev;
        
        
        _evictPageData      = nodeToDelete->data;
        _evictPagePRB       = nodeToDelete->PRB;
        _evictPagePTB       = nodeToDelete->PTB;
        _evictPageDirty     = nodeToDelete->dirty;

        
 
        
        _mappingTable.erase(nodeToDelete->data);
        _size--;
        delete nodeToDelete;
    }
}