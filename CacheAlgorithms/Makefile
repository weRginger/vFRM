TARGET=cache

SOURCES=$(wildcard *.cpp)

OBJECTS=$(patsubst %.cpp, %.o, $(SOURCES))

INCL=-I./

CC=g++

CFLAGS=-g -Wall -std=c++0x $(INCL)

all: $(TARGET) $(SOURCES)

$(TARGET):$(OBJECTS)
	$(CC) $(CFLAGS) -o $(TARGET) $(OBJECTS)

$(OBJECTS): %.o : %.cpp 

	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f *.o
	rm -f *~


