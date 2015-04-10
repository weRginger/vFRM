#!/usr/bin/python

import sys, os
import re, shutil
import linecache
import getopt

class g:
   """
   Global variables & initialization.
   """
   CACHE_SIZE = 0    #cache size in MB (1MB = 2048 Blocks)
   CACHE_FLUSH_UNIT = 2048    #minimal flush Unit in blocks
   NUM_CACHE_UNIT = 0      #number of unit in cache
   CACHE_FLUSH_EPOCH = 300    #cache flush interval in seconds

   numFile = 12       #number of input files
   inFile = [None for i in range(numFile)]       #Input I/O trace file
   cache = None      #instance of Cache class
   cachePartition = list()
   hitNum = 0     # number of cache hit
   ioNum = 0      # number of I/O used for cache hit calculation after cache warm
   hitNumFile = [0 for i in xrange(numFile)]
   ioNumFile = [0 for i in xrange(numFile)]

   unitHist = dict()    #histogram statistic for unit access by all the traces
   unitHistOneEpoch = dict()   #histogram statistic for unit access in each flush epoch
   numHistoryEpoch = 3     #number of history epoch in record
   unitHistEpochs = dict()    #format: {unit id : [unit histogram list for all the history epoch]}
   unitTemperature = dict()   #format: {unit id : unit temperature}
   epochWeight = [1.0, float(2)/3, float(1)/3]    #unit temperature weight for history epochs

def Usage():
   print 'USAGE'
   print '\t%s [OPTIONS] cache-size(MB) %d-trace-files\n' % (os.path.basename(sys.argv[0]), g.numFile)
   print 'OPTOIONS'
   print '\t-h, --help'
   print '\t\tPrint a usage message briefly summarizing the command-line options, then exit.'
   print '\t-e NUM, --epoch=NUM'
   print '\t\tCache flush interval in NUM seconds.'
   print '\n'
   sys.exit(1)


def main():
   # Check for arguments
   try:
      opts, args = getopt.getopt(sys.argv[1:], "he:", ["help", "epoch="])
   except getopt.GetoptError:
      Usage()
   if len(args) != g.numFile + 1:
      Usage()
   for opt, arg in opts:
      if opt in ("-h", "--help"):
         Usage()
      elif opt in ("-e", "--epoch"):
         g.CACHE_FLUSH_EPOCH = long(arg)
      else:
         Usage()

   for i in xrange(g.numFile):
      g.inFile[i] = args[i+1]
   g.CACHE_SIZE = long(args[0])
   g.NUM_CACHE_UNIT = g.CACHE_SIZE * 2048 / g.CACHE_FLUSH_UNIT
   g.cache = Cache()    # set instance of Cache class

   obj = '%dmin-cachesim-tier-global-%dMB-cachepart' % (g.CACHE_FLUSH_EPOCH/60, g.CACHE_SIZE)
   if os.path.isfile(obj):
      os.unlink(obj)

   numEpoch = 1   # the number of flush epoch
   numMigOut = 0  # number of MB migrated out of cache
   numMigIn = 0   # number of MB migrated into cache

   lineNum = [1 for i in range(g.numFile)]    #list used to record the current line number in trace files
   ioRW = [0 for i in range(g.numFile)]   #reference for Read/Write flag
   ioLBN = [0 for i in range(g.numFile)]  #reference for I/O logical block number (LBN)
   ioSize = [0 for i in range(g.numFile)] #reference for I/O size, number of blocks
   ioTime = [0 for i in range(g.numFile)] #reference for I/O access time
   timeOffset = [0 for i in range(g.numFile)]   #time offset for each trace starting from 0
   breakFlag = [False for i in range(g.numFile)] #flag for reading the last trace in each input file
   breakFinal = 0    #flag to break the "while" below
   #Initialize trace references
   for i in xrange(g.numFile):
      [ioTime[i], ioRW[i], ioLBN[i], ioSize[i]] = GetTraceReference(g.inFile[i], lineNum[i])
      if ioLBN[i] == 0:
         print 'Error: cannot get trace from the %dth trace file' % i
         sys.exit(1)
      lineNum[i] += 1
      timeOffset[i] = ioTime[i]   #calculate time offset for the starting time of each trace
      ioTime[i] = 0
   #Get the latest trace
   curr = GetTrace(ioTime, breakFlag)

   while True:
      # running progress record
      if lineNum[curr] % 10000 == 0:
         print curr, lineNum[curr]

      startUnit = ioLBN[curr] / g.CACHE_FLUSH_UNIT
      unitNum = (ioLBN[curr] + ioSize[curr] - 1) / g.CACHE_FLUSH_UNIT - startUnit + 1

      # Histogram statistic for unit access
      if ioTime[curr] < numEpoch * g.CACHE_FLUSH_EPOCH:
         HistStatis(startUnit, unitNum, curr)
         HistStatisOneEpoch(startUnit, unitNum, curr)
         if numEpoch >= 2:    # the first epoch is used for cache warm
            CheckCacheHit(startUnit, unitNum, g.cache, curr)  # check cache hit
      else:
         HistUpdateOneEpoch() # update unit histogram list of history epochs
         numMigOut, numMigIn = g.cache.FlushUnit(numMigOut, numMigIn)  # update cache units
         CheckCachePartition(g.cache)
         #---------------------------------------
         lineNum[curr] -= 1
         numGap = 1
         while ioTime[curr] >= (numEpoch + numGap) * g.CACHE_FLUSH_EPOCH:
            numGap += 1
         numEpoch += numGap
         g.unitHistOneEpoch.clear()    # clear unit histogram records of last epoch

      [ioTime[curr], ioRW[curr], ioLBN[curr], ioSize[curr]] = GetTraceReference(g.inFile[curr], lineNum[curr])
      ioTime[curr] -= timeOffset[curr]
      if ioLBN[curr] == 0:
         breakFlag[curr] = True
         breakFinal += 1
      if breakFinal == g.numFile:
         break
      lineNum[curr] += 1
      curr = GetTrace(ioTime, breakFlag)

   # Display results of program run
   PrintSummary(numMigOut, numMigIn)
   print 'hit num = %d\nio num = %d' % (g.hitNum, g.ioNum)


def GetTrace(ioTime, breakFlag):
   j = None
   for i in xrange(g.numFile):
      if not breakFlag[i]:
         minTime = ioTime[i]
         j = i
         break
   assert j is not None
   if (j+1) < g.numFile:
      for i in range(j+1, g.numFile):
         if not breakFlag[i] and ioTime[i] < minTime:
            minTime = ioTime[i]
            j = i
   return j


def CheckCacheHit(startUnit, unitNum, cache, curr):
   """
   Check cache hit. The cache instance is given in the 3rd
   argument "cache".
   """
   g.ioNum += 1
   g.ioNumFile[curr] += 1
   flagHit = True
   for i in xrange(unitNum):
      unitID = startUnit + i
      unitID = (unitID << 4) + curr
      cacheHit = cache.CheckHit(unitID)
      if not cacheHit:
         flagHit = False
   if flagHit:
      g.hitNum += 1
      g.hitNumFile[curr] += 1


def HistStatis(startUnit, unitNum, curr):
   """
   Unit histogram statistic for all the I/O traces.
   """
   for i in xrange(unitNum):
      unitID = startUnit + i
      unitID = (unitID << 4) + curr
      if unitID in g.unitHist:
         g.unitHist[unitID] += 1 / float(unitNum)
      else:
         g.unitHist[unitID] = 1 / float(unitNum)


def HistStatisOneEpoch(startUnit, unitNum, curr):
   """
   Unit histogram statistic in each epoch.
   """
   for i in xrange(unitNum):
      unitID = startUnit + i
      unitID = (unitID << 4) + curr
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


def CheckCachePartition(cache):
   g.cachePartition = [0 for i in xrange(g.numFile)]
   for key in cache.unitInCache:
      assert cache.unitInCache[key] == True
      k = key & 0xF
      assert 0 <= k < g.numFile
      g.cachePartition[k] += 1
   with open('%dmin-cachesim-tier-global-%dMB-cachepart' % (g.CACHE_FLUSH_EPOCH/60, g.CACHE_SIZE), 'a') as source:
      sum = 0.0
      for i in xrange(g.numFile):
         tmp = float(g.cachePartition[i]) / g.NUM_CACHE_UNIT * 100
         sum += tmp
         source.write('%.2f\t' % (tmp))
      source.write('%.2f\n' % (sum))


class Cache:
   """
   Cache Simulator
   """
   def __init__(self):
      self.unitInCache = dict()

   def CheckHit(self, unitID):
      if unitID in self.unitInCache:
         return True
      else:
         return False

   def FlushUnit(self, numMigOut, numMigIn):
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
            numMigOut += numEvict
         for key in keyOneEpochRemain:
            self.unitInCache[key] = True
         numMigIn += len(keyOneEpochRemain)
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
         for key in keyOneEpochRemain:
            self.unitInCache[key] = True
         numMigOut += len(keyInCacheRemain)
         numMigIn += len(keyOneEpochRemain)

      assert len(self.unitInCache) <= g.NUM_CACHE_UNIT
      return numMigOut, numMigIn


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
      ioTime = WindowsTickToUnixSeconds(long(line[0]))
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
      return [ioTime, ioRW, ioLBN, ioSize]
   else:
      return [0, 0, 0, 0]


def PrintSummary(numMigOut, numMigIn):
   """
   Print results of program execution. This is called at the
   end of the program run to provide a summary of what settings
   were used and the resulting hit ratio.
   """


   print '|---------------------------------------------'
#   print '|    Input files: ',
#   for i in xrange(g.numFile):
#      print g.inFile[i] + ' ',
#   print ''
   print '|    Cache size: %dMB' % (g.CACHE_SIZE)
   print '|    Migrate out %dMB' % numMigOut
   print '|    Migrate in  %dMB' % numMigIn
   print '|    Cache hit ratio: %f' % (float(g.hitNum) / g.ioNum)
   for i in xrange(g.numFile):
      print '|    Input files %d: %s\t%d\t%d\t%.2f' % (i, g.inFile[i], g.ioNumFile[i], g.hitNumFile[i], float(g.hitNumFile[i])/g.ioNumFile[i])
   print '|---------------------------------------------'

   outFile = open('%dm-cachesim-tier-global' % (g.CACHE_FLUSH_EPOCH/60), 'a')
#   outFile.write('Input files: ')
#   for i in xrange(g.numFile):
#      outFile.write(g.inFile[i] + ' ')
#   outFile.write('\n')
   outFile.write('Cache size: %dMB\n' % (g.CACHE_SIZE))
   outFile.write('Migrate out: %dMB\n' % numMigOut)
   outFile.write('Migrate in:  %dMB\n' % numMigIn)
   outFile.write('Cache hit ratio: %f\n' % (float(g.hitNum) / g.ioNum))
   for i in xrange(g.numFile):
      outFile.write('Input files %d: %s\t%d\t%d\t%.2f\n' % (i, g.inFile[i], g.ioNumFile[i], g.hitNumFile[i], float(g.hitNumFile[i])/g.ioNumFile[i]))
   outFile.write('\n')
   outFile.close()


if __name__ == "__main__":
   main()
