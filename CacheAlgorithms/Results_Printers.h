#include <iostream>
#include <fstream>
#include "Config.h"

using namespace std;

void printSummary (ofstream &resultFile, long cacheSizeInMegaBytes, long cacheSize, vector<long> &totalCacheHit, long IORequestCounter, long pageCounter,
                   vector<long> &overheadWBMatrix, vector<long> &overheadWTMatrix, vector<long> &overheadWB_IOAdmin_Matrix, vector<long> &overheadWB_IOEvict_Matrix,
                   vector<long> &overheadWT_IOAdmin_Matrix, vector<long> &overheadWT_IOEvict_Matrix, vector<int> &runAlgorithmVector, vector<string> &traceFileNameVector, vector<long> &cacheReadVector, vector<long> &cacheWriteVector)
{
    
    long SSDr,SSDw,HDDr,HDDw;
    

    resultFile<<"|------------------------------------------------------------------------------------------------------------------|"<<endl;
    resultFile<<"|  Input file ("<<traceFileNameVector.size()<<"):\t";
    for (int i=0; i<traceFileNameVector.size(); i++)
    {
        resultFile<<traceFileNameVector[i]<<" ";
    }
    resultFile<<endl;
    resultFile<<"|  Cache size:\t\t"<<cacheSizeInMegaBytes<<" MB ("<<cacheSize*4096<<" Bytes, "<<cacheSize<<" Pages)"<<endl;
    resultFile<<"|  Mapping Strategy:\tFully Associative"<<endl;
    resultFile<<"|  Total I/O Lines:\t"<<IORequestCounter<<endl;
    resultFile<<"|  Total I/O Size:\t"<<(float)pageCounter*4096/1024/1024/1024<<" GB ("<<pageCounter<<" Pages)"<<endl;
    resultFile<<"|  Cost(Total)\t\t= SSDr + SSDw + HDDr + HDDw"<<endl;
    resultFile<<"|  Cost(Flash)\t\t= Admin(HDDr+SSDw)+Evict(SSDr+HDDw)"<<endl;
    resultFile<<"|"<<endl;
    
    for (int j=0; j<5; j++)
    {
        if (runAlgorithmVector[j])
        {
            SSDr=cacheReadVector[j]+overheadWB_IOEvict_Matrix[j];
            SSDw=cacheWriteVector[j]+overheadWB_IOAdmin_Matrix[j];
            HDDr=overheadWB_IOAdmin_Matrix[j];
            HDDw=overheadWB_IOEvict_Matrix[j];
            
            
            switch (j) {
                case 0: resultFile<<"|  LRU:\t\t\t"; break;
                case 1: resultFile<<"|  CLOCK:\t\t"; break;
                case 2: resultFile<<"|  ARC:\t\t\t"; break;
                case 3: resultFile<<"|  CAR:\t\t\t"; break;
                case 4: resultFile<<"|  CART:\t\t"; break;
                default: break;
                    
            }
            
            resultFile<<"HR="<<(float)totalCacheHit[j]/IORequestCounter*100<<"% ("<<totalCacheHit[j]
            <<"), OH(Total)="<<SSDr<<"+"<<SSDw<<"+"<<HDDr<<"+"<<HDDw
            <<", OH(Flash)="<<overheadWB_IOAdmin_Matrix[j]<<"+"<<overheadWB_IOEvict_Matrix[j]<<endl;
            //Oh(WT)="<<overheadWTMatrix[0]<<"="<<overheadWT_IOAdmin_Matrix[0]<<"A+"<<overheadWT_IOEvict_Matrix[0]<<"E"<<endl;
        }
    }
    
    resultFile<<"|------------------------------------------------------------------------------------------------------------------|"<<endl;
    
    // Display
    
    cout<<"|------------------------------------------------------------------------------------------------------------------|"<<endl;
    cout<<"|  Input file ("<<traceFileNameVector.size()<<"):\t";
    for (int i=0; i<traceFileNameVector.size(); i++)
    {
        cout<<traceFileNameVector[i]<<" ";
    }
    cout<<endl;
    cout<<"|  Cache size:\t\t"<<cacheSizeInMegaBytes<<" MB ("<<cacheSize*4096<<" Bytes, "<<cacheSize<<" Pages)"<<endl;
    cout<<"|  Mapping Strategy:\tFully Associative"<<endl;
    cout<<"|  Total I/O Lines:\t"<<IORequestCounter<<endl;
    cout<<"|  Total I/O Size:\t"<<(float)pageCounter*4096/1024/1024/1024<<" GB ("<<pageCounter<<" Pages)"<<endl;
    cout<<"|  Cost(Total)\t\t= SSDr + SSDw + HDDr + HDDw"<<endl;
    cout<<"|  Cost(Flash)\t\t= Admin(HDDr+SSDw)+Evict(SSDr+HDDw)"<<endl;
    cout<<"|"<<endl;
    
    for (int j=0; j<5; j++)
    {
        if (runAlgorithmVector[j])
        {
            SSDr=cacheReadVector[j]+overheadWB_IOEvict_Matrix[j];
            SSDw=cacheWriteVector[j]+overheadWB_IOAdmin_Matrix[j];
            HDDr=overheadWB_IOAdmin_Matrix[j];
            HDDw=overheadWB_IOEvict_Matrix[j];
            
            
            switch (j) {
                case 0: cout<<"|  LRU:\t\t\t"; break;
                case 1: cout<<"|  CLOCK:\t\t"; break;
                case 2: cout<<"|  ARC:\t\t\t"; break;
                case 3: cout<<"|  CAR:\t\t\t"; break;
                case 4: cout<<"|  CART:\t\t"; break;
                default: break;
                    
            }
            
            cout<<"HR="<<(float)totalCacheHit[j]/IORequestCounter*100<<"% ("<<totalCacheHit[j]
            <<"), OH(Total)="<<SSDr<<"+"<<SSDw<<"+"<<HDDr<<"+"<<HDDw
            <<", OH(Flash)="<<overheadWB_IOAdmin_Matrix[j]<<"+"<<overheadWB_IOEvict_Matrix[j]<<endl;
            //Oh(WT)="<<overheadWTMatrix[0]<<"="<<overheadWT_IOAdmin_Matrix[0]<<"A+"<<overheadWT_IOEvict_Matrix[0]<<"E"<<endl;
        }
    }
    
    cout<<"|------------------------------------------------------------------------------------------------------------------|"<<endl;
}

void printTotalHitRatio (ofstream &resultFile, vector<long> &totalCacheHitVector, long IORequestCounter, int algorithmNumber, long lastEpoch)
{
    resultFile << lastEpoch <<"\t";
    for (int i=0; i<algorithmNumber; i++)
    {
        //cout << (float) totalCacheHitVector[i]/IORequestCounter*100 <<"%\t";
        resultFile << (float)totalCacheHitVector[i]/IORequestCounter*100 <<"%\t";
    }
    //cout << endl;
    resultFile << endl;
}


void printTotalHitNumber (ofstream &resultFile, vector<long> &totalCacheHitVector, long IORequestCounter, int algorithmNumber, long lastEpoch)
{
    resultFile << lastEpoch <<"\t";
    for (int i=0; i<algorithmNumber; i++)
    {
        //cout <<  totalCacheHitVector[i] <<"\t";
        resultFile << totalCacheHitVector[i] <<"\t";
    }
    //cout << endl;
    resultFile << endl;
}



void printOccupancyRatio (ofstream &resultFileOccupancyRatio, int algorithmID, vector<vector<float>> &occupancyRatioMatrix, int traceNumber, long lastEpoch)
{
    resultFileOccupancyRatio << lastEpoch <<"\t";
    for (int i=0; i<traceNumber; i++)
    {
        resultFileOccupancyRatio << occupancyRatioMatrix[algorithmID][i] * 100 <<"%\t";
    }
    resultFileOccupancyRatio << endl;
}



void printHitRatio (ofstream &resultFileHitRatio, int algorithmID, vector<vector<long>> &hitCounterMatrix, vector<long> &IORequestCounterVector, vector<vector<float>> &hitRatioMatrix, int traceNumber, long lastEpoch)
{
    resultFileHitRatio << lastEpoch <<"\t";
    for (int i=0; i<traceNumber; i++)
    {
        hitRatioMatrix[algorithmID][i]=(float) hitCounterMatrix[algorithmID][i]/IORequestCounterVector[i];
        resultFileHitRatio << 100.0*hitRatioMatrix[algorithmID][i]<<"%\t";
    }
    resultFileHitRatio << endl;
}




void printOverhead(ofstream &resultFileOverhead, vector<long> overheadVector, int algorithmNumber, long lastEpoch)
{
    resultFileOverhead << lastEpoch <<"\t";
    for (int i=0; i<algorithmNumber; i++)
    {
        resultFileOverhead << overheadVector[i] <<"\t";
    }
    resultFileOverhead << endl;
}


template <typename T>
void print2DVector(vector<vector<T>> const &v)
{
    for (int i=0; i<v.size(); i++)
    {
        for (int j=0; j<v[i].size(); j++)
        {
            cout<<v[i][j]<<"\t";
        }
        cout<<endl;
    }
}

template <typename T>
void print1DVector(vector<T> const &v)
{
    for (int i=0; i<v.size(); i++)
    {
        cout<<v[i]<<"\t";
    }
    cout<<endl;
}

