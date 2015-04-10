#ifndef _ARC_NODE_
#define _ARC_NODE_


struct ARC_Node
{
    long              data;
    bool              dirty;
    ARC_Node*         prev;
    ARC_Node*         next;
};

#endif
