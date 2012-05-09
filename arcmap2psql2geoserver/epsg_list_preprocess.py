#!/usr/bin/env python

import sys, os, re, pprint, traceback
import string, codecs
from collections import namedtuple
from collections import defaultdict

#file used to extract epsg codes 

def list_check():
    epsg_file_path = os.getcwd()
    epsg_file_path += "/epsg"
    regex = re.compile("<(\d{4,5})>")
    epsg_list = []
    if os.path.isfile(epsg_file_path):
        with open(epsg_file_path, 'r') as infile:
            for line in infile:
                for match in re.finditer(regex, line):
                    templist = list(match.groups())
                    #epsg_list = list(match.groups())
                    #epsg_list.append(match.groups())
                    epsg_list += templist
                    #for epsg in epsg_list:
    return epsg_list
        
if __name__ == '__main__':
    print(list_check())
