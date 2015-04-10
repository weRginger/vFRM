#!/usr/bin/python

import sys, os
import re, shutil
import linecache
import getopt
import operator

class g:
   """
   Global variables & initialization.
   """
   FLASH_SIZE = 0    #flash size in MB (1MB = 2048 Blocks)
   BIN_SIZE = 2048   #bin size in blocks
   NUM_BIN = 0       #number of bin in flash
   REPLACE_EPOCH = 300    #bin replace interval in seconds

   timeOffset = 0    # time offset - the access time of the first I/O
   inFile = None     # Input I/O trace file
   dirName = None    # input-file name without extention (.cvs)
   dirPath = None    # folder path for tier simulation results
   cache = None      # instance of Cache class

   binPop = dict()   #popularity statistic for bin access by all the traces
   binPopCurrEpoch = dict()   #popularity statistic for bin access in current epoch
   numOldEpoch = 14     #number of history epochs in record
   binPopOldEpochs = dict()   #popularity records for bins in each old epochs
   binPopNextEpoch = dict()   #predict popularity of each bin for the next epoch
   binReaces = dict()    #dict for bin reaccess statistic
   longGap = dict()

   numIOEpoch = 0    #number of I/Os in one epoch
   numHitEpoch = 0   #number of cache hit in one epoch
   numReadEpoch = 0
   numWriteEpoch = 0
   mean_topCE = 0.0  #CE: cache effectiveness
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
   g.FLASH_SIZE = long(args[0])
   g.NUM_BIN = g.FLASH_SIZE * 2048 / g.BIN_SIZE
   g.cache = Cache()    # set instance of Cache class

   CreateFolder()

   lineNum = 1    # current line number in trace file
   numEpoch = 1   # the number of flush epoch

   while True:
      # Get trace reference
      [ioTime, ioRW, ioLBN, ioSize] = GetTraceReference(g.inFile, lineNum)
      if ioLBN == 0:
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

      if ioTime < numEpoch * g.REPLACE_EPOCH:
         PopStat(startBinID, binNum)
         PopStatCurrEpoch(startBinID, binNum)
         ReacesStat(startBinID, binNum, ioTime)
         if numEpoch * g.REPLACE_EPOCH > 86400:   #second, the traces in the 1st day is used for flash warm-up
            flag = CheckCacheHit(startBinID, binNum, g.cache)  # check cache hit
            StatCurrEpoch(ioRW, flag)
      else:
         numGap = ioTime / g.REPLACE_EPOCH - numEpoch + 1

         if numEpoch * g.REPLACE_EPOCH <= 86400 and (numEpoch + numGap) * g.REPLACE_EPOCH > 86400:
            gap = (numEpoch + numGap) - 86400/g.REPLACE_EPOCH - 1;
            with open(os.path.join(g.dirPath, '%s-StatByEpoch-%dmin-%dMB' % (g.dirName, g.REPLACE_EPOCH/60, g.FLASH_SIZE)), 'a') as source:
               for i in xrange(gap):
                  source.write('%d\t0\t0\t0\t0\t0.0\t%d\t0\t0\t0.0\t0\t0\t0.0\n' % ((86400+(i+1)*g.REPLACE_EPOCH)/60, len(g.cache.binInCache)))
         elif numEpoch * g.REPLACE_EPOCH > 86400:
            StatByEpoch(g.cache, numEpoch*g.REPLACE_EPOCH)
            if numGap > 1:
               with open(os.path.join(g.dirPath, '%s-StatByEpoch-%dmin-%dMB' % (g.dirName, g.REPLACE_EPOCH/60, g.FLASH_SIZE)), 'a') as source:
                  for i in xrange(numGap-1):
                     source.write('%d\t0\t0\t0\t0\t0.0\t%d\t0\t0\t0.0\t0\t0\t0.0\n' % ((numEpoch+i+1)*g.REPLACE_EPOCH/60, len(g.cache.binInCache)))

         PopRecordByEpoch()
         PopPredNextEpoch()
         g.cache.FlushBin()  # update cached bins
         g.binPopCurrEpoch.clear()    # clear bin popularity records in last epoch

         numEpoch += numGap
         lineNum -= 1

   # Display results of program run
   PrintSummary(g.cache)


def CheckCacheHit(startBinID, binNum, cache):
   """
   Check cache hit. The cache instance is given in the 3rd
   argument "cache".
   """
   cache.ioNum += 1
   flagHit = True
   for i in xrange(binNum):
      binID = startBinID + i
      cacheHit = cache.CheckHit(binID)
      if not cacheHit:
         flagHit = False
   if flagHit:
      cache.hitNum += 1

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


def StatByEpoch(cache, time):
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

   keyInCache = cache.binInCache.keys()

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
      source.write('%d\t%d\t%d\t%d\t%d\t%.2f\t%d\t%d\t%d\t%.2f\t%d\t%d\t%.2f\n' % (time/60, g.numIOEpoch, g.numWriteEpoch, g.numReadEpoch, g.numHitEpoch, hitRatioEpoch, len(keyInCache), len(allKeyEpoch), len(allKeyIntersection), allCacheEffect, len(topKeyEpoch), len(topKeyIntersection), topCacheEffect))

   ## Clean in each epoch
   g.numIOEpoch = g.numHitEpoch = g.numWriteEpoch = g.numReadEpoch = 0


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


def ReacesStat(startBinID, binNum, ioTime):
   """
   Reaccess statistic for all I/Os.
   taking g.REPLACE_EPOCH as time granularity.
   """
   for i in xrange(binNum):
      binID = startBinID + i
      if binID not in g.binReaces:
         g.binReaces[binID] = [None, 0]
         g.binReaces[binID].extend([0 for i in xrange(g.numOldEpoch)])
         g.longGap[binID] = [None, None]  #[reaccess-long-gap-id, occur-time]
      if g.binReaces[binID][0] is None:
         g.binReaces[binID][0] = ioTime
      else:
         assert ioTime >= g.binReaces[binID][0]
         timeDiff = ioTime - g.binReaces[binID][0]
         i = timeDiff / g.REPLACE_EPOCH
         if i < g.numOldEpoch:
            g.binReaces[binID][i+2] += 1
            ##-----------------------------------------------------------------
            ## if i >= 1: record newest reaccess long gap (id) and occurence time;
            ## if i == 0: if there is long-gap record, all I/Os in one epoch (to the 
            ## recorded last long gap occurence time) belong to the effect of long-gap reaccess.
            if i >= 1:
               g.longGap[binID][0] = i+2
               g.longGap[binID][1] = ioTime
            elif i == 0:
               if g.longGap[binID][0] is not None:
                  if ioTime - g.longGap[binID][1] < g.REPLACE_EPOCH:
                     j = g.longGap[binID][0]
                     g.binReaces[binID][j] += 1
                     g.binReaces[binID][1] += 1
                  else:
                     g.longGap[binID] = [None, None]
            ##-----------------------------------------------------------------
         g.binReaces[binID][1] += 1
         g.binReaces[binID][0] = ioTime


def PopPredNextEpoch():
   """
   Predict bin's popularity for the next epoch.
   bin popularity = access num in last epoch * reaccess probability in an epoch granularity.
   """
   for key in g.binPopOldEpochs:
      g.binPopNextEpoch[key] = 0.0
      if g.binReaces[key][1] != 0:
         for i in xrange(len(g.binPopOldEpochs[key])):
            if g.binPopOldEpochs[key][-(i+1)] is not None:
               g.binPopNextEpoch[key] = g.binPopOldEpochs[key][-(i+1)] * g.binReaces[key][i+2] / g.binReaces[key][1]
               break


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
      g.binPopOldEpochs[key].append(None)


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
      if len(g.binPopNextEpoch) <= g.NUM_BIN:     # all accessed bins can be cached
         keyNextEpoch = g.binPopNextEpoch.keys()
      else:
         itemNextEpoch = [[key, g.binPopNextEpoch[key]] for key in g.binPopNextEpoch]
         itemNextEpoch.sort(key=operator.itemgetter(1))     #sort by the 2nd item in list
         keyNextEpoch = [itemNextEpoch[-(i+1)][0] for i in xrange(g.NUM_BIN)]

      keyInCache = self.binInCache.keys()

      keyIntersection = set(keyInCache).intersection(keyNextEpoch)
      keyInCacheRemain = set(keyInCache).difference(keyIntersection)
      keyNextEpochRemain = set(keyNextEpoch).difference(keyIntersection)
      if len(g.binPopNextEpoch) <= g.NUM_BIN:
         assert len(keyInCacheRemain) == 0

      #migrate out
      for key in keyInCacheRemain:
         del self.binInCache[key]
      #migrate in
      for key in keyNextEpochRemain:
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


def PrintSummary(cache, optCache=None):
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
   print '|    Cache hit ratio: %f' % (float(cache.hitNum) / cache.ioNum)
   print '|--------------------------------------------|'

   outFile = open(os.path.join(g.dirPath, '%s-stat-%dmin-%dMB' % (g.dirName, g.REPLACE_EPOCH/60, g.FLASH_SIZE)), 'a')
   outFile.write('Input file: %s\n' % g.inFile)
   outFile.write('Flash size: %dMB\n' % (g.FLASH_SIZE))
   outFile.write('Cache hit ratio: %f\n' % (float(cache.hitNum) / cache.ioNum))
   outFile.write('\n')
   outFile.close()


if __name__ == "__main__":
   main()
