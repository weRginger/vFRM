#!/usr/bin/python

import sys, os
import re, shutil
import linecache
import getopt
import operator
import copy
from collections import deque
import math
import heapq

class g:
   """
   Global variables & initialization.
   """
   FLASH_SIZE = 0    # flash size in MB (1MB = 2048 Blocks)
   BIN_SIZE = 2048   # bin size in blocks
   NUM_BIN = 0       # number of bin in flash
   REPLACE_EPOCH = 300     # bin replace interval in seconds
   WARMUP = 86400    # seconds, the traces in the first # seconds is used for flash training & warm-up:
   cache = None      # instance of Cache class
   numWL = 1
   wl = []       # workload: I/O trace from input files
   dirName = None    # input-file name without extention (.cvs)
   dirPath = None    # folder path for tier simulation results

   glbBinCurrPop = dict()   # popularity statistic for bin access in current epoch
   glbBinOldPop = dict()    # popularity records for bins in each old epochs
   glbBinNextPop = dict()   # predict popularity of each bin for the next epoch
   numOldEpoch = 3     # number of history epochs in record
   epochWeight = [float(numOldEpoch-i)/numOldEpoch for i in xrange(numOldEpoch)]

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


class Workload:
   def __init__(self):
      self.inFile = None     # input file path for this workload class
      self.fname = None      # input file name (not abspath)
      self.curLine = 1       # current line number in trace file
      self.lastLine = False  # flag for reading the last trace in each input file
      self.ioRW = 0       # reference for Read/Write flag
      self.ioLBN = 0      # reference for I/O logical block number (LBN)
      self.ioSize = 0     # reference for I/O size, number of blocks
      self.ioTime = 0     # reference for I/O access time
      self.timeOffset = 0   # time offset for each trace starting from 0
      self.timeLength = 0   # total time duration for the whole trace in this workload
      self.binCurrPop = dict()   # dict for popularity statistic of bins in current epoch
      self.numIO = 0
      self.numHit = 0
      self.numRead = 0
      self.numWrite = 0
      self.numIOEpoch = 0
      self.numHitEpoch = 0
      self.numReadEpoch= 0
      self.numWriteEpoch = 0

def Usage():
   print 'USAGE'
   print '\t%s [OPTIONS] <flash size(MB)> <trace files>\n' % (os.path.basename(sys.argv[0]))
   print 'OPTOIONS'
   print '\t-h, --help'
   print '\t\tPrint a usage message briefly summarizing the command-line options, then exit.'
   print '\t-e NUM, --epoch=NUM'
   print '\t\tFlash flush interval in NUM seconds.\n\t\tDefault is %d seconds' % g.REPLACE_EPOCH
   print '\n'
   sys.exit(1)


def main():
   # Check for arguments
   try:
      opts, args = getopt.getopt(sys.argv[1:], "he:", ["help", "epoch="])
   except getopt.GetoptError:
      Usage()
   if len(args) < 2:
      Usage()
   for opt, arg in opts:
      if opt in ("-h", "--help"):
         Usage()
      elif opt in ("-e", "--epoch"):
         g.REPLACE_EPOCH = long(arg)
      else:
         Usage()

   g.FLASH_SIZE = int(args[0])
   g.NUM_BIN = g.FLASH_SIZE * 2048 / g.BIN_SIZE
   g.cache = Cache()    # set instance of Cache class

   g.numWL = len(args) - 1;
   for i in xrange(g.numWL):
      g.wl.append(Workload())
      g.wl[i].inFile = args[i+1]
      fp = os.path.abspath(args[i+1])
      fh, ft = os.path.split(fp)
      g.wl[i].fname = os.path.splitext(ft)[0]

   CreateFolder()

   # Initialize trace references
   for i in xrange(g.numWL):
      [g.wl[i].ioTime, g.wl[i].ioRW, g.wl[i].ioLBN, g.wl[i].ioSize] = GetTraceReference(g.wl[i].inFile, g.wl[i].curLine)
      if g.wl[i].ioLBN == 0:
         print 'Error: cannot get trace from the %dth trace file: %s' % (i, g.wl[i].inFile)
         sys.exit(1)
      g.wl[i].curLine += 1
      g.wl[i].timeOffset = g.wl[i].ioTime   # calculate time offset for the starting time of each trace
      g.wl[i].ioTime = 0
   # Get the latest trace
   curWL = GetNextWorkload()
   curEpoch = 1   # the number of flush epoch
   breakWLs = 0    # flag to break the "while", all the workloads have been done.

   while True:
      # running progress record
      if g.wl[curWL].curLine % 10000 == 0:
         print '%s:\t%d' % (g.wl[curWL].inFile, g.wl[curWL].curLine)

      startBinID = g.wl[curWL].ioLBN / g.BIN_SIZE
      binNum = (g.wl[curWL].ioLBN + g.wl[curWL].ioSize - 1) / g.BIN_SIZE - startBinID + 1

      if g.wl[curWL].ioTime < curEpoch * g.REPLACE_EPOCH:
         PopStatCurrEpoch(startBinID, binNum, curWL)
         if curEpoch * g.REPLACE_EPOCH > g.WARMUP:
            flag = CheckCacheHit(startBinID, binNum, curWL)  # check cache hit
            StatCurrEpoch(curWL, flag)
      else:
         numGap = g.wl[curWL].ioTime / g.REPLACE_EPOCH - curEpoch + 1
         strEpoch = curEpoch * g.REPLACE_EPOCH
         endEpoch = (curEpoch + numGap) * g.REPLACE_EPOCH

         #StatByEpoch and/or ZeroToEpoch
         if endEpoch > g.WARMUP:
            if strEpoch <= g.WARMUP:
               gap = (endEpoch - g.WARMUP) / g.REPLACE_EPOCH - 1
               ZeroToEpoch(g.WARMUP/g.REPLACE_EPOCH+1, gap)
            else:    #strEpoch > g.WARMUP
               StatByEpoch(curEpoch)
               gap = numGap - 1
               ZeroToEpoch(curEpoch+1, gap)

#         CheckSpikeFilter(curEpoch)
         PopRecordByEpoch()
         PopPredNextEpoch()
         g.cache.FlushBin()  # update cached bins
         if g.numWL > 1:
            GetFlashShare(curEpoch, numGap)
         ClearStatCurrEpoch()

         curEpoch += numGap
#         g.wl[curWL].curLine -= 1
         continue

      # Get trace reference
      [g.wl[curWL].ioTime, g.wl[curWL].ioRW, g.wl[curWL].ioLBN, g.wl[curWL].ioSize] = GetTraceReference(g.wl[curWL].inFile, g.wl[curWL].curLine)
      g.wl[curWL].ioTime -= g.wl[curWL].timeOffset
      if g.wl[curWL].ioLBN == 0:
         g.wl[curWL].lastLine = True
         breakWLs += 1
         g.wl[curWL].timeLength = (GetTraceReference(g.wl[curWL].inFile, g.wl[curWL].curLine-1)[0] - g.wl[curWL].timeOffset) / float(3600)
         if breakWLs == g.numWL:
            break
      g.wl[curWL].curLine += 1
      curWL = GetNextWorkload()

   # Display results of program run
   PrintSummary()

def GetNextWorkload():
   j = None
   for i in xrange(g.numWL):
      if not g.wl[i].lastLine:
         minTime = g.wl[i].ioTime
         j = i
         break
   assert j is not None
   if (j+1) < g.numWL:
      for i in range(j+1, g.numWL):
         if not g.wl[i].lastLine and g.wl[i].ioTime < minTime:
            minTime = g.wl[i].ioTime
            j = i
   return j

def ClearStatCurrEpoch():
   g.glbBinCurrPop.clear()    # clear bin popularity records in last epoch
   g.glbBinNextPop.clear()
   for i in xrange(g.numWL):
      g.wl[i].binCurrPop.clear()
      g.wl[i].numIOEpoch = g.wl[i].numHitEpoch = g.wl[i].numWriteEpoch = g.wl[i].numReadEpoch = 0
#   g.filterNumRead = g.filterHitRatio = g.filterAccessBin = 0.0


def CheckSpikeFilter(curEpoch):
   # initialize metrics
   numRead = g.numReadEpoch
   if numRead == 0:
      numRead = 1
   hitRatio = float(g.numHitEpoch) / g.numIOEpoch * 100
   if hitRatio == 0.0:
      hitRatio = 0.01
   accessBin = len(g.binCurrPop)

   g.filterAccessBin = False
   g.filterHitRatio = False
   g.filterNumRead = False

   if not g.spikeFilter:
      # spike filter for metrix of number of Read I/Os
      if len(g.numReadRecords) == g.filterRecords:
         mean, sd, cv = StandardDeviation(g.numReadRecords)
         ret = mean + sd*(1-cv)
         if numRead > ret and numRead/mean > 100:
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
      if numRead < ret and mean/numRead > 100:
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


def Welford_alg(mean, std, req, n):
   std  = std + pow(req - mean, 2) * (n - 1) / n
   mean = mean + (req - mean) / n
   return mean, std


def CheckCacheHit(startBinID, binNum, n):
   """
   Check cache hit.
   """
   g.cache.numIO += 1
   if g.wl[n].ioRW == 'R':
      g.cache.numRead += 1
   else:
      g.cache.numWrite += 1

   flagHit = True
   for i in xrange(binNum):
      binID = startBinID + i
      binID = (binID << 4) + n
      cacheHit = g.cache.CheckHit(binID)
      if not cacheHit:
         flagHit = False
   if flagHit:
      g.cache.numHit += 1
   return flagHit


def StatCurrEpoch(n, flag):
   g.wl[n].numIO += 1
   g.wl[n].numIOEpoch += 1
   if g.wl[n].ioRW == 'W':
      g.wl[n].numWrite += 1
      g.wl[n].numWriteEpoch += 1
   else:
      g.wl[n].numRead += 1
      g.wl[n].numReadEpoch += 1
   if flag:
      g.wl[n].numHit += 1
      g.wl[n].numHitEpoch += 1


def CreateFolder():
   filePath = os.path.abspath(sys.argv[0])
   fileHead, fileTail = os.path.split(filePath)
   if g.numWL == 1:
      fp = os.path.abspath(g.wl[0].inFile)
      fh, ft = os.path.split(fp)
      g.dirName = os.path.splitext(ft)[0]
   else:
      g.dirName = 'globalflash'
   g.dirPath = os.path.join(fileHead, 'cachesim-tier-' + g.dirName)
   if not os.path.isdir(g.dirPath):
      os.makedirs(g.dirPath)

   if g.numWL == 1:
      obj = os.path.join(g.dirPath, '%s-StatByEpoch-%dmin-%dMB' % (g.dirName, g.REPLACE_EPOCH/60, g.FLASH_SIZE))
      if os.path.isfile(obj):
         os.unlink(obj)
   else:
      for i in xrange(g.numWL):
         obj = os.path.join(g.dirPath, 'global-%s-StatByEpoch-%dfile-%dmin-%dMB' % (g.wl[i].fname, g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE))
         if os.path.isfile(obj):
            os.unlink(obj)
      obj = os.path.join(g.dirPath, 'flashshare-%dfile-%dmin-%dMB' % (g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE))
      if os.path.isfile(obj):
         os.unlink(obj)


def ZeroToEpoch(epoch, num):
   if num == 0:   return
   if g.numWL == 1:
      with open(os.path.join(g.dirPath, '%s-StatByEpoch-%dmin-%dMB' % (g.dirName, g.REPLACE_EPOCH/60, g.FLASH_SIZE)), 'a') as source:
         for i in xrange(num):
            source.write('%d\t0\t0\t0\t0\t0.0\t%d\t0\t0\t0.0\t0\t0\t0.0\tFalse\n' % ((epoch+i)*g.REPLACE_EPOCH/60, len(g.cache.binInCache)))
   else:
      for i in xrange(g.numWL):
         with open(os.path.join(g.dirPath, 'global-%s-StatByEpoch-%dfile-%dmin-%dMB' % (g.wl[i].fname, g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE)), 'a') as source:
            for i in xrange(num):
               source.write('%d\t0\t0\t0\t0\t0.0\t%d\t0\t0\t0.0\t0\t0\t0.0\tFalse\n' % ((epoch+i)*g.REPLACE_EPOCH/60, len(g.cache.binInCache)))


def StatByEpoch(epoch):
   """
   Calculate the effectiveness of cached bins.
   Effectiveness means the percentage of cached bins which are the bins in optimal case.
   """
   if g.numWL == 1:
      allKeyEpoch = g.wl[0].binCurrPop.keys()
      if len(g.wl[0].binCurrPop) <= g.NUM_BIN:
         topKeyEpoch = g.wl[0].binCurrPop.keys()
      else:
         topKeyEpoch = heapq.nlargest(g.NUM_BIN, g.wl[0].binCurrPop.iteritems(), key=operator.itemgetter(1))
         topKeyEpoch = [item[0] for item in topKeyEpoch]
#         itemCurrEpoch = [[key, g.binCurrPop[key]] for key in g.binCurrPop]
#         itemCurrEpoch.sort(key=operator.itemgetter(1))
#         topKeyEpoch = [itemCurrEpoch[-(i+1)][0] for i in xrange(g.NUM_BIN)]
      keyInCache = g.cache.binInCache.keys()
      topCacheEffect = allCacheEffect = hitRatioEpoch = 0.0
      topKeyInts = set(topKeyEpoch).intersection(set(keyInCache))
      topCacheEffect = float(len(topKeyInts)) / len(topKeyEpoch) * 100
      allKeyInts = set(allKeyEpoch).intersection(set(keyInCache))
      allCacheEffect = float(len(allKeyInts)) / len(topKeyEpoch) * 100
      hitRatioEpoch = float(g.wl[0].numHitEpoch) / g.wl[0].numIOEpoch * 100
      with open(os.path.join(g.dirPath, '%s-StatByEpoch-%dmin-%dMB' % (g.dirName, g.REPLACE_EPOCH/60, g.FLASH_SIZE)), 'a') as source:
         source.write('%d\t%d\t%d\t%d\t%d\t%.2f\t%d\t%d\t%d\t%.2f\t%d\t%d\t%.2f\t%r\n' % (epoch*g.REPLACE_EPOCH/60, g.wl[0].numIOEpoch, g.wl[0].numReadEpoch, g.wl[0].numWriteEpoch, g.wl[0].numHitEpoch, hitRatioEpoch, len(keyInCache), len(allKeyEpoch), len(allKeyInts), allCacheEffect, len(topKeyEpoch), len(topKeyInts), topCacheEffect, g.spikeFilter))
   else:
      for i in xrange(g.numWL):
         if g.wl[i].numIOEpoch == 0:
            with open(os.path.join(g.dirPath, 'global-%s-StatByEpoch-%dfile-%dmin-%dMB' % (g.wl[i].fname, g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE)), 'a') as source:
               source.write('%d\t0\t0\t0\t0\t0.0\t%d\t0\t0\t0.0\t0\t0\t0.0\tFalse\n' % (epoch*g.REPLACE_EPOCH/60, len(g.cache.binInCache)))
         else:
            allKeyEpoch = g.wl[i].binCurrPop.keys()
            keyInCache = g.cache.binInCache.keys()
            allKeyInts = set(allKeyEpoch).intersection(set(keyInCache))
            allCacheEffect = float(len(allKeyInts)) / len(allKeyEpoch) * 100
            hitRatioEpoch = float(g.wl[i].numHitEpoch) / g.wl[i].numIOEpoch * 100
            with open(os.path.join(g.dirPath, 'global-%s-StatByEpoch-%dfile-%dmin-%dMB' % (g.wl[i].fname, g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE)), 'a') as source:
               source.write('%d\t%d\t%d\t%d\t%d\t%.2f\t%d\t%d\t%d\t%.2f\t%r\n' % (epoch*g.REPLACE_EPOCH/60, g.wl[i].numIOEpoch, g.wl[i].numReadEpoch, g.wl[i].numWriteEpoch, g.wl[i].numHitEpoch, hitRatioEpoch, len(keyInCache), len(allKeyEpoch), len(allKeyInts), allCacheEffect, g.spikeFilter))


def GetFlashShare(epoch, gap):
   shares = [0.0 for i in xrange(g.numWL)]
   shareSum = [0.0 for i in xrange(g.numWL)]
   for key in g.cache.binInCache:
      key = key & 0xF
      assert 0 <= key < g.numWL
      shares[key] += 1
   sum = 0.0
   for i in xrange(g.numWL):
      sum += float(shares[i]) / g.NUM_BIN * 100
      shareSum[i] = sum
   with open(os.path.join(g.dirPath, 'flashshare-%dfile-%dmin-%dMB' % (g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE)), 'a') as source:
      for i in xrange(gap):
         source.write('%d\t' % ((epoch+i)*g.REPLACE_EPOCH/60))
         for j in xrange(g.numWL):
            source.write('%.3f\t' % shareSum[j])
         source.write('\n')


def PopStatCurrEpoch(startBinID, binNum, n):
   """
   Bin popularity statistic in each epoch.
   """
   for i in xrange(binNum):
      binID = startBinID + i
      binID = (binID << 4) + n
      if binID in g.wl[n].binCurrPop:
         g.wl[n].binCurrPop[binID] += 1 / float(binNum)
#         g.wl[n].binCurrPop[binID] += 1
      else:
         g.wl[n].binCurrPop[binID] = 1 / float(binNum)
#         g.wl[n].binCurrPop[binID] = 1


def PopRecordByEpoch():
   """
   Update bin's popularity records of history epochs.
   Each bin maintains a list to record the history
   popularity for passed epochs. The length of list
   is equal to the number of history epochs need to
   be recorded.
   """
   # merge all the dict(s) of workloads to a global bin popularity dict
   g.glbBinCurrPop = copy.deepcopy(g.wl[0].binCurrPop)
   for i in xrange(1, g.numWL):
      g.glbBinCurrPop.update(g.wl[i].binCurrPop)

   keyCurrEpoch = g.glbBinCurrPop.keys()
   keyOldEpochs = g.glbBinOldPop.keys()

   keyInts = set(keyCurrEpoch).intersection(set(keyOldEpochs))  #key overlap
   keyCurrEpochDiff = set(keyCurrEpoch).difference(keyInts)   #keyCurrEpoch remainder
   keyOldEpochsDiff = set(keyOldEpochs).difference(keyInts)   #keyOldEpochs remainder

   #there is access for this bin in last epoch
   for key in keyInts:
      if len(g.glbBinOldPop[key]) == g.numOldEpoch:
         del g.glbBinOldPop[key][0]
      g.glbBinOldPop[key].append(g.glbBinCurrPop[key])

   #first access for this bin
   for key in keyCurrEpochDiff:
      assert key not in g.glbBinOldPop
      g.glbBinOldPop[key] = [g.glbBinCurrPop[key]]

   #no access for this bin in last epoch
   for key in keyOldEpochsDiff:
      if len(g.glbBinOldPop[key]) == g.numOldEpoch:
         del g.glbBinOldPop[key][0]
      g.glbBinOldPop[key].append(0.0)


def PopPredNextEpoch():
   """
   Predict bin(s) should be cached in the next epoch based on predicted popularity.
   //bin popularity = access num in last epoch * reaccess probability in an epoch granularity.
   bin popularity = access number in the last epoch.
   """
   if len(g.glbBinCurrPop) <= g.NUM_BIN:
      g.glbBinNextPop = copy.deepcopy(g.glbBinCurrPop)
   else:
      heapByValue = heapq.nlargest(g.NUM_BIN, g.glbBinCurrPop.iteritems(), key=operator.itemgetter(1))
      g.glbBinNextPop = dict(heapByValue)
#      items = [[key, g.glbBinCurrPop[key]] for key in g.glbBinCurrPop]
#      items.sort(key=operator.itemgetter(1))
#      for i in xrange(g.NUM_BIN):
#         g.glbBinNextPop[items[-1*(i+1)][0]] = items[-1*(i+1)][1]


class Cache:
   """
   Cache Simulator
   """
   def __init__(self):
      self.binInCache = dict()
      self.numHit = 0   # number of cache hit
      self.numIO = 0    # number of I/O used for cache hit calculation after cache warm
      self.numRead = 0
      self.numWrite = 0

   #Check if the data within bin is cached
   def CheckHit(self, binID):
      if binID in self.binInCache:
         return True
      else:
         return False

   #Flush cached bins by migrating out/in
   def FlushBin(self):
      keyNextEpoch = g.glbBinNextPop.keys()
      keyInCache = self.binInCache.keys()

      keyInts = set(keyInCache).intersection(keyNextEpoch)
      keyInCacheDiff = set(keyInCache).difference(keyInts)
      keyNextEpochDiff = set(keyNextEpoch).difference(keyInts)

      numEvict = len(keyNextEpochDiff) - (g.NUM_BIN - len(keyInCache))
      if 0 < numEvict < len(keyInCacheDiff):
         items = []
         for key in keyInCacheDiff:     #calculate popularity
            pop = 0.0
            for i in xrange(len(g.glbBinOldPop[key])):
               pop += g.epochWeight[i] * g.glbBinOldPop[key][-1*(i+1)]
            items.append([key, pop])
         items = heapq.nsmallest(numEvict, items, key=operator.itemgetter(1))
         for i in items:    #migrate out
            del self.binInCache[i[0]]
#         items.sort(key=operator.itemgetter(1))
#         for i in xrange(numEvict):
#            del self.binInCache[items[i][0]]
      elif numEvict == len(keyInCacheDiff):
         for key in keyInCacheDiff:     #migrate out
            del self.binInCache[key]
      else:
         assert numEvict <= 0

      #migrate in
      for key in keyNextEpochDiff:
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


def PrintSummary():
   """
   Print results of program execution. This is called at the
   end of the program run to provide a summary of what settings
   were used and the resulting hit ratio.
   """
   print '|--------------------------------------------|'
   if g.numWL == 1:
      print '|    Input file:', g.wl[0].inFile
   else:
      print '|    Input files: ', g.numWL
   print '|    Flash size: %dMB' % (g.FLASH_SIZE)
   print '|    Cache hit ratio: %.4f%%' % (float(g.cache.numHit) / g.cache.numIO * 100)
   print '|--------------------------------------------|'

   if g.numWL == 1:
      outFile = open(os.path.join(g.dirPath, '%s-stat-%dmin-%dMB' % (g.dirName, g.REPLACE_EPOCH/60, g.FLASH_SIZE)), 'a')
      outFile.write('Input file: %s\n' % g.wl[0].inFile)
      outFile.write('Flash size: %d(MB)\n' % (g.FLASH_SIZE))
      outFile.write('Time length: %.4f(hour)\n' % (g.wl[0].timeLength))
      outFile.write('Number of I/Os: %d\n' % (g.cache.numIO))
      outFile.write('Number of Read: %d\n' % (g.cache.numRead))
      outFile.write('Number of Write: %d\n' % (g.cache.numWrite))
      outFile.write('Cache hit ratio: %.4f%%\n' % (float(g.cache.numHit) / g.cache.numIO * 100))
      outFile.write('\n')
      outFile.close()
   else:
      outFile = open(os.path.join(g.dirPath, 'global-stat-%dfile-%dmin-%dMB' % (g.numWL, g.REPLACE_EPOCH, g.FLASH_SIZE)), 'a')
      outFile.write('Flash size: %d(MB)\n' % g.FLASH_SIZE)
      outFile.write('Number of I/Os: %d\n' % g.cache.numIO)
      outFile.write('Number of Read: %d\n' % g.cache.numRead)
      outFile.write('Number of Write: %d\n' % g.cache.numWrite)
      outFile.write('Cache hit ratio: %.4f%%\n' % (float(g.cache.numHit) / g.cache.numIO * 100))
      outFile.write('Input files:\n')
      for i in xrange(g.numWL):
         outFile.write('%s:\t%d\t%d\t%d\t%.4f%%\n ' % (g.wl[i].inFile, g.wl[i].numIO, g.wl[i].numRead, g.wl[i].numWrite, (float(g.wl[i].numHit)/g.wl[i].numIO*100)))
      outFile.write('\n')
      outFile.close()


if __name__ == "__main__":
   main()
