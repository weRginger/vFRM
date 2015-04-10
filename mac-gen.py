#!/usr/bin/python
# mac-gen.py script to generate a MAC address for Red Hat Virtualization guests
#
import random
#
def randomMAC():
   mac = [0x52, 0x54, 0x00,
         random.randint(0x00, 0x3f),
         random.randint(0x00, 0xff),
         random.randint(0x00, 0xff)]
   return ':'.join(map(lambda x: "%02x" % x, mac))

print randomMAC()
