#! /usr/bin/python

import sys, os
import linecache

class g:
   """
   Global variables & Initialization
   """
   #Global constants
   CACHE_SIZE = 0 #cache size in MB (1MB = 2048 Blocks)
   CACHE_LINE = 8 #cache line size in block, default value is 8 Blocks = 4KB
   SLOT_NUM = 0   #number of slot, (SLOT_NUM = CACHE_SIZE * 2048 / CACHE_LINE)
   N_WAY = 4   #for set associative, size of each set

   #Access cost from "view of I/O"
   SSD_TIME = 1   #number of clocks for read/write data from/to SSD
   HDD_TIME = 50  #number of clocks for data update between SSD and HDD
   cycles = 0     #clock cycle count for cost
   #cost from "view of SSD" for exchange data between SSD & HDD
   numAdmin = 0   #number of cache admission (migrate data from HDD into SSD)
   numEvict = 0   #number of cache eviction (migrate data from SSD out to HDD)
   numEvictDirty = 0   #number of cache eviction for dirty page (migrate out)

   #Global variables
   inFile = '' #file namd of input file
   mappingStrag = 0  #numeric code for mapping strategy
   replaceStrag = 0  #numeric code for cache replacement strategy
   writeStrag = 0    #numeric code for write strategy
   cache = None   #instance of cache class
   hitNum = 0     #number of I/O is cache hit
   ioNum = 0      #total number of I/O counted in cache hit calculation

   ## Mapping Strategy:
   ## 0 -> Fully associative cache
   ## 1 -> Direct mapped cache
   ## 2 -> Set associative cache

   ## Cache Replacement Strategy:
   ## 0 -> LRU
   ## 1 -> ARC

   ## Write Strategy:
   ## 0 -> Write back
   ## 1 -> Write through


def main():
   #Check for command line arguments
   if len(sys.argv) != 6:
      print 'Usage: %s [cache size(MB)] [mapping strategy] [replacement strategy] [write strategy] [trace file]' % os.path.basename(sys.argv[0])
      sys.exit(1)

   #Read arguments from command line
   g.CACHE_SIZE = long(sys.argv[1])
   g.SLOT_NUM = g.CACHE_SIZE * 2048 / g.CACHE_LINE
   g.mappingStrag = int(sys.argv[2])
   g.replaceStrag = int(sys.argv[3])
   g.writeStrag = int(sys.argv[4])
   g.inFile = sys.argv[5]

   #Core cache simulation
   g.cache = Cache() #set instance of cache class
   lineNum = 1 #current line number in input file
   ioRW = 0   #reference for Read/Write flag
   ioLBN = 0  #reference for I/O logical block number (LBN)
   ioSize = 0 #reference for I/O size, number of blocks
   while True:
      #Get trace reference
      [ioRW, ioLBN, ioSize] = GetTraceReference(g.inFile, lineNum)
      if ioLBN == 0:
         break    #EOF or end of input file
      lineNum += 1
      #Running progress record
      if lineNum % 10000 == 0:
         print lineNum

      startPageID = ioLBN / g.CACHE_LINE    #start page ID of I/O trace
      pageNum = (ioLBN + ioSize - 1) / g.CACHE_LINE - startPageID + 1    #number of pages spanned by I/O trace

      #Check cache hit
      CheckCacheHit(startPageID, pageNum, ioRW)

   #Display results of program run
   PrintSummary()


def CheckCacheHit(startPageID, pageNum, ioRW):
   """
   Check cache hit.
   """
   g.ioNum += 1
   flagHit = True    #cache hit flag for an entire I/O (an I/O may have many pages)
   for i in xrange(pageNum):
      pageID = startPageID + i
      cacheHit = g.cache.CheckHit(pageID, ioRW)    #cacheHit=True: cache hit
      AccessCost(cacheHit, pageID, ioRW)
      if not cacheHit:
         flagHit = False
   if flagHit:
      g.hitNum += 1


def AccessCost(cacheHit, pageID, ioRW):
   """
   Calculate I/O accessing cost by clock cycles.
   """
   #Read reference
   if ioRW == 'R':
      if cacheHit:
         #directly read page from SSD
         g.cycles += g.SSD_TIME
      else:
         #page is not cached, so read it from HDD
         g.cycles += g.HDD_TIME
         g.numAdmin += 1
   #Write reference & write back strategy
   elif ioRW == 'W' and g.writeStrag == 0:
      #no matter cache hit or miss, write page to SSD, 
      #then flag this page as dirty. This page will be 
      #written back to HDD on replacement
      g.cycles += g.SSD_TIME
      g.cache.SetDirtyFlag(pageID)
   #Write reference & write through strategy
   elif ioRW == 'W' and g.writeStrag == 1:
      #no matter cache hit or miss, write page to SSD,
      #then write through this page to HDD.
      g.cycles += g.SSD_TIME + g.HDD_TIME
      g.numEvictDirty += 1
      g.numEvict += 1
   else:
      print 'Error: wrong write strategy'
      sys.exit(1)


class Cache:
   """
   Cache Simulator
   """
   def __init__(self):
      self.dirtyFlag = dict()    #hold dirty flag for each page, format: {pageID:(True/False)}

      if g.mappingStrag == 0:    #Fully associative cache
         if g.replaceStrag == 0:    #LRU replacement
            self.cacheSlot = LinkedList()
            self.pageToNode = dict()   #format: {pageID:(Node reference in cacheSlot)}
         elif g.replaceStrag == 1:  #ARC replacement
            self.t1 = LinkedList()
            self.b1 = LinkedList()
            self.t2 = LinkedList()
            self.b2 = LinkedList()
            self.t1_pageToNode = dict()
            self.b1_pageToNode = dict()
            self.t2_pageToNode = dict()
            self.b2_pageToNode = dict()
            self.p = 0
            self.c = g.SLOT_NUM
         else:
            print 'Error: wrong cache replacement strategy'
            sys.exit(1)
      elif g.mappingStrag == 1:  #Direct mapped cache
         self.cacheSlot = dict()    #dict format: {slotID:pageID}
      elif g.mappingStrag == 2:  #Set associative cache
         self.cacheSet = dict()     #dict format: {setID:[N_WAY slots list]}
      else:
         print 'Error: wrong cache mapping strategy'
         sys.exit(1)

   #Set dirty flag for a particular page
   def SetDirtyFlag(self, pageID):
      self.dirtyFlag[pageID] = True

   #Return status of a page's dirty flag
   def IsDirtyPage(self, pageID):
      if pageID in self.dirtyFlag:
         return True
      else:
         return False

   #Calculate write back cost by clock cycles for dirty page 
   def WriteBackCost(self, pageID):
      if self.IsDirtyPage(pageID):
         g.cycles += g.HDD_TIME
         del self.dirtyFlag[pageID]
         g.numEvictDirty += 1
      g.numEvict += 1

   #Check if a page is in the cache
   def CheckHit(self, pageID, ioRW):
      if g.mappingStrag == 0 and g.replaceStrag == 0:    #Fully associative cache with LRU
         if pageID in self.pageToNode:    #cache hit
            self.cacheSlot.MoveToTail(self.pageToNode[pageID])    #update LRU sequence
            return True
         else:    #cache miss
            if self.cacheSlot.len < g.SLOT_NUM:   #cache slot queue is not full
               self.pageToNode[pageID] = self.cacheSlot.Append(pageID)  #store missed page to cache
            elif self.cacheSlot.len == g.SLOT_NUM:    #cache slot queue is full
               delPageID = self.cacheSlot.Remove(self.cacheSlot.head)   #pop out the first item in list based on LRU
               del self.pageToNode[delPageID]
               #if evict page is dirty, write it back to HDD before replacing it
               self.WriteBackCost(delPageID)
               self.pageToNode[pageID] = self.cacheSlot.Append(pageID)  #store missed page to cache
            else:
               print 'Error: cache slot queue overflow in fully associative cache'
               sys.exit(1)
            return False
      elif g.mappingStrag == 0 and g.replaceStrag == 1:    #Fully associative cache with ARC
         if pageID in self.t1_pageToNode:    #page in T1
            self.t1.Remove(self.t1_pageToNode[pageID])
            del self.t1_pageToNode[pageID]
            self.t2_pageToNode[pageID] = self.t2.Append(pageID)
            return True
         elif pageID in self.t2_pageToNode:  #page in T2
            self.t2.MoveToTail(self.t2_pageToNode[pageID])
            return True
         elif pageID in self.b1_pageToNode:  #page in B1
            self.p = min(self.c, self.p + max(1, self.b2.len / self.b1.len))
            self.Replace(pageID)
            self.b1.Remove(self.b1_pageToNode[pageID])
            del self.b1_pageToNode[pageID]
            self.t2_pageToNode[pageID] = self.t2.Append(pageID)
            return False
         elif pageID in self.b2_pageToNode:  #page in B2
            self.p = max(0, self.p - max(1, self.b1.len / self.b2.len))
            self.Replace(pageID)
            self.b2.Remove(self.b2_pageToNode[pageID])
            del self.b2_pageToNode[pageID]
            self.t2_pageToNode[pageID] = self.t2.Append(pageID)
            return False
         else:    #page not in T1 & T2 & B1 & B2
            if self.t1.len + self.b1.len == self.c:
               if self.t1.len < self.c:
                  delPageID = self.b1.Remove(self.b1.head)
                  del self.b1_pageToNode[delPageID]
                  self.Replace(pageID)
               else:    #B1 is empty
                  delPageID = self.t1.Remove(self.t1.head)
                  del self.t1_pageToNode[delPageID]
                  self.WriteBackCost(delPageID)
            else:
               assert self.t1.len + self.b1.len < self.c
               total = self.t1.len + self.t2.len + self.b1.len + self.b2.len
               if total >= self.c:
                  assert self.t1.len + self.t2.len == self.c
                  if total == 2 * self.c:
                     delPageID = self.b2.Remove(self.b2.head)
                     del self.b2_pageToNode[delPageID]
                  self.Replace(pageID)
            self.t1_pageToNode[pageID] = self.t1.Append(pageID)
            return False
      elif g.mappingStrag == 1:    #Direct mapped cache
         slotID = self.GetSlotID(pageID)
         if self.cacheSlot.has_key(slotID):
            if pageID == self.cacheSlot[slotID]:   #cache hit
               return True
            else:    #cache miss
               self.cacheSlot[slotID] = pageID  #update cache slot
               return False
         else:    #no data in this cache slot
            self.cacheSlot[slotID] = pageID
            return False
      else:    #Set associative cache
         setID = self.GetSlotID(pageID)
         if self.cacheSet.has_key(setID):
            if pageID in self.cacheSet[setID]:  #cache hit
               self.cacheSet[setID].remove(pageID)
               self.cacheSet[setID].append(pageID)
               return True
            else:    #cache miss
               if len(self.cacheSet[setID]) < g.N_WAY:  #cache set queue is not full
                  self.cacheSet[setID].append(pageID)
               elif len(self.cacheSet[setID]) == g.N_WAY:   #cache set queue is full
                  del self.cacheSet[setID][0]   #pop out the first item in list based on LRU
                  self.cacheSet[setID].append(pageID)
               else:
                  print 'Error: cache set queue overflow in %d-way set associative cache' % g.N_WAY
                  sys.exit(1)
               return False
         else:    #no data in the whole set slots
            self.cacheSet[setID] = list()    #create a new list for the cache set
            self.cacheset[setID].append(pageID)
            return False

   #Replacement policy used by ARC
   def Replace(self, pageID):
      if self.t1.len != 0 and (self.t1.len > self.p or (self.t1.len == self.p and self.b2_pageToNode.has_key(pageID))):
         delPageID = self.t1.Remove(self.t1.head)
         del self.t1_pageToNode[delPageID]
         #if evict page is dirty, write it back to HDD before replacing it
         self.WriteBackCost(delPageID)
         self.b1_pageToNode[delPageID] = self.b1.Append(delPageID)
      else:
         delPageID = self.t2.Remove(self.t2.head)
         del self.t2_pageToNode[delPageID]
         #if evict page is dirty, write it back to HDD before replacing it
         self.WriteBackCost(delPageID)
         self.b2_pageToNode[delPageID] = self.b2.Append(delPageID)

   #Get slot index (low bits) from page ID
   def GetSlotID(self, pageID):
      if g.mappingStrag == 1:    #Direct mapped cache
         return pageID % g.SLOT_NUM
      else:    #Set associative cache
         set_num = g.SLOT_NUM / g.N_WAY
         return pageID % set_num


class Node:
   def __init__(self, value):
      self.value = value
      self.prev = None
      self.next = None

   def __repr__(self):
      if not self:
         return '(Null)'
      else:
         return '%s' % self.value

class LinkedList:
   """
   LinkedList class is a replacement for the Python 'list'
   that provides better performance for modifying large lists
   """
   def __init__(self):
      self.len = 0   #lenght of the list
      self.head = None
      self.tail = None
      self.nodeDict = dict()  #record for Node reference existing in list, format: {(node reference):(True)}

   def __repr__(self):
      if not self:
         return 'List is Null'
      elif self.len == 0:
         return 'List is empty'
      else:
         tmpList = list()
         node = self.head
         for i in xrange(self.len):
            tmpList.append(repr(node))
            node = node.next
         return '%s' % str(tmpList)

   #Add a node to the end of the list, the value of node is argument
   def Append(self, value):
      node = Node(value)

      if self.head is None and self.tail is None:
         assert self.len == 0
         node.prev = node.next = node
         self.head = self.tail = node
      elif self.head is not None and self.tail is not None:
         assert self.len > 0
         self.InsertBetween(node, self.tail, self.head)
         self.tail = node
      else:
         raise KeyError('LinkedList.Append')

      self.nodeDict[node] = True
      self.len += 1
      return node

   #Insert a node between the left & the right nodes
   def InsertBetween(self, node, left, right):
      if node and left and right:
         node.prev = left
         node.next = right
         left.next = node
         right.prev = node
      else:
         raise KeyError('LinkedList.InsertBetween')

   #Return a node at the given position of index, return error if index is out of bound
   def GetNodeByIndex(self, index):
      if index >= self.len or index < 0:
         raise IndexError('LinkedList.GetNodeByIndex')
      else:
         node = self.head
         for i in xrange(index):
            node = node.next
      return node

   #Insert a node at the given positon of index
   def Intert(self, index, value):
      node = Node(value)

      right = self.GetNodeByIndex(index)
      self.InsertBetween(node, right.prev, right)

      if index == 0:
         self.head = node

      self.nodeDict[node] = True
      self.len += 1
      return node

   #Move a node to the tail of the list
   def MoveToTail(self, node):
      if node not in self.nodeDict:
         raise KeyError('LinkedList.MoveToTail: node is not in list')

      if node is self.tail:
         pass
      elif node is self.head:
         assert self.len > 1
         self.head = node.next
         self.tail = node
      else:    #node is not self.head and node is not self.tail:
         assert self.len > 2
         self.RemoveNode(node)
         self.InsertBetween(node, self.tail, self.head)
         self.tail = node

   #Remove a node from list, the node reference is the argument
   def Remove(self, node):
      if node not in self.nodeDict:
         raise KeyError('LinkedList.Remove: node is not in list')

      if node is self.head and node is self.tail:
         assert self.len == 1
         self.head = self.tail = None
         node.prev = node.next = None
      elif node is self.head and node is not self.tail:
         assert self.len > 1
         self.head = node.next
         self.RemoveNode(node)
      elif node is self.tail and node is not self.head:
         assert self.len > 1
         self.tail = node.prev
         self.RemoveNode(node)
      else:
         assert self.len > 2
         self.RemoveNode(node)

      del self.nodeDict[node]

      self.len -= 1
      assert self.len >= 0

      rntValue = node.value
      node = None
      return rntValue

   #Remove a node from list
   def RemoveNode(self, node):
      if node and node.prev and node.next:
         node.prev.next = node.next
         node.next.prev = node.prev
         node.prev = node.next = None
      else:
         raise KeyError('LinkedList.RemoveNode')

def GetTraceReference(inFile, lineNum):
   """
   Get specified line from input file.
   """
   line = linecache.getline(inFile, lineNum)
   if line != '':
      #Pick up references from I/O trace
      line = line.strip().split(',')
      ioLBN = long(line[4]) / 512
      ioSize = long(line[5]) / 512
      ioRW = line[3]
      if ioRW == 'Write':
         ioRW = 'W'
      elif ioRW == 'Read':
         ioRW = 'R'
      else:
         print 'Error: wrong W/R format'
         sys.exit(1)
      return [ioRW, ioLBN, ioSize]
   else:
      return [0, 0, 0]


def PrintSummary():
   """
   Print results of program execution. This is called at the
   end of the program run to provide a summary of what
   settings were used and the resulting hit ratio.
   """
   if g.mappingStrag == 0:
      mapping = "Fully Associative"
   elif g.mappingStrag == 1:
      mapping = "Direct Mapped"
   elif g.mappingStrag == 2:
      mapping = "Set Associative"

   if g.replaceStrag == 0:
      replacement = 'LRU'
   elif g.replaceStrag == 1:
      replacement = 'ARC'

   if g.writeStrag == 0:
      writing = 'Write Back'
      wrAbbr = 'WB'
   elif g.writeStrag == '1':
      writing = 'Write Through'
      wrAbbr = 'WT'

   print "|--------------------------------------------|"
   print "|    Input file:", g.inFile
   print "|    Cache size: %dMB" % (g.CACHE_SIZE)
   print "|    Mapping strategy:", mapping
   print "|    Replace strategy:", replacement
   print "|    Write strategy:", writing
   print "|    Clock cycles:", g.cycles
   print "|    Admin number:", g.numAdmin
   print "|    Evict number:", g.numEvict
   print "|    Evict dirty number:", g.numEvictDirty
   print "|    Cache hit ratio: %f" % (float(g.hitNum) / g.ioNum)
   print "|--------------------------------------------|"

   fcout = open('cachesim-%s-%s-%s' % (replacement, wrAbbr, g.inFile), 'a')
   fcout.write('Input file: %s\n' % g.inFile)
   fcout.write('Cache size: %dMB\n' % (g.CACHE_SIZE))
   fcout.write('Mapping strategy: %s\n' % mapping)
   fcout.write('Replace strategy: %s\n' % replacement)
   fcout.write('Write strategy: %s\n' % writing)
   fcout.write('Clock cycles: %d\n' % g.cycles)
   fcout.write('Admin number: %d\n' % g.numAdmin)
   fcout.write('Evict number: %d\n' % g.numEvict)
   fcout.write('Evict dirty number: %d\n' % g.numEvictDirty)
   fcout.write('Cache hit ratio: %f\n\n' % (float(g.hitNum) / g.ioNum))
   fcout.close()


if __name__ == '__main__':
   main()
