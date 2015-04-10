#!/usr/bin/python

import sys, os
import re
import shutil
import linecache
import operator


class g:
   """
   Global variables & initialization.
   """
   BIN_SIZE = 2048   #Bin size in block for pupularity statistic, xxx blocks = xxx/2 KB
   CACHE_LINE = 8    #Cache line size, default is 4KB

   inFile = None     #Input I/O trace file
   dirPath = None    #Created folder for all trace analysis results
   timeOffset = 0    #time offset -- the access time of the first I/O
   timeGranularity = 300   #second, time granularity for statistic
   popIO = dict()    #dict for popularity statistic for all I/Os, format: {binID : access count}
   popWrite = dict() #dict for popularity statistic for all WRITE I/Os
   popRead = dict()  #dict for popularity statistic for all READ I/Os
   reaccIO = dict()  #dict for reaccess statistic for all I/Os,
                     #format: {binID : [{time granularity in min : reaccess num}, total reaccess num, last access time]}
   binUtil = dict()  #dict for bin utilization statistic, format: {binID : {slotID : True}}
   randomIO = dict()       #dict for random IO statistic by time granularity
   sequentialIO = dict()   #dict for sequential IO statistic by time granularity
   mean_numIO_min = 0.0
   std_numIO_min = 0.0
   mean_binSize_min = 0.0
   std_binSize_min = 0.0
   mean_cacheSize_min = 0.0
   std_cacheSize_min = 0.0


def WindowsTickToUnixSeconds(windowsTicks):
      """
      Convert Windows filetime to Unix time.
      The windows epoch starts 1601-01-01T00:00:00Z.
      It's 11644473600 seconds before the UNIX/Linux
      epoch (1970-01-01T00:00:00Z). The Windows ticks
      are in 100 nanoseconds.
      """
      ticksPerSecond = 10000000
      epochDifference = 11644473600
      return windowsTicks / ticksPerSecond - epochDifference


def GetTraceReference(inFile, lineNum):
   """
   Get specified line from input file.
   """
   line = linecache.getline(inFile, lineNum)
   if line != '':
      #Pick up reference from I/O trace line
      line = line.strip().split(',')
      ioTime = WindowsTickToUnixSeconds(int(line[0]))
      ioLBN = int(line[4]) / 512
      ioSize = int(line[5]) / 512
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


def CreateFolder():
   """
   Create a new folder for trace analysis results.
   If the folder exists, then remove all objs in this folder.
   """
   filePath = os.path.abspath(g.inFile)
   fileHead, fileTail = os.path.split(filePath)
   dirName = os.path.splitext(fileTail)[0]
   g.dirPath = os.path.join(fileHead, 'stat-' + dirName)
   if not os.path.isdir(g.dirPath):
      os.makedirs(g.dirPath)
   else:
      for obj in os.listdir(g.dirPath):
         obj = os.path.join(g.dirPath, obj)
         if os.path.isfile(obj):
            os.unlink(obj)
         else:
            shutil.rmtree(obj)


def BinUtilStat(ioLBN, ioSize):
   startSlotID = ioLBN / g.CACHE_LINE
   slotNum = (ioLBN + ioSize - 1) / g.CACHE_LINE - startSlotID + 1

   for i in xrange(slotNum):
      slotID = startSlotID + i
      binID = slotID * g.CACHE_LINE / g.BIN_SIZE
      if binID not in g.binUtil:
         g.binUtil[binID] = dict()
      if slotID not in g.binUtil[binID]:
         g.binUtil[binID][slotID] = True


def BinUtilOutput():
   lists = [str(key) + ', ' + str(len(g.binUtil[key])) + ', ' + str(len(g.binUtil[key])/float(256)*100) + '\n' for key in g.binUtil]
   with open(os.path.join(g.dirPath, 'stat-BinUtilization'), 'w') as source:
      source.writelines(lists)


def PopStat(ioLBN, ioSize, ioRW):
   """
   Popularity statistic taking "g.BIN_SIZE" size of bin as unit.
   Traces are classified by all I/Os, WRITE I/Os and READ I/Os.
   """
   startBinID = ioLBN / g.BIN_SIZE
   binNum = (ioLBN + ioSize - 1) / g.BIN_SIZE - startBinID + 1

   #Popularity statistic for all I/Os
   for i in xrange(binNum):
      binID = startBinID + i
      g.popIO[binID] = g.popIO.get(binID, 0) + 1

   #Popularity statistic for WRITE or READ I/Os
   if ioRW == 'W':
      for i in xrange(binNum):
         binID = startBinID + i
         g.popWrite[binID] = g.popWrite.get(binID, 0) + 1
   else:
      for i in xrange(binNum):
         binID = startBinID + i
         g.popRead[binID] = g.popRead.get(binID, 0) + 1


def PopStatSortByBin(fileName, popDict):
   """
   Polularity statistic sorted by bin order in LBN space.
   output format:
      1: bin ID; 2: access count for each bin;
      3: sum of access count along bin order increasing;
      4: PDF of each bin (%); 5: CDF of bins (%).
   """
   assert len(popDict) > 0
   lines = [[key, popDict[key]] for key in popDict]
   lines.sort()
   popSum = 0.0
   for line in lines:
      popSum += line[1]
      line.append(popSum)
   for line in lines:
      line.extend([line[1]/popSum*100, line[2]/popSum*100])
   with open(os.path.join(g.dirPath, fileName), 'w') as source:
      lines = [str(line).strip('[]') + '\n' for line in lines]
      source.writelines(lines)


def PopStatSortByPop(fileName, popDict):
   """
   Popularity statistic sorted by the order of poplarity.
   The minimal unit size for popularity statistic is 1MB (2048 Blocks).
   output format:
      1: num of bin; 2: ratio of bin num to woking set size (max bin number);
      3: bin ID; 4: access count for each bin;
      5: sum of access count along bin increasing;
      6: PDF of each bin (%); 7: CDF of bins (%)
   """
   assert len(popDict) > 0
   lines = [[key, popDict[key]] for key in popDict]
   lines.sort(key=operator.itemgetter(1))    #sort by the 2nd element in list
   lines.reverse()

   #######################################################
   # Convert popularity in small bin size (less than 1MB)
   # into the popularity in 1MB bin size.
   # If there is no need to convert, just comment this code.
   Size_1MB = 2048
   if g.BIN_SIZE != Size_1MB:
      assert Size_1MB % g.BIN_SIZE == 0
      numBin_1MB = Size_1MB / g.BIN_SIZE
      id = 1
      popSum = 0.0
      tmpDict = dict()
      for i in xrange(len(lines)):
         if i >= id * numBin_1MB:
            tmpDict[id] = popSum
            popSum = lines[i][1]
            id += 1
         else:
            popSum += lines[i][1]
      tmpDict[id] = popSum
      lines = [[key, tmpDict[key]] for key in tmpDict]
      lines.sort()
   #######################################################

   popSum = 0.0
   maxBinNum = len(lines)
   i = 0
   for line in lines:
      i += 1
      line.insert(0, i)
      binPercent = float(line[0]) / maxBinNum * 100
      line.insert(1, binPercent)
      popSum += line[3]
      line.append(popSum)
   for line in lines:
      line.extend([line[3]/popSum*100, line[4]/popSum*100])
   with open(os.path.join(g.dirPath, fileName), 'w') as source:
      lines = [str(line).strip('[]') + '\n' for line in lines]
      source.writelines(lines)


def ReaccStat(ioLBN, ioSize, ioTime):
   """
   Reaccess statistic for all I/Os.
   taking "g.BIN_SIZE" as bin granularity;
   taking "1 minute" as time granularity.
   """
   startBinID = ioLBN / g.BIN_SIZE
   binNum = (ioLBN + ioSize - 1) / g.BIN_SIZE - startBinID + 1

   for i in xrange(binNum):
      binID = startBinID + i

      if binID not in g.reaccIO:
         g.reaccIO[binID] = [{}, 0, None]

      if g.reaccIO[binID][2] is None:
         g.reaccIO[binID][2] = ioTime
      else:
         assert ioTime >= g.reaccIO[binID][2]
         timeDiff = (ioTime - g.reaccIO[binID][2]) / 60 + 1    # 1 min as time granularity
         if timeDiff in g.reaccIO[binID][0]:
            g.reaccIO[binID][0][timeDiff] += 1
         else:
            g.reaccIO[binID][0][timeDiff] = 1
         g.reaccIO[binID][1] += 1
         g.reaccIO[binID][2] = ioTime


def ReaccStatByTime():
   """
   Reaccess statistic by specified time granularity.
   """
   #Time granularity in minute
#   TG_1MIN = 1
   TG_5MIN = 5
#   TG_10MIN = 10
#   TG_15MIN = 15
#   TG_20MIN = 20
   TG_30MIN = 30
#   TG_40MIN = 40
#   TG_50MIN = 50
   TG_60MIN = 60
#   TG_70MIN = 70
#   TG_23HR = 1380
   TG_24HR = 1440
#   TG_25HR = 1500

   temp1 = long(0)
   temp2 = long(0)
   tmpDict = dict()
   for binID in g.reaccIO:
      if g.reaccIO[binID][1] != 0:
#         tmpDict[binID] = [0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0]
         tmpDict[binID] = [0, 0,0,0,0,0]
         for timeDiff in g.reaccIO[binID][0]:
            if timeDiff <= TG_5MIN:
               tmpDict[binID][1] += g.reaccIO[binID][0][timeDiff]
               temp1 += g.reaccIO[binID][0][timeDiff]
            elif timeDiff <= TG_30MIN:
               tmpDict[binID][2] += g.reaccIO[binID][0][timeDiff]
            elif timeDiff <= TG_60MIN:
               tmpDict[binID][3] += g.reaccIO[binID][0][timeDiff]
            elif timeDiff <= TG_24HR:
               tmpDict[binID][4] += g.reaccIO[binID][0][timeDiff]
            else:
               tmpDict[binID][5] += g.reaccIO[binID][0][timeDiff]
         tmpDict[binID][0] += g.reaccIO[binID][1]
         temp2 += g.reaccIO[binID][1]
#         for i in range(0,9):
#            tmpPDF = float(tmpDict[binID][i]) / tmpDict[binID][9]
#            tmpDict[binID].append(tmpPDF)
#         tmpNum = 0
#         for i in range(0,9):
#            tmpNum += tmpDict[binID][i]
#            tmpCDF = float(tmpNum) / tmpDict[binID][9]
#            tmpDict[binID].append(tmpCDF)

   lines = [[key, tmpDict[key]] for key in tmpDict]
   lines.sort()
   with open(os.path.join(g.dirPath, 'stat-BinReaccess'), 'w') as source:
      lines = [str(line[0]) + ', ' + str(line[1]).strip('[]') + '\n' for line in lines]
      source.writelines(lines)
      source.write(str(temp1) + ', ' + str(temp2) + ', ' + str(float(temp1)/temp2))


def Welford_alg(mean, std, req, n):
   std  = std + pow(req - mean, 2) * (n - 1) / n
   mean = mean + (req - mean) / n
   return mean, std


def StatByMinute(ioLBN, ioSize, ioTime, ioRW):
   """
   Statistic per 'tg' second.
   tg - time granularity in second.
   """
   currLastMinute = StatByMinute.lastMinute
   currBinDict = StatByMinute.binDict
   currSlotDict = StatByMinute.slotDict
   currTimeDict = StatByMinute.timeDict

   startBinID = ioLBN / g.BIN_SIZE
   binNum = (ioLBN + ioSize - 1) / g.BIN_SIZE - startBinID + 1

   startSlotID = ioLBN / g.CACHE_LINE
   slotNum = (ioLBN + ioSize - 1) / g.CACHE_LINE - startSlotID + 1

   tg = g.timeGranularity
   currTime = ioTime / tg
   minuteGap = currTime - currLastMinute

   if minuteGap >= 1:
      #store results for the last minute record
      currTimeDict[currLastMinute][4] = len(currSlotDict)   # total number of cache lines (4KB) been accessed
      currTimeDict[currLastMinute][5] = len(currBinDict)    # total number of bins (1MB) been accessed
      currTimeDict[currLastMinute][3] = currTimeDict[currLastMinute][3] / 2   # convert to KB
      currTimeDict[currLastMinute][4] = currTimeDict[currLastMinute][4] * 4   # convert to KB
      tmpStr = str((currLastMinute+1)*tg/60) + ', ' + str(currTimeDict[currLastMinute]).strip('[]') + '\n'
      with open(os.path.join(g.dirPath, 'stat-ByMinute'), 'a') as source:
         source.write(tmpStr)
      g.mean_numIO_min, g.std_numIO_min = Welford_alg(g.mean_numIO_min, g.std_numIO_min, currTimeDict[currLastMinute][0], currLastMinute+1)
      g.mean_binSize_min, g.std_binSize_min = Welford_alg(g.mean_binSize_min, g.std_binSize_min, currTimeDict[currLastMinute][5], currLastMinute+1)
      g.mean_cacheSize_min, g.std_cacheSize_min = Welford_alg(g.mean_cacheSize_min, g.std_cacheSize_min, currTimeDict[currLastMinute][4], currLastMinute+1)
      #store zeros for the idle minutes
      for i in xrange(minuteGap-1):
         currLastMinute += 1
         tmpStr = str((currLastMinute+1)*tg/60) + ', 0, 0, 0, 0, 0, 0\n'
         with open(os.path.join(g.dirPath, 'stat-ByMinute'), 'a') as source:
            source.write(tmpStr)
      #clean dict and start a new record
      currLastMinute += 1
      currBinDict.clear()
      currSlotDict.clear()
      currTimeDict.clear()
      currTimeDict[currLastMinute] = [0,0,0,0,0,0]

   assert currLastMinute in currTimeDict
   for i in xrange(binNum):
      binID = startBinID + i
      if binID not in currBinDict:
         currBinDict[binID] = True
   for i in xrange(slotNum):
      slotID = startSlotID + i
      if slotID not in currSlotDict:
         currSlotDict[slotID] = True
   currTimeDict[currLastMinute][0] += 1   #I/O number
   if ioRW == 'W':
      currTimeDict[currLastMinute][1] += 1   #Write number
   elif ioRW == 'R':
      currTimeDict[currLastMinute][2] += 1   #Read number
   currTimeDict[currLastMinute][3] += ioSize    #total I/O size

   StatByMinute.lastMinute += minuteGap

# static variables attribute must be initialized
StatByMinute.lastMinute = 0
StatByMinute.binDict = dict()
StatByMinute.slotDict = dict()
StatByMinute.timeDict = dict()   #format: {minute ID : [num of IOs, total bins/per min, total cache size/per min]}
StatByMinute.timeDict[StatByMinute.lastMinute] = [0,0,0,0,0,0]


class SequentialQueue:
   def __init__(self):
      self.most_recent_io_sector = 0
      self.most_recent_io_size = 0
      self.sequential_count = 0
      self.sequential_io_list = []
      self.prev = None
      self.next = None

class CheckSequential:
   def __init__(self, queDepth=32, seqSize=256, seqGap=32):
      self.sequential_tracker_queue_depth = queDepth  #number of I/O flows to trace
      self.sequential_threshold_sector = seqSize      #maximal number of sectors for sequential I/O
      self.sequential_gap = seqGap      #number of sectors for the gap between two sequential I/Os
      self.head = None
      self.tail = None
      self.size = 0
      for i in xrange(self.sequential_tracker_queue_depth):
         seqQueue = SequentialQueue()
         self.SeqQueueMoveToLRUTail(seqQueue)

   def SeqQueueMoveToLRUTail(self, q):
      if q.next is not None:
         self.SeqQueueRemoveFromLRU(q)
      elif q is self.tail:
         return

      if self.tail is not None:
         self.tail.next = q
         q.prev = self.tail
         q.next = None
         self.tail = q
      else:
         assert self.head is None and self.size == 0
         self.head = self.tail = q
      self.size += 1

   def SeqQueueRemoveFromLRU(self, q):
      assert q.prev is not None or q.next is not None
      if q.prev is not None:
         q.prev.next = q.next
      else:
         assert self.head is q
         self.head = q.next
      if q.next is not None:
         q.next.prev = q.prev
      else:
         assert self.tail is q
         self.tail = q.prev
      q.prev = q.next = None
      self.size -= 1

   def CheckSeqThresh(self, q):
      if q.sequential_count >= self.sequential_threshold_sector:
         return True
      else:
         return False

   def CheckSequentialIO(self, ioLBN, ioSize, ioTime):
      assert self.size == self.sequential_tracker_queue_depth
      seqFlag = False
      seqThreshFlag = False
      q = self.tail
      while q is not None and not seqFlag:
         nextLBN = q.most_recent_io_sector + q.most_recent_io_size
         #check sequential I/O
         if q.most_recent_io_sector <= ioLBN <= nextLBN + self.sequential_gap:
            seqFlag = True
            #different sequential scenarios
            if ioLBN + ioSize <= nextLBN:    #seq-scenario-1: node1 contains node2
               seqOption = 1
            elif ioLBN < nextLBN:   #seq-scenario-2: node2 overlap node1
               seqOption = 2
            elif ioLBN == nextLBN:  #best sequential scenario
               seqOption = 3
            else:    #(nextLBN < ioLBN <= nextLBN + seqGap) seq-scenario-4: node2 has small gap with node1 
               seqOption = 4
            #update value
            if seqOption != 1:
               q.most_recent_io_sector = ioLBN
               q.most_recent_io_size = ioSize
            if seqOption == 2:
               q.sequential_count += ioLBN+ioSize-nextLBN
            elif seqOption == 3:
               q.sequential_count += ioSize
            elif seqOption == 4:
               q.sequential_count += ioLBN+ioSize-nextLBN
            q.sequential_io_list.append([ioTime, seqOption])
            #move queue to tail by LRU
            self.SeqQueueMoveToLRUTail(q)
            #check sequential threshold
            seqThreshFlag = self.CheckSeqThresh(q)
         #-----------------------------------------------------
         q = q.prev

      if not seqFlag:
         if self.head.sequential_io_list:
            assert not self.CheckSeqThresh(self.head)
            self.StatRandomIO(self.head)
         self.SeqQueueMoveToLRUTail(self.head)
         #init a new head node in tail-queue
         self.tail.most_recent_io_sector = ioLBN
         self.tail.most_recent_io_size = ioSize
         self.tail.sequential_count = ioSize
         self.tail.sequential_io_list = [[ioTime, 0]]    #seq-scenario-0: head node in sequential flow
         seqThreshFlag = self.CheckSeqThresh(self.tail)

      if seqThreshFlag:
         self.StatSequentialIO(self.tail)

   def StatRandomIO(self, q):
      for time, seqOption in q.sequential_io_list:
         timeID = time / g.timeGranularity + 1
         if timeID in g.randomIO:
            g.randomIO[timeID] += 1
         else:
            g.randomIO[timeID] = 1
      q.sequential_io_list = []

   def StatSequentialIO(self, q):
      for time, seqOption in q.sequential_io_list:
         timeID = time / g.timeGranularity + 1
         if timeID not in g.sequentialIO:
            g.sequentialIO[timeID] = [0,0,0,0,0]   #total 5 sequential scenarios
         g.sequentialIO[timeID][seqOption] += 1
      q.sequential_io_list = []

   def ClaimRemainingIO(self):
      q = self.head
      while q is not None:
         if q.sequential_io_list:
            assert not self.CheckSeqThresh(q)
            self.StatRandomIO(q)
         q = q.next

   def SeqStatOutput(self):
      maxTime = 0
      for key in g.randomIO:
         if key > maxTime:
            maxTime = key
      for key in g.sequentialIO:
         if key > maxTime:
            maxTime = key
      #output format: [timeID, random, 5-seq-scenarios, total-seq, total-IO]
      with open(os.path.join(g.dirPath, 'stat-Sequential'), 'w') as source:
         for i in xrange(maxTime):
            total = seq = 0
            timeID = i + 1
            statList = [timeID*g.timeGranularity/60]
            if timeID in g.randomIO:
               statList.append(g.randomIO[timeID])
               total += g.randomIO[timeID]
            else:
               statList.append(0)
            if timeID in g.sequentialIO:
               statList.extend(g.sequentialIO[timeID])
               seq += sum(g.sequentialIO[timeID])
               statList.append(seq)
               total += seq
            else:
               statList.extend([0,0,0,0,0,0])
            statList.append(total)
            source.write(re.sub(',', r'\t', str(statList).strip('[]')) + '\n')


def main():
   #Check for arguments
   if len(sys.argv) != 2:
      print 'Usage: %s [trace file]' % (os.path.basename(sys.argv[0]))
      sys.exit(1)

   g.inFile = sys.argv[1]
   CreateFolder()

   statSeqIO = CheckSequential()

   lineNum = 1    #current line number of I/O trace file
   while True:
      #Get trace reference
      [ioTime, ioRW, ioLBN, ioSize] = GetTraceReference(g.inFile, lineNum)
      if ioLBN == 0:
         break    #EOF or end of file
      if lineNum == 1:
         g.timeOffset = ioTime
      ioTime -= g.timeOffset
      lineNum += 1

      PopStat(ioLBN, ioSize, ioRW)
      ReaccStat(ioLBN, ioSize, ioTime)
      StatByMinute(ioLBN, ioSize, ioTime, ioRW)
      BinUtilStat(ioLBN, ioSize)
      statSeqIO.CheckSequentialIO(ioLBN, ioSize, ioTime)

   statSeqIO.ClaimRemainingIO()
   statSeqIO.SeqStatOutput()

   tmpStr = '\nmean numIO = %f\nmean bin size = %f\nmean cache size = %f\n' % (g.mean_numIO_min, g.mean_binSize_min, g.mean_cacheSize_min)
   with open(os.path.join(g.dirPath, 'stat-ByMinute'), 'a') as source:
      source.write(tmpStr)

   PopStatSortByBin('allIO-SortByBin', g.popIO)
   if len(g.popWrite) > 0:
      PopStatSortByBin('write-SortByBin', g.popWrite)
   if len(g.popRead) > 0:
      PopStatSortByBin('read-SortByBin', g.popRead)

   PopStatSortByPop('allIO-SortByPop', g.popIO)
   if len(g.popWrite) > 0:
      PopStatSortByPop('write-SortByPop', g.popWrite)
   if len(g.popRead) > 0:
      PopStatSortByPop('read-SortByPop', g.popRead)

   ReaccStatByTime()
   BinUtilOutput()

   print '\ntrace analysis succeed!\n'

if __name__ == "__main__":
   main()
