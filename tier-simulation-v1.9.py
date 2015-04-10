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
   FLASH_SIZE = 0    #flash size in MB (1MB = 2048 Blocks)
   BIN_SIZE = 2048   #bin size in blocks
   NUM_BIN = 0       #number of bin in flash
   REPLACE_EPOCH = 300     #bin replace interval in seconds
   WARMUP = 86400    #warmup time in second, the traces in the first number of seconds are used for flash training & warm-up

   cache = None         #instance of Cache class
   shadowCache = None   #instance of shadow cache for global policy (-g3)
   numWL = 1
   wl = []           #workload: I/O trace from input files
   dirName = None    #input-file name without extention (.cvs)
   dirPath = None    #folder path for tier simulation results
   outPrefix = ''    #prefix for the output files

   glbBinCurPop = dict()   #popularity statistic for bin access in current epoch
   glbBinOldPop = dict()    #popularity records for bins in each old epochs
   glbBinNextPop = dict()   #predict popularity of each bin for the next epoch
   numOldEpoch = 8     #number of history epochs in record
   linearWeight = [float(numOldEpoch - i) / numOldEpoch for i in xrange(numOldEpoch)]   #weight of history epochs in linear distribution
   expWeight = [1.0 / pow(2, i + 1) for i in xrange(numOldEpoch)]     #weight of history epochs in exponential distribution
   prvWeight = [1.0 / numOldEpoch for i in xrange(numOldEpoch)]      #sum is 1, evenly distribution weight for priviate queue
   pubWeight = [2.0 / 3, 1.0 / 3]      #sum is 1, only count the recent 2 epoch for public queue

   glbPolicy = 0        #global flash management policy ID
   NUM_PUBLIC_BIN = 0   #total number of bins publicly shared by all workloads for recency
   NUM_PRIVATE_BIN = 0  #total number of bins reserved by all workloads for private reservation or frequency
   numPubBin = 0
   numprvBin = 0
   pubQue = {}          #public queue for the shared bins of all workloads used for recency
   prvQue = {}          #private queue reserved for all workloads userd for private reservation or frequency
   glbBinCount = {}     #access counting for each global bin
   MAX_BIN_COUNT = 1000000000    #max access number for each global bin

   writePolicy = 0      #numeric code for write policy
   wrtAbbr = None        #abbreviation of write policy
   IO_SIZE = 256        #IO size in blocks
   NUM_IO_PER_BIN = BIN_SIZE / IO_SIZE
   #I/O cost for exchange data between SSD & MD
   numAdmin = 0         #number of cache admission (migrate data from MD to SSD)
   numEvict = 0         #number of cache eviction (migrate data from SSD out to MD)
   numBypass = 0        #number of both Read/Write I/O bypass cache and directly access MD
   numSsdRead = 0
   numSsdWrite = 0
   numMdRead = 0
   numMdWrite = 0


class Workload:
   def __init__(self):
      self.inFile = None     #input file path for this workload class
      self.fname = None      #input file name (not abspath)
      self.curLine = 1       #current line number in trace file
      self.lastLine = False  #flag for reading the last trace in each input file
      self.ioRW = 0       #reference for Read/Write flag
      self.ioLBN = 0      #reference for I/O logical block number (LBN)
      self.ioSize = 0     #reference for I/O size, number of blocks
      self.ioTime = 0     #reference for I/O access time
      self.timeOffset = 0   #time offset for each trace starting from 0
      self.timeLength = 0   #total time duration for the whole trace in this workload
      self.binCurPop = dict()   #dict for popularity statistic of bins in current epoch
      self.numPrvBin = 0      #minimal number of bins assigned to this workload
      self.prvQue = {}

      self.numIO = 0       #number I/O in workload
      self.numRead = 0
      self.numWrite = 0
      self.numIOFlash = 0     #number of I/O bypassed flash
      self.numHit = 0
      self.numReadFlash = 0
      self.numWriteFlash = 0
      self.numIOEpoch = 0     #number of I/O in an epoch
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
   print '\t\tThe NUM-th global flash management policy (g0~g4).\n\t\tDefault is global-%d policy.' % g.glbPolicy
   print '\t-w NUM, --write=NUM'
   print '\t\tThe flash write policy. \'0\' is Write Back and \'1\' is Write Through.\n\t\tDefault is Write Back.'
   print '\t-p PrefixName, --prefix=PrefixName'
   print '\t\tThe prefix for the output files.\n\t\tWithout specification, the default file name is created.'
   print '\n'
   sys.exit(1)


def main():
   #Check for arguments
   try:
      opts, args = getopt.getopt(sys.argv[1:], "he:g:w:p:", ["help", "epoch=", "global=", "write=", "prefix="])
   except getopt.GetoptERROR:
      Usage()
   if len(args) < 2:
      Usage()
   else:
      g.FLASH_SIZE = int(args[0])
      g.numWL = len(args) - 1;
      assert 0 < g.numWL <= 0xF
      g.wl = [Workload() for i in xrange(g.numWL)]
   for opt, arg in opts:
      if opt in ("-h", "--help"):
         Usage()
      elif opt in ("-e", "--epoch"):
         g.REPLACE_EPOCH = long(arg)
      elif opt in ("-g", "--global"):
         g.glbPolicy = int(arg)
         assert isinstance(g.glbPolicy, int) and 0 <= g.glbPolicy <= 4
      elif opt in ("-w", "--write"):
         g.writePolicy = int(arg)
         assert g.writePolicy == 0 or g.writePolicy == 1
      elif opt in ("-p", "--prefix"):
         g.outPrefix = arg + '-'
      else:
         Usage()

   if g.writePolicy == 0:
      g.wrtAbbr = 'WB'
   elif g.writePolicy == 1:
      g.wrtAbbr = 'WT'

   g.NUM_BIN = g.FLASH_SIZE * 2048 / g.BIN_SIZE
   g.cache = Cache()    #set instance of Cache class

   for i in xrange(g.numWL):
      g.wl[i].inFile = args[i+1]
      fp = os.path.abspath(args[i+1])
      fh, ft = os.path.split(fp)
      g.wl[i].fname = os.path.splitext(ft)[0]

   if g.glbPolicy == 1:
      g.shadowCache = ShadowCache()    #set instance of shadow cache class
   elif g.glbPolicy == 2:
      g.NUM_PRIVATE_BIN = int(0.5 * g.NUM_BIN)
      g.NUM_PUBLIC_BIN = g.NUM_BIN - g.NUM_PRIVATE_BIN
      for i in xrange(g.numWL):
         g.wl[i].numPrvBin = int(g.NUM_PRIVATE_BIN / g.numWL)
   elif g.glbPolicy == 3:
      g.NUM_PRIVATE_BIN = int(0.9 * g.NUM_BIN)
      g.NUM_PUBLIC_BIN = g.NUM_BIN - g.NUM_PRIVATE_BIN
   elif g.glbPolicy == 4:
      g.numPrvBin = g.numPubBin = int(0.5 * g.NUM_BIN)
   else:
      print "ERROR: g.glbPolicy is wrong."
      sys.exit(1)

   CreateFolder()

   #Initialize trace references
   for i in xrange(g.numWL):
      [g.wl[i].ioTime, g.wl[i].ioRW, g.wl[i].ioLBN, g.wl[i].ioSize] = GetTraceReference(g.wl[i].inFile, g.wl[i].curLine)
      if g.wl[i].ioLBN == 0:
         print 'ERROR: cannot get trace from the %dth trace file: %s' % (i, g.wl[i].inFile)
         sys.exit(1)
      g.wl[i].curLine += 1
      g.wl[i].timeOffset = g.wl[i].ioTime   #calculate time offset for the starting time of each trace
      g.wl[i].ioTime = 0
   #Get the latest trace
   curWL = GetNextWorkload()
   curEpoch = 1   #the number of flush epoch
   breakWLs = 0    #flag to break the "while", all the workloads have been done.

   #######################
   ### Main loop begin ###
   while True:
      #running progress record
      if g.wl[curWL].curLine % 100000 == 0:
         print '%s:\t%d' % (g.wl[curWL].inFile, g.wl[curWL].curLine)

      startBinID = g.wl[curWL].ioLBN / g.BIN_SIZE
      binNum = (g.wl[curWL].ioLBN + g.wl[curWL].ioSize - 1) / g.BIN_SIZE - startBinID + 1

      if g.wl[curWL].ioTime < curEpoch * g.REPLACE_EPOCH:
         PopStatCurEpoch(startBinID, binNum, curWL)
         WorkloadStat(curWL)
         if g.glbPolicy == 1:    #shadow cache update
            CheckShadowCacheHit(startBinID, binNum, curWL)
         if curEpoch * g.REPLACE_EPOCH > g.WARMUP:
            flag = CheckCacheHit(g.wl[curWL].ioLBN, g.wl[curWL].ioSize, g.wl[curWL].ioRW, curWL)  #check cache hit
            WorkloadStatInFlash(curWL, flag)
      else:
         numGap = g.wl[curWL].ioTime / g.REPLACE_EPOCH - curEpoch + 1
#         strEpoch = curEpoch * g.REPLACE_EPOCH
#         endEpoch = (curEpoch + numGap) * g.REPLACE_EPOCH

         StatByEpoch(curEpoch, numGap)

         PopRecordByEpoch()
         PopPredNextEpoch()
         g.cache.FlushBin()  #update cached bins
         if g.numWL > 1:
            GetFlashShare(curEpoch, numGap)
         ClearStatCurEpoch()

         curEpoch += numGap
#         g.wl[curWL].curLine -= 1
         continue

      #Get trace reference
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
   ### main loop end ###
   #####################

   StatByEpoch(curEpoch, 1)
   ClearStatCurEpoch()
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

def ClearStatCurEpoch():
   g.glbBinCurPop.clear()    #clear bin popularity records in last epoch
   g.glbBinNextPop.clear()
   for i in xrange(g.numWL):
      g.wl[i].binCurPop.clear()
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


def CheckShadowCacheHit(start, num, wl):
   """
   Check shadow cache hit.
   """
   for i in xrange(num):
      binID = start + i
      binID = (binID << 4) + wl
      g.shadowCache.CheckHit(binID)


def CheckCacheHit(ioLBN, ioSize, ioRW, wl):
   """
   Check cache hit.
   """
   g.cache.numIO += 1
   if ioRW == 'R':
      g.cache.numRead += 1
   else:
      g.cache.numWrite += 1

   startIO = ioLBN / g.IO_SIZE
   numIO = (ioLBN + ioSize - 1) / g.IO_SIZE - startIO + 1
   lastBin = -1
   n = 0
   flagHit = True
   cacheHit = False
   for i in xrange(numIO):
      ioID = startIO + i
      binID = ioID / g.NUM_IO_PER_BIN
      binID = (binID << 4) + wl
      if binID == lastBin:
         n += 1
      else:
         IOCost(cacheHit, lastBin, ioRW, n)
         n = 1
         lastBin = binID
         cacheHit = g.cache.CheckHit(binID)
         if not cacheHit:
            flagHit = False
   IOCost(cacheHit, lastBin, ioRW, n)
   if flagHit:
      g.cache.numHit += 1
   return flagHit


def IOCost(cacheHit, binID, ioRW, n):
   if n != 0:
      if ioRW == 'R':
         if cacheHit:
            g.numSsdRead += n
         else:    #if read miss, directly read MD and bypass flash
            g.numMdRead += n
            g.numBypass += n
      elif ioRW == 'W' and g.writePolicy == 0:
         if cacheHit:
            g.numSsdWrite += n
            g.cache.SetDirty(binID)
         else:    #in write back, if write miss, directly write to MD w/o flash update
            g.numMdWrite += n
            g.numBypass += n
      elif ioRW == 'W' and g.writePolicy == 1:
         pass
#         if cacheHit:
#            g.numEvict += 1
#         else:    #in write back, if write miss, directly write to MD w/o flash update
#            g.numBypass += 1
      else:
         print 'ERROR: wrong write policy.'
         sys.exit(1)


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
      obj = os.path.join(g.dirPath, '%sStatByEpoch-%dmin-%dMB-%s-glb%d' % (g.outPrefix, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.wrtAbbr, g.glbPolicy))
      if os.path.isfile(obj):
         os.unlink(obj)
   else:
      for i in xrange(g.numWL):
         obj = os.path.join(g.dirPath, '%sStatByEpoch-%dfile-%dmin-%dMB-glb%d-%s' % (g.outPrefix, g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.glbPolicy, g.wl[i].fname))
         if os.path.isfile(obj):
            os.unlink(obj)
      obj = os.path.join(g.dirPath, '%sStatByEpoch-%dfile-%dmin-%dMB-glb%d' % (g.outPrefix, g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.glbPolicy))
      if os.path.isfile(obj):
         os.unlink(obj)
      obj = os.path.join(g.dirPath, '%sFlashshare-%dfile-%dmin-%dMB-glb%d' % (g.outPrefix, g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.glbPolicy))
      if os.path.isfile(obj):
         os.unlink(obj)


def StatByEpoch(epoch, gap):
   """
   Calculate the effectiveness of cached bins.
   Effectiveness means the percentage of cached bins which are the bins in optimal case.
   """
   if g.numWL == 1:
      keyInCache = g.cache.binInCache.keys()
      keyInWL = g.wl[0].binCurPop.keys()
      keyInst = set(keyInWL).intersection(set(keyInCache))
      hitRatio= float(g.wl[0].numHitEpoch) / g.wl[0].numIOEpoch * 100
      with open(os.path.join(g.dirPath, '%sStatByEpoch-%dmin-%dMB-%s-glb%d' % (g.outPrefix, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.wrtAbbr, g.glbPolicy)), 'a') as source:
         source.write('%d\t%d\t%d\t%d\t%d\t%.2f\t%d\t%d\t%d\n' % (epoch*g.REPLACE_EPOCH/60, g.wl[0].numIOEpoch, g.wl[0].numReadEpoch, g.wl[0].numWriteEpoch, g.wl[0].numHitEpoch, hitRatio, len(keyInCache), len(keyInst), len(keyInWL)))
         for j in xrange(gap-1):
            source.write('%d\t0\t0\t0\t0\t0.0\t%d\t0\t0\n' % ((epoch+1+j)*g.REPLACE_EPOCH/60, len(keyInCache)))
   #for the cases with multiple workloads
   else:
      cacheShare = [0 for i in xrange(g.numWL)]
      cachePct = [0.0 for i in xrange(g.numWL)]
      for key in g.cache.binInCache:
         key = key & 0xF
         assert 0 <= key < g.numWL
         cacheShare[key] += 1
      for i in xrange(g.numWL):
         cachePct[i] = float(cacheShare[i]) / g.NUM_BIN * 100

      if g.glbPolicy == 2 or g.glbPolicy == 3:
         rectShare = [0 for i in xrange(g.numWL)]
         rectPct = [0.0 for i in xrange(g.numWL)]
         for key in g.pubQue:
            key = key & 0xF
            rectShare[key] += 1
         for i in xrange(g.numWL):
            rectPct[i] = float(rectShare[i]) / g.NUM_PUBLIC_BIN * 100

      if g.glbPolicy == 3:
         freqShare = [0 for i in xrange(g.numWL)]
         freqPct = [0.0 for i in xrange(g.numWL)]
         for key in g.prvQue:
            key = key & 0xF
            freqShare[key] += 1
         for i in xrange(g.numWL):
            freqPct[i] = float(freqShare[i]) / g.NUM_PRIVATE_BIN * 100

      with open(os.path.join(g.dirPath, '%sStatByEpoch-%dfile-%dmin-%dMB-%s-glb%d' % (g.outPrefix, g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.wrtAbbr, g.glbPolicy)), 'a') as source:
         keyInCache = g.cache.binInCache.keys()
         source.write('Time = %d\tCache = %d\n' % (epoch*g.REPLACE_EPOCH/60, len(keyInCache)))
         #---------------------------------------
         for i in xrange(g.numWL):
            keyInWL = g.wl[i].binCurPop.keys()
            keyInst = set(keyInWL).intersection(set(keyInCache))
            hitRatio = 0.0
            if g.wl[i].numIOEpoch != 0:
               hitRatio = float(g.wl[i].numHitEpoch) / g.wl[i].numIOEpoch * 100
            #---------------------------------------
            with open(os.path.join(g.dirPath, '%sStatByEpoch-%dfile-%dmin-%dMB-%s-glb%d-%s' % (g.outPrefix, g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.wrtAbbr, g.glbPolicy, g.wl[i].fname)), 'a') as subSource:
               if g.glbPolicy == 0:
                  subSource.write('%d\t%d\t%d\t%d\t%d\t%.2f\t%d\t%d\t%d\t%d\t%.2f\n' % (epoch*g.REPLACE_EPOCH/60, g.wl[i].numIOEpoch, g.wl[i].numReadEpoch, g.wl[i].numWriteEpoch, g.wl[i].numHitEpoch, hitRatio, len(keyInCache), len(keyInWL), len(keyInst), cacheShare[i], cachePct[i]))
                  for j in xrange(gap-1):
                     subSource.write('%d\t0\t0\t0\t0\t0.0\t%d\t0\t0\t%d\t%.2f\n' % ((epoch+1+j)*g.REPLACE_EPOCH/60, len(keyInCache), cacheShare[i], cachePct[i]))
               elif g.glbPolicy == 2:
                  subSource.write('%d\t%d\t%d\t%d\t%d\t%.2f\t%d\t%d\t%d\t%d\t%.2f\t%d\t%d\t%.2f\n' % (epoch*g.REPLACE_EPOCH/60, g.wl[i].numIOEpoch, g.wl[i].numReadEpoch, g.wl[i].numWriteEpoch, g.wl[i].numHitEpoch, hitRatio, len(keyInCache), len(keyInWL), len(keyInst), cacheShare[i], cachePct[i], len(g.wl[i].prvQue), rectShare[i], rectPct[i]))
                  for j in xrange(gap-1):
                     subSource.write('%d\t0\t0\t0\t0\t0.0\t%d\t0\t0\t%d\t%.2f\t%d\t%d\t%.2f\n' % ((epoch+1+j)*g.REPLACE_EPOCH/60, len(keyInCache), cacheShare[i], cachePct[i], len(g.wl[i].prvQue), rectShare[i], rectPct[i]))
               elif g.glbPolicy == 3:
                  subSource.write('%d\t%d\t%d\t%d\t%d\t%.2f\t%d\t%d\t%d\t%d\t%.2f\t%d\t%.2f\t%d\t%.2f\n' % (epoch*g.REPLACE_EPOCH/60, g.wl[i].numIOEpoch, g.wl[i].numReadEpoch, g.wl[i].numWriteEpoch, g.wl[i].numHitEpoch, hitRatio, len(keyInCache), len(keyInWL), len(keyInst), cacheShare[i], cachePct[i], freqShare[i], freqPct[i], rectShare[i], rectPct[i]))
                  for j in xrange(gap-1):
                     subSource.write('%d\t0\t0\t0\t0\t0.0\t%d\t0\t0\t%d\t%.2f\t%d\t%.2f\t%d\t%.2f\n' % ((epoch+1+j)*g.REPLACE_EPOCH/60, len(keyInCache), cacheShare[i], cachePct[i], freqShare[i], freqPct[i], rectShare[i], rectPct[i]))
               elif g.glbPolicy == 1:
                  subSource.write('%d\t%d\t%d\t%d\t%d\t%.2f\t%d\t%d\t%d\t%d\t%.2f\n' % (epoch*g.REPLACE_EPOCH/60, g.wl[i].numIOEpoch, g.wl[i].numReadEpoch, g.wl[i].numWriteEpoch, g.wl[i].numHitEpoch, hitRatio, len(keyInCache), len(keyInWL), len(keyInst), cacheShare[i], cachePct[i]))
                  for j in xrange(gap-1):
                     subSource.write('%d\t0\t0\t0\t0\t0.0\t%d\t0\t0\t%d\t%.2f\n' % ((epoch+1+j)*g.REPLACE_EPOCH/60, len(keyInCache), cacheShare[i], cachePct[i]))
            #---------------------------------------
            if g.glbPolicy == 0:
               source.write('%s\t%d\t%d\t%d\t%.2f\t%d\t%d\t%.2f\n' % (g.wl[i].fname, len(keyInWL), len(keyInst), cacheShare[i], cachePct[i], g.wl[i].numIOEpoch, g.wl[i].numHitEpoch, hitRatio))
            elif g.glbPolicy == 2:
               source.write('%s\t%d\t%d\t%d\t%.2f\t%d\t%d\t%.2f\t%d\t%d\t%.2f\n' % (g.wl[i].fname, len(keyInWL), len(keyInst), cacheShare[i], cachePct[i], len(g.wl[i].prvQue), rectShare[i], rectPct[i], g.wl[i].numIOEpoch, g.wl[i].numHitEpoch, hitRatio))
            elif g.glbPolicy == 3:
               source.write('%s\t%d\t%d\t%d\t%.2f\t%d\t%.2f\t%d\t%.2f\t%d\t%d\t%.2f\n' % (g.wl[i].fname, len(keyInWL), len(keyInst), cacheShare[i], cachePct[i], freqShare[i], freqPct[i], rectShare[i], rectPct[i], g.wl[i].numIOEpoch, g.wl[i].numHitEpoch, hitRatio))
            elif g.glbPolicy == 1:
               source.write('%s\t%d\t%d\t%d\t%.2f\t%d\t%d\t%.2f\n' % (g.wl[i].fname, len(keyInWL), len(keyInst), cacheShare[i], cachePct[i], g.wl[i].numIOEpoch, g.wl[i].numHitEpoch, hitRatio))
         source.write('\n')
         #---------------------------------------
         for j in xrange(gap-1):    #gaps for all the workloads
            source.write('Time = %d\tCache = %d\n' % ((epoch+1+j)*g.REPLACE_EPOCH/60, len(keyInCache)))
            for i in xrange(g.numWL):
               if g.glbPolicy == 0:
                  source.write('%s\t0\t0\t%d\t%.2f\t0\t0\t0.0\n' % (g.wl[i].fname, cacheShare[i], cachePct[i]))
               elif g.glbPolicy == 2:
                  source.write('%s\t0\t0\t%d\t%.2f\t%d\t%d\t%.2f\t0\t0\t0.0\n' % (g.wl[i].fname, cacheShare[i], cachePct[i], len(g.wl[i].prvQue), rectShare[i], rectPct[i]))
               elif g.glbPolicy == 3:
                  source.write('%s\t0\t0\t%d\t%.2f\t%d\t%.2f\t%d\t%.2f\t0\t0\t0.0\n' % (g.wl[i].fname, cacheShare[i], cachePct[i], freqShare[i], freqPct[i], rectShare[i], rectPct[i]))
               elif g.glbPolicy == 1:
                  source.write('%s\t0\t0\t%d\t%.2f\t0\t0\t0.0\n' % (g.wl[i].fname, cacheShare[i], cachePct[i]))
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
   with open(os.path.join(g.dirPath, '%sFlashshare-%dfile-%dmin-%dMB-%s-glb%d' % (g.outPrefix, g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.wrtAbbr, g.glbPolicy)), 'a') as source:
      for i in xrange(gap):
         source.write('%d\t' % ((epoch+i)*g.REPLACE_EPOCH/60))
         for j in xrange(g.numWL):
            source.write('%.3f\t' % sharePct[j])
         source.write('\n')


def PopStatCurEpoch(startBinID, binNum, n):
   """
   Bin popularity statistic in each epoch.
   """
   for i in xrange(binNum):
      binID = startBinID + i
      binID = (binID << 4) + n
      g.wl[n].binCurPop[binID] = g.wl[n].binCurPop.get(binID, 0) + 1
#      if binID in g.wl[n].binCurPop:
#         g.wl[n].binCurPop[binID] += 1 / float(binNum)
##         g.wl[n].binCurPop[binID] += 1
#      else:
#         g.wl[n].binCurPop[binID] = 1 / float(binNum)
##         g.wl[n].binCurPop[binID] = 1

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
   #merge all the dict(s) of workloads to a global bin popularity dict
   for i in xrange(g.numWL):
      g.glbBinCurPop.update(g.wl[i].binCurPop)

   for key in g.glbBinCurPop:
      g.glbBinCount[key] = g.glbBinCount.get(key, 0) + g.glbBinCurPop[key]
   ThrottleGlbBinCount()

   keyCurEpoch = g.glbBinCurPop.keys()
   keyOldEpochs = g.glbBinOldPop.keys()

   keyInst = set(keyCurEpoch).intersection(set(keyOldEpochs))  #key overlap
   keyCurEpochDiff = set(keyCurEpoch).difference(keyInst)   #keyCurEpoch remainder
   keyOldEpochsDiff = set(keyOldEpochs).difference(keyInst)   #keyOldEpochs remainder

   #there is access for this bin in last epoch
   for key in keyInst:
      if len(g.glbBinOldPop[key]) == g.numOldEpoch:
         del g.glbBinOldPop[key][0]
      g.glbBinOldPop[key].append(g.glbBinCurPop[key])

   #first access for this bin
   for key in keyCurEpochDiff:
      assert key not in g.glbBinOldPop
      g.glbBinOldPop[key] = [g.glbBinCurPop[key]]

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
      if len(g.glbBinCurPop) < g.NUM_BIN:
         keyNextEpoch = g.glbBinCurPop.keys()
         keyInCache = g.cache.binInCache.keys()
         keyInst = set(keyInCache).intersection(keyNextEpoch)
         keyInCacheDiff = set(keyInCache).difference(keyInst)
         keyNextEpochDiff = set(keyNextEpoch).difference(keyInst)

         g.glbBinNextPop = copy.deepcopy(g.cache.binInCache)
         numEvict = len(keyNextEpochDiff) - (g.NUM_BIN - len(keyInCache))
         if 0 < numEvict < len(keyInCacheDiff):
            items = GetNSmallest(numEvict, keyInCacheDiff, 0)
            #migrate out
            for key in items:
               del g.glbBinNextPop[key]
         else:
            assert numEvict <= 0
         #migrate in
         for key in keyNextEpochDiff:
            g.glbBinNextPop[key] = True
         assert len(g.glbBinNextPop) <= g.NUM_BIN
      elif len(g.glbBinCurPop) == g.NUM_BIN:
         g.glbBinNextPop = dict.fromkeys(g.glbBinCurPop.keys(), True)
      else:
         items = GetNLargest(g.NUM_BIN, g.glbBinCurPop, 0)
         g.glbBinNextPop = dict.fromkeys(items, True)

   elif g.glbPolicy == 1:
      assert g.shadowCache.t1.len + g.shadowCache.t2.len >= len(g.cache.binInCache)
      g.glbBinNextPop.update(LinkedListToBinDict(g.shadowCache.t1))
      g.glbBinNextPop.update(LinkedListToBinDict(g.shadowCache.t2))
      assert len(g.glbBinNextPop) <= g.NUM_BIN

   elif g.glbPolicy == 2:
      #get extraBin & evictBin dicts and update g.wl[i].prvQue
      extraBin = []
      evictBin = []
      for i in xrange(g.numWL):
         keyWL = g.wl[i].binCurPop.keys()
         keyPrv = g.wl[i].prvQue.keys()
         keyInst = set(keyWL).intersection(set(keyPrv))
         keyWLDiff = set(keyWL).difference(keyInst)
         keyPrvDiff = set(keyPrv).difference(keyInst)

         if len(keyWL) < g.wl[i].numPrvBin:
            numEvict = len(keyWLDiff) - (g.wl[i].numPrvBin - len(g.wl[i].prvQue))
            assert numEvict < len(keyPrvDiff)
            if numEvict > 0:
               items = GetNSmallest(numEvict, keyPrvDiff, 1)
               evictBin.extend(items)
               for key in items:
                  del g.wl[i].prvQue[key]
            for key in keyWLDiff:
               g.wl[i].prvQue[key] = True
            assert len(g.wl[i].prvQue) <= g.wl[i].numPrvBin
         elif len(keyWL) == g.wl[i].numPrvBin:
            evictBin.extend(keyPrvDiff)
            g.wl[i].prvQue = dict.fromkeys(keyWL, True)
         else:
            evictBin.extend(keyPrvDiff)
            items = GetNLargest(g.wl[i].numPrvBin, keyWL, 1)
            g.wl[i].prvQue = dict.fromkeys(items, True)
            keyDiff = set(keyWL).different(set(items))
            extraBin.extend(list(keyDiff))

      #update g.pubQue
      if len(extraBin) > g.NUM_PUBLIC_BIN:
         items = GetNLargest(g.NUM_PUBLIC_BIN, extraBin, 1)
         g.pubQue = dict.fromkeys(items, True)
      elif len(extraBin) == g.NUM_PUBLIC_BIN:
         g.pubQue = dict.fromkeys(extraBin, True)
      elif len(extraBin) + len(evictBin) > g.NUM_PUBLIC_BIN:
         numAdmin = g.NUM_PUBLIC_BIN - len(extraBin)
         items = GetNLargest(numAdmin, evictBin, 1)
         items.extend(extraBin)
         g.pubQue = dict.fromkeys(items, True)
      elif len(extraBin) + len(evictBin) == g.NUM_PUBLIC_BIN:
         evictBin.extend(extraBin)
         g.pubQue = dict.fromkeys(evictBin, True)
      elif 0 < len(extraBin) + len(evictBin) < g.NUM_PUBLIC_BIN:
         keyPub = g.pubQue.keys()
         keyWL = g.glbBinCurPop.keys()
         keyInst = set(keyPub).intersection(set(keyWL))
         for key in keyInst:
            del g.pubQue[key]
         numEvict = len(extraBin) + len(evictBin) - (g.NUM_PUBLIC_BIN - len(g.pubQue))
         if numEvict > 0:
            items = GetNSmallest(numEvict, g.pubQue.keys(), 1)
            for key in items:
               del g.pubQue[key]
         g.pubQue.update(dict.fromkeys(extraBin + evictBin, True))
         if numEvict > 0:
            assert len(g.pubQue) == g.NUM_PUBLIC_BIN
      else:
         assert len(extraBin) + len(evictBin) == 0

      #update g.glbBinNextPop
      for i in xrange(g.numWL):
         g.glbBinNextPop.update(g.wl[i].prvQue)
      g.glbBinNextPop.update(g.pubQue)
      assert len(g.glbBinNextPop) <= g.NUM_BIN

   elif g.glbPolicy == 4:
      #update g.prvQue
      if len(g.glbBinCount) <= g.numPrvBin:
         g.prvQue = dict.fromkeys(g.glbBinCount.keys(), True)
      else: #len(g.glbBinCount) > g.numPrvBin
         items = heapq.nlargest(g.numPrvBin, g.glbBinCount.iteritems(), key=operator.itemgetter(1))
         items = [key[0] for key in items]
         keyPrvDiff = set(g.prvQue).difference(items)
         g.prvQue = dict.fromkeys(items, True)

      #update g.pubQue
      if g.numPrvBin < len(g.glbBinCount) <= g.NUM_BIN:
         g.pubQue.clear()
         for key in g.glbBinCount:
            if key not in g.prvQue:
               g.pubQue[key] = True
      elif len(g.glbBinCount) > g.NUM_BIN:
         #delete overlap key
         for key in g.prvQue:
            if key in g.pubQue:
               del g.pubQue[key]
            if key in g.glbBinCurPop:
               del g.glbBinCurPop[key]
         keyPubQue = g.pubQue.keys()
         keyCurPop = g.glbBinCurPop.keys()
         keyInst = set(keyPubQue).intersection(set(keyCurPop))
         keyPubDiff = set(g.pubQue).difference(keyInst)
         if len(keyCurPop) + len(keyPubDiff) <= g.numPubBin:
            g.pubQue = dict.fromkeys(keyCurPop + list(keyPubDiff), True)
            numAdmin = g.numPubBin - len(g.pubQue)
            if numAdmin > 0:  #so pubQue might not be fully utilized
               keyDiff = set(keyPrvDiff).difference(set(g.pubQue))
               items = GetNLargest(numAdmin, keyDiff, 1)
               g.pubQue.update(dict.fromkeys(items, True))
         else:    #len(keyCurPop) + len(keyPubDiff) > g.numPubBin
            if len(keyCurPop) > g.numPubBin:
               items = GetNLargest(g.numPubBin, g.glbBinCurPop, 1)
               g.pubQue = dict.fromkeys(items, True)
            elif len(keyCurPop) == g.numPubBin:
               g.pubQue = dict.fromkeys(keyCurPop, True)
            else:    #len(keyCurPop) < g.numPubBin
               numAdmin = g.numPubBin - len(keyCurPop)
               items = GetNLargest(numAdmin, list(keyPubDiff), 1)
               g.pubQue = dict.fromkeys(items + keyCurPop, True)
      else: # len(g.glbBinCount) <= g.numPrvBin 
         assert len(g.pubQue) == 0 and len(g.prvQue) == len(g.glbBinCount)

      #update g.glbBinNextPop
      g.glbBinNextPop.update(g.prvQue)
      g.glbBinNextPop.update(g.pubQue)
      assert len(g.glbBinNextPop) <= g.NUM_BIN
      ShiftFlashWindow()

   elif g.glbPolicy == 3:
      #update g.prvQue
      if len(g.glbBinCount) <= g.NUM_PRIVATE_BIN:
         g.prvQue = dict.fromkeys(g.glbBinCount.keys(), True)
      else: #len(g.glbBinCount) > g.NUM_PRIVATE_BIN 
         items = heapq.nlargest(g.NUM_PRIVATE_BIN, g.glbBinCount.iteritems(), key=operator.itemgetter(1))
         items = [key[0] for key in items]
         keyInst = set(items).intersection(set(g.prvQue))
         keyPrvDiff = set(g.prvQue).difference(keyInst)
         g.prvQue = dict.fromkeys(items, True)
#         keyPrvDiff = []
#         if len(g.prvQue) == g.NUM_PRIVATE_BIN:
#            diffRatio = (g.NUM_PRIVATE_BIN - len(keyInst)) / float(g.NUM_PRIVATE_BIN)
#            if diffRatio >= 0.2:
#               keyPrvDiff = set(g.prvQue).difference(keyInst)
#               g.prvQue = dict.fromkeys(items, True)
#         else:
#            keyPrvDiff = set(g.prvQue).difference(keyInst)
#            g.prvQue = dict.fromkeys(items, True)
      #update g.pubQue
      if g.NUM_PRIVATE_BIN < len(g.glbBinCount) <= g.NUM_BIN:
         g.pubQue.clear()
         for key in g.glbBinCount:
            if key not in g.prvQue:
               g.pubQue[key] = True
      elif len(g.glbBinCount) > g.NUM_BIN:
         #delete overlap key
         for key in g.prvQue:
            if key in g.pubQue:
               del g.pubQue[key]
            if key in g.glbBinCurPop:
               del g.glbBinCurPop[key]
         #get g.pubQue
         if len(g.glbBinCurPop) > g.NUM_PUBLIC_BIN:
            items = GetNLargest(g.NUM_PUBLIC_BIN, g.glbBinCurPop, 1)
            g.pubQue = dict.fromkeys(items, True)
         elif len(g.glbBinCurPop) == g.NUM_PUBLIC_BIN:
            g.pubQue = dict.fromkeys(g.glbBinCurPop.keys(), True)
         else:    #len(g.glbBinCurPop) < g.NUM_PUBLIC_BIN
            numAdmin = g.NUM_PUBLIC_BIN - len(g.glbBinCurPop)
            keyPub = g.pubQue.keys() + list(keyPrvDiff)  #merge the evicted key of g.prvQue to g.pubQue
            keyPubDiff = set(keyPub).difference(set(g.glbBinCurPop))
            g.pubQue.clear()
            if len(keyPubDiff) <= numAdmin:     #so pubQue might not be fully utilized
               g.pubQue = dict.fromkeys(list(keyPubDiff) + g.glbBinCurPop.keys(), True)
            else:
               items = GetNLargest(numAdmin, keyPubDiff, 1)
               g.pubQue = dict.fromkeys(items + g.glbBinCurPop.keys(), True)
               assert len(g.pubQue) + len(g.prvQue) == g.NUM_BIN
      else: #len(g.glbBinCount) <= g.NUM_PRIVATE_BIN
         assert len(g.pubQue) == 0 and len(g.prvQue) == len(g.glbBinCount)

      #update g.glbBinNextPop
      g.glbBinNextPop.update(g.prvQue)
      g.glbBinNextPop.update(g.pubQue)
      assert len(g.glbBinNextPop) <= g.NUM_BIN

   else: #other g.glbPolicy
      print 'ERROR: g.glbPolicy is wrong.'
      sys.exit(1)


def ShiftFlashWindow():
   if len(g.glbBinCount) >= g.NUM_BIN:
      keyPopInst = set(g.prvQue).intersection(g.glbBinCurPop)
      keyPrvDiff = set(g.prvQue).difference(keyPopInst)
      weightFrequency = GetPopAverage(keyPrvDiff, 0)
      weightRecency = GetPopAverage(g.pubQue.keys() + list(keyPopInst), 1)
#      weightFrequency = GetPopAverage(g.prvQue, 0)
#      weightRecency = GetPopAverage(g.pubQue, 1)
      if weightFrequency < weightRecency:
         if g.numPrvBin - int(0.01 * g.NUM_BIN) >= int(0.2 * g.NUM_BIN):
            g.numPrvBin -= int(0.01 * g.NUM_BIN)
            g.numPubBin = g.NUM_BIN - g.numPrvBin
      elif weightFrequency > weightRecency:
         if g.numPubBin - int(0.01 * g.NUM_BIN) >= int(0.2 * g.NUM_BIN):
            g.numPubBin -= int(0.01 * g.NUM_BIN)
            g.numPrvBin = g.NUM_BIN - g.numPubBin
      else:
         pass


def GetPopAverage(queDict, flag):
   n = 0
   mean = 0.0
   std = 0.0
   for key in queDict:
      n += 1
      pop = 0.0
      if flag == 0:
         for i in xrange(len(g.glbBinOldPop[key])):
            pop += g.prvWeight[i] * g.glbBinOldPop[key][-1*(i+1)]
      elif flag == 1:
         tmp = min(len(g.pubWeight), len(g.glbBinOldPop[key]))
         for i in xrange(tmp):
            pop += g.pubWeight[i] * g.glbBinOldPop[key][-1*(i+1)]
      else:
         print 'ERROR: flag is wrong.'
         sys.exit(1)
      mean, std = Welford_alg(mean, std, pop, n)
   return mean


def Welford_alg(mean, std, req, n):
   std = std  + pow(req - mean, 2) * (n - 1) / n
   mean = mean + (req - mean) / n
   return mean, std


def LinkedListToBinDict():
   tmpDict = dict()
   for key in ll.nodeDict:
      tmpDict[key.value] = True
   return tmpDict


def GetNSmallest(n, keyList, flag):
   items = []
   for key in keyList:
      pop = 0.0
      for i in xrange(len(g.glbBinOldPop[key])):
         if flag == 0:
            pop += g.linearWeight[i] * g.glbBinOldPop[key][-1*(i+1)]
         elif flag == 1:
            pop += g.expWeight[i] * g.glbBinOldPop[key][-1*(i+1)]
         else:
            print 'ERROR: flag is wrong.'
            sys.exit(1)
      items.append([key, pop])
   items = heapq.nsmallest(n, items, key=operator.itemgetter(1))
   return map(lambda x: x[0], items)

def GetNLargest(n, keyList, flag):
   items = []
   for key in keyList:
      pop = 0.0
      for i in xrange(len(g.glbBinOldPop[key])):
         if flag == 0:
            pop += g.linearWeight[i] * g.glbBinOldPop[key][-1*(i+1)]
         elif flag == 1:
            pop += g.expWeight[i] * g.glbBinOldPop[key][-1*(i+1)]
         else:
            print 'ERROR: flag is wrong.'
            sys.exit(1)
      items.append([key, pop])
   items = heapq.nlargest(n, items, key=operator.itemgetter(1))
   return map(lambda x: x[0], items)


class Cache:
   """
   Cache Simulator
   """
   def __init__(self):
      self.dirtyFlag = dict()    #hold dirty flag for each bin, format: {binID:(True/False)}
      self.binInCache = dict()
      self.numHit = 0   #number of cache hit
      self.numIO = 0    #number of I/O used for cache hit calculation after cache warm
      self.numRead = 0
      self.numWrite = 0

   #Set dirty flag
   def SetDirty(self, binID):
      self.dirtyFlag[binID] = True

   #Check dirty status
   def IsDirty(self, binID):
      return binID in self.dirtyFlag

   #Calculate the number of I/O eviction for dirty bin(1MB) in Write Back policy
   def WBEvictIOCost(self, binID):
      if g.writePolicy == 0 and self.IsDirty(binID):
         del self.dirtyFlag[binID]
         g.numEvict += g.NUM_IO_PER_BIN
         g.numSsdRead += g.NUM_IO_PER_BIN
         g.numMdWrite += g.NUM_IO_PER_BIN

   #Check if the data within bin is cached
   def CheckHit(self, binID):
      return binID in self.binInCache

   #Flush cached bins by migrating out/in
   def FlushBin(self):
      keyInCache = self.binInCache.keys()
      keyNextEpoch = g.glbBinNextPop.keys()

      keyInst = set(keyInCache).intersection(keyNextEpoch)
      keyInCacheDiff = set(keyInCache).difference(keyInst)
      keyNextEpochDiff = set(keyNextEpoch).difference(keyInst)

      if (g.glbPolicy == 0 or g.glbPolicy == 3 or g.glbPolicy == 1) and len(keyNextEpoch) < g.NUM_BIN:
         assert len(keyInCacheDiff) == 0

      for key in keyInCacheDiff:
         self.WBEvictIOCost(key)
      for key in self.dirtyFlag:
         if key not in keyInst:
            print 'ERROR: test error.'
            sys.exit(1)
      g.numAdmin += len(keyNextEpochDiff) * g.NUM_IO_PER_BIN
      g.numMdRead += len(keyNextEpochDiff) * g.NUM_IO_PER_BIN
      g.numSsdWrite += len(keyNextEpochDiff) * g.NUM_IO_PER_BIN

      self.binInCache.clear()
      self.binInCache = copy.deepcopy(g.glbBinNextPop)


class ShadowCache:
   """
   shadow cache implemented ARC caching algorithm used by global policy (-g3)
   """
   def __init__(self):
      self.t1 = LinkedList()
      self.t2 = LinkedList()
      self.b1 = LinkedList()
      self.b2 = LinkedList()
      self.t1_binToNode = dict()
      self.t2_binToNode = dict()
      self.b1_binToNode = dict()
      self.b2_binToNode = dict()
      self.p = 0
      self.c = g.NUM_BIN

   def CheckHit(self, binID):
      if binID in self.t1_binToNode:   #bin in t1
         self.t1.Remove(self.t1_binToNode[binID])
         del self.t1_binToNode[binID]
         self.t2_binToNode[binID] = self.t2.Append(binID)
         return True
      elif binID in self.t2_binToNode:    #bin in t2
         self.t2.MoveToTail(self.t2_binToNode[binID])
         return True
      elif binID in self.b1_binToNode:    #bin in b1
         self.p = min(self.c, self.p + max(1, self.b2.len / self.b1.len))
         self.Replace(binID)
         self.b1.Remove(self.b1_binToNode[binID])
         del self.b1_binToNode[binID]
         self.t2_binToNode[binID] = self.t2.Append(binID)
         return False
      elif binID in self.b2_binToNode:    #bin in b2
         self.p = max(0, self.p - max(1, self.b1.len / self.b2.len))
         self.Replace(binID)
         self.b2.Remove(self.b2_binToNode[binID])
         del self.b2_binToNode[binID]
         self.t2_binToNode[binID] = self.t2.Append(binID)
         return False
      else:    #bin not in t1, t2, b1, b2
         if self.t1.len + self.b1.len == self.c:
            if self.t1.len < self.c:
               delBinID = self.b1.Remove(self.b1.head)
               del self.b1_binToNode[delBinID]
               self.Replace(binID)
            else:    #b1 is empty
               delBinID = self.t1.Remove(self.t1.head)
               del self.t1_binToNode[delBinID]
         else:
            assert self.t1.len + self.b1.len < self.c
            total = self.t1.len + self.t2.len + self.b1.len + self.b2.len
            if total >= self.c:
               assert self.t1.len + self.t2.len == self.c
               if total == 2 * self.c:
                  delBinID = self.b2.Remove(self.b2.head)
                  del self.b2_binToNode[delBinID]
               self.Replace(binID)
         self.t1_binToNode[binID] = self.t1.Append(binID)
         return False

   def Replace(self, binID):
      if self.t1.len != 0 and (self.t1.len > self.p or (self.t1.len == self.p and binID in self.b2_binToNode)):
         delBinID = self.t1.Remove(self.t1.head)
         del self.t1_binToNode[delBinID]
         self.b1_binToNode[delBinID] = self.b1.Append(delBinID)
      else:
         delBinID = self.t2.Remove(self.t2.head)
         del self.t2_binToNode[delBinID]
         self.b2_binToNode[delBinID] = self.b2.Append(delBinID)


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
      #Pick up reference from I/O trace line
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
         print 'ERROR: wrong W/R format'
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
   print '|    Input files(%d):' % g.numWL,
   for i in xrange(g.numWL):
      print g.wl[i].inFile,
   print ''
   print '|    Flash size: %dMB' % (g.FLASH_SIZE)
   print '|    Write Policy: %s' % (g.wrtAbbr)
   print '|    Flash admin num: %d' % (g.numAdmin)
   print '|    Flash evict num: %d' % (g.numEvict)
   print '|    Bypass flash num: %d' % (g.numBypass)
   print '|    SSD read num: %d' % (g.numSsdRead)
   print '|    SSD write num: %d' % (g.numSsdWrite)
   print '|    MD read num: %d' % (g.numMdRead)
   print '|    MD write num: %d' % (g.numMdWrite)
   print '|    Cache hit ratio: %.4f%%' % (float(g.cache.numHit) / g.cache.numIO * 100)
   print '|--------------------------------------------|'

   if g.numWL == 1:
      outFile = open(os.path.join(g.dirPath, '%sSummary-%dmin-%dMB-%s-glb%d' % (g.outPrefix, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.wrtAbbr, g.glbPolicy)), 'a')
      outFile.write('Input file: %s\n' % g.wl[0].inFile)
      outFile.write('Flash size: %d(MB)\n' % (g.FLASH_SIZE))
      outFile.write('Write policy: %s\n' % (g.wrtAbbr))
      outFile.write('Time length: %.4f(hour)\n' % (g.wl[0].timeLength))
      outFile.write('Number of I/Os: %d\n' % (g.cache.numIO))
      outFile.write('Number of Read: %d\n' % (g.cache.numRead))
      outFile.write('Number of Write: %d\n' % (g.cache.numWrite))
      outFile.write('Flash admin num: %d\n' % (g.numAdmin))
      outFile.write('Flash evict num: %d\n' % (g.numEvict))
      outFile.write('Bypass flash num: %d\n' % (g.numBypass))
      outFile.write('SSD read num: %d\n' % (g.numSsdRead))
      outFile.write('SSD write num: %d\n' % (g.numSsdWrite))
      outFile.write('MD read num: %d\n' % (g.numMdRead))
      outFile.write('MD write num: %d\n' % (g.numMdWrite))
      outFile.write('Cache hit ratio: %.4f%%\n' % (float(g.cache.numHit) / g.cache.numIO * 100))
      outFile.write('\n')
      outFile.close()
   else:
      outFile = open(os.path.join(g.dirPath, '%sSummary-%dfile-%dmin-%dMB-%s-glb%d' % (g.outPrefix, g.numWL, g.REPLACE_EPOCH/60, g.FLASH_SIZE, g.wrtAbbr, g.glbPolicy)), 'a')
      outFile.write('Flash size: %d(MB)\n' % g.FLASH_SIZE)
      outFile.write('Write policy: %s\n' % (g.wrtAbbr))
      outFile.write('Number of I/Os: %d\n' % g.cache.numIO)
      outFile.write('Number of Read: %d\n' % g.cache.numRead)
      outFile.write('Number of Write: %d\n' % g.cache.numWrite)
      outFile.write('Flash admin num: %d\n' % (g.numAdmin))
      outFile.write('Flash evict num: %d\n' % (g.numEvict))
      outFile.write('Bypass flash num: %d\n' % (g.numBypass))
      outFile.write('SSD read num: %d\n' % (g.numSsdRead))
      outFile.write('SSD write num: %d\n' % (g.numSsdWrite))
      outFile.write('MD read num: %d\n' % (g.numMdRead))
      outFile.write('MD write num: %d\n' % (g.numMdWrite))
      outFile.write('Cache hit ratio: %.4f%%\n' % (float(g.cache.numHit) / g.cache.numIO * 100))
      outFile.write('Input files(%d):\n' % (g.numWL))
      for i in xrange(g.numWL):
         outFile.write('%s:\t%d\t%d\t%d\t%.4f%%\n' % (g.wl[i].inFile, g.wl[i].numIOFlash, g.wl[i].numReadFlash, g.wl[i].numWriteFlash, (float(g.wl[i].numHit)/g.wl[i].numIOFlash*100)))
      outFile.write('\n')
      outFile.close()


if __name__ == "__main__":
   main()

