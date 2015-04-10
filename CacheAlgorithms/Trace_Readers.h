#include <iostream>
#include <vector>
#include <fstream>
#include <climits>


using namespace std;

void readMSRLine(string currentIOLine, long long & timeStamp, long long & startPageNumber, long long & endPageNumber, int & readWriteFlag)
{
    string timeStampStr;
    string startStr;
    string offsetStr;
    string substring1;
    string substring2;
    string substring3;
    
    

    
    // scan whole line for "write"
    for (int i=0;i<currentIOLine.length();i++)
    {
        
        if (currentIOLine[i]=='W')
        {
            readWriteFlag=0;
            timeStampStr=currentIOLine.substr(0,i-6);
            substring1=currentIOLine.substr(i+6); //Write, -> w [r i t e ,]
            break;
        }
        else if (currentIOLine[i]=='R')
        {
            readWriteFlag=1;
            timeStampStr=currentIOLine.substr(0,i-6);
            substring1=currentIOLine.substr(i+5); //Write, -> r [e a d ,]
            break;
        }
    }
    
    
    
    
    // Start address
    for (int i=0; i<substring1.length(); i++)
    {
        if (substring1[i]==',')
        {
            startStr=substring1.substr(0,i);
            substring2=substring1.substr(i+1);
            break;
        }
    }
    
    // Offset length
    for (int i=0; i<substring2.length(); i++)
    {
        if (substring2[i]==',')
        {
            offsetStr=substring2.substr(0,i);
            
        }
    }
    
    

    //long startPageAddress       =   atol(startChar);
    //long endPageAddress         =   atol(startChar) + atol(offsetChar) - 1;
    

    
    timeStamp   =  atoll(timeStampStr.c_str()) / 10000000 - 11644473600;
    
    
    //startPageNumber   = atoll(startChar)/4096;
    startPageNumber   = atoll(startStr.c_str())/512;
    startPageNumber   = startPageNumber/8;
    
    //endPageNumber     = (atoll(startChar)+atoll(offsetChar)-1)/4096;
    endPageNumber     = (atoll(startStr.c_str())/512+atoll(offsetStr.c_str())/512-1)/8;

    
//    cout<<"TimeStamp=\t\t\t\t\t"<<timeStamp<<endl;
//    cout<<"StartPageNumber=\t\t\t"<<startPageNumber<<endl;
//    cout<<"EndPageNumber=\t\t\t\t"<<endPageNumber<<endl;
//    cout<<"Number of Accessed Pages=\t"<<endPageNumber-startPageNumber+1<<endl<<endl;
}





int getTraceWithMinTime ( const vector<long long> &time, const vector<long long> &start, const vector<int> &finish, int traceNumber)
{

    int minTraceID=0;
    long long minNumber=LONG_LONG_MAX;
    for (int i=0; i<traceNumber; i++)
    {
        if(finish[i]==0 && (time[i]-start[i]<minNumber))
        {
            minNumber=time[i]-start[i];
            minTraceID=i;
        }
    }
    //cout<<minTraceID<<endl;
    return minTraceID;
}