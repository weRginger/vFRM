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
   numOldEpoch = 8     # number of history epochs in record
   epochWeight = [float(numOldEpoch-i)/numOldEpoch for i in xrange(numOldEpoch)]

   glbPolicy = 0        # global flash policy ID
   NUM_SHARED_BIN = 0   # number of bin shared by all workloads
   pubFlashQue = {}

   enSpkFlt = None     # flag of enable/disable spike filter module

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
      self.numBin = 0      # minimal number of bins assigned to this workload
      self.prvFlashQue = {}

      self.numIO = 0       # number I/O in workload
      self.numRead = 0
      self.numWrite = 0
      self.numIOFlash = 0     # number of I/O bypassed flash
      self.numHit = 0
      self.numReadFlash = 0
      self.numWriteFlash = 0
      self.numIOEpoch = 0     # number of I/O in an epoch
      self.numHitEpoch = 0
      self.numReadEpoch= 0
      self.numWriteEpoch = 0

      self.enSpkFlt = False   # flag of enable/disable spike filter module
      self.inSpike = False    #True: workload is currently within spike period
      self.filterRecords = 6     # data recording in number of epochs for spike filter
      self.numReadRecords = deque([])    # number of Read I/Os in recorded epochs
      self.hitRatioRecords = deque([])    # hit ratio in recorded epochs
      self.accessBinRecords = deque([])   # number of accessed bins in recorded epochs
      self.numReadSpikeRecords = deque()
      self.hitRatioSpikeRecords = deque()
      self.accessBinSpikeRecords = deque()


def Usage():
   print 'USAGE'
   print '\t%s [OPTIONS] <flash size(MB)> <trace files>\n' % (os.path.basename(sys.argv[0]))
   print 'OPTOIONS'
   print '\t-h, --help'
   print '\t\tPrint a usage message briefly summarizing the command-line options, then exit.'
   print '\t-e NUM, --epoch=NUM'
   print '\t\tFlash flush interval in NUM seconds.\n\t\tDefault is %d seconds.' % g.REPLACE_EPOCH
   print '\t-g NUM, --global=NUM'
   print '\t\tThe NUM-th global flash policy.\n\t\tDefault is global-%d policy.' % g.glbPolicy
   print '\t-s NUM, --spike-filter=NUM'
   print '\t\tEnable spike filter module for each workload.'
   print '\t\tFor example, \'-s 1010\' means enable spike filter for the 1st & 3rd workloads.'
   print '\n'
   sys.exit(1)


def main():
   # Check for arguments
   try:
      opts, args = getopt.getopt(sys.argv[1:], "he:g:s:", ["help", "epoch=", "global=", "spike-filter="])
   except getopt.GetoptError:
      Usage()
   if len(args) < 2:
      Usage()
   else:
      g.FLASH_SIZE = int(args[0])
      g.numWL = len(args) - 1;
      g.wl = [Workload() for i in xrange(g.numWL)]
   for opt, arg in opts:
      if opt in ("-h", "--help"):
         Usage()
      elif opt in ("-e", "--epoch"):
         g.REPLACE_EPOCH = long(arg)
      elif opt in ("-g", "--global"):
         g.glbPolicy = int(arg)
         assert g.glbPolicy == 0 or g.glbPolicy == 1
      elif opt in ("-s", "--spike-filter"):
         g.enSpkFlt = str(arg)
         if len(g.enSpkFlt) != g.numWL:
            print 'The bits in \'-s\' flag does not match the number of traces.'
            Usage()
      else:
         Usage()
   if g.numWL == 1:
      g.glbPolicy = 0
      g.enSpkFlt = None

   g.NUM_BIN = g.FLASH_SIZE * 2048 / g.BIN_SIZE
   g.NUM_SHARED_BIN = g.NUM_BIN
   g.cache = Cache()    # set instance of Cache class

   for i in xrange(g.numWL):
      g.wl[i].inFile = args[i+1]
      fp = os.path.abspath(args[i+1])
      fh, ft = os.path.split(fp)
      g.wl[i].fname = os.path.splitext(ft)[0]
      g.wl[i].numBin = int(g.NUM_BIN / g.numWL / 2)
      g.NUM_SHARED_BIN -= g.wl[i].numBin
      if g.enSpkFlt is not None and int(g.enSpkFlt[i]) == 1:
         g.wl[i].enSpkFlt = True

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
         WorkloadStat(curWL)
         if curEpoch * g.REPLACE_EPOCH > g.WARMUP:
            flag = CheckCacheHit(startBinID, binNum, curWL)  # check cache hit
            WorkloadStatInFlash(curWL, flag)
      else:
         numGap = g.wl[curWL].ioTime / g.REPLACE_EPOCH - curEpoch + 1
#         strEpoch = curEpoch * g.REPLACE_EPOCH
#         endEpoch = (curEpoch + numGap) * g.REPLACE_EPOCH

         StatByEpoch(curEpoch, numGap)
         CheckSpikeFilter()

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

   StatByEpoch(curEpoch, 1)
   ClearStatCurrEpoch()
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


def CheckSpikeFilter():
   for i in xrange(g.numWL):
      if not g.wl[i].enSpkFlt:
         continue
      if g.wl[i].numIOEpoch == 0:
         g.wl[i].inSpike = False
         continue
      # initialize metrics
      numRead = g.wl[i].numReadEpoch
      if numRead == 0:
         numRead = 1
      hitRatio = float(g.wl[i].numHitEpoch) / g.wl[i].numIOEpoch * 100
      if hitRatio == 0.0:
         hitRatio = 0.01
      accessBin = len(g.wl[i].binCurrPop)

      filterAccessBin = False
      filterHitRatio = False
      filterNumRead = False

      if not g.wl[i].inSpike:
         # spike filter for metrix of number of Read I/Os
         if len(g.wl[i].numReadRecords) == g.wl[i].filterRecords:
            mean, sd, cv = StandardDeviation(g.wl[i].numReadRecords)
            ret = mean + sd*(1-cv)
            if numRead > ret and numRead/mean > 100:
               filterNumRead = True
         # spike filter for metrix of hit ratio
         if len(g.wl[i].hitRatioRecords) == g.wl[i].filterRecords:
            mean, sd, cv = StandardDeviation(g.wl[i].hitRatioRecords)
            ret = mean - sd*(1-cv)
            if hitRatio < ret and mean/hitRatio > 2.5:
               filterHitRatio = True
         # spike filter for metrix of number of accessed bins
         if len(g.wl[i].accessBinRecords) == g.wl[i].filterRecords:
            mean, sd, cv = StandardDeviation(g.wl[i].accessBinRecords)
            ret = mean + sd*(1-cv)
            if accessBin > ret and accessBin/mean > 10:
               filterAccessBin = True
         # overall spike filter check
         if filterNumRead and filterHitRatio and filterAccessBin:
            g.wl[i].inSpike = True
            g.wl[i].numReadSpikeRecords = deque([numRead])
            g.wl[i].hitRatioSpikeRecords = deque([hitRatio])
            g.wl[i].accessBinSpikeRecords = deque([accessBin])
         else:
            if len(g.wl[i].numReadRecords) == g.wl[i].filterRecords:
               assert len(g.wl[i].hitRatioRecords) == len(g.wl[i].accessBinRecords) == g.wl[i].filterRecords
               g.wl[i].numReadRecords.popleft()
               g.wl[i].hitRatioRecords.popleft()
               g.wl[i].accessBinRecords.popleft()
            g.wl[i].numReadRecords.append(numRead)
            g.wl[i].hitRatioRecords.append(hitRatio)
            g.wl[i].accessBinRecords.append(accessBin)
      else:    #g.inSpike = True
         # spike filter for metrix of number of Read I/Os
         mean, sd, cv = StandardDeviation(g.wl[i].numReadSpikeRecords)
         ret = mean - sd*(1-cv)
         if numRead < ret and mean/numRead > 100:
            filterNumRead = True
         # spike filter for metrix of hit ratio
         mean, sd, cv = StandardDeviation(g.wl[i].hitRatioSpikeRecords)
         ret = mean + sd*(1-cv)
         if hitRatio > ret and hitRatio/mean > 2.5:
            filterHitRatio = True
         # spike filter for metrix of number of accessed bins
         mean, sd, cv = StandardDeviation(g.wl[i].accessBinSpikeRecords)
         ret = mean - sd*(1-cv)
         if accessBin < ret and mean/accessBin > 10:
            filterAccessBin = True
         # overall spike filter check
         if filterNumRead and filterHitRatio and filterAccessBin:
            g.wl[i].inSpike = False
            if len(g.wl[i].numReadRecords) == g.wl[i].filterRecords:
               assert len(g.wl[i].hitRatioRecords) == len(g.wl[i].accessBinRecords) == g.wl[i].filterRecords
               g.wl[i].numReadRecords.popleft()
               g.wl[i].hitRatioRecords.popleft()
               g.wl[i].accessBinRecords.popleft()
            g.wl[i].numReadRecords.append(numRead)
            g.wl[i].hitRatioRecords.append(hitRatio)
            g.wl[i].accessBinRecords.append(accessBin)
         else:
            if len(g.wl[i].numReadSpikeRecords) == g.wl[i].filterRecords:
               assert len(g.wl[i].hitRatioSpikeRecords) == len(g.wl[i].accessBinSpikeRecords) == g.wl[i].filterRecords
               g.wl[i].numReadSpikeRecords.popleft()
               g.wl[i].hitRatioSpikeRecords.popleft()
               g.wl[i].accessBinSpikeRecords.popleft()
            g.wl[i].numReadSpikeRecords.append(numRead)
            g.wl[i].hitRatioSpikeRecords.append(hitRatio)
            g.wl[i].accessBinSpikeRecords.append(accessBin)


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


def WorkloadStat(n):
   g.wl[n].numIO += 1
   g.wl[n].numIOEpoch += 1
   if g.wl[n].ioRW == 'W':
      g.wl[n].numWrite += 1
      g.wl[n].numWriteEpoch += 1
   else:
      g.wl[n].numRead += 1
      g.wl[n].numReadEpoch += 1

def WorkloadStatInFlash(n, flag):
   g.wl[n].numIOFlash += 1
   if g.wl[n].ioRW == 'W':
      g.wl[n].numWriteFlash += 1
   else:
      g.wl[n].numReadFlash += 1
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
      spk = g.enSpkFlt is not None and 1 or 0
      for i in xrange(g.numWL):
         obj = os.path.join(g.dirPath, '%s-StatByEpoch-%dfile-%dmin-%dMB-glb%d-spk%d' % (g.wl[i].fname, g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.glbPolicy, spk))
         if os.path.isfile(obj):
            os.unlink(obj)
      obj = os.path.join(g.dirPath, 'AllStatByEpoch-%dfile-%dmin-%dMB-glb%d-spk%d' % (g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.glbPolicy, spk))
      if os.path.isfile(obj):
         os.unlink(obj)
      obj = os.path.join(g.dirPath, 'flashshare-%dfile-%dmin-%dMB-glb%d-spk%d' % (g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.glbPolicy, spk))
      if os.path.isfile(obj):
         os.unlink(obj)


def StatByEpoch(epoch, gap):
   """
   Calculate the effectiveness of cached bins.
   Effectiveness means the percentage of cached bins which are the bins in optimal case.
   """
   if g.numWL == 1:
      keyInCache = g.cache.binInCache.keys()
      keyInWL = g.wl[0].binCurrPop.keys()
      keyInst = set(keyInWL).intersection(set(keyInCache))
      hitRatio= float(g.wl[0].numHitEpoch) / g.wl[0].numIOEpoch * 100
      with open(os.path.join(g.dirPath, '%s-StatByEpoch-%dmin-%dMB' % (g.dirName, g.REPLACE_EPOCH/60, g.FLASH_SIZE)), 'a') as source:
         source.write('%d\t%d\t%d\t%d\t%d\t%.2f\t%d\t%d\t%d\t%r\n' % (epoch*g.REPLACE_EPOCH/60, g.wl[0].numIOEpoch, g.wl[0].numReadEpoch, g.wl[0].numWriteEpoch, g.wl[0].numHitEpoch, hitRatio, len(keyInCache), len(keyInst), len(keyInWL), g.wl[0].inSpike))
         for j in xrange(gap-1):
            source.write('%d\t0\t0\t0\t0\t0.0\t%d\t0\t0\t%r\n' % ((epoch+1+j)*g.REPLACE_EPOCH/60, len(keyInCache), g.wl[0].inSpike))
   else:
      shares = [0 for i in xrange(g.numWL)]
      sharePct = [0.0 for i in xrange(g.numWL)]
      for key in g.cache.binInCache:
         key = key & 0xF
         assert 0 <= key < g.numWL
         shares[key] += 1
      for i in xrange(g.numWL):
         sharePct[i] = float(shares[i]) / g.NUM_BIN * 100

      pubQueShare = [0 for i in xrange(g.numWL)]
      pubQuePct = [0.0 for i in xrange(g.numWL)]
      for key in g.pubFlashQue:
         key = key & 0xF
         pubQueShare[key] += 1
      for i in xrange(g.numWL):
         pubQuePct[i] = float(pubQueShare[i]) / g.NUM_SHARED_BIN * 100

      spk = g.enSpkFlt is not None and 1 or 0
      with open(os.path.join(g.dirPath, 'AllStatByEpoch-%dfile-%dmin-%dMB-glb%d-spk%d' % (g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.glbPolicy, spk)), 'a') as source:
         source.write('Time\t%d\n' % (epoch*g.REPLACE_EPOCH/60))
         keyInCache = g.cache.binInCache.keys()
         for i in xrange(g.numWL):
            keyInWL = g.wl[i].binCurrPop.keys()
            keyInst = set(keyInWL).intersection(set(keyInCache))
            hitRatio = 0.0
            if g.wl[i].numIOEpoch != 0:
               hitRatio = float(g.wl[i].numHitEpoch) / g.wl[i].numIOEpoch * 100
            with open(os.path.join(g.dirPath, '%s-StatByEpoch-%dfile-%dmin-%dMB-glb%d-spk%d' % (g.wl[i].fname, g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.glbPolicy, spk)), 'a') as subSource:
               subSource.write('%d\t%d\t%d\t%d\t%d\t%.2f\t%d\t%d\t%.2f\t%d\t%d\t%.2f\t%d\t%d\t%r\n' % (epoch*g.REPLACE_EPOCH/60, g.wl[i].numIOEpoch, g.wl[i].numReadEpoch, g.wl[i].numWriteEpoch, g.wl[i].numHitEpoch, hitRatio, len(keyInCache), shares[i], sharePct[i], len(g.wl[i].prvFlashQue), pubQueShare[i], pubQuePct[i], len(keyInst), len(keyInWL), g.wl[i].inSpike))
               for j in xrange(gap-1):
                  subSource.write('%d\t0\t0\t0\t0\t0.0\t%d\t%d\t%.2f\t%d\t%d\t%.2f\t0\t0\t%r\n' % ((epoch+1+j)*g.REPLACE_EPOCH/60, len(keyInCache), shares[i], sharePct[i], len(g.wl[i].prvFlashQue), pubQueShare[i], pubQuePct[i], g.wl[i].inSpike))
            source.write('%s\t%d\t%.2f\t%d\t%d\t%.2f\t%d\t%d\t%d\t%d\n' % (g.wl[i].fname, shares[i], sharePct[i], len(g.wl[i].prvFlashQue), pubQueShare[i], pubQuePct[i], len(keyInst), len(keyInWL), g.wl[i].numHitEpoch, g.wl[i].numIOEpoch))
         source.write('\n')

         for j in xrange(gap-1):    # gaps for all the workloads
            source.write('Time\t%d\n' % ((epoch+1+j)*g.REPLACE_EPOCH/60))
            for i in xrange(g.numWL):
               source.write('%s\t%d\t%.2f\t%d\t%d\t%.2f\t0\t0\t0\t0\n' % (g.wl[i].fname, shares[i], sharePct[i], len(g.wl[i].prvFlashQue), pubQueShare[i], pubQuePct[i]))
            source.write('\n')


def GetFlashShare(epoch, gap):
   shares = [0.0 for i in xrange(g.numWL)]
   sharePct = [0.0 for i in xrange(g.numWL)]
   shareSum = [0.0 for i in xrange(g.numWL)]
   for key in g.cache.binInCache:
      key = key & 0xF
      assert 0 <= key < g.numWL
      shares[key] += 1
   sum = 0.0
   for i in xrange(g.numWL):
      sharePct[i] = float(shares[i]) / g.NUM_BIN * 100
      sum += sharePct[i]
      shareSum[i] = sum
   spk = g.enSpkFlt is not None and 1 or 0
   with open(os.path.join(g.dirPath, 'flashshare-%dfile-%dmin-%dMB-glb%d-spk%d' % (g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.glbPolicy, spk)), 'a') as source:
      for i in xrange(gap):
         source.write('%d\t' % ((epoch+i)*g.REPLACE_EPOCH/60))
         for j in xrange(g.numWL):
            source.write('%.3f\t' % sharePct[j])
         source.write('\n')


def PopStatCurrEpoch(startBinID, binNum, n):
   """
   Bin popularity statistic in each epoch.
   """
   for i in xrange(binNum):
      binID = startBinID + i
      binID = (binID << 4) + n
#      g.wl[n].binCurrPop[binID] = g.wl[n].binCurrPop.get(binID, 0) + 1/float(binNum)
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
   for i in xrange(g.numWL):
      if not g.wl[i].inSpike:
         g.glbBinCurrPop.update(g.wl[i].binCurrPop)

   keyCurrEpoch = g.glbBinCurrPop.keys()
   keyOldEpochs = g.glbBinOldPop.keys()

   keyInst = set(keyCurrEpoch).intersection(set(keyOldEpochs))  #key overlap
   keyCurrEpochDiff = set(keyCurrEpoch).difference(keyInst)   #keyCurrEpoch remainder
   keyOldEpochsDiff = set(keyOldEpochs).difference(keyInst)   #keyOldEpochs remainder

   #there is access for this bin in last epoch
   for key in keyInst:
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
   if g.glbPolicy == 0:
      if len(g.glbBinCurrPop) < g.NUM_BIN:
         keyNextEpoch = g.glbBinCurrPop.keys()
         keyInCache = g.cache.binInCache.keys()

         keyInst = set(keyInCache).intersection(keyNextEpoch)
         keyInCacheDiff = set(keyInCache).difference(keyInst)
         keyNextEpochDiff = set(keyNextEpoch).difference(keyInst)

         g.glbBinNextPop = copy.deepcopy(g.cache.binInCache)
         numEvict = len(keyNextEpochDiff) - (g.NUM_BIN - len(keyInCache))
         if 0 < numEvict < len(keyInCacheDiff):
            items = []
            for key in keyInCacheDiff:
               pop = 0.0
               for i in xrange(len(g.glbBinOldPop[key])):
                  pop += g.epochWeight[i] * g.glbBinOldPop[key][-1*(i+1)]
               items.append([key, pop])
            items = heapq.nsmallest(numEvict, items, key=operator.itemgetter(1))
            # migrate out
            for i in items:
               del g.glbBinNextPop[i[0]]
         else:
            assert numEvict <= 0
         # migrate in
         for key in keyNextEpochDiff:
            g.glbBinNextPop[key] = True
         assert len(g.glbBinNextPop) <= g.NUM_BIN
      elif len(g.glbBinCurrPop) == g.NUM_BIN:
         g.glbBinNextPop = copy.deepcopy(g.glbBinCurrPop)
      else:
         heapByValue = heapq.nlargest(g.NUM_BIN, g.glbBinCurrPop.iteritems(), key=operator.itemgetter(1))
         g.glbBinNextPop = dict(heapByValue)
   elif g.glbPolicy == 1:
      # get extraBin & evictBin dicts and update g.wl[i].prvFlashQue
      extraBin = {}
      evictBin = {}
      for i in xrange(g.numWL):
         keyInWL = []
         if not g.wl[i].inSpike:
            keyInWL = g.wl[i].binCurrPop.keys()
         keyInQue = g.wl[i].prvFlashQue.keys()
         keyInst = set(keyInWL).intersection(set(keyInQue))
         keyWLDiff = set(keyInWL).difference(keyInst)
         keyQueDiff = set(keyInQue).difference(keyInst)

         if len(keyInWL) < g.wl[i].numBin:
            evict = len(keyWLDiff) - (g.wl[i].numBin - len(g.wl[i].prvFlashQue))
            assert evict < len(keyQueDiff)
            if evict > 0:
               items = []
               for key in keyQueDiff:
                  pop = 0.0
                  for j in xrange(len(g.glbBinOldPop[key])):
                     pop += g.epochWeight[j] * g.glbBinOldPop[key][-1*(j+1)]
                  items.append([key, pop])
               smallItems = heapq.nsmallest(evict, items, key=operator.itemgetter(1))
               evictBin.update(dict(smallItems))
               for key in smallItems:
                  del g.wl[i].prvFlashQue[key[0]]
            for key in keyWLDiff:
               g.wl[i].prvFlashQue[key] = g.wl[i].binCurrPop[key]
            assert len(g.wl[i].prvFlashQue) <= g.wl[i].numBin
         elif len(keyInWL) == g.wl[i].numBin:
            for key in keyQueDiff:
               evictBin[key] = g.wl[i].prvFlashQue[key]
            g.wl[i].prvFlashQue.clear()
            g.wl[i].prvFlashQue.update(g.wl[i].binCurrPop)
         else:
            for key in keyQueDiff:
               evictBin[key] = g.wl[i].prvFlashQue[key]
            items = [[key, g.wl[i].binCurrPop[key]] for key in g.wl[i].binCurrPop]
            items.sort(key=operator.itemgetter(1))
            g.wl[i].prvFlashQue = dict(items[-1*g.wl[i].numBin:])
            extraBin.update(dict(items[:-1*g.wl[i].numBin]))

      # update g.pubFlashQue
      if len(extraBin) > g.NUM_SHARED_BIN:
         items = [[key, g.glbBinCurrPop[key]] for key in extraBin]
         largeItems = sorted(items, key=operator.itemgetter(1))[-1*g.NUM_SHARED_BIN:]
         g.pubFlashQue = dict(largeItems)
      elif len(extraBin) == g.NUM_SHARED_BIN:
         g.pubFlashQue = copy.deepcopy(extraBin)
      elif len(extraBin) + len(evictBin) > g.NUM_SHARED_BIN:
         g.pubFlashQue = copy.deepcopy(extraBin)
         select = g.NUM_SHARED_BIN - len(extraBin)
         items = []
         for key in evictBin:
            pop = 0.0
            for j in xrange(len(g.glbBinOldPop[key])):
               pop += g.epochWeight[j] * g.glbBinOldPop[key][-1*(j+1)]
            items.append([key, pop])
         largeItems = heapq.nlargest(select, items, key=operator.itemgetter(1))
         g.pubFlashQue.update(dict(largeItems))
      elif len(extraBin) + len(evictBin) == g.NUM_SHARED_BIN:
         g.pubFlashQue = copy.deepcopy(extraBin)
         g.pubFlashQue.update(evictBin)
      else:    # len(extraBin) + len(evictBin) < g.NUM_SHARED_BIN
         keyShareQue = g.pubFlashQue.keys()
         keyGlbWL = g.glbBinCurrPop.keys()
         keyShareInst = set(keyShareQue).intersection(set(keyGlbWL))
         for key in keyShareInst:
            del g.pubFlashQue[key]
         evict = len(extraBin) + len(evictBin) - (g.NUM_SHARED_BIN - len(g.pubFlashQue))
         if evict > 0:
            items = []
            for key in g.pubFlashQue:
               pop = 0.0
               for j in xrange(len(g.glbBinOldPop[key])):
                  pop += g.epochWeight[j] * g.glbBinOldPop[key][-1*(j+1)]
               items.append([key, pop])
            smallItems = heapq.nsmallest(evict, items, key=operator.itemgetter(1))
            for key in smallItems:
               del g.pubFlashQue[key[0]]
         g.pubFlashQue.update(extraBin)
         g.pubFlashQue.update(evictBin)

      # update g.glbBinNextPop
      for i in xrange(g.numWL):
         g.glbBinNextPop.update(g.wl[i].prvFlashQue)
      g.glbBinNextPop.update(g.pubFlashQue)
      assert len(g.glbBinNextPop) <= g.NUM_BIN
   else:
      print 'ERROR: g.glbPolicy is wrong.'
      sys.exit(1)


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
      self.binInCache.clear()
      self.binInCache = copy.deepcopy(g.glbBinNextPop)


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
      spk = g.enSpkFlt is not None and 1 or 0
      outFile = open(os.path.join(g.dirPath, 'Summary-%dfile-%dmin-%dMB-glb%d-spk%d' % (g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.glbPolicy, spk)), 'a')
      outFile.write('Flash size: %d(MB)\n' % g.FLASH_SIZE)
      outFile.write('Number of I/Os: %d\n' % g.cache.numIO)
      outFile.write('Number of Read: %d\n' % g.cache.numRead)
      outFile.write('Number of Write: %d\n' % g.cache.numWrite)
      outFile.write('Cache hit ratio: %.4f%%\n' % (float(g.cache.numHit) / g.cache.numIO * 100))
      outFile.write('Input files:\n')
      for i in xrange(g.numWL):
         outFile.write('%s:\t%d\t%d\t%d\t%.4f%%\n' % (g.wl[i].inFile, g.wl[i].numIOFlash, g.wl[i].numReadFlash, g.wl[i].numWriteFlash, (float(g.wl[i].numHit)/g.wl[i].numIOFlash*100)))
      outFile.write('\n')
      outFile.close()


if __name__ == "__main__":
   main()
