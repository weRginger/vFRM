#ifndef _CART_NODE_
#define _CART_NODE_


struct CART_Node
{
    long               data;
    int                PRB;
    int                PTB;
    bool               dirty;
    CART_Node*         prev;
    CART_Node*         next;
};

#endif
