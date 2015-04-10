#include "CAR_CLOCK.h"

CAR_CLOCK::CAR_CLOCK()
{
    _size =0;
    _head = new CAR_Node;
    _head->prev = _head;
    _head->next = _head;
    
}


long CAR_CLOCK::size()
{
    return _size;
}

void CAR_CLOCK::print()
{
    if (_size==0)
    {
        cout<<"Empty list."<<endl;
    }
    else
    {
        vector <int> PRB;
        CAR_Node * currentNode = _head->next;
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



CAR_Node* CAR_CLOCK::search(long pageToSearch)
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

void CAR_CLOCK::attachToTail(long newPageData, int newPagePRB, bool newPageDirty)
{
    // New node
    CAR_Node *newNode = new CAR_Node;
    
    newNode->data   = newPageData;
    newNode->PRB    = newPagePRB;
    newNode->dirty  = newPageDirty;
    
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


long CAR_CLOCK::getPageAt(CAR_Node* node)
{
    if (_size==0) return -1;
    return node->data;
}

int CAR_CLOCK::getPRBAt(CAR_Node* node)
{
    if (_size==0) return -1;
    return node->PRB;
}



void CAR_CLOCK::setPRBAt(CAR_Node* node, int newPagePRB)
{
    node->PRB=newPagePRB;
}

void CAR_CLOCK::setDirtyAt(CAR_Node* node, bool newPageDirty)
{
    node->dirty=newPageDirty;
}

long CAR_CLOCK::getHeadPage()
{
    if (_size==0) return -1;
    return _head->next->data;
}

int CAR_CLOCK::getHeadPRB()
{
    if (_size==0) return -1;
    return _head->next->PRB;
}


void CAR_CLOCK::evictAt(CAR_Node* nodeToDelete, long &_evictPageData, int &_evictPagePRB, bool &_evictPageDirty)
{
    if (_size!=0 && nodeToDelete!=NULL)
    {
        nodeToDelete->prev->next = nodeToDelete->next;
        nodeToDelete->next->prev = nodeToDelete->prev;
        
        _evictPageData      = nodeToDelete->data;
        _evictPagePRB       = nodeToDelete->PRB;
        _evictPageDirty     = nodeToDelete->dirty;
        
        _mappingTable.erase(nodeToDelete->data);
        _size--;
        delete nodeToDelete;
    }
}

void CAR_CLOCK::evictHead(long &_evictPageData, int &_evictPagePRB, bool &_evictPageDirty)
{
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

void CAR_CLOCK::getOccupancyRatio(int algorithmID, vector<vector<long>> &occupancyNumberMatrix, int traceNumber, int algorithmNumber)
{
    CAR_Node * currentNode = _head->next;
    for (long i=0; i<_size; i++)
    {
        occupancyNumberMatrix[algorithmID][(currentNode->data)%10000]++;
        currentNode=currentNode->next;
    }
}