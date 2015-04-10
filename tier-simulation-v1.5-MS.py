#!/usr/bin/python

import sys, os
import re, shutil
import linecache
import getopt
import operator
import copy
from collections import deque
import math

class g:
   """
   Global variables & initialization.
   """
   FLASH_SIZE = 0    # flash size in MB (1MB = 2048 Blocks)
   BIN_SIZE = 2048   # bin size in blocks
   NUM_BIN = 0       # number of bin in flash
   REPLACE_EPOCH = 300     # bin replace interval in seconds
   TRAININGTIME = 3600    # seconds, the traces in the first # seconds is used for flash training & warm-up

   timeOffset = 0    # time offset - the access time of the first I/O
   inFile = None     # Input I/O trace file
   dirName = None    # input-file name without extention (.cvs)
   dirPath = None    # folder path for tier simulation results
   cache = None      # instance of Cache class

   binPop = dict()   # popularity statistic for bin access by all the traces
   numOldEpoch = 3     # number of history epochs in record
   binPopCurrEpoch = dict()   # popularity statistic for bin access in current epoch
   binPopOldEpochs = dict()   # popularity records for bins in each old epochs
   binPopNextEpoch = dict()   # predict popularity of each bin for the next epoch
   epochWeight = [float(numOldEpoch-i)/numOldEpoch for i in xrange(numOldEpoch)]

   numIOEpoch = 0    # number of I/Os in one epoch
   numHitEpoch = 0   # number of cache hit in one epoch
   numReadEpoch = 0
   numWriteEpoch = 0
   numRead = 0    # total number of Read
   numWrite = 0   # total number of Write
   timeDuration = 0.0   # hour, toatl time duration for the overall traces

   filterRecords = 6     # data recording in number of epochs for spike filter
   numReadRecords = deque([])    # number of Read I/Os in recorded epochs
   hitRatioRecords = deque([])    # hit ratio in recorded epochs
   accessBinRecords = deque([])   # number of accessed bins in recorded epochs
   numReadSpikeRecords = deque()
   hitRatioSpikeRecords = deque()
   accessBinSpikeRecords = deque()
   filterNumRead = False
   filterHitRatio = False
   filterAccessBin = False
   spikeFilter = False     # spike status flag
   #---------------------------------------------------
   mean_topCE = 0.0  # CE: cache effectiveness
   std_topCE = 0.0
   mean_allCE = 0.0
   std_allCE = 0.0
   mean_hitRatio = 0.0
   std_hitRatio = 0.0
   id_epoch = 1


def Usage():
   print 'USAGE'
   print '\t%s [OPTIONS] cache-size(MB) trace-file\n' % (os.path.basename(sys.argv[0]))
   print 'OPTOIONS'
   print '\t-h, --help'
   print '\t\tPrint a usage message briefly summarizing the command-line options, then exit.'
   print '\t-e NUM, --epoch=NUM'
   print '\t\tCache flush interval in NUM seconds.\n\t\tDefault is %d seconds' % g.REPLACE_EPOCH
   print '\n'
   sys.exit(1)


def main():
   # Check for arguments
   try:
      opts, args = getopt.getopt(sys.argv[1:], "he:", ["help", "epoch="])
   except getopt.GetoptError:
      Usage()
   if len(args) != 2:
      Usage()
   for opt, arg in opts:
      if opt in ("-h", "--help"):
         Usage()
      elif opt in ("-e", "--epoch"):
         g.REPLACE_EPOCH = long(arg)
      else:
         Usage()

   g.inFile = args[1]
   g.FLASH_SIZE = int(args[0])
   g.NUM_BIN = g.FLASH_SIZE * 2048 / g.BIN_SIZE
   g.cache = Cache()    # set instance of Cache class

   CreateFolder()

   lineNum = 1    # current line number in trace file
   curEpoch = 1   # the number of flush epoch

   while True:
      # Get trace reference
      [ioTime, ioRW, ioLBN, ioSize] = GetTraceReference(g.inFile, lineNum)
      if ioLBN == 0:
         g.timeDuration = (GetTraceReference(g.inFile, lineNum-1)[0] - g.timeOffset) / float(3600)
         break

      if lineNum == 1:
         g.timeOffset = ioTime
      ioTime -= g.timeOffset
      lineNum += 1

      startBinID = ioLBN / g.BIN_SIZE
      binNum = (ioLBN + ioSize - 1) / g.BIN_SIZE - startBinID + 1

      # running progress record
      if lineNum % 10000 == 0:
         print lineNum

      if ioTime < curEpoch * g.REPLACE_EPOCH:
         PopStat(startBinID, binNum)
         PopStatCurrEpoch(startBinID, binNum)
         if curEpoch * g.REPLACE_EPOCH > g.TRAININGTIME:
            flag = CheckCacheHit(startBinID, binNum, ioRW)  # check cache hit
            StatCurrEpoch(ioRW, flag)
      else:
         numGap = ioTime / g.REPLACE_EPOCH - curEpoch + 1
         strEpoch = curEpoch * g.REPLACE_EPOCH
         endEpoch = (curEpoch + numGap) * g.REPLACE_EPOCH

         #StatByEpoch and/or ZeroToEpoch
         if endEpoch > g.TRAININGTIME:
            if strEpoch <= g.TRAININGTIME:
               gap = (endEpoch - g.TRAININGTIME) / g.REPLACE_EPOCH - 1
               ZeroToEpoch(g.TRAININGTIME/g.REPLACE_EPOCH+1, gap)
            else:    #strEpoch > g.TRAININGTIME
               CheckSpikeFilter(curEpoch)
               StatByEpoch(curEpoch)
               gap = numGap - 1
               ZeroToEpoch(curEpoch+1, gap)

         PopRecordByEpoch()
         PopPredNextEpoch()
         g.cache.FlushBin()  # update cached bins
         ClearStatCurrEpoch()

         curEpoch += numGap
         lineNum -= 1

   # Display results of program run
   PrintSummary()


def ClearStatCurrEpoch():
   g.binPopCurrEpoch.clear()    # clear bin popularity records in last epoch
   g.binPopNextEpoch.clear()
   g.numIOEpoch = g.numHitEpoch = g.numWriteEpoch = g.numReadEpoch = 0
   g.filterNumRead = g.filterHitRatio = g.filterAccessBin = 0.0


def CheckSpikeFilter(curEpoch):
   # initialize metrics
   numRead = g.numReadEpoch
   if numRead == 0:
      numRead = 1
   hitRatio = float(g.numHitEpoch) / g.numIOEpoch * 100
   if hitRatio == 0.0:
      hitRatio = 0.01
   accessBin = len(g.binPopCurrEpoch)

   g.filterAccessBin = False
   g.filterHitRatio = False
   g.filterNumRead = False

   if not g.spikeFilter:
      # spike filter for metrix of number of Read I/Os
      if len(g.numReadRecords) == g.filterRecords:
         mean, sd, cv = StandardDeviation(g.numReadRecords)
         ret = mean + sd*(1-cv)
         if numRead > ret and numRead/mean > 50:
            g.filterNumRead = True
      # spike filter for metrix of hit ratio
      if len(g.hitRatioRecords) == g.filterRecords:
         mean, sd, cv = StandardDeviation(g.hitRatioRecords)
         ret = mean - sd*(1-cv)
         if hitRatio < ret and mean/hitRatio > 2.5:
            g.filterHitRatio = True
      # spike filter for metrix of number of accessed bins
      if len(g.accessBinRecords) == g.filterRecords:
         mean, sd, cv = StandardDeviation(g.accessBinRecords)
         ret = mean + sd*(1-cv)
         if accessBin > ret and accessBin/mean > 10:
            g.filterAccessBin = True
      # overall spike filter check
      if g.filterNumRead and g.filterHitRatio and g.filterAccessBin:
         g.spikeFilter = True
         g.numReadSpikeRecords = deque([numRead])
         g.hitRatioSpikeRecords = deque([hitRatio])
         g.accessBinSpikeRecords = deque([accessBin])
      else:
         if len(g.numReadRecords) == g.filterRecords:
            assert len(g.hitRatioRecords) == len(g.accessBinRecords) == g.filterRecords
            g.numReadRecords.popleft()
            g.hitRatioRecords.popleft()
            g.accessBinRecords.popleft()
         g.numReadRecords.append(numRead)
         g.hitRatioRecords.append(hitRatio)
         g.accessBinRecords.append(accessBin)
   else:    #g.spikeFilter = True
      # spike filter for metrix of number of Read I/Os
      mean, sd, cv = StandardDeviation(g.numReadSpikeRecords)
      ret = mean - sd*(1-cv)
      if numRead < ret and mean/numRead > 50:
         g.filterNumRead = True
      # spike filter for metrix of hit ratio
      mean, sd, cv = StandardDeviation(g.hitRatioSpikeRecords)
      ret = mean + sd*(1-cv)
      if hitRatio > ret and hitRatio/mean > 2.5:
         g.filterHitRatio = True
      # spike filter for metrix of number of accessed bins
      mean, sd, cv = StandardDeviation(g.accessBinSpikeRecords)
      ret = mean - sd*(1-cv)
      if accessBin < ret and mean/accessBin > 10:
         g.filterAccessBin = True
      # overall spike filter check
      if g.filterNumRead and g.filterHitRatio and g.filterAccessBin:
         g.spikeFilter = False
         if len(g.numReadRecords) == g.filterRecords:
            assert len(g.hitRatioRecords) == len(g.accessBinRecords) == g.filterRecords
            g.numReadRecords.popleft()
            g.hitRatioRecords.popleft()
            g.accessBinRecords.popleft()
         g.numReadRecords.append(numRead)
         g.hitRatioRecords.append(hitRatio)
         g.accessBinRecords.append(accessBin)
      else:
         if len(g.numReadSpikeRecords) == g.filterRecords:
            assert len(g.hitRatioSpikeRecords) == len(g.accessBinSpikeRecords) == g.filterRecords
            g.numReadSpikeRecords.popleft()
            g.hitRatioSpikeRecords.popleft()
            g.accessBinSpikeRecords.popleft()
         g.numReadSpikeRecords.append(numRead)
         g.hitRatioSpikeRecords.append(hitRatio)
         g.accessBinSpikeRecords.append(accessBin)


def StandardDeviation(q):
   mean = sum(q) / float(len(q))
   var = map(lambda x : math.pow(x-mean,2), q)
   sd = sum(var) / float(len(q))
   sd = math.sqrt(sd)
   cv = sd / mean
   return mean, sd, cv


def CheckCacheHit(startBinID, binNum, rw):
   """
   Check cache hit.
   """
   g.cache.ioNum += 1
   flagHit = True
   for i in xrange(binNum):
      binID = startBinID + i
      cacheHit = g.cache.CheckHit(binID)
      if not cacheHit:
         flagHit = False
   if flagHit:
      g.cache.hitNum += 1

   if rw == "W":
      g.numWrite += 1
   else:
      g.numRead += 1

   return flagHit


def CreateFolder():
   filePath = os.path.abspath(g.inFile)
   fileHead, fileTail = os.path.split(filePath)
   g.dirName = os.path.splitext(fileTail)[0]
   g.dirPath = os.path.join(fileHead, 'cachesim-tier-' + g.dirName)
   if not os.path.isdir(g.dirPath):
      os.makedirs(g.dirPath)

   obj = os.path.join(g.dirPath, '%s-StatByEpoch-%dmin-%dMB' % (g.dirName, g.REPLACE_EPOCH/60, g.FLASH_SIZE))
   if os.path.isfile(obj):
      os.unlink(obj)


def Welford_alg(mean, std, req, n):
   std  = std + pow(req - mean, 2) * (n - 1) / n
   mean = mean + (req - mean) / n
   return mean, std


def StatCurrEpoch(rw, flag):
   g.numIOEpoch += 1
   if rw == 'W':
      g.numWriteEpoch += 1
   elif rw == 'R':
      g.numReadEpoch += 1
   if flag:
      g.numHitEpoch += 1


def ZeroToEpoch(epoch, num):
   if num == 0:   return
   with open(os.path.join(g.dirPath, '%s-StatByEpoch-%dmin-%dMB' % (g.dirName, g.REPLACE_EPOCH/60, g.FLASH_SIZE)), 'a') as source:
      for i in xrange(num):
         source.write('%d\t0\t0\t0\t0\t0.0\t%d\t0\t0\t0.0\t0\t0\t0.0\tFalse\n' % ((epoch+i)*g.REPLACE_EPOCH/60, len(g.cache.binInCache)))


def StatByEpoch(epoch):
   """
   Calculate the effectiveness of cached bins.
   Effectiveness means the percentage of cached bins which are the bins in optimal case.
   """
   allKeyEpoch = g.binPopCurrEpoch.keys()
   if len(g.binPopCurrEpoch) <= g.NUM_BIN:
      topKeyEpoch = g.binPopCurrEpoch.keys()
   else:
      itemCurrEpoch = [[key, g.binPopCurrEpoch[key]] for key in g.binPopCurrEpoch]
      itemCurrEpoch.sort(key=operator.itemgetter(1))
      topKeyEpoch = [itemCurrEpoch[-(i+1)][0] for i in xrange(g.NUM_BIN)]

   keyInCache = g.cache.binInCache.keys()

   topCacheEffect = allCacheEffect = hitRatioEpoch = 0.0

   if g.numIOEpoch != 0:
      topKeyIntersection = set(topKeyEpoch).intersection(set(keyInCache))
      topCacheEffect = float(len(topKeyIntersection)) / len(topKeyEpoch) * 100

      allKeyIntersection = set(allKeyEpoch).intersection(set(keyInCache))
      allCacheEffect = float(len(allKeyIntersection)) / len(topKeyEpoch) * 100

      hitRatioEpoch = float(g.numHitEpoch) / g.numIOEpoch * 100

      g.mean_topCE, g.std_topCE = Welford_alg(g.mean_topCE, g.std_topCE, topCacheEffect, g.id_epoch)
      g.mean_allCE, g.std_allCE = Welford_alg(g.mean_allCE, g.std_allCE, allCacheEffect, g.id_epoch)
      g.mean_hitRatio, g.std_hitRatio = Welford_alg(g.mean_hitRatio, g.std_hitRatio, hitRatioEpoch, g.id_epoch)
      g.id_epoch += 1
   else:
      assert len(topKeyEpoch) == 0

   with open(os.path.join(g.dirPath, '%s-StatByEpoch-%dmin-%dMB' % (g.dirName, g.REPLACE_EPOCH/60, g.FLASH_SIZE)), 'a') as source:
      source.write('%d\t%d\t%d\t%d\t%d\t%.2f\t%d\t%d\t%d\t%.2f\t%d\t%d\t%.2f\t%r\n' % (epoch*g.REPLACE_EPOCH/60, g.numIOEpoch, g.numWriteEpoch, g.numReadEpoch, g.numHitEpoch, hitRatioEpoch, len(keyInCache), len(allKeyEpoch), len(allKeyIntersection), allCacheEffect, len(topKeyEpoch), len(topKeyIntersection), topCacheEffect, g.spikeFilter))


def PopStat(startBinID, binNum):
   """
   Bin popularity statistic for all I/Os.
   """
   for i in xrange(binNum):
      binID = startBinID + i
      if binID in g.binPop:
         g.binPop[binID] += 1 / float(binNum)
      else:
         g.binPop[binID] = 1 / float(binNum)


def PopStatCurrEpoch(startBinID, binNum):
   """
   Bin popularity statistic in each epoch.
   """
   for i in xrange(binNum):
      binID = startBinID + i
      if binID in g.binPopCurrEpoch:
         g.binPopCurrEpoch[binID] += 1 / float(binNum)
      else:
         g.binPopCurrEpoch[binID] = 1 / float(binNum)


def PopPredNextEpoch():
   """
   Predict bin(s) should be cached in the next epoch based on predicted popularity.
   //bin popularity = access num in last epoch * reaccess probability in an epoch granularity.
   bin popularity = access number in the last epoch.
   """
   if len(g.binPopCurrEpoch) <= g.NUM_BIN:
      g.binPopNextEpoch = copy.deepcopy(g.binPopCurrEpoch)
   else:
      items = [[key, g.binPopCurrEpoch[key]] for key in g.binPopCurrEpoch]
      items.sort(key=operator.itemgetter(1))
      for i in xrange(g.NUM_BIN):
         g.binPopNextEpoch[items[-1*(i+1)][0]] = items[-1*(i+1)][1]


def PopRecordByEpoch():
   """
   Update bin's popularity records of history epochs.
   Each bin maintains a list to record the history
   popularity for passed epochs. The length of list
   is equal to the number of history epochs need to
   be recorded.
   """
   keyCurrEpoch = g.binPopCurrEpoch.keys()
   keyOldEpochs = g.binPopOldEpochs.keys()

   keyIntersection = set(keyCurrEpoch).intersection(set(keyOldEpochs))  #key overlap
   keyCurrEpochRemain = set(keyCurrEpoch).difference(keyIntersection)   #keyCurrEpoch remainder
   keyOldEpochsRemain = set(keyOldEpochs).difference(keyIntersection)   #keyOldEpochs remainder

   #there is access for this bin in last epoch
   for key in keyIntersection:
      if len(g.binPopOldEpochs[key]) == g.numOldEpoch:
         del g.binPopOldEpochs[key][0]
      g.binPopOldEpochs[key].append(g.binPopCurrEpoch[key])

   #first access for this bin
   for key in keyCurrEpochRemain:
      assert key not in g.binPopOldEpochs
      g.binPopOldEpochs[key] = [g.binPopCurrEpoch[key]]

   #no access for this bin in last epoch
   for key in keyOldEpochsRemain:
      if len(g.binPopOldEpochs[key]) == g.numOldEpoch:
         del g.binPopOldEpochs[key][0]
      g.binPopOldEpochs[key].append(0.0)


class Cache:
   """
   Cache Simulator
   """
   def __init__(self):
      self.binInCache = dict()
      self.hitNum = 0   # number of cache hit
      self.ioNum = 0    # number of I/O used for cache hit calculation after cache warm

   #Check if the data within bin is cached
   def CheckHit(self, binID):
      if binID in self.binInCache:
         assert self.binInCache[binID] == True
         return True
      else:
         return False

   #Flush cached bins by migrating out/in
   def FlushBin(self):
      keyNextEpoch = g.binPopNextEpoch.keys()
      keyInCache = self.binInCache.keys()

      keyIntersection = set(keyInCache).intersection(keyNextEpoch)
      keyInCacheRmn = set(keyInCache).difference(keyIntersection)
      keyNextEpochRmn = set(keyNextEpoch).difference(keyIntersection)

      numEvict = len(keyNextEpochRmn) - (g.NUM_BIN - len(keyInCache))
      if 0 < numEvict < len(keyInCacheRmn):
         items = []
         for key in keyInCacheRmn:     #calculate popularity
            pop = 0.0
            for i in xrange(len(g.binPopOldEpochs[key])):
               pop += g.epochWeight[i] * g.binPopOldEpochs[key][-1*(i+1)]
            items.append([key, pop])
         items.sort(key=operator.itemgetter(1))
         for i in xrange(numEvict):    #migrate out
            key = items[i][0]
            del self.binInCache[key]
      elif numEvict == len(keyInCacheRmn):
         for key in keyInCacheRmn:     #migrate out
            del self.binInCache[key]
      else:
         assert numEvict <= 0

      #migrate in
      for key in keyNextEpochRmn:
         self.binInCache[key] = True
      assert len(self.binInCache) <= g.NUM_BIN


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
      ioTime = int(line[1])/1000000
      ioLBN = long(line[5], 16) / 512
      ioSize = long(line[6], 16) / 512
      ioRW = line[0]
      if ioRW == 'DiskWrite':
         ioRW = 'W'
      elif ioRW == 'DiskRead':
         ioRW = 'R'
      else:
         print 'Error: wrong W/R format'
         sys.exit(1)
      return [ioTime, ioRW, ioLBN, ioSize]
   else:
      return [0, 0, 0, 0]


def PrintSummary():
   """
   Print results of program execution. This is called at the
   end of the program run to provide a summary of what settings
   were used and the resulting hit ratio.
   """

   with open(os.path.join(g.dirPath, '%s-StatByEpoch-%dmin-%dMB' % (g.dirName, g.REPLACE_EPOCH/60, g.FLASH_SIZE)), 'a') as source:
      source.write('\nmean cache effect = %.2f\nmean top cache effect = %.2f\nmean hit ratio = %.2f\n' % (g.mean_allCE, g.mean_topCE, g.mean_hitRatio))

   print '|--------------------------------------------|'
   print '|    Input file:', g.inFile
   print '|    Flash size: %dMB' % (g.FLASH_SIZE)
   print '|    Cache hit ratio: %f' % (float(g.cache.hitNum) / g.cache.ioNum)
   print '|--------------------------------------------|'

   outFile = open(os.path.join(g.dirPath, '%s-stat-%dmin-%dMB' % (g.dirName, g.REPLACE_EPOCH/60, g.FLASH_SIZE)), 'a')
   outFile.write('Input file: %s\n' % g.inFile)
   outFile.write('Flash size: %d(MB)\n' % (g.FLASH_SIZE))
   outFile.write('Time duration: %.3f(hour)\n' % (g.timeDuration))
   outFile.write('Number of I/Os: %d\n' % (g.cache.ioNum))
   outFile.write('Number of Read: %d\n' % (g.numRead))
   outFile.write('Number of Write: %d\n' % (g.numWrite))
   outFile.write('Read/Write ratio: %.3f\n' % (float(g.numRead) / g.numWrite))
   outFile.write('Cache hit ratio: %f\n' % (float(g.cache.hitNum) / g.cache.ioNum))
   outFile.write('\n')
   outFile.close()


if __name__ == "__main__":
   main()
