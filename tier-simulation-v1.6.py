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
   numWl = 1
   wl = []       # workload: I/O trace from input files
   dirName = None    # input-file name without extention (.cvs)
   dirPath = None    # folder path for tier simulation results

   glbBinCurrPop = dict()   # popularity statistic for bin access in current epoch
   glbBinOldPop = dict()    # popularity records for bins in each old epochs
   glbBinNextPop = dict()   # predict popularity of each bin for the next epoch
   numOldEpoch = 8     # number of history epochs in record
   epochWeight = [float(numOldEpoch-i)/numOldEpoch for i in xrange(numOldEpoch)]

   glbPolicy = 0        # global flash policy ID
   NUM_PUBLIC_RECENT_BIN = 0   # total number of bin shared by all workloads in recent-zone
   NUM_PUBLIC_FREQUENT_BIN = 0   # total number of bin shared by all workloads in frequent-zone
                                 # in global-2: the total num of hot bins in the accumulated popularity histogram
   NUM_PRIVATE_BIN = 0  # the sum of the private reserved bins of all workloads
   pubRectQue = {}      # public queue for the shared bins of all workloads in recent-zone
   pubFreqQue = {}      # public queue for the shared bins of all workloads in frequent-zone
   glbBinCount = {}     # access counting for each global bin
   MAX_BIN_COUNT = 1000000000    # max access number for each global bin

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
      self.numPrvBin = 0      # minimal number of bins assigned to this workload
      self.prvQue = {}

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
   print '\n'
   sys.exit(1)


def main():
   # Check for arguments
   try:
      opts, args = getopt.getopt(sys.argv[1:], "he:g:", ["help", "epoch=", "global="])
   except getopt.GetoptError:
      Usage()
   if len(args) < 2:
      Usage()
   else:
      g.FLASH_SIZE = int(args[0])
      g.numWl = len(args) - 1;
      assert 0 < g.numWl <= 0xF
      g.wl = [Workload() for i in xrange(g.numWl)]
   for opt, arg in opts:
      if opt in ("-h", "--help"):
         Usage()
      elif opt in ("-e", "--epoch"):
         g.REPLACE_EPOCH = long(arg)
      elif opt in ("-g", "--global"):
         g.glbPolicy = int(arg)
         assert g.glbPolicy == 0 or g.glbPolicy == 1 or g.glbPolicy == 2
      else:
         Usage()

   if g.numWl == 1:
      g.glbPolicy = 0

   g.NUM_BIN = g.FLASH_SIZE * 2048 / g.BIN_SIZE
   g.cache = Cache()    # set instance of Cache class

   for i in xrange(g.numWl):
      g.wl[i].inFile = args[i+1]
      fp = os.path.abspath(args[i+1])
      fh, ft = os.path.split(fp)
      g.wl[i].fname = os.path.splitext(ft)[0]
      if g.glbPolicy == 1:
         g.wl[i].numPrvBin = int(g.NUM_BIN / g.numWl / 2)
         g.NUM_PRIVATE_BIN += g.wl[i].numPrvBin

   if g.glbPolicy == 2:
      g.NUM_PUBLIC_FREQUENT_BIN = g.NUM_BIN / 2
   g.NUM_PUBLIC_RECENT_BIN = g.NUM_BIN - g.NUM_PRIVATE_BIN - g.NUM_PUBLIC_FREQUENT_BIN
   assert g.NUM_PUBLIC_RECENT_BIN > 0

   CreateFolder()

   # Initialize trace references
   for i in xrange(g.numWl):
      [g.wl[i].ioTime, g.wl[i].ioRW, g.wl[i].ioLBN, g.wl[i].ioSize] = GetTraceReference(g.wl[i].inFile, g.wl[i].curLine)
      if g.wl[i].ioLBN == 0:
         print 'Error: cannot get trace from the %dth trace file: %s' % (i, g.wl[i].inFile)
         sys.exit(1)
      g.wl[i].curLine += 1
      g.wl[i].timeOffset = g.wl[i].ioTime   # calculate time offset for the starting time of each trace
      g.wl[i].ioTime = 0
   # Get the latest trace
   curWl = GetNextWorkload()
   curEpoch = 1   # the number of flush epoch
   breakWls = 0    # flag to break the "while", all the workloads have been done.

   # Main loop
   while True:
      # running progress record
      if g.wl[curWl].curLine % 10000 == 0:
         print '%s:\t%d' % (g.wl[curWl].inFile, g.wl[curWl].curLine)

      startBinID = g.wl[curWl].ioLBN / g.BIN_SIZE
      binNum = (g.wl[curWl].ioLBN + g.wl[curWl].ioSize - 1) / g.BIN_SIZE - startBinID + 1

      if g.wl[curWl].ioTime < curEpoch * g.REPLACE_EPOCH:
         PopStatCurrEpoch(startBinID, binNum, curWl)
         WorkloadStat(curWl)
         if curEpoch * g.REPLACE_EPOCH > g.WARMUP:
            flag = CheckCacheHit(startBinID, binNum, curWl)  # check cache hit
            WorkloadStatInFlash(curWl, flag)
      else:
         numGap = g.wl[curWl].ioTime / g.REPLACE_EPOCH - curEpoch + 1
#         strEpoch = curEpoch * g.REPLACE_EPOCH
#         endEpoch = (curEpoch + numGap) * g.REPLACE_EPOCH

         StatByEpoch(curEpoch, numGap)

         PopRecordByEpoch()
         PopPredNextEpoch()
         g.cache.FlushBin()  # update cached bins
         if g.numWl > 1:
            GetFlashShare(curEpoch, numGap)
         ClearStatCurrEpoch()

         curEpoch += numGap
#         g.wl[curWl].curLine -= 1
         continue

      # Get trace reference
      [g.wl[curWl].ioTime, g.wl[curWl].ioRW, g.wl[curWl].ioLBN, g.wl[curWl].ioSize] = GetTraceReference(g.wl[curWl].inFile, g.wl[curWl].curLine)
      g.wl[curWl].ioTime -= g.wl[curWl].timeOffset
      if g.wl[curWl].ioLBN == 0:
         g.wl[curWl].lastLine = True
         breakWls += 1
         g.wl[curWl].timeLength = (GetTraceReference(g.wl[curWl].inFile, g.wl[curWl].curLine-1)[0] - g.wl[curWl].timeOffset) / float(3600)
         if breakWls == g.numWl:
            break
      g.wl[curWl].curLine += 1
      curWl = GetNextWorkload()
   #while end

   StatByEpoch(curEpoch, 1)
   ClearStatCurrEpoch()
   # Display results of program run
   PrintSummary()

def GetNextWorkload():
   j = None
   for i in xrange(g.numWl):
      if not g.wl[i].lastLine:
         minTime = g.wl[i].ioTime
         j = i
         break
   assert j is not None
   if (j+1) < g.numWl:
      for i in range(j+1, g.numWl):
         if not g.wl[i].lastLine and g.wl[i].ioTime < minTime:
            minTime = g.wl[i].ioTime
            j = i
   return j

def ClearStatCurrEpoch():
   g.glbBinCurrPop.clear()    # clear bin popularity records in last epoch
   g.glbBinNextPop.clear()
   for i in xrange(g.numWl):
      g.wl[i].binCurrPop.clear()
      g.wl[i].numIOEpoch = g.wl[i].numHitEpoch = g.wl[i].numWriteEpoch = g.wl[i].numReadEpoch = 0


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
   if g.numWl == 1:
      fp = os.path.abspath(g.wl[0].inFile)
      fh, ft = os.path.split(fp)
      g.dirName = os.path.splitext(ft)[0]
   else:
      g.dirName = 'globalflash'
   g.dirPath = os.path.join(fileHead, 'cachesim-tier-' + g.dirName)
   if not os.path.isdir(g.dirPath):
      os.makedirs(g.dirPath)

   if g.numWl == 1:
      obj = os.path.join(g.dirPath, '%s-StatByEpoch-%dmin-%dMB' % (g.dirName, g.REPLACE_EPOCH/60, g.FLASH_SIZE))
      if os.path.isfile(obj):
         os.unlink(obj)
   else:
      for i in xrange(g.numWl):
         obj = os.path.join(g.dirPath, '%s-StatByEpoch-%dfile-%dmin-%dMB-glb%d' % (g.wl[i].fname, g.numWl, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.glbPolicy))
         if os.path.isfile(obj):
            os.unlink(obj)
      obj = os.path.join(g.dirPath, 'AllStatByEpoch-%dfile-%dmin-%dMB-glb%d' % (g.numWl, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.glbPolicy))
      if os.path.isfile(obj):
         os.unlink(obj)
      obj = os.path.join(g.dirPath, 'flashshare-%dfile-%dmin-%dMB-glb%d' % (g.numWl, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.glbPolicy))
      if os.path.isfile(obj):
         os.unlink(obj)


def StatByEpoch(epoch, gap):
   """
   Calculate the effectiveness of cached bins.
   Effectiveness means the percentage of cached bins which are the bins in optimal case.
   """
   if g.numWl == 1:
      keyInCache = g.cache.binInCache.keys()
      keyInWl = g.wl[0].binCurrPop.keys()
      keyInst = set(keyInWl).intersection(set(keyInCache))
      hitRatio= float(g.wl[0].numHitEpoch) / g.wl[0].numIOEpoch * 100
      with open(os.path.join(g.dirPath, '%s-StatByEpoch-%dmin-%dMB' % (g.dirName, g.REPLACE_EPOCH/60, g.FLASH_SIZE)), 'a') as source:
         source.write('%d\t%d\t%d\t%d\t%d\t%.2f\t%d\t%d\t%d\n' % (epoch*g.REPLACE_EPOCH/60, g.wl[0].numIOEpoch, g.wl[0].numReadEpoch, g.wl[0].numWriteEpoch, g.wl[0].numHitEpoch, hitRatio, len(keyInCache), len(keyInst), len(keyInWl)))
         for j in xrange(gap-1):
            source.write('%d\t0\t0\t0\t0\t0.0\t%d\t0\t0\n' % ((epoch+1+j)*g.REPLACE_EPOCH/60, len(keyInCache)))
   #for the cases with multiple workloads
   else:
      cacheShare = [0 for i in xrange(g.numWl)]
      cachePct = [0.0 for i in xrange(g.numWl)]
      for key in g.cache.binInCache:
         key = key & 0xF
         assert 0 <= key < g.numWl
         cacheShare[key] += 1
      for i in xrange(g.numWl):
         cachePct[i] = float(cacheShare[i]) / g.NUM_BIN * 100

      if g.glbPolicy == 1 or g.glbPolicy == 2:
         rectShare = [0 for i in xrange(g.numWl)]
         rectPct = [0.0 for i in xrange(g.numWl)]
         for key in g.pubRectQue:
            key = key & 0xF
            rectShare[key] += 1
         for i in xrange(g.numWl):
            rectPct[i] = float(rectShare[i]) / g.NUM_PUBLIC_RECENT_BIN * 100

      if g.glbPolicy == 2:
         freqShare = [0 for i in xrange(g.numWl)]
         freqPct = [0.0 for i in xrange(g.numWl)]
         for key in g.pubFreqQue:
            key = key & 0xF
            freqShare[key] += 1
         for i in xrange(g.numWl):
            freqPct[i] = float(freqShare[i]) / g.NUM_PUBLIC_FREQUENT_BIN * 100

      with open(os.path.join(g.dirPath, 'AllStatByEpoch-%dfile-%dmin-%dMB-glb%d' % (g.numWl, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.glbPolicy)), 'a') as source:
         keyInCache = g.cache.binInCache.keys()
         source.write('Time = %d\tCache = %d\n' % (epoch*g.REPLACE_EPOCH/60, len(keyInCache)))
         #---------------------------------------
         for i in xrange(g.numWl):
            keyInWl = g.wl[i].binCurrPop.keys()
            keyInst = set(keyInWl).intersection(set(keyInCache))
            hitRatio = 0.0
            if g.wl[i].numIOEpoch != 0:
               hitRatio = float(g.wl[i].numHitEpoch) / g.wl[i].numIOEpoch * 100
            #---------------------------------------
            with open(os.path.join(g.dirPath, '%s-StatByEpoch-%dfile-%dmin-%dMB-glb%d' % (g.wl[i].fname, g.numWl, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.glbPolicy)), 'a') as subSource:
               if g.glbPolicy == 0:
                  subSource.write('%d\t%d\t%d\t%d\t%d\t%.2f\t%d\t%d\t%d\t%d\t%.2f\n' % (epoch*g.REPLACE_EPOCH/60, g.wl[i].numIOEpoch, g.wl[i].numReadEpoch, g.wl[i].numWriteEpoch, g.wl[i].numHitEpoch, hitRatio, len(keyInCache), len(keyInWl), len(keyInst), cacheShare[i], cachePct[i]))
                  for j in xrange(gap-1):
                     subSource.write('%d\t0\t0\t0\t0\t0.0\t%d\t0\t0\t%d\t%.2f\n' % ((epoch+1+j)*g.REPLACE_EPOCH/60, len(keyInCache), cacheShare[i], cachePct[i]))
               elif g.glbPolicy == 1:
                  subSource.write('%d\t%d\t%d\t%d\t%d\t%.2f\t%d\t%d\t%d\t%d\t%.2f\t%d\t%d\t%.2f\n' % (epoch*g.REPLACE_EPOCH/60, g.wl[i].numIOEpoch, g.wl[i].numReadEpoch, g.wl[i].numWriteEpoch, g.wl[i].numHitEpoch, hitRatio, len(keyInCache), len(keyInWl), len(keyInst), cacheShare[i], cachePct[i], len(g.wl[i].prvQue), rectShare[i], rectPct[i]))
                  for j in xrange(gap-1):
                     subSource.write('%d\t0\t0\t0\t0\t0.0\t%d\t0\t0\t%d\t%.2f\t%d\t%d\t%.2f\n' % ((epoch+1+j)*g.REPLACE_EPOCH/60, len(keyInCache), cacheShare[i], cachePct[i], len(g.wl[i].prvQue), rectShare[i], rectPct[i]))
               elif g.glbPolicy == 2:
                  subSource.write('%d\t%d\t%d\t%d\t%d\t%.2f\t%d\t%d\t%d\t%d\t%.2f\t%d\t%.2f\t%d\t%.2f\n' % (epoch*g.REPLACE_EPOCH/60, g.wl[i].numIOEpoch, g.wl[i].numReadEpoch, g.wl[i].numWriteEpoch, g.wl[i].numHitEpoch, hitRatio, len(keyInCache), len(keyInWl), len(keyInst), cacheShare[i], cachePct[i], freqShare[i], freqPct[i], rectShare[i], rectPct[i]))
                  for j in xrange(gap-1):
                     subSource.write('%d\t0\t0\t0\t0\t0.0\t%d\t0\t0\t%d\t%.2f\t%d\t%.2f\t%d\t%.2f\n' % ((epoch+1+j)*g.REPLACE_EPOCH/60, len(keyInCache), cacheShare[i], cachePct[i], freqShare[i], freqPct[i], rectShare[i], rectPct[i]))
            #---------------------------------------
            if g.glbPolicy == 0:
               source.write('%s\t%d\t%d\t%d\t%.2f\t%d\t%d\t%.2f\n' % (g.wl[i].fname, len(keyInWl), len(keyInst), cacheShare[i], cachePct[i], g.wl[i].numIOEpoch, g.wl[i].numHitEpoch, hitRatio))
            elif g.glbPolicy == 1:
               source.write('%s\t%d\t%d\t%d\t%.2f\t%d\t%d\t%.2f\t%d\t%d\t%.2f\n' % (g.wl[i].fname, len(keyInWl), len(keyInst), cacheShare[i], cachePct[i], len(g.wl[i].prvQue), rectShare[i], rectPct[i], g.wl[i].numIOEpoch, g.wl[i].numHitEpoch, hitRatio))
            elif g.glbPolicy == 2:
               source.write('%s\t%d\t%d\t%d\t%.2f\t%d\t%.2f\t%d\t%.2f\t%d\t%d\t%.2f\n' % (g.wl[i].fname, len(keyInWl), len(keyInst), cacheShare[i], cachePct[i], freqShare[i], freqPct[i], rectShare[i], rectPct[i], g.wl[i].numIOEpoch, g.wl[i].numHitEpoch, hitRatio))
         source.write('\n')
         #---------------------------------------
         for j in xrange(gap-1):    # gaps for all the workloads
            source.write('Time = %d\tCache = %d\n' % ((epoch+1+j)*g.REPLACE_EPOCH/60, len(keyInCache)))
            for i in xrange(g.numWl):
               if g.glbPolicy == 0:
                  source.write('%s\t0\t0\t%d\t%.2f\t0\t0\t0.0\n' % (g.wl[i].fname, cacheShare[i], cachePct[i]))
               elif g.glbPolicy == 1:
                  source.write('%s\t0\t0\t%d\t%.2f\t%d\t%d\t%.2f\t0\t0\t0.0\n' % (g.wl[i].fname, cacheShare[i], cachePct[i], len(g.wl[i].prvQue), rectShare[i], rectPct[i]))
               elif g.glbPolicy == 2:
                  source.write('%s\t0\t0\t%d\t%.2f\t%d\t%.2f\t%d\t%.2f\t0\t0\t0.0\n' % (g.wl[i].fname, cacheShare[i], cachePct[i], freqShare[i], freqPct[i], rectShare[i], rectPct[i]))
            source.write('\n')


def GetFlashShare(epoch, gap):
   shares = [0.0 for i in xrange(g.numWl)]
   sharePct = [0.0 for i in xrange(g.numWl)]
   shareSum = [0.0 for i in xrange(g.numWl)]
   for key in g.cache.binInCache:
      key = key & 0xF
      assert 0 <= key < g.numWl
      shares[key] += 1
   sum = 0.0
   for i in xrange(g.numWl):
      sharePct[i] = float(shares[i]) / g.NUM_BIN * 100
      sum += sharePct[i]
      shareSum[i] = sum
   with open(os.path.join(g.dirPath, 'flashshare-%dfile-%dmin-%dMB-glb%d' % (g.numWl, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.glbPolicy)), 'a') as source:
      for i in xrange(gap):
         source.write('%d\t' % ((epoch+i)*g.REPLACE_EPOCH/60))
         for j in xrange(g.numWl):
            source.write('%.3f\t' % sharePct[j])
         source.write('\n')


def PopStatCurrEpoch(startBinID, binNum, n):
   """
   Bin popularity statistic in each epoch.
   """
   for i in xrange(binNum):
      binID = startBinID + i
      binID = (binID << 4) + n
      g.wl[n].binCurrPop[binID] = g.wl[n].binCurrPop.get(binID, 0) + 1
#      if binID in g.wl[n].binCurrPop:
#         g.wl[n].binCurrPop[binID] += 1 / float(binNum)
##         g.wl[n].binCurrPop[binID] += 1
#      else:
#         g.wl[n].binCurrPop[binID] = 1 / float(binNum)
##         g.wl[n].binCurrPop[binID] = 1

def ThrottleGlbBinCount():
   throttle = False
   for key in g.glbBinCount:
      if g.glbBinCount[key] >= g.MAX_BIN_COUNT:
         throttle = True
         break
   if throttle:
      for key in g.glbBinCount:
         g.glbBinCount[key] = int(math.log10(g.glbBinCount[key]))

def PopRecordByEpoch():
   """
   Update bin's popularity records of history epochs.
   Each bin maintains a list to record the history
   popularity for passed epochs. The length of list
   is equal to the number of history epochs need to
   be recorded.
   """
   # merge all the dict(s) of workloads to a global bin popularity dict
   for i in xrange(g.numWl):
      g.glbBinCurrPop.update(g.wl[i].binCurrPop)

   for key in g.glbBinCurrPop:
      g.glbBinCount[key] = g.glbBinCount.get(key, 0) + g.glbBinCurrPop[key]
   ThrottleGlbBinCount()

   keyCurrEpoch = g.glbBinCurrPop.keys()
   keyOldEpochs = g.glbBinOldPop.keys()

   keyInst = set(keyCurrEpoch).intersection(set(keyOldEpochs))  #key overlap
   keyCurrEpochDiff = set(keyCurrEpoch).difference(keyInst)   #keyCurrEpoch remainder
   keyOldEpochsDiff = set(keyOldEpochs).difference(keyInst)   #keyOldEpochs remainder

   # there is access for this bin in last epoch
   for key in keyInst:
      if len(g.glbBinOldPop[key]) == g.numOldEpoch:
         del g.glbBinOldPop[key][0]
      g.glbBinOldPop[key].append(g.glbBinCurrPop[key])

   # first access for this bin
   for key in keyCurrEpochDiff:
      assert key not in g.glbBinOldPop
      g.glbBinOldPop[key] = [g.glbBinCurrPop[key]]

   # no access for this bin in last epoch
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
            items = GetNSmallest(numEvict, keyInCacheDiff)
            # migrate out
            for key in items:
               del g.glbBinNextPop[key]
         else:
            assert numEvict <= 0
         # migrate in
         for key in keyNextEpochDiff:
            g.glbBinNextPop[key] = True
         assert len(g.glbBinNextPop) <= g.NUM_BIN
      elif len(g.glbBinCurrPop) == g.NUM_BIN:
         g.glbBinNextPop = dict.fromkeys(g.glbBinCurrPop.keys(), True)
      else:
         items = heapq.nlargest(g.NUM_BIN, g.glbBinCurrPop.iteritems(), key=operator.itemgetter(1))
         g.glbBinNextPop = dict.fromkeys(map(lambda i: i[0], items), True)

   elif g.glbPolicy == 1:
      # get extraBin & evictBin dicts and update g.wl[i].prvQue
      extraBin = []
      evictBin = []
      for i in xrange(g.numWl):
         keyWl = g.wl[i].binCurrPop.keys()
         keyPrv = g.wl[i].prvQue.keys()
         keyInst = set(keyWl).intersection(set(keyPrv))
         keyWlDiff = set(keyWl).difference(keyInst)
         keyPrvDiff = set(keyPrv).difference(keyInst)

         if len(keyWl) < g.wl[i].numPrvBin:
            numEvict = len(keyWlDiff) - (g.wl[i].numPrvBin - len(g.wl[i].prvQue))
            assert numEvict < len(keyPrvDiff)
            if numEvict > 0:
               items = GetNSmallest(numEvict, keyPrvDiff)
               evictBin.extend(items)
               for key in items:
                  del g.wl[i].prvQue[key]
            for key in keyWlDiff:
               g.wl[i].prvQue[key] = True
            assert len(g.wl[i].prvQue) <= g.wl[i].numPrvBin
         elif len(keyWl) == g.wl[i].numPrvBin:
            evictBin.extend(keyPrvDiff)
            g.wl[i].prvQue = dict.fromkeys(keyWl, True)
         else:
            evictBin.extend(keyPrvDiff)
            items = [[key, g.wl[i].binCurrPop[key]] for key in g.wl[i].binCurrPop]
            items.sort(key=operator.itemgetter(1))
            items = [key[0] for key in items]
            g.wl[i].prvQue = dict.fromkeys(items[-1*g.wl[i].numPrvBin:], True)
            extraBin.extend(items[:-1*g.wl[i].numPrvBin])

      # update g.pubRectQue
      if len(extraBin) > g.NUM_PUBLIC_RECENT_BIN:
#         items = [[key, g.glbBinCurrPop[key]] for key in extraBin]
#         items.sort(key=operator.itemgetter(1))
#         items = items[-1*g.NUM_PUBLIC_RECENT_BIN:]
#         items = [key[0] for key in items]
         items = GetNLargest(g.NUM_PUBLIC_RECENT_BIN, extraBin)
         g.pubRectQue = dict.fromkeys(items, True)
      elif len(extraBin) == g.NUM_PUBLIC_RECENT_BIN:
         g.pubRectQue = dict.fromkeys(extraBin, True)
      elif len(extraBin) + len(evictBin) > g.NUM_PUBLIC_RECENT_BIN:
         numAdmin = g.NUM_PUBLIC_RECENT_BIN - len(extraBin)
         items = GetNLargest(numAdmin, evictBin)
         items.extend(extraBin)
         g.pubRectQue = dict.fromkeys(items, True)
      elif len(extraBin) + len(evictBin) == g.NUM_PUBLIC_RECENT_BIN:
         evictBin.extend(extraBin)
         g.pubRectQue = dict.fromkeys(evictBin, True)
      elif 0 < len(extraBin) + len(evictBin) < g.NUM_PUBLIC_RECENT_BIN:
         keyRect = g.pubRectQue.keys()
         keyWl = g.glbBinCurrPop.keys()
         keyInst = set(keyRect).intersection(set(keyWl))
         for key in keyInst:
            del g.pubRectQue[key]
         numEvict = len(extraBin) + len(evictBin) - (g.NUM_PUBLIC_RECENT_BIN - len(g.pubRectQue))
         if numEvict > 0:
            items = GetNSmallest(numEvict, g.pubRectQue.keys())
            for key in items:
               del g.pubRectQue[key]
         evictBin.extend(extraBin)
         g.pubRectQue.update(dict.fromkeys(evictBin, True))
         if numEvict > 0:
            assert len(g.pubRectQue) == g.NUM_PUBLIC_RECENT_BIN
      else:
         assert len(extraBin) + len(evictBin) == 0

      # update g.glbBinNextPop
      for i in xrange(g.numWl):
         g.glbBinNextPop.update(g.wl[i].prvQue)
      g.glbBinNextPop.update(g.pubRectQue)
      assert len(g.glbBinNextPop) <= g.NUM_BIN

   elif g.glbPolicy == 2:
      # update g.pubFreqQue
      if len(g.glbBinCount) <= g.NUM_PUBLIC_FREQUENT_BIN:
         g.pubFreqQue = dict.fromkeys(g.glbBinCount.keys(), True)
      elif len(g.pubFreqQue) < g.NUM_PUBLIC_FREQUENT_BIN:
         items = heapq.nlargest(g.NUM_PUBLIC_FREQUENT_BIN, g.glbBinCount.iteritems(), key=operator.itemgetter(1))
         items = [key[0] for key in items]
         g.pubFreqQue = dict.fromkeys(items, True)
      else:
         items = heapq.nlargest(g.NUM_PUBLIC_FREQUENT_BIN, g.glbBinCount.iteritems(), key=operator.itemgetter(1))
         items = [key[0] for key in items]
         keyInst = set(items).intersection(set(g.pubFreqQue.keys()))
         diffRatio = (g.NUM_PUBLIC_FREQUENT_BIN - len(keyInst)) / float(g.NUM_PUBLIC_FREQUENT_BIN)
         if diffRatio >= 0.2:
            g.pubFreqQue = dict.fromkeys(items, True)

      # update g.pubRectQue
      if g.NUM_PUBLIC_FREQUENT_BIN < len(g.glbBinCount) <= g.NUM_BIN:
         g.pubRectQue.clear()
         for key in g.glbBinCount:
            if key not in g.pubFreqQue:
               g.pubRectQue[key] = True
      elif len(g.glbBinCount) > g.NUM_BIN:
         for key in g.pubFreqQue:
            if key in g.pubRectQue:
               del g.pubRectQue[key]
            if key in g.glbBinCurrPop:
               del g.glbBinCurrPop[key]
         if len(g.glbBinCurrPop) > g.NUM_PUBLIC_RECENT_BIN:
            items = heapq.nlargest(g.NUM_PUBLIC_RECENT_BIN, g.glbBinCurrPop.iteritems(), key=operator.itemgetter(1))
            items = [key[0] for key in items]
            g.pubRectQue = dict.fromkeys(items, True)
         elif len(g.glbBinCurrPop) == g.NUM_PUBLIC_RECENT_BIN:
            g.pubRectQue = dict.fromkeys(g.glbBinCurrPop.keys(), True)
         else:    # len(g.glbBinCurrPop) < g.NUM_PUBLIC_RECENT_BIN:
            keyWl = g.glbBinCurrPop.keys()
            keyRect = g.pubRectQue.keys()
            keyInst = set(keyWl).intersection(set(keyRect))
            keyWlDiff = set(keyWl).difference(keyInst)
            keyRectDiff = set(keyRect).difference(keyInst)
            numEvict = len(keyWlDiff) - (g.NUM_PUBLIC_RECENT_BIN - len(keyRect))
            if numEvict > 0:
               items = GetNSmallest(numEvict, keyRectDiff)
               for key in items:
                  del g.pubRectQue[key]
            g.pubRectQue.update(dict.fromkeys(keyWlDiff, True))
            if numEvict > 0:
               assert len(g.pubRectQue) + len(g.pubFreqQue) == g.NUM_BIN
      else:    # len(g.glbBinCount) <= g.NUM_PUBLIC_FREQUENT_BIN
         assert len(g.pubRectQue) == 0 and len(g.pubFreqQue) == len(g.glbBinCount)

      # update g.glbBinNextPop
      g.glbBinNextPop.update(g.pubFreqQue)
      g.glbBinNextPop.update(g.pubRectQue)
      assert len(g.glbBinNextPop) <= g.NUM_BIN

   else:
      print 'ERROR: g.glbPolicy is wrong.'
      sys.exit(1)


def GetNSmallest(n, keyList):
   items = []
   for key in keyList:
      pop = 0.0
      for i in xrange(len(g.glbBinOldPop[key])):
         pop += g.epochWeight[i] * g.glbBinOldPop[key][-1*(i+1)]
      items.append([key, pop])
   items = heapq.nsmallest(n, items, key=operator.itemgetter(1))
   return map(lambda x: x[0], items)


def GetNLargest(n, keyList):
   items = []
   for key in keyList:
      pop = 0.0
      for i in xrange(len(g.glbBinOldPop[key])):
         pop += g.epochWeight[i] * g.glbBinOldPop[key][-1*(i+1)]
      items.append([key, pop])
   items = heapq.nlargest(n, items, key=operator.itemgetter(1))
   return map(lambda x: x[0], items)


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
   if g.numWl == 1:
      print '|    Input file:', g.wl[0].inFile
   else:
      print '|    Input files: ', g.numWl
   print '|    Flash size: %dMB' % (g.FLASH_SIZE)
   print '|    Cache hit ratio: %.4f%%' % (float(g.cache.numHit) / g.cache.numIO * 100)
   print '|--------------------------------------------|'

   if g.numWl == 1:
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
      outFile = open(os.path.join(g.dirPath, 'Summary-%dfile-%dmin-%dMB-glb%d' % (g.numWl, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.glbPolicy)), 'a')
      outFile.write('Flash size: %d(MB)\n' % g.FLASH_SIZE)
      outFile.write('Number of I/Os: %d\n' % g.cache.numIO)
      outFile.write('Number of Read: %d\n' % g.cache.numRead)
      outFile.write('Number of Write: %d\n' % g.cache.numWrite)
      outFile.write('Cache hit ratio: %.4f%%\n' % (float(g.cache.numHit) / g.cache.numIO * 100))
      outFile.write('Input files:\n')
      for i in xrange(g.numWl):
         outFile.write('%s:\t%d\t%d\t%d\t%.4f%%\n' % (g.wl[i].inFile, g.wl[i].numIOFlash, g.wl[i].numReadFlash, g.wl[i].numWriteFlash, (float(g.wl[i].numHit)/g.wl[i].numIOFlash*100)))
      outFile.write('\n')
      outFile.close()


if __name__ == "__main__":
   main()
