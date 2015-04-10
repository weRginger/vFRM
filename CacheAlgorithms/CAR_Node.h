#ifndef _CAR_NODE_
#define _CAR_NODE_


struct CAR_Node
{
    long              data;
    int               PRB;
    bool              dirty;
    CAR_Node*         prev;
    CAR_Node*         next;
};

#endif
