#!/usr/bin/python

import sys, os
import re, shutil
import linecache
import getopt

class g:
   """
   Global variables & initialization.
   """
   CACHE_SIZE = 0    # number of blocks in cache (1 Block = 512 Bytes)
   CACHE_FLUSH_UNIT = 2048    # minimal flush Unit in blocks
   NUM_CACHE_UNIT = 0      # number of unit in cache
   CACHE_FLUSH_EPOCH = 300    # cache flush interval in seconds

   SSD_TIME = 1   #number of clocks for read/write data from/to SSD
   HDD_TIME = 50  #number of clocks for data update between SSD and HDD
   cycles = 0     # clock cycle count for cost

   timeOffset = 0    # time offset - the access time of the first I/O
   inFile = None     # Input I/O trace file
   cache = None      # instance of Cache class

   unitHist = dict() # histogram statistic for unit access by all the traces
   unitHistOneEpoch = dict()   # histogram statistic for unit access in each flush epoch
   numHistoryEpoch = 3  # number of history epoch in record
   unitHistEpochs = dict() # format: {unit id : [unit histogram list for all the history epoch]}
   unitTemperature = dict()   # format: {unit id : unit temperature}
   epochWeight = [1.0, float(2)/3, float(1)/3]    # unit temperature weight for history epochs

def Usage():
   print 'USAGE'
   print '\t%s [OPTIONS] trace-file cache-size\n' % (os.path.basename(sys.argv[0]))
   print 'OPTOIONS'
   print '\t-h, --help'
   print '\t\tPrint a usage message briefly summarizing the command-line options, then exit.'
   print '\t--opt'
   print '\t\tOptimal cache is triggered.'
   print '\t-e NUM, --epoch=NUM'
   print '\t\tCache flush interval in NUM seconds.'
   print '\n'
   sys.exit(1)


def main():
   # Check for arguments
   try:
      opts, args = getopt.getopt(sys.argv[1:], "he:", ["help", "opt", "epoch="])
   except getopt.GetoptError:
      Usage()
   if len(args) != 2:
      Usage()
   flagOptCache = False    # "False": runRound is always equal to 1; "True": optimal cache is triggered
   for opt, arg in opts:
      if opt in ("-h", "--help"):
         Usage()
      elif opt == "--opt":
         flagOptCache = True
      elif opt in ("-e", "--epoch"):
         g.CACHE_FLUSH_EPOCH = long(arg)
      else:
         Usage()

   g.inFile = args[0]
   g.CACHE_SIZE = long(args[1])
   g.NUM_CACHE_UNIT = g.CACHE_SIZE / g.CACHE_FLUSH_UNIT
   g.cache = Cache()    # set instance of Cache class

   lineNum = 1    # current line number in trace file
   numEpoch = 1   # the number of flush epoch
   runRound = 1   # runRound=1 or 2, "1" means the 1st round reading trace for histogram statis, "2" means the 2nd round reading the same trace again for calculating hit ratio as top units have been cached after the 1st round.

   if flagOptCache:
      # Parameters for optimal cache simulation
      optCache = OptimalCache()  # set instance of optimal cache class
      epochStartLine = 1   # the first line number in one epoch
      epochEndLine = 1     # the last line number in one epoch
      flagFileEnd = False  # "True": the final epoch for the 2nd round is triggered

   while True:
      # Get trace reference
      [ioTime, ioRW, ioLBN, ioSize] = GetTraceReference(g.inFile, lineNum)
      if ioLBN == 0:
         if not flagOptCache:
            break    # EOF or end of file
         else:
            optCache.FlushUnit()
            epochEndLine = lineNum - 1
            lineNum = epochStartLine
            runRound = 2
            flagFileEnd = True
            continue
      if lineNum == 1:
         g.timeOffset = ioTime
      ioTime -= g.timeOffset
      lineNum += 1

      startUnit = ioLBN / g.CACHE_FLUSH_UNIT
      unitNum = (ioLBN + ioSize - 1) / g.CACHE_FLUSH_UNIT - startUnit + 1

      if runRound == 1:
         # running progress record
         if lineNum % 10000 == 0:
            print lineNum

         # Histogram statistic for unit access
         if ioTime < numEpoch * g.CACHE_FLUSH_EPOCH:
            HistStatis(startUnit, unitNum)
            HistStatisOneEpoch(startUnit, unitNum)
            if numEpoch >= 2:    # the first epoch is used for cache warm
               CheckCacheHit(startUnit, unitNum, g.cache, ioRW)  # check cache hit
         else:
            HistUpdateOneEpoch() # update unit histogram list of history epochs
            g.cache.FlushUnit()  # update cache units
            #---------------------------------------
            if flagOptCache:
               if numEpoch == 1:
                  epochStartLine = lineNum - 1     # initialise epochStartLine
                  lineNum -= 1
               else:
                  optCache.FlushUnit() # update optimal cache units
                  epochEndLine = lineNum - 2
                  lineNum = epochStartLine
                  runRound = 2   # run the same trace in current epoch again
            else:    # if flagOptCache=False, runRound is always equal to 1
               lineNum -= 1
            #---------------------------------------
            numGap = 1
            while ioTime >= (numEpoch + numGap) * g.CACHE_FLUSH_EPOCH:
               numGap += 1
            numEpoch += numGap
            g.unitHistOneEpoch.clear()    # clear unit histogram records of last epoch
      #----------------------------------------------
      elif runRound == 2:
         CheckCacheHit(startUnit, unitNum, optCache) # check optimal cache hit
         if (lineNum - 1)  == epochEndLine:
            epochStartLine = epochEndLine + 1
            runRound = 1   # enter the next new epoch
            if flagFileEnd:
               break
      else:
         print 'Error: wrong "runRound" value\n'
         sys.exit(1)

   # Display results of program run
   if flagOptCache:
      assert g.cache.ioNum == optCache.ioNum
      PrintSummary(g.cache, optCache)
   else:
      PrintSummary(g.cache)


def CheckCacheHit(startUnit, unitNum, cache, ioRW=None):
   """
   Check cache hit. The cache instance is given in the 3rd
   argument "cache".
   """
   cache.ioNum += 1
   flagHit = True
   for i in xrange(unitNum):
      unitID = startUnit + i
      cacheHit = cache.CheckHit(unitID)
      if ioRW is not None:
         AccessCost(cacheHit, unitID, ioRW)
      if not cacheHit:
         flagHit = False
   if flagHit:
      cache.hitNum += 1


def AccessCost(cacheHit, unitID, ioRW):
   """
   Calculate I/O accessing cost by clock cycles.
   """
   #Read reference
   if ioRW == 'R':
      if cacheHit:
         #directly read data from SSD
         g.cycles += g.SSD_TIME
      else:
         #data is not in SSD, then read from HDD
         g.cycles += g.HDD_TIME
   #Write reference
   elif ioRW == 'W':
      if cacheHit:
         #for tiering, only write back strategy is used
         #write data to SSD, then flag this unit(1M) as dirty.
         #this unit will be write back to HDD on replacement.
         g.cycles += g.SSD_TIME
         g.cache.SetDirtyFlag(unitID)
      else:
         #data is not in SSD, directly write to HDD
         g.cycles += g.HDD_TIME


def HistStatis(startUnit, unitNum):
   """
   Unit histogram statistic for all the I/O traces.
   """
   for i in xrange(unitNum):
      unitID = startUnit + i
      if unitID in g.unitHist:
         g.unitHist[unitID] += 1 / float(unitNum)
      else:
         g.unitHist[unitID] = 1 / float(unitNum)


def HistStatisOneEpoch(startUnit, unitNum):
   """
   Unit histogram statistic in each epoch.
   """
   for i in xrange(unitNum):
      unitID = startUnit + i
      if unitID in g.unitHistOneEpoch:
         g.unitHistOneEpoch[unitID] += 1 / float(unitNum)
      else:
         g.unitHistOneEpoch[unitID] = 1 / float(unitNum)


def HistUpdateOneEpoch():
   """
   1. Update unit's histogram list of history epochs;
   2. Update estimated temperature for each unit.
   Each unit maintains a list to record the history
   histograms for passed epochs. The length of list
   is equal to the number of history epochs need to
   be recorded.
   """
   keyOneEpoch = g.unitHistOneEpoch.keys()
   keyEpochs = g.unitHistEpochs.keys()

   keyIntersection = set(keyOneEpoch).intersection(set(keyEpochs))   # key overlap
   keyOneEpochRemain = set(keyOneEpoch).difference(keyIntersection)  # keyOneEpoch remainder
   keyEpochsRemain = set(keyEpochs).difference(keyIntersection)   # keyEpochs remainder

   # Update unit histogram list
   for key in keyIntersection:   # there is access for this unit in last epoch
      if len(g.unitHistEpochs[key]) == g.numHistoryEpoch:
         del g.unitHistEpochs[key][0]
      g.unitHistEpochs[key].append(g.unitHistOneEpoch[key])

   for key in keyOneEpochRemain:    # first access for this unit
      assert key not in g.unitHistEpochs
      g.unitHistEpochs[key] = [g.unitHistOneEpoch[key]]

   for key in keyEpochsRemain:   # no access for this unit in last epoch
      if len(g.unitHistEpochs[key]) == g.numHistoryEpoch:
         del g.unitHistEpochs[key][0]
      g.unitHistEpochs[key].append(0.0)

   # Update unit temperature
   for key in g.unitHistEpochs:
      assert len(g.unitHistEpochs[key]) <= g.numHistoryEpoch
      g.unitTemperature[key] = 0.0
      for i in xrange(len(g.unitHistEpochs[key])):
         g.unitTemperature[key] += g.epochWeight[i] * g.unitHistEpochs[key][-1*(i+1)]


class Cache:
   """
   Cache Simulator
   """
   def __init__(self):
      self.unitInCache = dict()
      self.hitNum = 0   # number of cache hit
      self.ioNum = 0    # number of I/O used for cache hit calculation after cache warm
      self.dirtyFlag = dict()    #hold dirty flag for each unit, {unitID:(True/False)}

   #Check if the data unit is cached in SSD
   def CheckHit(self, unitID):
      if unitID in self.unitInCache:
         return True
      else:
         return False

   #Set dirty flag for a data unit
   def SetDirtyFlag(self, unitID):
      self.dirtyFlag[unitID] = True

   #Return status of the data unit's dirty flag
   def IsDirtyUnit(self, unitID):
      if unitID in self.dirtyFlag:
         return True
      else:
         return False

   #Calculate write back cost by clock cycles for dirty units migrated out
   def WriteBackCost(self, unitID):
      if self.IsDirtyUnit(unitID):
         g.cycles += g.HDD_TIME * 8    #here we set each write back I/O is 128KB, so 1MB unit has 8 I/Os
         del self.dirtyFlag[unitID]

   #Calculate unit admin cost by clock cycles for each unit migrated in
   def AdminCost(self):
      g.cycles += g.HDD_TIME * 8

   #Flush cached units by migrating out/in
   def FlushUnit(self):
      if len(g.unitHistOneEpoch) <= g.NUM_CACHE_UNIT:  # all accessed units can be cached
         keyOneEpoch = g.unitHistOneEpoch.keys()
         keyInCache = self.unitInCache.keys()

         keyIntersection = set(keyInCache).intersection(keyOneEpoch)
         keyInCacheRemain = set(keyInCache).difference(keyIntersection)
         keyOneEpochRemain = set(keyOneEpoch).difference(keyIntersection)

         numEvict = len(keyOneEpochRemain) - (g.NUM_CACHE_UNIT - len(self.unitInCache))
         if numEvict > 0:
            itemTmptInCacheRemain = [[g.unitTemperature[key], key] for key in keyInCacheRemain]
            itemTmptInCacheRemain.sort()
            for i in xrange(numEvict):
               key = itemTmptInCacheRemain[i][1]
               del self.unitInCache[key]
               self.WriteBackCost(key)
         for key in keyOneEpochRemain:
            self.unitInCache[key] = True
            self.AdminCost()
         assert len(self.unitInCache) <= g.NUM_CACHE_UNIT
      else:
         itemOneEpoch = [[g.unitHistOneEpoch[key], key] for key in g.unitHistOneEpoch]
         itemOneEpoch.sort()
         keyOneEpoch = list()
         for i in xrange(g.NUM_CACHE_UNIT):
            key = itemOneEpoch[-1*(i+1)][1]
            keyOneEpoch.append(key)

         keyInCache = self.unitInCache.keys()

         keyIntersection = set(keyInCache).intersection(keyOneEpoch)
         keyInCacheRemain = set(keyInCache).difference(keyIntersection)
         keyOneEpochRemain = set(keyOneEpoch).difference(keyIntersection)

         for key in keyInCacheRemain:
            del self.unitInCache[key]
            self.WriteBackCost(key)
         for key in keyOneEpochRemain:
            self.unitInCache[key] = True
            self.AdminCost()
         assert len(self.unitInCache) == g.NUM_CACHE_UNIT


class OptimalCache:
   """
   Cache simulator used to cache the top N units within the
   first round of each epoch as the optimal caching policy.
   In the 2nd round, read the same trace in the 1st round
   again and then calculate the hit ratio using the optimal
   cached units in the 1st round.
   """
   def __init__(self):
      self.unitInCache = dict()
      self.hitNum = 0   # number of cache hit
      self.ioNum = 0    # number of I/O used for cache hit calculation after cache warm

   def CheckHit(self, unitID):
      if unitID in self.unitInCache:
         return True
      else:
         return False

   def FlushUnit(self):
      self.unitInCache.clear()

      if len(g.unitHistOneEpoch) <= g.NUM_CACHE_UNIT:    # all accessed units can be cached
         for key in g.unitHistOneEpoch:
            self.unitInCache[key] = True
      else:
         itemOneEpoch = [[g.unitHistOneEpoch[key], key] for key in g.unitHistOneEpoch]
         itemOneEpoch.sort()
         for i in xrange(g.NUM_CACHE_UNIT):
            key = itemOneEpoch[-1*(i+1)][1]
            self.unitInCache[key] = True
      assert len(self.unitInCache) <= g.NUM_CACHE_UNIT


def WindowsTickToUnixSeconds(windowsTicks):
   """
   Convert Windows filetime to Unix time.
   The windows epoch starts 1601-01-01T00:00:00Z.
   It's 11644473600 seconds before the UNIX/Linux
   epoch (1970-01-01T00:00:00Z). The Windows ticks
   are in 100 nanoseconds.
   """
   ticksPerSecond = 10000000
   epochDifference = 11644473600L
   return windowsTicks / ticksPerSecond - epochDifference


def GetTraceReference(inFile, lineNum):
   """
   Get specified line from input file.
   """
   line = linecache.getline(inFile, lineNum)
   if line != '':
      # Pick up reference from I/O trace line
      line = line.strip().split(',')
      ioTime = long(float(line[4]))
      ioLBN = long(line[1])
      ioSize = long(line[2]) / 512
      ioRW = line[3]
      return [ioTime, ioRW, ioLBN, ioSize]
   else:
      return [0, 0, 0, 0]


def PrintSummary(cache, optCache=None):
   """
   Print results of program execution. This is called at the
   end of the program run to provide a summary of what settings
   were used and the resulting hit ratio.
   """

   print '|--------------------------------------------|'
   print '|    Input file:', g.inFile
   print '|    Cache size: %dMB' % (g.CACHE_SIZE / 2048)
   print '|    Clock cycles: %d' % g.cycles
   print '|    Cache hit ratio: %f' % (float(cache.hitNum) / cache.ioNum)
   if optCache is not None:
      print '|    Optimal hit ratio: %f' % (float(optCache.hitNum) / optCache.ioNum)
   print '|--------------------------------------------|'

   outFile = open('%dm-cachesim-tier-%s' % ((g.CACHE_FLUSH_EPOCH/60), g.inFile), 'a')
   outFile.write('Input file: %s\n' % g.inFile)
   outFile.write('Cache size: %dMB\n' % (g.CACHE_SIZE / 2048))
   outFile.write('Clock cycles: %d\n' % g.cycles)
   outFile.write('Cache hit ratio: %f\n' % (float(cache.hitNum) / cache.ioNum))
   if optCache is not None:
      outFile.write('Optimal hit ratio: %f\n' % (float(optCache.hitNum) / optCache.ioNum))
   outFile.write('\n')
   outFile.close()


if __name__ == "__main__":
   main()
