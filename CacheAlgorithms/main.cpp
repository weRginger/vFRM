#include <iostream>
#include <fstream>
#include <vector>
#include <climits>
#include "Config.h"
#include "Trace_Readers.h"
#include "Results_Printers.h"
#include "LRU.h"
#include "CLOCK.h"
#include "ARC.h"
#include "CAR.h"
#include "CART.h"
using namespace std;




int main(int argc, char** argv)
{
    
    /* 01. Main function commands */
    
    /* Wrong arguement list */
    if (argc<9)
    {
        cout<<"Format: CacheSim [cacheSize] [LRU 0/1] [CLOCK 0/1] [ARC 0/1] [CAR 0/1] [CART 0/1] [ResultFileName] [File1] [File2] ...\n";
        //                 0          1         2           3           4       5           6       7                8        9
        return 0;
    }

    /* Cache size */
    long cacheSizeInMegaBytes=atol(argv[1]);
    long cacheSize=cacheSizeInMegaBytes*256;  // Number of pages (4KB) * 52100 = 20 MegaBytes
    {
        //// Cache size
        ///*
        // Manually set these parameters:
        // WorkLoadSize = 63834567 Pages * 512 Bytes/Page / 1024^3 = 30 GigaBytes
        // CacheSize    = 100 MegaBytes / 512 Bytes/Page = 204800 Pages
        // SectorSize   = 512   Bytes
        // PageSize     = 3072  Bytes   = 8 Sectors
        //*/
        //
        //// Mode 1: in MegaBytes
        //
        //long        cacheSizeInMegaBytes=100;   // MegaBytes 2048=2G
        //long        cacheSize=cacheSizeInMegaBytes*256;  // Number of pages (4KB) * 52100 = 20 MegaBytes
        //
        //// Mode 2: in Page
        ///*
        //long        cacheSize=5;  // Number of pages (4KB) * 52100 = 20 MegaBytes
        //long        cacheSizeInMegaBytes=cacheSize/256;
        //*/
    }
    
    
    /* Cache policy */
    vector<int> runAlgorithmVector;
    int algorithmNumber=5;
    for (int i=2; i<7; i++)
    {
        runAlgorithmVector.push_back(atoi(argv[i]));
//        if (atoi(argv[i])==1)
//        {
//            algorithmNumber++;
//        }
    }
    //cout<<"algorithmNumber="<<algorithmNumber<<endl;

    string resultFileName = argv[7];
    
    /* Trace files */
    vector<fstream*> traceFilesVector;
    vector<string>   traceFileNameVector;
    int traceNumber=argc-8;
    cout<<"traceNumber="<<traceNumber<<endl;
    for (int i=8; i<argc; i++)
    {
        cout<<"Openning "<<argv[i]<<endl;
        traceFileNameVector.push_back(argv[i]);
        traceFilesVector.push_back(new fstream (argv[i]));
    }


    /* Output: Summary */
    ofstream    resultFileSummary                   ((resultFileName + "-" + to_string(cacheSizeInMegaBytes) + "MB-Summary.csv").c_str());

    /* Output: Total hit number */
    ofstream    resultFileTotalHitNumber            ((resultFileName + "-" + to_string(cacheSizeInMegaBytes) + "MB-TotalHitNumber.csv").c_str());
    
    /* Output: Total hit ratio */
    ofstream    resultFileTotalHitRatio             ((resultFileName + "-" + to_string(cacheSizeInMegaBytes) + "MB-TotalHitRatio.csv").c_str());

    /* Output: Hit ratio*/
    vector<ofstream*> resultFileHitRatioVector;
    resultFileHitRatioVector.push_back(new ofstream              ((resultFileName + "-" + to_string(cacheSizeInMegaBytes) + "MB-HitRatioLRU.csv").c_str())      );
    resultFileHitRatioVector.push_back(new ofstream              ((resultFileName + "-" + to_string(cacheSizeInMegaBytes) + "MB-HitRatioCLOCK.csv").c_str())    );
    resultFileHitRatioVector.push_back(new ofstream              ((resultFileName + "-" + to_string(cacheSizeInMegaBytes) + "MB-HitRatioARC.csv").c_str())      );
    resultFileHitRatioVector.push_back(new ofstream              ((resultFileName + "-" + to_string(cacheSizeInMegaBytes) + "MB-HitRatioCAR.csv").c_str())      );
    resultFileHitRatioVector.push_back(new ofstream              ((resultFileName + "-" + to_string(cacheSizeInMegaBytes) + "MB-HitRatioCART.csv").c_str())     );

    /* Output: Occupancy ratio */
    vector<ofstream*> resultFileOccupancyRatioVector;
    resultFileOccupancyRatioVector.push_back(new ofstream        ((resultFileName + "-" + to_string(cacheSizeInMegaBytes) + "MB-OccupancyRatioLRU.csv").c_str())    );
    resultFileOccupancyRatioVector.push_back(new ofstream        ((resultFileName + "-" + to_string(cacheSizeInMegaBytes) + "MB-OccupancyRatioCLOCK.csv").c_str())  );
    resultFileOccupancyRatioVector.push_back(new ofstream        ((resultFileName + "-" + to_string(cacheSizeInMegaBytes) + "MB-OccupancyRatioARC.csv").c_str())     );
    resultFileOccupancyRatioVector.push_back(new ofstream        ((resultFileName + "-" + to_string(cacheSizeInMegaBytes) + "MB-OccupancyRatioCAR.csv").c_str())     );
    resultFileOccupancyRatioVector.push_back(new ofstream        ((resultFileName + "-" + to_string(cacheSizeInMegaBytes) + "MB-OccupancyRatioCART.csv").c_str())    );

//    /* Output: Overhead */
//    vector<ofstream*> resultFileOverheadVector;
//    resultFileOverheadVector.push_back(new ofstream        ((resultFileName + "-" + to_string(cacheSizeInMegaBytes) + "MB-OverheadWriteBack.csv").c_str())       );
//    resultFileOverheadVector.push_back(new ofstream        ((resultFileName + "-" + to_string(cacheSizeInMegaBytes) + "MB-OverheadWriteThrough.csv").c_str())    );

    /* 03. Initialization */


    /* New instance of each algorithms */
    LRU         LRU_Cache(cacheSize);
    CLOCK       CLOCK_Cache(cacheSize);
    ARC         ARC_Cache(cacheSize);
    CAR         CAR_Cache(cacheSize);
    CART        CART_Cache(cacheSize);

    /* Page and line counters */
    long        totalIORequestCounter=0;
    long        totalPageCounter=0;
    vector<long> IORequestCounterForEachTraceVector;
    vector<long> pageCounterForEachTraceVector;
    

    /* Finish flags */
    bool        finish=false;
//    bool		traceFinish[traceNumber];
    vector<int> traceFinishVector;
    
    /* Trace start time */
//	long long	traceStartTime[traceNumber];
    vector<long long> traceStartTimeVector;

    /* For each IO request line from each trace */
    /* Cleanup for each IO request line */
    
    vector<string> 		currentTraceLineVector;
	vector<long long>	currentTraceLineStartPageVector;
    vector<long long>	currentTraceLineEndPageVector;
    vector<long long>	currentTraceLineTimeVector;
    vector<int>         currentReadWriteFlagVector;
    
    
    
    /* Hit counters  */
    vector<long>                totalHitCounterForEachAlgorithmVector;
    vector<vector<long>>        hitCounterForEachAlgorithmAndTraceVector;
    vector<vector<float>>       hitRatioForEachAlgorithmAndTraceVector;
    
    /* Overhead - SSD-HDD Updates */
    vector<long>        totalOverheadWBForEachAlgorithmVector;
    vector<long>        totalOverheadWTForEachAlgorithmVector;
    vector<long>        totalOverheadWB_IOAdmin_ForEachAlgorithmVector;
    vector<long>        totalOverheadWB_IOEvict_ForEachAlgorithmVector;
    vector<long>        totalOverheadWT_IOAdmin_ForEachAlgorithmVector;
    vector<long>        totalOverheadWT_IOEvict_ForEachAlgorithmVector;
    
    /* Overhead - Original IO */
    vector<long>        totalOverheadCounterWB_IO_CacheRead_ForEachAlgorithmVector;
    vector<long>        totalOverheadCounterWB_IO_CacheWrite_ForEachAlgorithmVector;

    
    //cout<<"C-1"<<endl;
    
    
    /* Hit flag for all pages in an IO request line */
    vector<int>            currentIOLineHitFlagForEachAlgorithmVector;
    vector<vector<int>>    currentIOLineHitFlagForEachAlgorithmAndTraceVector;
    
    
    
    
    
    /* Occupancy */
    vector<vector<long>>    occupancyNumberForEachAlgorithmAndTraceVector;
    vector<vector<float>>   occupancyRatioForEachAlgorithmAndTraceVector;
    
    
    /* Initialize all arrays */
    /* 1D: algorithmNumber, var=10 */
    for (int j=0; j<algorithmNumber; j++)
    {

        totalHitCounterForEachAlgorithmVector.push_back(0);
        
        // Overhead - SSD-HDD Updates
        totalOverheadWBForEachAlgorithmVector.push_back(0);
        totalOverheadWTForEachAlgorithmVector.push_back(0);
        totalOverheadWB_IOAdmin_ForEachAlgorithmVector.push_back(0);
        totalOverheadWB_IOEvict_ForEachAlgorithmVector.push_back(0);
        totalOverheadWT_IOAdmin_ForEachAlgorithmVector.push_back(0);
        totalOverheadWT_IOEvict_ForEachAlgorithmVector.push_back(0);
        // Overhead - Original IO
        totalOverheadCounterWB_IO_CacheRead_ForEachAlgorithmVector.push_back(0);
        totalOverheadCounterWB_IO_CacheWrite_ForEachAlgorithmVector.push_back(0);
        
        currentIOLineHitFlagForEachAlgorithmVector.push_back(1);
    
    }
    //cout<<"C-2"<<endl;
    
    /* 1D: traceNumber, var=9 */
    for (int i=0; i<traceNumber; i++)
    {


        IORequestCounterForEachTraceVector.push_back(0);
        pageCounterForEachTraceVector.push_back(0);
        traceFinishVector.push_back(0);
        traceStartTimeVector.push_back(0);

        currentTraceLineStartPageVector.push_back(0);
        currentTraceLineEndPageVector.push_back(0);
        currentTraceLineTimeVector.push_back(0);
        currentReadWriteFlagVector.push_back(0); //default write

        currentTraceLineVector.push_back("");
        
        
        getline(*traceFilesVector[i], currentTraceLineVector[i]);

        readMSRLine(currentTraceLineVector[i], currentTraceLineTimeVector[i], currentTraceLineStartPageVector[i], currentTraceLineEndPageVector[i], currentReadWriteFlagVector[i]);

        traceStartTimeVector[i]=currentTraceLineTimeVector[i];
    }
    
    
//    cout<<"traceStartTimeVector\n";
//    print1DVector(traceStartTimeVector);
    

    //cout<<"C-3"<<endl;

    /*  2D: algorithmNumber and traceNumber, var=5 */
    /*
     Matrix[algorithmID][traceID]
     Matrix[j][i]
     column     ->  i   ->  traceID
     row        ->  j   ->  algorithmID
     */
    // j(algoID) is row, each row has serveral traces (i), row is the subvector
    for (int j=0; j<algorithmNumber; j++)
    {
        hitCounterForEachAlgorithmAndTraceVector.push_back(vector<long>());
        hitRatioForEachAlgorithmAndTraceVector.push_back(vector<float>());
        currentIOLineHitFlagForEachAlgorithmAndTraceVector.push_back(vector<int>());
        occupancyNumberForEachAlgorithmAndTraceVector.push_back(vector<long>());
        occupancyRatioForEachAlgorithmAndTraceVector.push_back(vector<float>());
        for (int i=0; i<traceNumber; i++)
        {
            hitCounterForEachAlgorithmAndTraceVector[j].push_back(0);
            hitRatioForEachAlgorithmAndTraceVector[j].push_back(0);
            currentIOLineHitFlagForEachAlgorithmAndTraceVector[j].push_back(1);
            occupancyNumberForEachAlgorithmAndTraceVector[j].push_back(0);
            occupancyRatioForEachAlgorithmAndTraceVector[j].push_back(0);
        }
    }
    
    //cout<<"Initialization finished.\n";
    //cout<<"C-4"<<endl;
    /* 04. Run algorithm(s) for a I/O line */
    /* i=traceID, j=algorithmID */
    int i=0; // traceID
    
    long currentEpochID=0;
    long lastEpochID=-1;
    
    while (!finish)
    {
        
        //cout<<"Check Point 1.\n";
        
        
        i = getTraceWithMinTime(currentTraceLineTimeVector, traceStartTimeVector, traceFinishVector, traceNumber);
        //cout<<"TraceWithMinTime="<<i<<endl;   // i=traceID
        totalIORequestCounter++;
        IORequestCounterForEachTraceVector[i]++;
        
        
        
        // Send to each algorithms
        // Cleanup flags
        // Selected i, for its all j (rowID, algorithms)
        for (int j=0; j<algorithmNumber; j++)
        {
            currentIOLineHitFlagForEachAlgorithmVector[j]=1;
            currentIOLineHitFlagForEachAlgorithmAndTraceVector[j][i]=1;
        }
        
        long long currentWritePage=currentTraceLineStartPageVector[i];
        
        
        //cout<<"Check Point 3.\n";
        for (; currentWritePage<=currentTraceLineEndPageVector[i]; currentWritePage++)
        {
            totalPageCounter++;
            pageCounterForEachTraceVector[i]++;
            //cout<<"Check Point 4.\n";
            if ( runAlgorithmVector[0]   &&  (!LRU_Cache.input(currentWritePage*10000+i, currentReadWriteFlagVector[i])) )
            {
                // Update hit flag matrix
                //cout<<"M ";
                
                currentIOLineHitFlagForEachAlgorithmVector[0]=0;
                currentIOLineHitFlagForEachAlgorithmAndTraceVector[0][i]=0;
            }
            if ( runAlgorithmVector[1]   &&  (!CLOCK_Cache.input(currentWritePage*10000+i, currentReadWriteFlagVector[i])) )
            {
                // Update hit flag matrix
                currentIOLineHitFlagForEachAlgorithmVector[1]=0;
                currentIOLineHitFlagForEachAlgorithmAndTraceVector[1][i]=0;
            }
            if ( runAlgorithmVector[2]   &&  (!ARC_Cache.input(currentWritePage*10000+i, currentReadWriteFlagVector[i])) )
            {
                // Update hit flag matrix
                currentIOLineHitFlagForEachAlgorithmVector[2]=0;
                currentIOLineHitFlagForEachAlgorithmAndTraceVector[2][i]=0;

            }
            if ( runAlgorithmVector[3]   &&  (!CAR_Cache.input(currentWritePage*10000+i, currentReadWriteFlagVector[i])) )
            {
                // Update hit flag matrix
                currentIOLineHitFlagForEachAlgorithmVector[3]=0;
                currentIOLineHitFlagForEachAlgorithmAndTraceVector[3][i]=0;

            }
            if ( runAlgorithmVector[4]   &&  (!CART_Cache.input(currentWritePage*10000+i, currentReadWriteFlagVector[i])) )
            {
                // Update hit flag matrix
                currentIOLineHitFlagForEachAlgorithmVector[4]=0;
                currentIOLineHitFlagForEachAlgorithmAndTraceVector[4][i]=0;
            }
            //cout<<"Check Point 10.\n";
        }
        
        // Update hit ratio matrix, for each I/O line
        for (int j=0; j<algorithmNumber; j++)
        {
            
            if (runAlgorithmVector[j])
            {
                // For each algorithm
                if (currentIOLineHitFlagForEachAlgorithmVector[j])
                {
                    totalHitCounterForEachAlgorithmVector[j]++;
                    //resultFileTotalHitRatio<<"H "<<i<<" "<<IORequestCounterForEachTrace[i]<<endl;
                }
                if (currentIOLineHitFlagForEachAlgorithmAndTraceVector[j][i])
                {
                    hitCounterForEachAlgorithmAndTraceVector[j][i]++;
                    //resultFile<<"H "<<i<<" "<<currentTraceLineNumber[i]<<endl;
                }
                
            }
           
            
        }

      //  cout<<"C-5"<<endl;
        
        
        // Print cout monitoring status
        if (totalIORequestCounter%coutMonitorStep==0)
        {
            cout<<totalIORequestCounter<<endl;
            // printTotalHitRatio(resultFileTotalHitRatio, totalHitCounterForEachAlgorithm, totalIORequestCounter);
        }
        
        // fileMonitorStep=5min
        currentEpochID=(currentTraceLineTimeVector[i]-traceStartTimeVector[i])/fileMonitorStep;
        
        while (currentEpochID>lastEpochID)
        {
            
            lastEpochID++;
            //cout<< lastEpochID <<endl;
            printTotalHitRatio      (resultFileTotalHitRatio,  totalHitCounterForEachAlgorithmVector, totalIORequestCounter, algorithmNumber, lastEpochID);
            
            
            for (int j=0; j<algorithmNumber; j++)
            {
                if (runAlgorithmVector[j])
                {
                    switch (j)
                    {
                        case 0:
                            LRU_Cache.getOccupancyRatio(j, occupancyNumberForEachAlgorithmAndTraceVector, occupancyRatioForEachAlgorithmAndTraceVector, traceNumber, algorithmNumber);
                            break;
                        case 1:
                            CLOCK_Cache.getOccupancyRatio(j, occupancyNumberForEachAlgorithmAndTraceVector, occupancyRatioForEachAlgorithmAndTraceVector, traceNumber, algorithmNumber);
                            break;
                        case 2:
                            ARC_Cache.getOccupancyRatio(j, occupancyNumberForEachAlgorithmAndTraceVector, occupancyRatioForEachAlgorithmAndTraceVector, traceNumber, algorithmNumber);
                            break;
                        case 3:
                            CAR_Cache.getOccupancyRatio(j, occupancyNumberForEachAlgorithmAndTraceVector, occupancyRatioForEachAlgorithmAndTraceVector, traceNumber, algorithmNumber);
                            break;
                        case 4:
                            CART_Cache.getOccupancyRatio(j, occupancyNumberForEachAlgorithmAndTraceVector, occupancyRatioForEachAlgorithmAndTraceVector, traceNumber, algorithmNumber);
                            break;
                        default:
                            break;
                    }
                    
                    //printOverhead(*resultFileOverheadVector[0], totalOverheadWBForEachAlgorithmVector, algorithmNumber, lastEpochID);
                    //printOverhead(*resultFileOverheadVector[1], totalOverheadWTForEachAlgorithmVector, algorithmNumber, lastEpochID);
                    printOccupancyRatio(*resultFileOccupancyRatioVector[j], j, occupancyRatioForEachAlgorithmAndTraceVector, traceNumber, lastEpochID);
                    printHitRatio(*resultFileHitRatioVector[j], j, hitCounterForEachAlgorithmAndTraceVector, IORequestCounterForEachTraceVector, hitRatioForEachAlgorithmAndTraceVector, traceNumber, lastEpochID);
                    
                }
            }
            

        }// end of monitor
        
        
        
        
        
        
        //
        
        // Read next line in the current trace file
        if (!getline(*traceFilesVector[i], currentTraceLineVector[i]))
        {
            traceFinishVector[i]=1;
            currentTraceLineTimeVector[i]=LONG_LONG_MAX;
            traceStartTimeVector[i]=0;
            cout<<"Trace "<<i<<" is finished."<<endl;
        }
        else
        {
            // Read next line of the current trace[i]

            readMSRLine(currentTraceLineVector[i], currentTraceLineTimeVector[i], currentTraceLineStartPageVector[i], currentTraceLineEndPageVector[i], currentReadWriteFlagVector[i]);

        }
				
        // Check all traces are finished or not
        finish=1;
        for (int i=0; i<traceNumber; i++)
        {
            // traceFinish[i]==true?cout<<"Trace "<<i<<" is finished.\n":cout<<"Trace "<<i<" is not finished.\n";
            // traceFinish[i]==true?cout<<"Trace is finished. ":cout<<"Trace is not finished. ";
            finish=finish&traceFinishVector[i];
        }
        //finish==true?cout<<"Finish=true\n":cout<<"Finish=false\n";
        
    }
    
    
    
    
    
    // Update overhead matrix
    for (int j=0; j<algorithmNumber; j++)
    {
        
        if (runAlgorithmVector[j])
        {
            if (j==0)
            {
                totalOverheadWBForEachAlgorithmVector[j]=LRU_Cache.getOverheadWB();
                totalOverheadWTForEachAlgorithmVector[j]=LRU_Cache.getOverheadWT();
                totalOverheadWB_IOAdmin_ForEachAlgorithmVector[j]=LRU_Cache.getOverheadWB_IOAdmin();
                totalOverheadWB_IOEvict_ForEachAlgorithmVector[j]=LRU_Cache.getOverheadWB_IOEvict();
                totalOverheadWT_IOAdmin_ForEachAlgorithmVector[j]=LRU_Cache.getOverheadWT_IOAdmin();
                totalOverheadWT_IOEvict_ForEachAlgorithmVector[j]=LRU_Cache.getOverheadWT_IOEvict();
                totalOverheadCounterWB_IO_CacheRead_ForEachAlgorithmVector[j]=LRU_Cache.getOverheadWB_IO_CacheRead();
                totalOverheadCounterWB_IO_CacheWrite_ForEachAlgorithmVector[j]=LRU_Cache.getOverheadWB_IO_CacheWrite();
            }
            
            if (j==1)
            {
                totalOverheadWBForEachAlgorithmVector[j]=CLOCK_Cache.getOverheadWB();
                totalOverheadWTForEachAlgorithmVector[j]=CLOCK_Cache.getOverheadWT();
                totalOverheadWB_IOAdmin_ForEachAlgorithmVector[j]=CLOCK_Cache.getOverheadWB_IOAdmin();
                totalOverheadWB_IOEvict_ForEachAlgorithmVector[j]=CLOCK_Cache.getOverheadWB_IOEvict();
                totalOverheadWT_IOAdmin_ForEachAlgorithmVector[j]=CLOCK_Cache.getOverheadWT_IOAdmin();
                totalOverheadWT_IOEvict_ForEachAlgorithmVector[j]=CLOCK_Cache.getOverheadWT_IOEvict();
                totalOverheadCounterWB_IO_CacheRead_ForEachAlgorithmVector[j]=CLOCK_Cache.getOverheadWB_IO_CacheRead();
                totalOverheadCounterWB_IO_CacheWrite_ForEachAlgorithmVector[j]=CLOCK_Cache.getOverheadWB_IO_CacheWrite();
            }
            
            if (j==2)
            {
                totalOverheadWBForEachAlgorithmVector[j]=ARC_Cache.getOverheadWB();
                totalOverheadWTForEachAlgorithmVector[j]=ARC_Cache.getOverheadWT();
                totalOverheadWB_IOAdmin_ForEachAlgorithmVector[j]=ARC_Cache.getOverheadWB_IOAdmin();
                totalOverheadWB_IOEvict_ForEachAlgorithmVector[j]=ARC_Cache.getOverheadWB_IOEvict();
                totalOverheadWT_IOAdmin_ForEachAlgorithmVector[j]=ARC_Cache.getOverheadWT_IOAdmin();
                totalOverheadWT_IOEvict_ForEachAlgorithmVector[j]=ARC_Cache.getOverheadWT_IOEvict();
                totalOverheadCounterWB_IO_CacheRead_ForEachAlgorithmVector[j]=ARC_Cache.getOverheadWB_IO_CacheRead();
                totalOverheadCounterWB_IO_CacheWrite_ForEachAlgorithmVector[j]=ARC_Cache.getOverheadWB_IO_CacheWrite();
            }
            if (j==3)
            {
                totalOverheadWBForEachAlgorithmVector[j]=CAR_Cache.getOverheadWB();
                totalOverheadWTForEachAlgorithmVector[j]=CAR_Cache.getOverheadWT();
                totalOverheadWB_IOAdmin_ForEachAlgorithmVector[j]=CAR_Cache.getOverheadWB_IOAdmin();
                totalOverheadWB_IOEvict_ForEachAlgorithmVector[j]=CAR_Cache.getOverheadWB_IOEvict();
                totalOverheadWT_IOAdmin_ForEachAlgorithmVector[j]=CAR_Cache.getOverheadWT_IOAdmin();
                totalOverheadWT_IOEvict_ForEachAlgorithmVector[j]=CAR_Cache.getOverheadWT_IOEvict();
                totalOverheadCounterWB_IO_CacheRead_ForEachAlgorithmVector[j]=CAR_Cache.getOverheadWB_IO_CacheRead();
                totalOverheadCounterWB_IO_CacheWrite_ForEachAlgorithmVector[j]=CAR_Cache.getOverheadWB_IO_CacheWrite();
            }
            if (j==4)
            {
                totalOverheadWBForEachAlgorithmVector[j]=CART_Cache.getOverheadWB();
                totalOverheadWTForEachAlgorithmVector[j]=CART_Cache.getOverheadWT();
                totalOverheadWB_IOAdmin_ForEachAlgorithmVector[j]=CART_Cache.getOverheadWB_IOAdmin();
                totalOverheadWB_IOEvict_ForEachAlgorithmVector[j]=CART_Cache.getOverheadWB_IOEvict();
                totalOverheadWT_IOAdmin_ForEachAlgorithmVector[j]=CART_Cache.getOverheadWT_IOAdmin();
                totalOverheadWT_IOEvict_ForEachAlgorithmVector[j]=CART_Cache.getOverheadWT_IOEvict();
                totalOverheadCounterWB_IO_CacheRead_ForEachAlgorithmVector[j]=CART_Cache.getOverheadWB_IO_CacheRead();
                totalOverheadCounterWB_IO_CacheWrite_ForEachAlgorithmVector[j]=CART_Cache.getOverheadWB_IO_CacheWrite();
            }
        }
        
        
    }

    
    
    
    
    
    // 05. Print results
    printSummary(resultFileSummary, cacheSizeInMegaBytes, cacheSize, totalHitCounterForEachAlgorithmVector, totalIORequestCounter, totalPageCounter,
                 totalOverheadWBForEachAlgorithmVector, totalOverheadWTForEachAlgorithmVector, totalOverheadWB_IOAdmin_ForEachAlgorithmVector, totalOverheadWB_IOEvict_ForEachAlgorithmVector, totalOverheadWT_IOAdmin_ForEachAlgorithmVector, totalOverheadWT_IOEvict_ForEachAlgorithmVector, runAlgorithmVector, traceFileNameVector, totalOverheadCounterWB_IO_CacheRead_ForEachAlgorithmVector, totalOverheadCounterWB_IO_CacheWrite_ForEachAlgorithmVector);
    
    
    return 0;
}
