#include "CART_CLOCK.h"

CART_CLOCK::CART_CLOCK()
{
    _size =0;
    _head = new CART_Node;
    _head->prev = _head;
    _head->next = _head;

}


long CART_CLOCK::size()
{
    return _size;
}

void CART_CLOCK::print()
{
    if (_size==0)
    {
        cout<<"Empty list."<<endl;
    }
    else
    {
        vector <int> PRB;
        vector <int> PTB;
        CART_Node * currentNode = _head->next;
        cout<<"["<<currentNode->data<<"]\t";
        PRB.push_back(currentNode->PRB);
        PTB.push_back(currentNode->PTB);
        currentNode=currentNode->next;
        long i=1;
        while (i<_size)
        {
            cout<<currentNode->data<<"\t";
            PRB.push_back(currentNode->PRB);
            PTB.push_back(currentNode->PTB);
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
    
 

CART_Node* CART_CLOCK::search(long pageToSearch)
{
    CART_Node* foundNode = _mappingTable[pageToSearch];
    if(foundNode)
    {
        if (displayCoutCART) cout<<"Found."<<endl;
        return foundNode;
    }
    else
    {
        if (displayCoutCART) cout<<"not found"<<endl;
        return NULL;
    }
}

void CART_CLOCK::attachToTail(long newPageData, int PRBValue, int PTBValue, bool DirtyValue)
{
    // New node
    CART_Node *newNode = new CART_Node;
    
    newNode->data = newPageData;
    newNode->PRB = PRBValue;
    newNode->PTB = PTBValue;
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
    {
        // _head -> old1 -> old2 -> [x] -> _head
        newNode->next = _head;
        newNode->prev = _head->prev;
        _head->prev->next=newNode;
        _head->prev=newNode;
    }
    _size++;
}


long CART_CLOCK::getPageAt(CART_Node* node)
{
    if (_size==0) return -1;
    return node->data;
}

int CART_CLOCK::getPRBAt(CART_Node* node)
{
    if (_size==0) return -1;
    return node->PRB;
}

int CART_CLOCK::getPTBAt(CART_Node* node)
{
    if (_size==0) return -1;
    return node->PTB;
}


void CART_CLOCK::setPRBAt(CART_Node* node, int PRBvalue)
{
    node->PRB=PRBvalue;
}


void CART_CLOCK::setPTBAtTailToL()
{
    _head->prev->PTB=1;
}


void CART_CLOCK::setDirtyAt(CART_Node* node, bool newPageDirty)
{
    node->dirty=newPageDirty;
}



long CART_CLOCK::getHeadPage()
{
    if (_size==0) return -1;
    return _head->next->data;
}

int CART_CLOCK::getHeadPRB()
{
    if (_size==0) return -1;
    return _head->next->PRB;
}

int CART_CLOCK::getHeadPTB()
{
    if (_size==0) return -1;
    return _head->next->PTB;
}

void CART_CLOCK::evictAt(CART_Node* nodeToDelete, long &_evictPageData, int &_evictPagePRB, int &_evictPagePTB, bool &_evictPageDirty)
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

void CART_CLOCK::evictHead(long &_evictPageData, int &_evictPagePRB, int &_evictPagePTB, bool &_evictPageDirty)
{
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

void CART_CLOCK::getOccupancyRatio(int algorithmID, vector<vector<long>> &occupancyNumberMatrix, int traceNumber, int algorithmNumber)
{
    CART_Node * currentNode = _head->next;
    for (long i=0; i<_size; i++)
    {
        occupancyNumberMatrix[algorithmID][(currentNode->data)%10000]++;
        currentNode=currentNode->next;
    }
}



